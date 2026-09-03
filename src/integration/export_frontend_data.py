from __future__ import annotations

import json
from pathlib import Path

from ..api.integration_service import get_system_data
from ..api.service import get_services


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    target = root / "frontend" / "public" / "data"
    target.mkdir(parents=True, exist_ok=True)
    services = get_services()
    system = get_system_data()
    rows = services.loader.load_jds()
    counts: dict[str, int] = {}
    for row in rows:
        title = str(row.get("standard_job_title") or "").strip()
        if title:
            counts[title] = counts.get(title, 0) + 1
    write_json(target / "system_overview.json", system.overview())
    write_json(target / "jobs.json", {"data_version": services.loader.version.get("data_version"), "jobs": [{"standard_job_title": title, "jd_count": counts[title]} for title in sorted(counts)]})
    write_json(target / "graph_compat_v1.json", system.graph.load())
    focus = ["AI Agent开发工程师", "RAG引擎研发工程师", "AI安全技术工程师"]
    write_json(target / "evolution_status.json", {"jobs": {title: system.evolution.for_job(title) for title in focus}})
    emerging = system.emerging_list()
    write_json(target / "emerging_jobs_v2.json", emerging)
    # Keep the V1 filename for already deployed bundles that still request it.
    write_json(target / "emerging_jobs_v1.json", emerging)
    write_json(target / "job_analysis_v1.json", {"jobs": [system.job_analysis(title) for title in focus]})
    print(f"已生成前端真实数据降级文件：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
