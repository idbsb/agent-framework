from __future__ import annotations

import json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from graph.graph_builder import build_graph, file_hashes, load_sources
from graph.evolution_analyzer import analyze_evolution

KEY_JOBS = ["AI Agent开发工程师", "RAG引擎研发工程师", "AI安全技术工程师"]

def serial(v):
    if isinstance(v, (pd.Timestamp,)): return v.isoformat()
    if pd.isna(v) if not isinstance(v, (list, dict)) else False: return None
    return v

def records(df):
    return [{k: serial(v) for k, v in r.items()} for r in df.to_dict("records")]

def main():
    out, img, reports, docs = ROOT/"outputs", ROOT/"05_图片"/"图谱动态", ROOT/"reports", ROOT/"docs"
    for p in (out,img,reports,docs): p.mkdir(parents=True, exist_ok=True)
    before = file_hashes(ROOT)
    graph = build_graph(ROOT)
    evo, time_meta = analyze_evolution(ROOT, graph)
    jd, mapping, skills, aliases, human = load_sources(ROOT)
    valid = graph["valid_jd"]
    data_check = {
        "jd_total": len(jd), "confirmed_job_jd": len(valid), "standard_job_count": int(valid["标准岗位名称"].nunique()),
        "standard_skill_count": len(skills), "jd_id_unique": bool(jd["JD编号"].is_unique), "skill_id_unique": bool(skills["skill_id"].is_unique),
        "key_job_jd_counts": {j:int((valid["标准岗位名称"]==j).sum()) for j in KEY_JOBS}, **time_meta,
    }
    all_nodes=[]
    type_id={"Jobs":"job_id","Skills":"skill_id","JDs":"jd_id","Companies":"company_id","Domains":"domain_id"}
    labels={"Jobs":"standard_job_title","Skills":"standard_skill_name","JDs":"original_job_title","Companies":"company_name","Domains":"domain_name"}
    singular={"Jobs":"Job","Skills":"Skill","JDs":"JD","Companies":"Company","Domains":"Domain"}
    for typ, arr in graph["nodes"].items():
        for n in arr: all_nodes.append({"id":n[type_id[typ]],"label":n[labels[typ]],"type":singular[typ],**n})
    all_edges=[]
    for typ, arr in graph["edges"].items():
        for i,e in enumerate(arr): all_edges.append({"id":f"{typ}-{i+1:05d}","edge_type":typ,**e})
    kg={"nodes":all_nodes,"edges":all_edges,"meta":{"version":"v1","data_check":data_check,
        "node_counts":{k:len(v) for k,v in graph["nodes"].items()},"edge_counts":{k:len(v) for k,v in graph["edges"].items()},
        "evidence_policy":"所有Job-Skill边至少含一个真实JD编号；技能ID仅来自正式技能库。"}}
    (out/"knowledge_graph_v1.json").write_text(json.dumps(kg,ensure_ascii=False,indent=2,default=serial),encoding="utf-8")

    job_skill=pd.DataFrame(graph["edges"]["Job_Skill"])
    profiles=[]
    key_evo={"meta":time_meta,"jobs":{}}
    for job in KEY_JOBS:
        p=job_skill[job_skill.job_title==job].sort_values(["frequency","source_count"],ascending=False).copy()
        p["岗位名称"]=job
        p["技能重要程度"]=p.apply(lambda r:r.importance or ("核心技能" if r.frequency>=.6 else "重要技能" if r.frequency>=.3 else "相关技能"),axis=1)
        profiles.append(p)
        je=evo[evo["标准岗位"]==job].copy()
        latest=je[je["时间窗口"]==je["时间窗口"].max()] if len(je) else je
        key_evo["jobs"][job]={"support_jd_count":data_check["key_job_jd_counts"][job],"time_range":[time_meta["effective_start"],time_meta["effective_end"]],
          "current_top":records(p.head(15)[["skill_id","skill_name","frequency","source_count","importance","evidence_jd_ids"]]) if len(p) else [],
          "records":records(je),"status_summary":{s:records(latest[latest["演化状态"]==s].head(15)) for s in ["快速增长","新增","稳定","下降","样本不足"]}}
    profile_df=pd.concat(profiles,ignore_index=True) if profiles else pd.DataFrame()
    (out/"key_job_evolution_v1.json").write_text(json.dumps(key_evo,ensure_ascii=False,indent=2,default=serial),encoding="utf-8")
    export={"nodes":graph["nodes"],"edges":graph["edges"],"profiles":records(profile_df),"evolution":records(evo),"data_check":data_check}
    (out/"workbook_data_v1.json").write_text(json.dumps(export,ensure_ascii=False,default=serial),encoding="utf-8")
    (out/"data_check_v1.json").write_text(json.dumps(data_check,ensure_ascii=False,indent=2),encoding="utf-8")
    make_figures(img, job_skill, evo)
    write_reports(reports,docs,data_check,kg,profile_df,evo,before,file_hashes(ROOT))
    if before != file_hashes(ROOT): raise RuntimeError("冻结数据哈希发生变化")
    print(json.dumps({"data_check":data_check,"nodes":len(all_nodes),"edges":len(all_edges),"profiles":len(profile_df)},ensure_ascii=False,indent=2))

def make_figures(img, js, evo):
    import html, math
    colors={"AI Agent开发工程师":"#2563EB","RAG引擎研发工程师":"#059669","AI安全技术工程师":"#DC2626"}
    def svg_start(w,h,title): return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="#fff"/><style>text{{font-family:"Microsoft YaHei",sans-serif;fill:#17202A}}</style><text x="{w/2}" y="42" text-anchor="middle" font-size="24" font-weight="700">{html.escape(title)}</text>'
    for job in KEY_JOBS:
        d=js[js.job_title==job].nlargest(15,"frequency")
        w,h,cx,cy=1200,820,600,415; s=svg_start(w,h,f"{job}能力图谱（Top 15，真实JD证据）")
        pts=[]
        for i,(_,r) in enumerate(d.iterrows()):
            a=2*math.pi*i/max(1,len(d))-math.pi/2; x=cx+390*math.cos(a); y=cy+300*math.sin(a); pts.append((x,y,r))
            s+=f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#94A3B8" stroke-width="{1+4*r.frequency:.1f}" opacity=".65"/>'
        s+=f'<circle cx="{cx}" cy="{cy}" r="76" fill="{colors[job]}"/><text x="{cx}" y="{cy-7}" text-anchor="middle" font-size="19" fill="#fff" style="fill:#fff">{html.escape(job[:8])}</text><text x="{cx}" y="{cy+20}" text-anchor="middle" font-size="15" fill="#fff" style="fill:#fff">真实JD证据</text>'
        for x,y,r in pts:
            rr=28+24*r.frequency; s+=f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rr:.1f}" fill="#DBEAFE" stroke="{colors[job]}" stroke-width="2"/><text x="{x:.1f}" y="{y-3:.1f}" text-anchor="middle" font-size="13">{html.escape(str(r.skill_name)[:14])}</text><text x="{x:.1f}" y="{y+17:.1f}" text-anchor="middle" font-size="12">{r.frequency:.0%} · {r.source_count} JD</text>'
        (img/f"{job}能力图谱.svg").write_text(s+"</svg>",encoding="utf-8")
    top=pd.concat([js[js.job_title==j].nlargest(10,"frequency").assign(job=j) for j in KEY_JOBS])
    w,h=1500,760; s=svg_start(w,h,"三个重点岗位核心技能Top 10")
    for col,job in enumerate(KEY_JOBS):
        x0=30+col*495; s+=f'<text x="{x0+230}" y="82" text-anchor="middle" font-size="17" font-weight="700">{job}</text>'
        for i,(_,r) in enumerate(top[top.job==job].sort_values("frequency",ascending=False).iterrows()):
            y=115+i*59; s+=f'<text x="{x0}" y="{y+18}" font-size="13">{html.escape(str(r.skill_name)[:16])}</text><rect x="{x0+150}" y="{y}" width="{285*r.frequency:.1f}" height="25" rx="4" fill="{colors[job]}"/><text x="{x0+445}" y="{y+18}" text-anchor="end" font-size="13">{r.frequency:.0%}</text>'
    (img/"三个岗位核心技能Top图.svg").write_text(s+"</svg>",encoding="utf-8")
    latest=evo[evo["时间窗口"]==evo.groupby(["标准岗位","skill_id"])["时间窗口"].transform("max")]
    w,h=1500,720; s=svg_start(w,h,"重点岗位技能动态变化（小样本仅作原型观察）")
    for col,job in enumerate(KEY_JOBS):
        x0=20+col*495; s+=f'<text x="{x0+230}" y="82" text-anchor="middle" font-size="17" font-weight="700">{job}</text><line x1="{x0+250}" y1="105" x2="{x0+250}" y2="660" stroke="#334155"/>'
        d=latest[(latest["标准岗位"]==job)&latest["变化量"].notna()].sort_values("变化量",ascending=False).head(8)
        for i,(_,r) in enumerate(d.iterrows()):
            y=115+i*65; val=float(r["变化量"]); bw=min(180,abs(val)*420); bx=x0+250 if val>=0 else x0+250-bw
            s+=f'<text x="{x0+5}" y="{y+18}" font-size="12">{html.escape(str(r["技能名称"])[:15])}</text><rect x="{bx:.1f}" y="{y}" width="{bw:.1f}" height="25" fill="{"#16A34A" if val>=0 else "#DC2626"}"/><text x="{x0+470}" y="{y+18}" text-anchor="end" font-size="12">{val:+.1%}</text>'
    (img/"技能动态变化图.svg").write_text(s+"</svg>",encoding="utf-8")
    summary=latest.groupby(["标准岗位","演化状态"]).size().unstack(fill_value=0).reindex(KEY_JOBS)
    cats=["快速增长","新增","稳定","下降","样本不足"]; cc=["#16A34A","#2563EB","#64748B","#DC2626","#F59E0B"]
    w,h=1200,650; s=svg_start(w,h,"增长 / 新增 / 下降 / 样本不足技能数量")
    maxv=max([int(summary.get(c,pd.Series([0])).max()) for c in cats]+[1])
    for j,job in enumerate(KEY_JOBS):
        for i,c in enumerate(cats):
            v=int(summary.loc[job,c]) if c in summary.columns else 0; x=100+j*350+i*55; bh=430*v/maxv
            s+=f'<rect x="{x}" y="{545-bh:.1f}" width="42" height="{bh:.1f}" fill="{cc[i]}"/><text x="{x+21}" y="{535-bh:.1f}" text-anchor="middle" font-size="12">{v}</text>'
        s+=f'<text x="{100+j*350+132}" y="585" text-anchor="middle" font-size="14">{job}</text>'
    for i,c in enumerate(cats): s+=f'<rect x="{270+i*140}" y="610" width="16" height="16" fill="{cc[i]}"/><text x="{292+i*140}" y="623" font-size="13">{c}</text>'
    (img/"增长新增下降技能展示图.svg").write_text(s+"</svg>",encoding="utf-8")

def write_reports(reports,docs,dc,kg,profiles,evo,before,after):
    n,e=len(kg["nodes"]),len(kg["edges"]); key_counts=profiles.groupby("岗位名称")["skill_id"].nunique().to_dict() if len(profiles) else {}
    latest=evo[evo["时间窗口"]==evo.groupby(["标准岗位","skill_id"])["时间窗口"].transform("max")] if len(evo) else evo
    def names(status): return "、".join(latest[latest["演化状态"]==status]["技能名称"].drop_duplicates().head(12)) or "无可靠结论"
    report=f'''# 知识图谱与动态演化报告\n\n## 1. 模块目标\n基于191条真实JD、正式岗位映射和82项正式技能构建可追溯知识图谱与近期动态演化原型。\n\n## 2. 数据来源\n三个冻结V1工作簿只读；辅助画像与人工技能分析用于继承重要度。有效标准岗位JD为{dc['confirmed_job_jd']}条。\n\n## 3. 图谱Schema\n节点包括Job、Skill、JD、Company、Domain；关系包括INSTANCE_OF、REQUIRES、BONUS_SKILL、MENTIONS、BELONGS_TO、RECRUITS。\n\n## 4. 节点设计\n共{n}个节点；Skill节点的skill_id全部直接来自正式技能库。\n\n## 5. 关系设计\n共{e}条关系。Job-Skill边包含频率、支持JD数、证据JD列表、关系类型、重要度和置信度。\n\n## 6. Evidence证据链机制\n只允许正文命中正式技能名称或审核别名后建边；每条Job-Skill边至少保存一个真实JD编号。\n\n## 7. 三个重点岗位能力图谱\nAI Agent开发工程师、RAG引擎研发工程师、AI安全技术工程师分别识别{key_counts.get(KEY_JOBS[0],0)}、{key_counts.get(KEY_JOBS[1],0)}、{key_counts.get(KEY_JOBS[2],0)}项有证据技能。\n\n## 8. 动态演化方法\n按岗位×技能×时间窗口计算JD数、出现数、频率、前期频率、变化量与变化率；阈值来自config/evolution_config.yaml。\n\n## 9. 时间字段可用性\n标准发布时间有效{dc['publish_valid']}条，缺失{dc['publish_missing']}条，覆盖率{dc['publish_coverage']:.1%}。实际使用“{dc['time_source']}”，仅支持近期变化观察，不支持多年趋势。\n\n## 10. 演化结果\n快速增长：{names('快速增长')}。新增：{names('新增')}。下降：{names('下降')}。\n\n## 11. 样本量限制\n窗口少于3条JD统一标记“样本不足”，不得解释为市场需求升降。\n\n## 12. 数据接口\n提供get_job_graph、get_job_skills、get_skill_jobs、get_job_evolution、get_skill_evolution，并预留四类GET API映射。\n\n## 13. 增量更新机制\n更新冻结输入后重新运行run_graph_module.py与工作簿构建器，图谱和演化结果自动重算，已有JD编号与skill_id不变。\n\n## 14. 当前局限\n文本命中法不会推断隐含技能；发布时间缺失严重；采集批次时间跨度短；无法可靠区分未明确写在必备/加分栏之外的技能强度。\n\n## 15. 后续扩展\n增加更长时间跨度JD、证据片段定位及可选Neo4j CSV导出。当前未实现Neo4j，主流程完全基于JSON。\n'''
    (reports/"知识图谱与动态演化报告.md").write_text(report,encoding="utf-8")
    delivery=f'''# 图谱动态模块交付说明\n\n- 新增：src/graph、config、outputs、reports、docs、05_图片/图谱动态及运行脚本；未修改主项目其他模块。\n- 依赖：Python pandas、PyYAML、matplotlib、networkx；Excel由@oai/artifact-tool生成。\n- 运行：先执行 `python run_graph_module.py`，再执行 `node build_workbooks.mjs`。\n- 输入：三个冻结V1 Excel及两个辅助岗位分析Excel。\n- 输出：图谱节点/边Excel、统一JSON、重点岗位画像Excel、演化Excel、重点岗位演化JSON、图片与报告。\n- 图谱：{n}个节点、{e}条关系。三个重点岗位技能数：{key_counts}。\n- 时间：{dc['time_source']}；范围{dc['effective_start']}至{dc['effective_end']}，不支持严格长期趋势。\n- 快速增长：{names('快速增长')}。新增：{names('新增')}。下降：{names('下降')}。样本不足结果不得下结论。\n- JSON：outputs/knowledge_graph_v1.json；前端可直接读取nodes、edges、meta。\n- 查询：`from graph.query_service import configure; svc=configure(项目根目录)`。\n- API映射：GET /api/graph/job/{{job_title}}→get_job_graph；/api/graph/skill/{{skill_id}}→get_skill_jobs；演化接口同理。\n- 更新：新增标准化JD后重新运行两条命令。\n- Neo4j：未实现；避免引入运行依赖。\n- 冻结数据：运行前后SHA-256完全一致，未覆盖或修改。\n- 合并：复制新增目录/文件即可；不涉及src/core。\n- 当前问题：发布时间覆盖不足、采集跨度短；短别名采用英文边界匹配，仍建议未来加入证据片段人工抽检。\n'''
    (docs/"图谱动态模块交付说明.md").write_text(delivery,encoding="utf-8")

if __name__=="__main__": main()
