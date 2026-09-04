from __future__ import annotations

import json
import copy
import re
import hashlib
from pathlib import Path
from typing import Any

from ..core.skill_extractor import SkillIndex
from ..data_loader import DataLoader
from ..core.effective_profiles import EffectiveJobProfiles
from .incremental_data import BATCH_ID, GRAPH_VERSION, BASELINE_GRAPH_VERSION, IncrementalDataService


GRAPH_SOURCE_LABEL = "由组员A现有正式关系表转换"


def _text(value: object) -> str:
    return str(value or "").strip()


def _evidence_ids(value: object) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        values = [_text(item).upper() for item in value]
    else:
        values = re.findall(r"JD-\d+", _text(value), flags=re.IGNORECASE)
    return list(dict.fromkeys(item for item in values if re.fullmatch(r"JD-\d+", item, flags=re.IGNORECASE)))


class GraphAdapter:
    """Prefer formal graph JSON; otherwise convert only existing formal Excel relations."""

    def __init__(self, loader: DataLoader, skill_index: SkillIndex, *, effective_profiles=None):
        self.loader = loader
        self.skill_index = skill_index
        self.project_root = loader.project_root
        self.effective_profiles = effective_profiles or EffectiveJobProfiles(loader, skill_index, {})

    def _json_paths(self) -> list[Path]:
        return [
            self.project_root / "external_modules" / "graph_dynamic" / "outputs" / "knowledge_graph_v1.json",
            self.project_root / "outputs" / "knowledge_graph_v1.json",
            self.project_root / "knowledge_graph_v1.json",
            self.project_root / "组员图谱动态" / "knowledge_graph_v1.json",
        ]

    def _excel_paths(self) -> list[Path]:
        return [
            self.project_root / "组员图谱动态" / "重要岗位技能分析表.xlsx",
            self.project_root / "outputs" / "job_skill_analysis_cleaned.xlsx",
        ]

    def _from_json(self, path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"{path.name} 顶层必须是JSON对象")
        raw_nodes = value.get("nodes")
        raw_edges = value.get("edges")
        if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
            raise ValueError(f"{path.name} 必须包含nodes与edges数组")

        nodes: list[dict[str, Any]] = []
        for item in raw_nodes:
            if not isinstance(item, dict):
                continue
            formal_type = _text(item.get("type") or item.get("node_type"))
            name = _text(
                item.get("name") or item.get("label") or item.get("standard_job_title")
                or item.get("standard_skill_name") or item.get("jd_id")
                or item.get("company_name") or item.get("domain_name") or item.get("id")
            )
            nodes.append({**item, "name": name, "type": formal_type.lower(), "formal_type": formal_type})

        edges: list[dict[str, Any]] = []
        for item in raw_edges:
            if not isinstance(item, dict):
                continue
            evidence_ids = _evidence_ids(item.get("evidence_jd_ids"))
            try:
                frequency = float(item.get("frequency") or 0)
            except (TypeError, ValueError):
                frequency = 0.0
            edges.append({
                **item,
                "frequency": frequency,
                "evidence_jd_ids": evidence_ids,
                "evidence_count": len(evidence_ids),
            })

        job_skill_count = sum(1 for edge in edges if edge.get("edge_type") == "Job_Skill")
        qa_path = path.with_name("qa_report_v1.json")
        qa_report = json.loads(qa_path.read_text(encoding="utf-8")) if qa_path.exists() else None
        baseline = {
            **{key: item for key, item in value.items() if key not in {"nodes", "edges", "summary"}},
            "available": True,
            "status": "connected",
            "source_type": "formal_json",
            "source_label": "组员A正式知识图谱",
            "source_file": str(path.relative_to(self.project_root)),
            "notice": "正式图谱完整保留在后台；当前接口按所选岗位或技能返回直接关联子图。",
            "nodes": nodes,
            "edges": edges,
            "summary": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "job_skill_edge_count": job_skill_count,
                "job_count": sum(1 for node in nodes if node.get("type") == "job"),
                "skill_count": sum(1 for node in nodes if node.get("type") == "skill"),
            },
            "formal_qa_report": qa_report,
        }
        return self._overlay_incremental(baseline)

    def _overlay_incremental(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply the read-only batch as a transparent Graph V2 overlay."""
        service = IncrementalDataService(self.project_root, self.skill_index)
        by_job = service.skill_names()
        rows = service.standardized_jds()
        evidence_by_job: dict[str, list[str]] = {}
        for row in rows:
            evidence_by_job.setdefault(_text(row.get("standard_job_title")), []).append(_text(row.get("evidence_id")))
        result = copy.deepcopy(payload)
        baseline_summary = dict(result.get("summary", {}))
        nodes = {node["id"]: node for node in result.get("nodes", [])}
        job_by_name = {_text(node.get("name")).casefold(): node for node in nodes.values() if node.get("type") == "job"}
        skill_by_name = {_text(node.get("name")).casefold(): node for node in nodes.values() if node.get("type") == "skill"}
        pair_to_edge = {(edge.get("source"), edge.get("target")): edge for edge in result.get("edges", []) if self._is_job_skill(edge)}
        new_jobs = new_skills = new_relations = updated_relations = 0
        for job_title, skills in sorted(by_job.items()):
            job_rows = [row for row in rows if _text(row.get("standard_job_title")) == job_title]
            job = job_by_name.get(job_title.casefold())
            if job is None:
                job_id = "job:inc:" + hashlib.sha1(job_title.encode("utf-8")).hexdigest()[:12]
                job = {"id": job_id, "name": job_title, "type": "job", "formal_type": "Job", "batch_status": "NEW", "batch_id": BATCH_ID, "is_emerging": True}
                nodes[job_id] = job; job_by_name[job_title.casefold()] = job; new_jobs += 1
            else:
                job.update(batch_status="UPDATED", batch_id=BATCH_ID)
            dates = sorted(_text(row.get("publish_date")) for row in job_rows if _text(row.get("publish_date")))
            job.update(
                standard_job_title=job_title, job_status="新兴岗位候选" if any(_text(row.get("job_family")) == "新兴岗位候选" for row in job_rows) else "既有岗位",
                is_emerging=any(_text(row.get("job_family")) == "新兴岗位候选" for row in job_rows),
                incremental_jd_count=len(job_rows), company_count=len({_text(row.get("company")) for row in job_rows if _text(row.get("company"))}),
                source_count=len({_text(row.get("source")) for row in job_rows if _text(row.get("source"))}), evidence_count=len(job_rows),
                first_seen=dates[0] if dates else "", last_seen=dates[-1] if dates else "", updated_at="2026-09-04",
                graph_version=GRAPH_VERSION, evidence_ids=evidence_by_job.get(job_title, []), core_skills=sorted(skills),
            )
            for skill_name in sorted(skills):
                skill = skill_by_name.get(skill_name.casefold())
                if skill is None:
                    skill_id = "skill:inc:" + hashlib.sha1(skill_name.casefold().encode("utf-8")).hexdigest()[:12]
                    skill = {"id": skill_id, "name": skill_name, "type": "skill", "formal_type": "Skill", "batch_status": "NEW", "batch_id": BATCH_ID}
                    nodes[skill_id] = skill; skill_by_name[skill_name.casefold()] = skill; new_skills += 1
                pair = (job["id"], skill["id"])
                ids = evidence_by_job.get(job_title, [])
                if pair in pair_to_edge:
                    edge = pair_to_edge[pair]
                    edge["incremental_evidence_ids"] = ids
                    edge["evidence_jd_ids"] = list(dict.fromkeys([*edge.get("evidence_jd_ids", []), *ids]))
                    edge["evidence_count"] = len(edge["evidence_jd_ids"])
                    edge.update(batch_status="UPDATED", batch_id=BATCH_ID); updated_relations += 1
                else:
                    edge = {"id": f"inc:{job['id']}:{skill['id']}", "source": job["id"], "target": skill["id"], "edge_type": "Job_Skill",
                        "relation": "requires_skill", "job_title": job_title, "skill_name": skill_name, "frequency": 0,
                        "mention_count": len(ids), "evidence_jd_ids": ids, "evidence_count": len(ids), "batch_status": "NEW", "batch_id": BATCH_ID}
                    result["edges"].append(edge); pair_to_edge[pair] = edge; new_relations += 1
        result["nodes"] = list(nodes.values())
        result["baseline_summary"] = baseline_summary
        result["graph_version"] = GRAPH_VERSION
        result["baseline_graph_version"] = BASELINE_GRAPH_VERSION
        result["batch_id"] = BATCH_ID
        result["graph_change"] = {"new_job_node_count": new_jobs, "new_skill_node_count": new_skills, "new_relation_count": new_relations, "updated_relation_count": updated_relations}
        result["summary"] = {**baseline_summary, "node_count": len(result["nodes"]), "edge_count": len(result["edges"]),
            "job_skill_edge_count": sum(self._is_job_skill(edge) for edge in result["edges"]),
            "job_count": sum(node.get("type") == "job" for node in result["nodes"]), "skill_count": sum(node.get("type") == "skill" for node in result["nodes"])}
        result["source_label"] = "Graph V2（正式基准图谱 + 2026-09-04真实增量批次）"
        result["notice"] = "NEW 为本批次新增节点/关系，UPDATED 为本批次有新增 Evidence 的既有关系。"
        return result

    def _from_excel(self, path: Path) -> dict[str, Any]:
        workbook_sheet = "Sheet1" if path.name == "重要岗位技能分析表.xlsx" else "技能明细"
        rows = self.loader.read_sheet(path, workbook_sheet)
        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []
        current_job = ""
        current_level = ""
        for row in rows:
            row_job = _text(row.get("岗位名称"))
            if row_job and (row_job.startswith("重要程度") or set(row_job) <= {"★", "☆"}):
                break
            if row_job:
                current_job = row_job
            row_level = _text(row.get("技能层次"))
            if row_level:
                current_level = row_level
            job_title = current_job
            skill_name = _text(row.get("技能名称"))
            ids = _evidence_ids(row.get("依据来源（JD编号）"))
            if not job_title or not skill_name or not ids:
                continue
            job_id = f"job:{job_title}"
            skill_id = self.skill_index.resolve_name(skill_name) or f"skill-name:{skill_name}"
            nodes[job_id] = {"id": job_id, "name": job_title, "type": "job", "category": "岗位"}
            skill_record = self.skill_index.skills.get(skill_id)
            nodes[skill_id] = {
                "id": skill_id,
                "name": skill_name,
                "type": "skill",
                "category": skill_record.category if skill_record else current_level or "技能",
            }
            frequency = row.get("出现频率")
            try:
                frequency_value = float(frequency)
            except (TypeError, ValueError):
                frequency_value = 0.0
            edges.append({
                "id": f"{job_id}->{skill_id}",
                "source": job_id,
                "target": skill_id,
                "relation": "requires_skill",
                "skill_level": current_level,
                "importance": _text(row.get("重要程度")),
                "occurrence": _text(row.get("出现次数")),
                "frequency": round(frequency_value, 4),
                "platform_sources": _text(row.get("JD来源（平台）")),
                "evidence_jd_ids": ids,
                "evidence_count": len(ids),
            })
        edges.sort(key=lambda item: (item["source"], -item["frequency"], item["target"]))
        return {
            "available": True,
            "status": "compatibility_conversion",
            "source_type": "formal_excel_compatibility",
            "source_label": GRAPH_SOURCE_LABEL,
            "source_file": str(path.relative_to(self.project_root)),
            "notice": "仅转换组员A现有正式岗位—技能关系，不重新推导或补全关系。",
            "nodes": list(nodes.values()),
            "edges": edges,
            "summary": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "job_count": sum(1 for node in nodes.values() if node["type"] == "job"),
                "skill_count": sum(1 for node in nodes.values() if node["type"] == "skill"),
            },
        }

    def load(self) -> dict[str, Any]:
        for path in self._json_paths():
            if path.exists():
                return self._from_json(path)
        for path in self._excel_paths():
            if path.exists():
                return self._from_excel(path)
        return {
            "available": False,
            "status": "not_connected",
            "source_type": "missing",
            "source_label": "岗位能力图谱数据尚未接入",
            "notice": "未找到组员A正式图谱JSON或关系Excel。",
            "nodes": [],
            "edges": [],
            "summary": {"node_count": 0, "edge_count": 0, "job_count": 0, "skill_count": 0},
        }

    @staticmethod
    def _filter_payload(payload: dict[str, Any], edges: list[dict[str, Any]]) -> dict[str, Any]:
        node_ids = {edge["source"] for edge in edges} | {edge["target"] for edge in edges}
        nodes = [node for node in payload.get("nodes", []) if node.get("id") in node_ids]
        return {
            **{key: value for key, value in payload.items() if key not in {"nodes", "edges", "summary"}},
            "nodes": nodes,
            "edges": edges,
            "summary": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "job_skill_edge_count": sum(1 for edge in edges if edge.get("edge_type") == "Job_Skill"),
                "evidence_count": sum(int(edge.get("evidence_count", 0)) for edge in edges),
            },
        }

    @staticmethod
    def _is_job_skill(edge):
        return edge.get("edge_type") == "Job_Skill" or edge.get("relation") in {"requires_skill", "prefers_skill"}

    def _overlay_published(self, payload, profiles):
        """Replace only capability edges, never mutate static files or other relations."""
        active = {title: p for title, p in profiles.items() if p["profile_source"] == "published_dynamic"}
        if not active:
            return payload
        result = copy.deepcopy(payload)
        nodes = {n["id"]: n for n in result["nodes"]}
        for title, profile in active.items():
            job = next((n for n in nodes.values() if n.get("type") == "job" and n["name"] == title), None)
            job_id = job["id"] if job else f"job:published:{profile['profile_id']}"
            if job is None:
                nodes[job_id] = dict(id=job_id, name=title, type="job", formal_type="Job")
            nodes[job_id].update(self.effective_profiles.metadata(profile))
            result["edges"] = [e for e in result["edges"] if not (self._is_job_skill(e) and job_id in {e["source"], e["target"]})]
            seen = set()
            for field, role in (("required_skills", "required"), ("preferred_skills", "preferred")):
                for skill in profile["definition"][field]:
                    sid = skill["skill_id"]
                    if sid in seen:
                        continue
                    seen.add(sid)
                    nodes.setdefault(sid, dict(id=sid, name=self.skill_index.standard_name(sid), type="skill", formal_type="Skill"))
                    ids = list(dict.fromkeys(skill["supporting_job_ids"]))
                    result["edges"].append(dict(id=f"published:{profile['profile_id']}:{sid}", source=job_id, target=sid,
                        edge_type="Job_Skill", relation="requires_skill" if role == "required" else "prefers_skill",
                        job_title=title, skill_name=self.skill_index.standard_name(sid), importance=role,
                        frequency=skill["coverage"], mention_count=skill["evidence_count"],
                        evidence_jd_ids=ids, evidence_count=len(ids),
                        evidence="\n".join(s["text"] for s in skill["evidence_snippets"]),
                        evidence_records=[r for r in profile["publication"]["evidence"] if r["job_id"] in ids],
                        **self.effective_profiles.metadata(profile)))
        result["nodes"] = list(nodes.values())
        result.update(available=True, status="connected", source_label="有效岗位画像（发布优先，其他关系保留静态基线）",
                      notice="岗位—技能关系使用最新人工发布版本；未发布岗位和非能力关系保持原图谱。",
                      profile_versions={title: self.effective_profiles.metadata(p) for title, p in active.items()})
        result["summary"] = dict(result["summary"], node_count=len(nodes), edge_count=len(result["edges"]),
                                 job_skill_edge_count=sum(self._is_job_skill(e) for e in result["edges"]))
        return result

    def load_effective(self):
        publications = self.effective_profiles.published_profiles()
        profiles = {title: self.effective_profiles.get_effective_job_profile(title, publications) for title in publications}
        return self._overlay_published(self.load(), profiles)

    def for_job(self, job_title: str, limit: int | None = None, *, effective_profile=None) -> dict[str, Any]:
        effective = effective_profile or self.effective_profiles.get_effective_job_profile(job_title)
        payload = self._overlay_published(self.load(), {job_title: effective})
        job_node = next((
            node for node in payload.get("nodes", [])
            if node.get("type") == "job" and _text(node.get("name")) == job_title
        ), None)
        job_id = job_node.get("id") if job_node else f"job:{job_title}"
        edges = [
            edge for edge in payload.get("edges", [])
            if edge.get("source") == job_id and (payload.get("source_type") != "formal_json" or edge.get("edge_type") == "Job_Skill")
        ]
        edges.sort(key=lambda item: (-float(item.get("frequency", 0)), str(item.get("target", ""))))
        result = self._filter_payload(payload, edges[:limit] if limit is not None else edges)
        result["job_title"] = job_title
        result.update(self.effective_profiles.metadata(effective))
        if payload.get("available") and not edges:
            result["status"] = "job_not_found"
            result["notice"] = "当前组员A关系表中没有该岗位。"
        return result

    def for_skill(self, skill_id: str) -> dict[str, Any]:
        payload = self.load_effective()
        edges = [
            edge for edge in payload.get("edges", [])
            if edge.get("target") == skill_id and (payload.get("source_type") != "formal_json" or edge.get("edge_type") == "Job_Skill")
        ]
        result = self._filter_payload(payload, edges)
        result["skill_id"] = skill_id
        if payload.get("available") and not edges:
            result["status"] = "skill_not_found"
            result["notice"] = "当前组员A关系表中没有该技能。"
        return result
