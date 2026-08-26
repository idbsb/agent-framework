from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class EvolutionAdapter:
    """Read formal evolution artifacts only; never calculates trends."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def _paths(self) -> list[Path]:
        return [
            self.project_root / "external_modules" / "graph_dynamic" / "outputs" / "key_job_evolution_v1.json",
            self.project_root / "outputs" / "key_job_evolution_v1.json",
            self.project_root / "key_job_evolution_v1.json",
            self.project_root / "组员图谱动态" / "key_job_evolution_v1.json",
        ]

    def _missing(self, job_title: str) -> dict[str, Any]:
        return {
            "available": False,
            "status": "not_connected",
            "job_title": job_title,
            "source_file": "",
            "message": "动态演化数据尚未接入",
            "notice": "等待组员A正式 key_job_evolution_v1.json；当前未重新计算任何趋势。",
            "time_range": None,
            "sample_notice": "当前没有正式演化样本。",
            "core_skills": [],
            "growing_skills": [],
            "new_skills": [],
            "stable_skills": [],
            "declining_skills": [],
        }

    def for_job(self, job_title: str) -> dict[str, Any]:
        path = next((item for item in self._paths() if item.exists()), None)
        if path is None:
            return self._missing(job_title)
        payload = json.loads(path.read_text(encoding="utf-8"))
        record: Any = None
        if isinstance(payload, dict):
            jobs = payload.get("jobs") or payload.get("data") or payload.get("job_evolution")
            if isinstance(jobs, list):
                record = next((item for item in jobs if str(item.get("job_title") or item.get("岗位名称") or "") == job_title), None)
            elif isinstance(jobs, dict):
                record = jobs.get(job_title)
            elif job_title in payload:
                record = payload.get(job_title)
        if record is None:
            result = self._missing(job_title)
            result.update({"available": True, "status": "job_not_found", "source_file": path.name, "message": "正式演化文件中暂无该岗位"})
            return result
        if not isinstance(record, dict):
            record = {"data": record}
        status_summary = record.get("status_summary") if isinstance(record.get("status_summary"), dict) else {}

        def records_for(label: str) -> list[dict[str, Any]]:
            values = status_summary.get(label, [])
            return [item for item in values if isinstance(item, dict)] if isinstance(values, list) else []

        groups = {
            "growing": records_for("快速增长"),
            "new": records_for("新增"),
            "stable": records_for("稳定"),
            "declining": records_for("下降"),
            "sample_insufficient": records_for("样本不足"),
        }

        def names(values: list[dict[str, Any]]) -> list[str]:
            return [_text for item in values if (_text := str(item.get("技能名称") or item.get("skill_name") or "").strip())]

        current_top = record.get("current_top") if isinstance(record.get("current_top"), list) else []
        sample_insufficient = bool(groups["sample_insufficient"])
        support_count = int(record.get("support_jd_count") or 0)
        if sample_insufficient:
            sample_notice = f"正式结果支持JD {support_count}条；当前比较窗口被组员A正式结果标记为样本不足，未形成可靠的增长、下降、新增或稳定结论。"
        else:
            sample_notice = f"正式结果支持JD {support_count}条；当前分类直接来自组员A正式演化结果。"
        return {
            **record,
            "available": True,
            "status": "connected",
            "job_title": job_title,
            "source_file": str(path.relative_to(self.project_root)),
            "message": "已接入组员A正式动态演化结果",
            "notice": "当前结果基于现有招聘数据时间窗口进行近期岗位能力变化观察，用于验证岗位能力动态更新机制，不代表多年长期产业趋势。",
            "meta": payload.get("meta", {}),
            "support_jd_count": support_count,
            "sample_insufficient": sample_insufficient,
            "sample_notice": sample_notice,
            "core_skills": names([item for item in current_top if isinstance(item, dict)]),
            "growing_skills": names(groups["growing"]),
            "new_skills": names(groups["new"]),
            "stable_skills": names(groups["stable"]),
            "declining_skills": names(groups["declining"]),
            "sample_insufficient_skills": names(groups["sample_insufficient"]),
            "skill_groups": groups,
        }
