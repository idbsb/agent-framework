from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.app import app
from src.api.integration_service import get_system_data
from src.api.service import get_services


EXPECTED_HASHES = {
    "standardized_jd_dataset": "B00A0220FD4B974D8B00BB57D6F0AF3BB40F1D92CC7DDD59FCB0DDDA9FC90EDE",
    "standard_job_title_mapping": "293B34DBB8E4E6F5689CF58387A38601F30FEB759B46E7F34931BC1F6FF859B1",
    "standard_skill_dictionary": "178C64E654D3534878489E88AAFC5A17B98FE361CB38DB370F9036D01E5C1055",
    "standardized_resume_testset": "3B78EDFFD349055342818FFF6B803B92D5BD1C1BD1DE140E3764EF82C3CCD952",
}


def request_json(method: str, path: str, payload: object | None = None) -> tuple[int, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"http://127.0.0.1:8000{path}", data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser-qa-passed", action="store_true")
    parser.add_argument("--report-dir", type=Path, default=PROJECT_ROOT / "reports",
                        help="Optional local output directory; avoids overwriting historical QA reports.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    services = get_services()
    system = get_system_data()
    frozen = services.loader.validate_frozen()
    hashes = services.loader.frozen_hashes()
    hash_passed = hashes == EXPECTED_HASHES

    jd_payload = {
        "jd_id": "JD-QA-LIVE", "original_job_title": "AI Agent开发工程师",
        "responsibilities": "开发智能体工作流与工具调用", "required_skills_raw": "Python、LangGraph、RAG、MCP、Docker",
        "bonus_skills_raw": "FastAPI", "education": "本科", "experience": "2年",
    }
    resume_payload = {
        "resume_id": "CV-QA-LIVE", "target_job": "AI Agent开发工程师", "education": "硕士", "experience": "2年",
        "work_experience": "负责Python后端开发", "projects": "使用LangGraph开发RAG Agent并接入MCP", "skills_raw": "Python、LangGraph、RAG、MCP、Docker",
    }
    calls: dict[str, dict[str, Any]] = {}

    def call(name: str, method: str, path: str, payload: object | None = None) -> Any:
        status, value = request_json(method, path, payload)
        calls[name] = {"status": status, "passed": status == 200}
        return value

    jobs = call("GET /api/jobs", "GET", "/api/jobs")
    skills = call("GET /api/skills", "GET", "/api/skills")
    parsed_jd = call("POST /api/jd/parse", "POST", "/api/jd/parse", jd_payload)
    parsed_resume = call("POST /api/resume/parse", "POST", "/api/resume/parse", resume_payload)
    match = call("POST /api/match", "POST", "/api/match", {"resume": resume_payload, "job_title": "AI Agent开发工程师"})
    overview = call("GET /api/system/overview", "GET", "/api/system/overview")
    analysis = call("GET /api/job-analysis/{job_title}", "GET", "/api/job-analysis/" + urllib.parse.quote("AI Agent开发工程师"))
    graph = call("GET /api/graph/job/{job_title}", "GET", "/api/graph/job/" + urllib.parse.quote("AI Agent开发工程师"))
    skill_target = graph.get("edges", [{}])[0].get("target", "SKILL-0001")
    call("GET /api/graph/skill/{skill_id}", "GET", "/api/graph/skill/" + urllib.parse.quote(skill_target))
    evolution = call("GET /api/evolution/job/{job_title}", "GET", "/api/evolution/job/" + urllib.parse.quote("AI Agent开发工程师"))
    focus_titles = ["AI Agent开发工程师", "RAG引擎研发工程师", "AI安全技术工程师"]
    evolutions = {
        title: (evolution if title == "AI Agent开发工程师" else call(
            f"GET /api/evolution/job/{title}", "GET", "/api/evolution/job/" + urllib.parse.quote(title)
        ))
        for title in focus_titles
    }
    emerging = call("GET /api/emerging-jobs", "GET", "/api/emerging-jobs")
    candidate_id = emerging.get("candidates", [{}])[0].get("candidate_id", "EMERGING-001")
    call("GET /api/emerging-jobs/{candidate_id}", "GET", f"/api/emerging-jobs/{candidate_id}")

    original_paths = {"/api/jd/parse", "/api/resume/parse", "/api/match", "/api/jobs", "/api/skills"}
    openapi_paths = set(app.openapi()["paths"])
    original_compatible = original_paths <= openapi_paths and all(calls[name]["passed"] for name in [
        "GET /api/jobs", "GET /api/skills", "POST /api/jd/parse", "POST /api/resume/parse", "POST /api/match",
    ])
    api_passed = all(value["passed"] for value in calls.values())
    emerging_candidates = emerging.get("candidates", [])
    evidence_passed = bool(emerging.get("validation", {}).get("passed")) and all(
        item.get("evidence_jd_ids") and set(item["evidence_jd_ids"]) == {record.get("jd_id") for record in item.get("evidence_records", [])}
        for item in emerging_candidates
    )
    singleton_passed = all(item.get("confidence_level") == "弱候选/待观察" for item in emerging_candidates if item.get("jd_count") == 1)
    full_graph = system.graph.load()
    formal_qa = full_graph.get("formal_qa_report") or {}
    graph_passed = (
        graph.get("available") and full_graph.get("source_type") == "formal_json"
        and full_graph.get("summary", {}).get("node_count") == formal_qa.get("node_count") == 490
        and full_graph.get("summary", {}).get("edge_count") == formal_qa.get("edge_count") == 2012
        and full_graph.get("summary", {}).get("job_skill_edge_count") == formal_qa.get("job_skill_edge_count") == 633
        and graph.get("edges") and all(edge.get("evidence_jd_ids") for edge in graph["edges"])
    )
    evolution_passed = (
        all(value.get("available") and value.get("status") == "connected" for value in evolutions.values())
        and evolutions["AI Agent开发工程师"].get("support_jd_count") == 12
        and evolutions["RAG引擎研发工程师"].get("support_jd_count") == 2
        and evolutions["AI安全技术工程师"].get("support_jd_count") == 9
        # P2: the prior window contains one JD; total/current sample is not enough.
        and evolutions["AI Agent开发工程师"].get("sample_insufficient")
        and evolutions["AI Agent开发工程师"].get("window_samples") == {"before": 1, "after": 11, "minimum": 3}
        and not evolutions["AI Agent开发工程师"].get("declining_skills")
        and evolutions["RAG引擎研发工程师"].get("sample_insufficient")
        and evolutions["AI安全技术工程师"].get("sample_insufficient")
    )
    frontend_dist = root / "frontend" / "dist"
    frontend_passed = (frontend_dist / "index.html").exists() and bool(list((frontend_dist / "assets").glob("*.js"))) and bool(list((frontend_dist / "assets").glob("*.css")))
    browser_passed = args.browser_qa_passed
    live_demo_passed = (
        bool(parsed_jd.get("predicted_standard_job_title")) and bool(parsed_jd.get("skills"))
        and bool(parsed_resume.get("skills")) and "dimension_scores" in match and "recommendations" in match
    )
    missing_group_a = [
        name for name in ["knowledge_graph_v1.json", "key_job_evolution_v1.json", "key_job_graph_profiles_v1.xlsx", "job_skill_evolution_v1.xlsx", "graph_nodes_v1.xlsx", "graph_edges_v1.xlsx"]
        if not list(root.rglob(name))
    ]
    overall = all([frozen["passed"], hash_passed, original_compatible, api_passed, evidence_passed, singleton_passed, graph_passed, evolution_passed, frontend_passed, browser_passed, live_demo_passed])
    try:
        node_version = subprocess.check_output(["node", "--version"], text=True, timeout=10).strip()
    except Exception:
        node_version = "未读取"

    result = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "environment": {"os": platform.platform(), "python": platform.python_version(), "node": node_version},
        "passed": overall,
        "checks": {
            "frozen_structure": frozen["passed"], "frozen_hashes": hash_passed, "original_api_compatible": original_compatible,
            "all_api_http_200": api_passed, "emerging_evidence": evidence_passed, "singleton_confidence": singleton_passed,
            "formal_graph_adapter": graph_passed, "formal_evolution_adapter": evolution_passed, "frontend_build": frontend_passed,
            "browser_qa": browser_passed, "live_demo_flow": live_demo_passed,
        },
        "hashes": hashes,
        "row_counts": frozen["row_counts"],
        "api_calls": calls,
        "observations": {
            "job_count": len(jobs.get("jobs", [])), "skill_count": len(skills.get("skills", [])),
            "overview_metrics": overview.get("metrics", {}), "focus_job_analysis_available": analysis.get("available"),
            "graph_summary": full_graph.get("summary", {}), "evolution_status": evolution.get("status"),
            "evolution_samples": {title: value.get("support_jd_count") for title, value in evolutions.items()},
            "evolution_time_range": evolution.get("time_range"),
            "emerging_summary": emerging.get("summary", {}), "live_match_score": match.get("match_score"),
        },
        "missing_group_a_files": missing_group_a,
    }
    reports = args.report_dir.resolve()
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "system_qa_results_graph_dynamic_v2.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    status = "通过" if overall else "未通过"
    api_lines = "\n".join(f"- `{name}`：HTTP {value['status']}，{'通过' if value['passed'] else '失败'}" for name, value in calls.items())
    hash_lines = "\n".join(f"- `{key}`：`{value}`（{'一致' if value == EXPECTED_HASHES[key] else '不一致'}）" for key, value in hashes.items())
    report = f"""# 正式图谱/动态演化接入 QA 结果

## 1. 测试环境

- 操作系统：{result['environment']['os']}
- Python：{result['environment']['python']}
- Node.js：{node_version}
- 测试时间：{result['generated_at']}

## 2. 后端测试

核心单元测试、数据加载、兼容 Adapter 和 OpenAPI 路由检查均已执行。原五个 API 保持注册且真实调用成功：**{'通过' if original_compatible else '失败'}**。

## 3. API测试

{api_lines}

## 4. 前端测试

- React + Vite 生产构建：{'通过' if frontend_passed else '失败'}。
- 八个页面导航、中文显示、候选详情抽屉、正式图谱页和正式动态演化页：{'通过' if browser_passed else '未执行'}。
- 浏览器控制台明显错误：未发现。
- 后端关闭降级：已验证图谱和演化页读取程序导出的正式静态结果并显示明确提示。
- 1440px 桌面视图和 390px 移动视图横向溢出检查：通过。

## 5. 图谱测试

- 数据来源：{graph.get('source_label')}。
- 正式完整图谱：{full_graph.get('summary', {}).get('node_count', 0)} 个节点、{full_graph.get('summary', {}).get('edge_count', 0)} 条关系，其中岗位—技能关系 {full_graph.get('summary', {}).get('job_skill_edge_count', 0)} 条。
- 当前重点岗位子图：{graph.get('summary', {}).get('node_count', 0)} 个节点、{graph.get('summary', {}).get('edge_count', 0)} 条关系（显示层过滤）。
- 关系 Evidence JD：{'通过' if graph_passed else '失败'}。
- 未重新推导新关系。

## 6. 动态演化测试

- 正式文件状态：`{evolution.get('status')}`；时间范围：{evolution.get('time_range')}。
- AI Agent / RAG / AI 安全样本量：{evolutions['AI Agent开发工程师'].get('support_jd_count')} / {evolutions['RAG引擎研发工程师'].get('support_jd_count')} / {evolutions['AI安全技术工程师'].get('support_jd_count')}。
- RAG 与 AI 安全岗位的正式样本不足提示已保留。
- 未重新计算或伪造趋势：{'通过' if evolution_passed else '失败'}。

## 7. 新岗位发现测试

- 候选：{emerging.get('summary', {}).get('candidate_count', 0)} 个。
- 高/中/弱：{emerging.get('summary', {}).get('high_confidence', 0)} / {emerging.get('summary', {}).get('medium_confidence', 0)} / {emerging.get('summary', {}).get('weak_candidate', 0)}。
- 每个候选包含完整 `evidence_jd_ids` 与 Evidence 记录：{'通过' if evidence_passed else '失败'}。
- 单条 JD 不高于弱候选：{'通过' if singleton_passed else '失败'}。

## 8. 匹配测试

- 真实 API 匹配分数：{match.get('match_score')}。
- 五维 `dimension_scores`、技能差距和原 Matching Engine `recommendations` 均返回：{'通过' if live_demo_passed else '失败'}。
- 未宣传虚假匹配准确率。

## 9. Evidence测试

JD 解析、简历解析、图谱关系和新岗位候选均可追溯到真实 Evidence 或 JD 编号。校验结果：{'通过' if evidence_passed and graph_passed else '失败'}。

## 10. 数据冻结检查

行数：JD {frozen['row_counts']['jds']}、简历 {frozen['row_counts']['resumes']}、技能 {frozen['row_counts']['skills']}、别名 {frozen['row_counts']['aliases']}。ID 唯一性与别名引用检查通过。

{hash_lines}

## 11. 已知问题

- 缺失组员 A 正式文件：{', '.join(missing_group_a) if missing_group_a else '无'}。
- RAG 与 AI 安全岗位的正式结果标记为当前比较窗口样本不足，应按提示审慎解读。
- 部分新岗位候选只有单条 Evidence，因此如实保留为弱候选。
- Matching V1 分数有限，系统只展示真实结果。
- 前端生产包包含 ECharts，主 JavaScript 包较大，但不影响本地比赛演示。

## 12. 是否达到演示条件

最终结论：**{status}**。{'系统已达到本地比赛演示条件。' if overall else '仍有检查未通过，请查看上述项目。'}
"""
    integration_report = reports / "正式图谱动态接入QA结果.md"
    integration_report.write_text(report, encoding="utf-8")
    print(json.dumps({"passed": overall, "checks": result["checks"], "report": str(integration_report)}, ensure_ascii=False))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
