import { useEffect, useState } from "react";
import { getJson, postThenGet } from "../api";
import { safeEvidenceUrl, statusLabel } from "../closure";
import type { ClosureVersion, Definition, History, JDEvidence, SkillSupport, TextEvidence, VersionDiff } from "../closure";
import "./closure.css";
import ClosureAccess from "./ClosureAccess";

export function EvidenceList({ evidence }: { evidence: JDEvidence[] }) {
  return <div className="closure-evidence">{evidence.map(row => {
    const url = safeEvidenceUrl(row.url);
    return <article className="evidence-card" key={row.job_id}><b>{row.job_id} · {row.original_title}</b>
      <p>{row.company || "企业未提供"} · {row.source || "来源未提供"}</p>
      <small>发布时间：{row.published_at || "缺失"}；采集时间：{row.collected_at || "缺失"}；首次见到：{row.first_seen_at || "未提供"}</small>
      <p>时间依据：{row.time_source === "published_at" ? "招聘发布时间" : row.time_source === "collected_at_fallback" ? "采集时间回退（非发布时间）" : "未知"}</p>
      <p>{row.responsibilities}</p><p>{row.required_skills_raw}</p><p>{row.bonus_skills_raw}</p>
      {url ? <a href={url} target="_blank" rel="noopener noreferrer">查看原招聘信息</a> : <small>无可安全访问的原链接</small>}
    </article>;
  })}</div>;
}

export function DefinitionView({ definition: d, label }: { definition: Definition; label: string }) {
  const text = (items: TextEvidence[], empty: string) => items.length ? <ul>{items.map((s, i) => <li key={i}>{s.text}<small>证据：{s.supporting_job_ids.join("、")}</small></li>)}</ul> : <p>{empty}</p>;
  const skills = (items: SkillSupport[]) => items.length ? <ul>{items.map(s => <li key={s.skill_id}>{s.skill_name} · 覆盖率 {(100*s.coverage).toFixed(1)}% · {s.evidence_count} 条JD<small>{s.skill_id}；{s.supporting_job_ids.join("、")}</small></li>)}</ul> : <p>insufficient_evidence · 暂无足够技能证据</p>;
  return <section className="closure-definition"><h3>{label}</h3><h4>岗位名称</h4><p>{d.job_name}</p>
    <small>名称依据：{d.job_name_supporting_job_ids?.join("、") || "参见JD证据"}</small>
    <h4>核心职责</h4>{text(d.core_responsibilities, "insufficient_evidence · 暂无足够职责证据")}
    <h4>必备技能</h4>{skills(d.required_skills)}<h4>加分技能</h4>{skills(d.preferred_skills)}
    <h4>典型行业应用场景</h4>{text(d.application_scenarios, "insufficient_evidence · 场景证据不足，不自动编造")}</section>;
}

function DefinitionEditor({ item, busy, save, cancel }: { item: ClosureVersion; busy: boolean; save: (d: Definition) => void; cancel: () => void }) {
  const [draft, setDraft] = useState<Definition>(() => structuredClone(item.manual_definition || item.auto_definition));
  const known = new Map<string, SkillSupport>();
  [...item.auto_definition.required_skills, ...item.auto_definition.preferred_skills, ...draft.required_skills, ...draft.preferred_skills].forEach(s => known.set(s.skill_id, s));
  item.evidence.forEach(row => row.skill_evidence?.filter(s => s.accepted && s.polarity === "affirmed").forEach(s => {
    if (!known.has(s.skill_id)) known.set(s.skill_id, { skill_id: s.skill_id, skill_name: s.standard_skill_name, coverage: 0, evidence_count: 0, supporting_job_ids: [], evidence_snippets: [] });
  }));
  function textField(field: 'core_responsibilities' | 'application_scenarios', label: string) {
    const supported = item.evidence.filter(row => field === 'core_responsibilities' ? row.responsibilities : row.industry || row.scenario || row.business_context);
    return <fieldset><legend>{label}</legend>{draft[field].map((value, i) => <div className="closure-edit-row" key={i}>
      <label>{label} {i+1}<textarea value={value.text} onChange={e => setDraft({ ...draft, [field]: draft[field].map((v,j) => j===i ? {...v,text:e.target.value} : v) })} /></label>
      <label>支持此描述的JD（可多选）<select multiple value={value.supporting_job_ids} onChange={e => setDraft({ ...draft, [field]: draft[field].map((v,j) => j===i ? {...v,supporting_job_ids:Array.from(e.target.selectedOptions, o => o.value)} : v) })}>{supported.map(r => <option key={r.job_id} value={r.job_id}>{r.job_id} · {r.original_title}</option>)}</select></label>
      <button type="button" onClick={() => setDraft({...draft,[field]:draft[field].filter((_,j) => i!==j)})}>删除此项</button></div>)}
      <button type="button" disabled={!supported.length} onClick={() => setDraft({...draft,[field]:[...draft[field],{text:"",supporting_job_ids:[],evidence_snippets:[]}]})}>添加{label}</button>
      {!supported.length ? <p>没有该字段原文证据，不能补写。</p> : null}</fieldset>;
  }
  return <form className="closure-editor" onSubmit={e => {e.preventDefault(); save(draft);}}>
    <p>人工摘要仍须人工核验；证据ID与技能支持度由后端校验，不覆盖自动结果。</p>
    <label>修订岗位名称<input required value={draft.job_name} onChange={e => setDraft({...draft,job_name:e.target.value})} /></label>
    {textField('core_responsibilities','职责')}
    <fieldset><legend>必备 / 加分技能（仅列出正向证据技能）</legend>{Array.from(known.values()).map(s => <label key={s.skill_id}>{s.skill_name}<select value={draft.required_skills.some(v => v.skill_id===s.skill_id) ? 'required' : draft.preferred_skills.some(v => v.skill_id===s.skill_id) ? 'preferred' : 'excluded'} onChange={e => setDraft({...draft,required_skills:[...draft.required_skills.filter(v=>v.skill_id!==s.skill_id),...(e.target.value==='required'?[s]:[])],preferred_skills:[...draft.preferred_skills.filter(v=>v.skill_id!==s.skill_id),...(e.target.value==='preferred'?[s]:[])]})}><option value="required">必备</option><option value="preferred">加分</option><option value="excluded">不纳入</option></select></label>)}</fieldset>
    {textField('application_scenarios','场景')}<button disabled={busy}>保存人工修改</button><button type="button" onClick={cancel}>取消编辑</button>
  </form>;
}

function EvidenceImport({ jobTitle, saved }: { jobTitle?: string; saved: () => void }) {
  const empty = {job_id:"",original_title:"",responsibilities:"",required_skills_raw:"",bonus_skills_raw:"",company:"",source:"",url:"",published_at:"",collected_at:"",industry:"",scenario:""};
  const [form,setForm] = useState(empty); const [message,setMessage] = useState(""); const [busy,setBusy] = useState(false);
  const labels: Record<keyof typeof empty,string> = {job_id:"新JD编号",original_title:"原始岗位名称",responsibilities:"JD职责原文",required_skills_raw:"必备技能原文",bonus_skills_raw:"加分技能原文",company:"企业",source:"来源",url:"原始招聘链接",published_at:"真实发布时间",collected_at:"采集时间",industry:"行业原文",scenario:"场景原文"};
  return <details><summary>追加JD证据（不覆盖原始数据）</summary><form className="closure-editor" onSubmit={async e => {
    e.preventDefault(); setBusy(true); setMessage("");
    try {await postThenGet<JDEvidence,JDEvidence>('/api/closure/evidence',{...form,standard_job_title:jobTitle || ""},created=>`/api/closure/evidence/${encodeURIComponent(created.job_id)}`);setForm(empty);setMessage("JD证据已保存并从后端重新读取。请点击运行发现或重新计算更新。");saved();}
    catch(error){setMessage(error instanceof Error ? error.message : String(error));}finally{setBusy(false);}
  }}><p>{jobTitle ? `归属既有岗位：${jobTitle}` : '作为未标准化新岗位证据；不假定已发现正式新职业。'} 不清楚的字段留空，不使用示例值。</p>
    {Object.entries(labels).map(([key,label]) => <label key={key}>{label}<textarea required={key==='job_id'||key==='original_title'} value={form[key as keyof typeof empty]} onChange={e => setForm({...form,[key]:e.target.value})} /></label>)}
    <button disabled={busy}>保存JD证据</button><p role="status">{message}</p></form></details>;
}

function ReviewDetail({ item, replace }: { item: ClosureVersion; replace: (i: ClosureVersion) => void }) {
  const [history,setHistory] = useState<History|null>(null); const [viewVersion,setViewVersion] = useState(item.version);
  const [diff,setDiff] = useState<VersionDiff|null>(null); const [editing,setEditing] = useState(false);
  const [reviewer,setReviewer] = useState(""); const [note,setNote] = useState(""); const [ack,setAck] = useState(false);
  const [busy,setBusy] = useState(false); const [error,setError] = useState("");
  const path = `/api/closure/${item.kind}/${encodeURIComponent(item.id)}`;
  useEffect(() => {let active=true;setViewVersion(item.version);setEditing(false);setDiff(null);setHistory(null);
    getJson<History>(`${path}/versions`).then(r => {if(active)setHistory(r.data);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};
  },[path,item.version,item.revision]);
  const shown = history?.versions.find(v=>v.version===viewVersion) || item;
  const publication = history?.publications.at(-1);
  async function change(endpoint:string,payload:unknown){setBusy(true);setError("");try{replace(await postThenGet<ClosureVersion,ClosureVersion>(path+endpoint,payload,()=>path));setNote("");setAck(false);}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
  const expected = {expected_version:item.version,expected_revision:item.revision};
  return <article className="closure-detail" data-testid="closure-detail"><h3>{(shown.manual_definition||shown.auto_definition).job_name}</h3>
    <p data-testid="closure-status">{statusLabel[shown.status]} · 草稿内容 V{shown.version} · 前版本 {shown.previous_version ?? "无"} · {shown.source_job_count} 条JD</p>
    <p>{shown.created_at} · 审核人 {shown.reviewer || "未提供"} · {shown.reviewed_at} · {shown.review_note}</p>
    <p data-testid="publication-status">{publication ? `当前已发布画像 V${publication.profile_version}（${publication.origin==='legacy_baseline'?'冻结数据基线，非人工审批':`内容版本 V${publication.version}`}）` : "尚未发布；候选不等于正式岗位"}</p>
    {publication ? <details><summary>查看当前正式发布画像</summary><DefinitionView definition={publication.manual_definition||publication.auto_definition} label="正式发布快照"/><EvidenceList evidence={publication.evidence}/></details>:null}
    <div className="toolbar"><label>查看内容版本<select value={viewVersion} onChange={e=>{setViewVersion(Number(e.target.value));setDiff(null);setEditing(false);}}>{(history?.versions||[item]).map(v=><option key={v.version} value={v.version}>V{v.version} · {statusLabel[v.status]}</option>)}</select></label>
      <button disabled={!shown.previous_version||busy} onClick={async()=>{try{setDiff((await getJson<VersionDiff>(`${path}/diff?before=${shown.previous_version}&after=${shown.version}`)).data);}catch(e){setError(String(e));}}}>查看与前版差异</button></div>
    {diff ? <section data-testid="version-diff"><h4>版本变化原因</h4><p>证据数：{diff.evidence_count_before} → {diff.evidence_count_after}</p><p>新增技能：{diff.added_skills.map(s=>s.skill_name).join('、')||'无'}</p><p>删除技能：{diff.removed_skills.map(s=>s.skill_name).join('、')||'无'}</p><p>修改技能：{diff.modified_skills.map(s=>s.after.skill_name).join('、')||'无'}</p><p>岗位名称 / 职责 / 场景变化：{[diff.job_name_changed,diff.responsibilities_changed,diff.scenarios_changed].map(v=>v?'有':'无').join(' / ')}</p></section>:null}
    {shown.change_set ? <section data-testid="change-set"><h4>能力变化审核单</h4><p>{shown.change_set.status} · 前窗口 {shown.change_set.before_count} / 后窗口 {shown.change_set.after_count}（最低各 {shown.change_set.minimum_sample}）</p><p>{shown.change_set.before_window} → {shown.change_set.after_window} · {shown.change_set.mode}</p><p>{shown.change_set.notice}</p>
      {shown.change_set.status==='insufficient_sample'?<p>样本不足，不给出上涨/下降结论，不允许批准发布。</p>:null}
      {(['added_skills','removed_skills','modified_skills'] as const).map((key,i)=><div key={key}><h4>{['新增能力','删除能力','修改能力'][i]}</h4>{shown.change_set![key].length?shown.change_set![key].map(c=><details key={c.skill_id}><summary>{c.skill_name}：{(100*c.before).toFixed(1)}% → {(100*c.after).toFixed(1)}% · {c.before_role} → {c.after_role}</summary><h5>前窗口证据</h5><EvidenceList evidence={c.before_evidence}/><h5>后窗口证据</h5><EvidenceList evidence={c.after_evidence}/></details>):<p>无</p>}</div>)}
      <small>未参与时间比较的无日期JD：{shown.change_set.excluded_undated_job_ids.join('、')||'无'}</small></section>:null}
    {shown.change_set?.withheld_skills.length?<p>新增技能证据未达最低2条，暂不纳入发布：{shown.change_set.withheld_skills.map(s=>s.skill_name).join('、')}</p>:null}
    <details open><summary>自动定义（保留原始聚合结果）</summary><DefinitionView definition={shown.auto_definition} label="自动定义" /></details>
    {shown.manual_definition?<DefinitionView definition={shown.manual_definition} label="人工修订（需人工核验证据）"/>:null}
    <details><summary>全部JD证据（{shown.evidence.length}）</summary><EvidenceList evidence={shown.evidence}/></details>
    {viewVersion===item.version?<><div className="closure-actions">
      {item.kind==='candidate'?<button disabled={busy} onClick={()=>setEditing(true)}>编辑五要素</button>:null}
      <label>审核人（可空）<input value={reviewer} onChange={e=>setReviewer(e.target.value)}/></label><label>审核说明 / 驳回理由<textarea value={note} onChange={e=>setNote(e.target.value)}/></label>
      <label><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>已核验引用证据，明确接受缺失场景 / 加分技能保持空值</label>
      {(['submit','approve','reject','publish'] as const).map((action,i)=>{const allowed={submit:['candidate','rejected'],approve:['pending_review'],reject:['candidate','pending_review','approved'],publish:['approved']}[action];return <button key={action} disabled={busy||!allowed.includes(item.status)||(action==='approve'&&!!item.change_set&&item.change_set.status!=='ready')} onClick={()=>change('/actions',{...expected,action,reviewer,note,acknowledge_gaps:ack})}>{['提交审核','批准','驳回','发布'][i]}</button>;})}</div>
      {editing?<DefinitionEditor key={item.version} item={item} busy={busy} cancel={()=>setEditing(false)} save={d=>change('/manual',{...expected,definition:d})}/>:null}</>:<p>历史版本只读。请切回最新版本操作。</p>}
    <p role="alert">{error}</p><details><summary>审核事件记录</summary>{history?.events.map((event,i)=><p key={i}>{event.at} · V{event.version} · {event.event} · {event.reviewer||'未提供审核人'} · {event.note}</p>)}</details>
  </article>;
}

export default function ClosurePanel({ jobTitle }: { jobTitle?: string }) {
  const [items,setItems] = useState<ClosureVersion[]>([]); const [selected,setSelected] = useState("");
  const [error,setError] = useState(""); const [busy,setBusy] = useState(false);
  useEffect(()=>{let active=true;setItems([]);setSelected("");setError("");
    const endpoint=jobTitle?`/api/closure/profile/${encodeURIComponent(jobTitle)}`:'/api/closure/candidates';
    getJson<ClosureVersion|ClosureVersion[]>(endpoint).then(r=>{if(active){const list=Array.isArray(r.data)?r.data:[r.data];setItems(list);setSelected(list[0]?.id||"");}}).catch(()=>{if(active)setError("尚无闭环记录，或后端暂不可用。可确认写入权限后运行下方流程。");});return()=>{active=false;};
  },[jobTitle]);
  async function run(){setBusy(true);setError("");try{const refreshed=await postThenGet<ClosureVersion|ClosureVersion[],ClosureVersion|ClosureVersion[]>(jobTitle?'/api/closure/profiles/run':'/api/closure/discovery/run',jobTitle?{job_title:jobTitle}:{},()=>jobTitle?`/api/closure/profile/${encodeURIComponent(jobTitle)}`:'/api/closure/candidates');const list=Array.isArray(refreshed)?refreshed:[refreshed];setItems(list);setSelected(list.some(i=>i.id===selected)?selected:list[0]?.id||"");}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
  const item=items.find(i=>i.id===selected);
  return <details className="panel closure-panel"><summary>数据质量与审核记录</summary><div className="closure-panel-body"><h2>{jobTitle?'岗位画像更新审核':'新岗位定义与发布审核'}</h2>
    <p>以下为数据维护功能，普通求职分析无需操作。待审内容不会覆盖已经发布的岗位画像。</p>
    <ClosureAccess/>
    <EvidenceImport jobTitle={jobTitle} saved={()=>setError('新证据已追加；正式版本未改变，请重新计算。')}/>
    <button disabled={busy} onClick={run}>{busy?'计算中…':jobTitle?'重新计算能力更新':'运行新岗位发现'}</button><p role="status">{error}</p>
    {!jobTitle?<div className="closure-candidate-list">{items.map(i=><button key={i.id} aria-pressed={selected===i.id} onClick={()=>setSelected(i.id)}>{(i.manual_definition||i.auto_definition).job_name} · {statusLabel[i.status]} · V{i.version}<small>发现规则得分 {i.discovery_score}（非真实性概率） · JD {i.source_job_count} · 企业 {i.company_count} · 来源 {i.source_count}</small></button>)}</div>:null}
    {item?<ReviewDetail key={item.id} item={item} replace={updated=>setItems(items.map(i=>i.id===updated.id?updated:i))}/>:<p>尚无候选 / 更新审核单。</p>}
  </div></details>;
}

export function PublishedProfile({ profile }: { profile?: ClosureVersion | null }) {
  if(!profile || profile.origin==='legacy_baseline')return null;
  return <section className="panel closure-panel" data-testid="published-profile"><h2>人工审核发布画像 V{profile.profile_version}</h2><p>本页技能、正式匹配与岗位技能图谱使用统一的有效发布画像；待审或驳回版本不生效。</p><DefinitionView definition={profile.manual_definition||profile.auto_definition} label="正式发布定义"/><details><summary>发布依据JD证据</summary><EvidenceList evidence={profile.evidence}/></details></section>;
}
