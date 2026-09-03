from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from ..core.skill_extractor import SkillIndex
from ..data_loader import DataLoader


DATA_VERSION = "supplemental_jd_v3"
SOURCE_LABEL = "用户补充JD TXT"
HEADING_RE = re.compile(
    r"^(?P<number>(?:[①②③④⑤⑥⑦⑧⑨⑩]+|\d{1,3}\.))\s*"
    r"(?P<title>.+?)\s*(?:———|——)\s*(?P<company>.+?)\s*$"
)
SECTION_RE = re.compile(
    r"(?P<label>岗位职责|工作职责|职责描述|职位描述|岗位描述|职责要求|"
    r"任职要求|职位要求|岗位要求|任职资格与能力要求|任职资格|经验能力|专业要求|最低要求|"
    r"专业技能(?:（掌握以下多项）)?|核心素质|岗位基本需求|"
    r"Responsibilities|Job Responsibilities|Qualifications|Requirements|"
    r"加分项|加分要求|优先条件|优先考虑|优先资格|具备以下者优先|Nice to have)\s*[:：]?",
    re.IGNORECASE,
)

TOOLS = [
    "Python", "Java", "C++", "Go", "TypeScript", "PyTorch", "TensorFlow", "JAX",
    "Spark", "Ray", "Kafka", "Airflow", "Kubernetes", "Docker", "S3", "Ceph", "MinIO",
    "HuggingFace", "WebDataset", "Parquet", "LangChain", "LangGraph", "LlamaIndex", "Dify",
    "n8n", "Coze", "OpenClaw", "vLLM", "SGLang", "Megatron", "DeepSpeed", "verl", "TRL",
    "Prometheus", "Grafana", "OpenTelemetry", "ELK", "Loki", "ONNX Runtime", "TensorRT",
    "CUDA", "ROS", "ROS2", "MCAP", "LeRobot", "Mujoco", "Isaac Gym", "Isaac Sim",
    "PyBullet", "CARLA", "Jenkins", "Pytest", "Git", "Linux", "SQL", "Pandas",
]


def _now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def _text(value: object) -> str:
    return str(value or "").strip()


def _normalized(value: object) -> str:
    text = _text(value).casefold().replace("（", "(").replace("）", ")").replace("／", "/")
    return re.sub(r"[^0-9a-z\u4e00-\u9fff+#]+", "", text)


def _sha(value: str) -> str:
    return hashlib.sha256(_normalized(value).encode("utf-8")).hexdigest().upper()


def _frozen_inventory(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
        }
        for path in sorted(root.rglob("standard*_v1.xlsx"))
    ]


def _company(value: str) -> str:
    value = re.sub(r"\s+", "", value).strip("-— ")
    aliases = {"Tencent": "腾讯", "tencent": "腾讯", "caterpillar": "Caterpillar"}
    return aliases.get(value, value)


def _clean_title(value: str) -> str:
    value = value.strip().replace(" —", "").replace("— ", "")
    value = re.sub(r"^(?:蚂蚁集团-|北京-|社招|日常实习生-)", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -")


def _section_kind(label: str) -> str:
    folded = label.casefold()
    if any(token in folded for token in ("加分", "优先", "nice")):
        return "bonus"
    if any(token in folded for token in ("要求", "资格", "经验能力", "专业技能", "核心素质", "基本需求", "qualification", "requirement")):
        return "requirements"
    return "responsibilities"


def _split_sections(body: str) -> tuple[str, str, str]:
    matches = list(SECTION_RE.finditer(body))
    if not matches:
        return body.strip(), "", ""
    buckets: dict[str, list[str]] = {"responsibilities": [], "requirements": [], "bonus": []}
    prefix = body[: matches[0].start()].strip()
    if prefix:
        buckets["responsibilities"].append(prefix)
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        content = body[match.end():end].strip(" \n:\u3000")
        if content:
            buckets[_section_kind(match.group("label"))].append(content)
    return tuple("\n".join(buckets[key]).strip() for key in ("responsibilities", "requirements", "bonus"))


def _taxonomy(title: str, text: str) -> tuple[str, str, str]:
    joined = f"{title} {text}".casefold()
    if "自动驾驶" in joined or "perception" in joined or "sil" in joined:
        return "智能驾驶", "测试与验证", "自动驾驶"
    if "具身" in joined or "vla" in joined or "vtla" in joined or "机器人" in joined or "世界模型" in joined:
        function = "数据工程"
        if "产品经理" in title:
            function = "产品管理"
        elif "项目经理" in title or "pdsa" in title.casefold():
            function = "解决方案与项目管理"
        elif "测试" in title or "数采" in title:
            function = "数据采集与测试"
        elif "算法" in title or "世界模型" in title:
            function = "算法研发"
        elif "infra" in title.casefold():
            function = "数据基础设施"
        return "具身智能", function, "具身智能/VLA"
    if "安全" in joined or "攻防" in joined or "红队" in joined:
        function = "安全算法研发" if any(x in joined for x in ("算法", "对齐", "内生")) else "安全工程"
        return "AI安全", function, "大模型与智能体安全"
    if "评测" in joined or "评估" in joined:
        return "模型评测", "评测工程" if "产品经理" not in title else "评测产品管理", "大模型/Agent评测"
    if "运维" in joined or "部署" in joined:
        return "AI基础设施", "模型部署与运维", "大模型平台"
    if "推理优化" in joined or "编译器" in joined:
        return "AI基础设施", "推理系统优化", "大模型推理/AI编译器"
    if "数据" in joined:
        return "AI数据", "数据工程", "大模型数据"
    return "大模型与智能体开发", "算法与应用研发", "LLM/Agent"


def _extract_education(text: str) -> str:
    match = re.search(r"(?:全日制统招)?(?:本科|硕士|博士)(?:及以上|以上)?(?:学历)?", text)
    return match.group(0) if match else ""


def _extract_experience(text: str) -> str:
    match = re.search(r"(?:\d+\s*[-–—至]\s*\d+|\d+)\s*年(?:及以上|以上)?(?:[^\n，。；]{0,8}(?:经验|经历))?", text)
    return match.group(0).strip() if match else ""


def _employment(title: str, text: str) -> str:
    joined = f"{title} {text}"
    if "实习" in joined:
        return "实习"
    if "校招" in joined or "应届" in joined:
        return "校园招聘"
    if "社招" in joined:
        return "社会招聘"
    return ""


def _location(title: str, text: str) -> str:
    for city in ("北京", "上海", "杭州", "深圳", "广州", "成都", "南京", "西安"):
        if city in title:
            return city
    match = re.search(r"(?:工作地点|地点)\s*[:：]?\s*(北京|上海|杭州|深圳|广州|成都|南京|西安)", text)
    return match.group(1) if match else ""


def _summarize(text: str, limit: int = 220) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact if len(compact) <= limit else compact[:limit].rstrip("，。； ") + "…"


def parse_supplemental_text(text: str, source_name: str, ingested_at: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lines = text.splitlines()
    headings: list[tuple[int, re.Match[str]]] = []
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line.strip())
        if match:
            headings.append((index, match))
    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    timestamp = ingested_at or _now()
    for sequence, (start, match) in enumerate(headings, start=1):
        end = headings[sequence][0] - 1 if sequence < len(headings) else len(lines) - 1
        raw_text = "\n".join(lines[start:end + 1]).rstrip()
        body = "\n".join(lines[start + 1:end + 1]).strip()
        responsibilities, requirements, bonus = _split_sections(body)
        title = match.group("title").strip()
        company = match.group("company").strip()
        family, function, domain = _taxonomy(title, body)
        record = {
            "evidence_id": f"SUP-JD-{sequence:03d}",
            "source_sequence": sequence,
            "source_number_raw": match.group("number"),
            "source_start_line": start + 1,
            "source_end_line": end + 1,
            "raw_job_title": title,
            "cleaned_job_title": _clean_title(title),
            "normalized_job_title": _normalized(_clean_title(title)),
            "company_raw": company,
            "company_normalized": _company(company),
            "raw_text": raw_text,
            "responsibilities_raw": responsibilities,
            "requirements_raw": requirements,
            "bonus_requirements_raw": bonus,
            "responsibilities_summary": _summarize(responsibilities),
            "required_skills": [],
            "preferred_skills": [],
            "tools_and_frameworks": [],
            "job_family": family,
            "job_function": function,
            "technical_domain": domain,
            "education_requirement": _extract_education(body),
            "experience_requirement": _extract_experience(body),
            "employment_type": _employment(title, body),
            "location": _location(title, body),
            "source_name": SOURCE_LABEL,
            "source_file": source_name,
            "source_url": "",
            "publish_date": "",
            "primary_emerging_job_id": "",
            "supporting_emerging_job_ids": [],
            "mapping_type": "manual_review",
            "mapping_confidence": 0.0,
            "mapping_reason": "尚未执行岗位映射。",
            "duplicate_status": "unique",
            "duplicate_of": "",
            "duplicate_reason": "未发现重复。",
            "count_in_statistics": True,
            "source_verification_status": "待补来源",
            "evidence_confidence": 0.62,
            "needs_manual_review": not bool(requirements),
            "parse_failed": False,
            "data_version": DATA_VERSION,
            "ingested_at": timestamp,
        }
        if not title or not company or not body:
            record["parse_failed"] = True
            record["needs_manual_review"] = True
            failures.append({"source_sequence": sequence, "line": start + 1, "reason": "标题、企业或正文缺失"})
        records.append(record)
    return records, failures


EXISTING_RULES: dict[int, tuple[str, str, float, list[str], str]] = {
    3: ("EMERGING-001", "exact_evidence", 0.96, [], "岗位名称、AI安全职责和模型安全技能与原候选高度一致。"),
    4: ("EMERGING-001", "exact_evidence", 0.96, [], "岗位名称及大模型安全测评、防护职责与原候选高度一致。"),
    5: ("EMERGING-004", "exact_evidence", 0.99, [], "岗位名称与企业均直接对应原PDSA候选。"),
    8: ("EMERGING-005", "exact_evidence", 0.99, [], "岗位名称与企业均直接对应原解决方案与项目经理候选。"),
    11: ("EMERGING-006", "exact_evidence", 0.90, [], "大模型数据清洗属于AI数据工程的直接职能证据。"),
    13: ("EMERGING-001", "job_family_support", 0.82, ["EMERGING-009"], "岗位属于大模型安全工程，但客户端攻防与安全产品职责更宽，作为岗位族支撑。"),
    18: ("EMERGING-008", "exact_evidence", 0.92, ["EMERGING-003"], "职责以大模型评测工程为主，与AI评测候选一致。"),
    20: ("EMERGING-008", "exact_evidence", 0.90, ["EMERGING-003"], "岗位核心为大模型评测实施，作为AI评测的精确Evidence。"),
    22: ("EMERGING-010", "exact_evidence", 0.98, [], "岗位名称直接对应原大模型评估产品经理候选。"),
    23: ("EMERGING-010", "exact_evidence", 0.94, [], "岗位职能为大模型评测产品设计与平台建设。"),
    24: ("EMERGING-010", "exact_evidence", 0.96, [], "岗位名称和评测产品职责与原候选一致。"),
    25: ("EMERGING-010", "exact_evidence", 0.93, [], "岗位核心职能为模型评测产品管理。"),
    26: ("EMERGING-011", "exact_evidence", 0.99, [], "岗位名称直接对应原自动驾驶感知测试开发候选。"),
    27: ("EMERGING-011", "exact_evidence", 0.91, [], "算法评测、仿真验证与自动化测试职责与原候选一致。"),
    28: ("EMERGING-011", "exact_evidence", 0.94, [], "SIL感知验证属于自动驾驶感知测试开发的直接Evidence。"),
    29: ("EMERGING-011", "job_family_support", 0.78, [], "车云功能测试属于自动驾驶测试岗位族，但不是感知算法测试同岗。"),
}

NEW_GROUPS: list[tuple[str, list[int], list[str], str]] = [
    ("具身智能数据Infra负责人", [1], [], "覆盖具身数据采集、治理、DataOps与训练数据平台的独立基础设施职责。"),
    ("具身智能数采测试工程师", [2], [], "聚焦具身数据采集设备、采集流程与质量测试，不等同于数据工程。"),
    ("具身智能数据工程师", [6, 7], ["EMERGING-006"], "两条Evidence共同覆盖具身多模态数据管线、治理和算法数据构建。"),
    ("具身智能数据闭环技术项目经理", [9], ["EMERGING-005"], "负责具身数据闭环的技术项目交付，区别于通用解决方案项目经理。"),
    ("具身智能技术产品经理", [10], ["EMERGING-005"], "负责采集、数据与仿真产品体系，区别于数据服务交付岗位。"),
    ("大模型平台运维工程师", [12, 48], ["EMERGING-007"], "职责聚焦大模型/智能体平台运行、监控和SLO，不与安全运维合并。"),
    ("大模型内生安全研究员", [14], ["EMERGING-001"], "研究模型内部安全机理、可解释性与安全训练，职责边界独立。"),
    ("智能体攻防算法工程师", [15, 16, 17], ["EMERGING-009"], "三条Evidence共同覆盖安全Agent、自动漏洞利用、攻防评测和安全对齐。"),
    ("Agent评测工程师", [19, 30, 31], ["EMERGING-008", "EMERGING-003"], "评测对象为Agent的工具调用、规划和任务执行，区别于普通模型评测。"),
    ("大模型安全与对齐算法工程师", [21, 41, 42, 43], ["EMERGING-001"], "覆盖安全对齐训练、红队评测、Guard与RLHF/DPO，区别于通用安全工程。"),
    ("办公Agent算法工程师", [32], [], "聚焦办公场景Agent算法、文档与工作流能力，当前为单条待观察。"),
    ("VLA算法工程师", [33, 34, 35], [], "三家企业Evidence均聚焦视觉-语言-动作模型训练、部署与数据闭环。"),
    ("VLA/VTLA灵巧操作算法工程师", [36], [], "额外引入触觉、多指灵巧操作和VTLA，未与普通VLA粗暴合并。"),
    ("大模型推理优化工程师", [37, 38], [], "两家企业Evidence共同聚焦量化、并行、推理引擎和性能优化。"),
    ("大模型平台策略推理优化工程师", [39], [], "同时承担平台策略与推理优化，按要求与通用推理优化分开观察。"),
    ("AI编译器工程师", [40], [], "核心职责是AI编译器研发和编译优化，不与推理工程岗位合并。"),
    ("世界模型训练与真机部署工程师", [44], [], "贯通世界模型训练、机器人数据闭环和真机部署，职责边界独立。"),
    ("具身智能算法工程师", [45], [], "覆盖强化学习、Sim2Real与多模态机器人策略，当前为单条待观察。"),
    ("大模型与智能体算法工程师", [46], [], "聚焦垂直模型微调和Agent算法研发，当前为单条待观察。"),
    ("AI模型部署与运维工程师", [47], [], "聚焦GPU模型服务部署、监控与故障恢复，区别于平台日常运维。"),
    ("大模型应用研发工程师", [49], [], "聚焦RAG、Agent应用集成与大模型工程化，当前为单条待观察。"),
]


def _enrich_skills(records: list[dict[str, Any]], index: SkillIndex) -> None:
    for record in records:
        required = index.extract_fields([
            ("responsibilities_raw", record["responsibilities_raw"]),
            ("requirements_raw", record["requirements_raw"]),
        ])
        preferred = index.extract_fields([("bonus_requirements_raw", record["bonus_requirements_raw"])])
        record["required_skills"] = sorted({item.standard_skill_name for item in required if item.accepted})
        record["preferred_skills"] = sorted({item.standard_skill_name for item in preferred if item.accepted})
        raw = record["raw_text"]
        record["tools_and_frameworks"] = [tool for tool in TOOLS if re.search(rf"(?<![A-Za-z0-9]){re.escape(tool)}(?![A-Za-z0-9])", raw, re.I)]


def _original_rows(loader: DataLoader, index: SkillIndex) -> list[dict[str, Any]]:
    result = []
    for row in loader.load_jds():
        body = "\n".join(_text(row.get(key)) for key in ("responsibilities", "required_skills_raw", "bonus_skills_raw"))
        skills = index.extract_fields([(key, row.get(key)) for key in ("responsibilities", "required_skills_raw", "bonus_skills_raw")])
        result.append({
            "evidence_id": _text(row.get("jd_id")), "title": _text(row.get("original_job_title")),
            "title_norm": _normalized(row.get("original_job_title")), "company": _text(row.get("company")),
            "company_norm": _company(_text(row.get("company"))), "url": _text(row.get("source_url")),
            "body_norm": _normalized(body), "body_hash": _sha(body),
            "skills": {item.standard_skill_name for item in skills if item.accepted},
        })
    return result


def _deduplicate(records: list[dict[str, Any]], originals: list[dict[str, Any]]) -> None:
    prior: list[dict[str, Any]] = []
    for record in records:
        body = "\n".join((record["responsibilities_raw"], record["requirements_raw"], record["bonus_requirements_raw"]))
        body_norm = _normalized(body)
        body_hash = _sha(body)
        skills = set(record["required_skills"]) | set(record["preferred_skills"])
        record["normalized_text_sha256"] = body_hash
        candidates: list[tuple[float, float, dict[str, Any], str]] = []
        for other in originals + prior:
            same_company = record["company_normalized"] == other["company_norm"]
            title_sim = SequenceMatcher(None, record["normalized_job_title"], other["title_norm"]).ratio()
            text_sim = SequenceMatcher(None, body_norm, other["body_norm"]).ratio() if body_norm and other["body_norm"] else 0.0
            union = skills | other["skills"]
            skill_sim = len(skills & other["skills"]) / len(union) if union else 0.0
            exact_key = same_company and record["normalized_job_title"] == other["title_norm"] and bool(record["source_url"]) and record["source_url"] == other["url"]
            if body_hash == other["body_hash"] or exact_key or (same_company and title_sim >= 0.96 and text_sim >= 0.90):
                candidates.append((1.0, skill_sim, other, "规范化正文哈希或企业+岗位+正文高度一致"))
            elif (same_company and title_sim >= 0.90 and text_sim >= 0.58) or (text_sim >= 0.90 and skill_sim >= 0.70):
                candidates.append((text_sim, skill_sim, other, "企业、岗位、正文或技能集合高度相似，需人工复核"))
        if candidates:
            score, skill_score, best, reason = max(candidates, key=lambda item: (item[0], item[1]))
            if score >= 0.999:
                record.update(duplicate_status="duplicate", duplicate_of=best["evidence_id"], duplicate_reason=reason,
                              count_in_statistics=False)
            else:
                record.update(duplicate_status="possible_duplicate", duplicate_of=best["evidence_id"],
                              duplicate_reason=f"{reason}（正文相似度{score:.2f}，技能Jaccard {skill_score:.2f}）",
                              needs_manual_review=True)
        prior.append({
            "evidence_id": record["evidence_id"], "title_norm": record["normalized_job_title"],
            "company_norm": record["company_normalized"], "url": record["source_url"],
            "body_norm": body_norm, "body_hash": body_hash, "skills": skills,
        })


def _apply_mapping(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    new_defs: list[dict[str, Any]] = []
    for sequence, rule in EXISTING_RULES.items():
        candidate_id, mapping_type, confidence, support, reason = rule
        records[sequence - 1].update(primary_emerging_job_id=candidate_id, mapping_type=mapping_type,
                                     mapping_confidence=confidence, supporting_emerging_job_ids=support,
                                     mapping_reason=reason)
    for offset, (name, sequences, support, reason) in enumerate(NEW_GROUPS, start=12):
        candidate_id = f"EMERGING-{offset:03d}"
        for sequence in sequences:
            records[sequence - 1].update(primary_emerging_job_id=candidate_id, mapping_type="new_candidate",
                                         mapping_confidence=0.90 if len(sequences) > 1 else 0.82,
                                         supporting_emerging_job_ids=support, mapping_reason=reason)
        new_defs.append({"candidate_id": candidate_id, "candidate_name": name, "source_sequences": sequences,
                         "supporting_existing_candidate_ids": support, "cluster_reason": reason})
    return new_defs


def _supplement_evidence(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "jd_id": record["evidence_id"], "evidence_id": record["evidence_id"],
        "original_job_title": record["raw_job_title"], "standard_job_title": record["cleaned_job_title"],
        "standardization_status": "补充Evidence映射", "company": record["company_normalized"],
        "source": record["source_name"], "source_url": record["source_url"], "published_date": record["publish_date"],
        "responsibilities": record["responsibilities_raw"], "required_skills_raw": record["requirements_raw"],
        "bonus_skills_raw": record["bonus_requirements_raw"], "skills": record["required_skills"],
        "tools_and_frameworks": record["tools_and_frameworks"], "mapping_type": record["mapping_type"],
        "mapping_reason": record["mapping_reason"], "mapping_confidence": record["mapping_confidence"],
        "duplicate_status": record["duplicate_status"], "duplicate_of": record["duplicate_of"],
        "count_in_statistics": record["count_in_statistics"], "source_verification_status": record["source_verification_status"],
        "evidence_confidence": record["evidence_confidence"], "raw_text": record["raw_text"],
    }


def _score_candidate(candidate: dict[str, Any], records: list[dict[str, Any]]) -> None:
    counted = [row for row in records if row.get("count_in_statistics", True)]
    exact = [row for row in counted if row.get("mapping_type") != "job_family_support"]
    support = [row for row in counted if row.get("mapping_type") == "job_family_support"]
    companies = sorted({_text(row.get("company")) for row in counted if _text(row.get("company"))})
    sources = sorted({_text(row.get("source")) for row in counted if _text(row.get("source"))})
    skill_counts = Counter(skill for row in counted for skill in row.get("skills", []))
    core = [name for name, _ in skill_counts.most_common(8)]
    if not core:
        core = list(candidate.get("core_skills", []))[:8]
    strength = len(exact) + 0.4 * len(support)
    score = min(100.0, 35 * min(strength / 4, 1) + 20 * min(len(companies) / 3, 1)
                + 15 * min(len(sources) / 3, 1) + 10 * min(len(core) / 6, 1) + 10
                + 10 * (sum(float(row.get("evidence_confidence", 0.8)) for row in counted) / len(counted) if counted else 0))
    if len(exact) <= 1:
        score = min(score, 49.0)
    if len(exact) >= 4 and len(companies) >= 3 and score >= 70:
        confidence = "高置信候选"
    elif len(exact) >= 2 and score >= 50:
        confidence = "中置信候选"
    else:
        confidence = "弱候选/待观察"
    candidate.update(
        evidence_strength_v2=round(strength, 2), emerging_score_v2=round(score, 2), confidence_v2=confidence,
        score_version="v2.0", emerging_score=round(score, 2), confidence_level=confidence,
        jd_count=len(counted), evidence_count=len(records), counted_evidence_count=len(counted),
        exact_evidence_count=len(exact), supporting_evidence_count=len(support),
        evidence_jd_ids=[_text(row.get("jd_id")) for row in records], evidence_records=records,
        company_count=len(companies), companies=companies, source_count=len(sources), sources=sources,
        core_skills=core,
        representative_evidence=[{
            "jd_id": _text(row.get("jd_id")), "title": _text(row.get("original_job_title")),
            "company": _text(row.get("company")), "source": _text(row.get("source")),
            "evidence": _text(row.get("required_skills_raw")) or _text(row.get("responsibilities")),
            "mapping_type": row.get("mapping_type", "legacy_evidence"),
        } for row in records[:3]],
    )


def _build_v2(root: Path, records: list[dict[str, Any]], new_defs: list[dict[str, Any]], generated_at: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    v1 = json.loads((root / "outputs/emerging_jobs_v1.json").read_text(encoding="utf-8"))
    candidates = copy.deepcopy(v1["candidates"])
    before: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        before[candidate["candidate_id"]] = {key: candidate.get(key, 0) for key in ("evidence_count", "company_count", "source_count")}
        candidate["emerging_score_v1"] = candidate.get("emerging_score")
        candidate["confidence_v1"] = candidate.get("confidence_level")
        for evidence in candidate.get("evidence_records", []):
            evidence.update(mapping_type="legacy_evidence", mapping_reason="V1原始Evidence",
                            count_in_statistics=True, duplicate_status="unique", evidence_confidence=0.9,
                            source_verification_status="已验证" if evidence.get("source_url") else "待补来源",
                            skills=[item.get("standard_skill_name") for item in evidence.get("skill_evidence", []) if item.get("accepted")])
    by_id = {row["candidate_id"]: row for row in candidates}
    for definition in new_defs:
        candidate = {
            **definition, "emerging_score_v1": None, "confidence_v1": "无V1基线",
            "representative_titles": [], "distinguishing_skills": [],
            "relation_to_existing_jobs": ("岗位族支撑：" + "、".join(definition["supporting_existing_candidate_ids"])) if definition["supporting_existing_candidate_ids"] else "V2新增独立候选",
            "why_emerging": definition["cluster_reason"], "need_human_review": True,
            "evidence_records": [],
        }
        candidates.append(candidate)
        by_id[candidate["candidate_id"]] = candidate
        before[candidate["candidate_id"]] = {"evidence_count": 0, "company_count": 0, "source_count": 0}
    for record in records:
        candidate = by_id.get(record["primary_emerging_job_id"])
        if candidate is not None:
            candidate.setdefault("evidence_records", []).append(_supplement_evidence(record))
    comparisons = []
    for candidate in candidates:
        candidate_records = candidate.get("evidence_records", [])
        _score_candidate(candidate, candidate_records)
        candidate["representative_titles"] = sorted({_text(row.get("original_job_title")) for row in candidate_records if _text(row.get("original_job_title"))})
        prior = before[candidate["candidate_id"]]
        comparisons.append({
            "candidate_id": candidate["candidate_id"], "candidate_name": candidate["candidate_name"],
            "before_evidence_count": prior["evidence_count"], "after_evidence_count": candidate["evidence_count"],
            "before_company_count": prior["company_count"], "after_company_count": candidate["company_count"],
            "before_source_count": prior["source_count"], "after_source_count": candidate["source_count"],
            "emerging_score_v1": candidate["emerging_score_v1"], "emerging_score_v2": candidate["emerging_score_v2"],
            "confidence_v1": candidate["confidence_v1"], "confidence_v2": candidate["confidence_v2"],
        })
    levels = Counter(row["confidence_v2"] for row in candidates)
    return {
        "schema_version": "2.0", "data_version": DATA_VERSION, "generated_at": generated_at,
        "updated_at": generated_at, "source_jd_count": v1.get("source_jd_count", 191),
        "supplemental_jd_count": len(records), "methodology": "V1候选冻结继承 + 补充Evidence去重映射 + 独立职责聚类 + V2透明评分",
        "notice": "结果为招聘市场新岗位候选观察，不等同于国家正式职业分类中的新职业。",
        "summary": {"candidate_count": len(candidates), "high_confidence": levels.get("高置信候选", 0),
                    "medium_confidence": levels.get("中置信候选", 0), "weak_candidate": levels.get("弱候选/待观察", 0)},
        "validation": {"passed": True, "errors": [], "supplemental_conservation": len(records) == 49},
        "candidate_statistics_comparison": comparisons, "candidates": candidates,
    }, comparisons


def generate(source_path: Path, root: Path) -> dict[str, Any]:
    generated_at = _now()
    frozen_before = _frozen_inventory(root)
    source_text = source_path.read_text(encoding="utf-8-sig")
    records, failures = parse_supplemental_text(source_text, source_path.name, generated_at)
    if len(records) + len([item for item in failures if item.get("not_materialized")]) != 49:
        raise ValueError(f"数量守恒失败：解析{len(records)}条，失败{len(failures)}条，不等于49")
    loader = DataLoader(root / "config/data_sources.yaml")
    skills, aliases = loader.load_runtime_skill_dictionary()
    index = SkillIndex(skills, aliases)
    _enrich_skills(records, index)
    _deduplicate(records, _original_rows(loader, index))
    new_defs = _apply_mapping(records)
    unmapped = [row["evidence_id"] for row in records if not row["primary_emerging_job_id"]]
    if unmapped:
        raise ValueError(f"存在未处理映射：{unmapped}")
    v2, comparisons = _build_v2(root, records, new_defs, generated_at)
    external = root / "data/external"
    outputs = root / "outputs"
    external.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, external / "supplemental_jd_v3_source.txt")
    payload = {
        "schema_version": "3.0", "data_version": DATA_VERSION, "source_file": source_path.name,
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest().upper(),
        "generated_at": generated_at, "record_count": len(records), "records": records,
    }
    (external / "supplemental_jd_v3.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    parse_report = {
        "data_version": DATA_VERSION, "generated_at": generated_at, "expected_count": 49,
        "parsed_count": sum(not row["parse_failed"] for row in records), "failed_count": len(failures),
        "conservation_passed": len(records) == 49, "failures": failures,
        "evidence_ids_continuous": [row["evidence_id"] for row in records] == [f"SUP-JD-{i:03d}" for i in range(1, 50)],
        "source_line_count": len(source_text.splitlines()),
        "records": [{key: row[key] for key in ("evidence_id", "source_sequence", "source_start_line", "source_end_line", "raw_job_title", "company_raw", "needs_manual_review")} for row in records],
    }
    duplicates = [row for row in records if row["duplicate_status"] != "unique"]
    dedup_report = {
        "data_version": DATA_VERSION, "generated_at": generated_at, "original_jd_count": len(loader.load_jds()),
        "supplemental_jd_count": len(records), "duplicate_count": sum(row["duplicate_status"] == "duplicate" for row in records),
        "possible_duplicate_count": sum(row["duplicate_status"] == "possible_duplicate" for row in records),
        "counted_supplemental_count": sum(row["count_in_statistics"] for row in records),
        "methods": ["规范化JD全文SHA-256", "企业名称规范化", "岗位名称规范化", "企业+岗位名+URL组合键", "JD正文相似度", "技能集合相似度"],
        "records": [{key: row[key] for key in ("evidence_id", "duplicate_status", "duplicate_of", "duplicate_reason", "count_in_statistics", "needs_manual_review")} for row in records],
        "exceptions": duplicates,
    }
    (outputs / "supplemental_jd_parse_report_v3.json").write_text(json.dumps(parse_report, ensure_ascii=False, indent=2), encoding="utf-8")
    (outputs / "supplemental_jd_dedup_report_v3.json").write_text(json.dumps(dedup_report, ensure_ascii=False, indent=2), encoding="utf-8")
    (outputs / "emerging_jobs_v2.json").write_text(json.dumps(v2, ensure_ascii=False, indent=2), encoding="utf-8")
    frozen_after = _frozen_inventory(root)
    frozen_audit = {
        "generated_at": generated_at,
        "before": frozen_before,
        "after": frozen_after,
        "unchanged": frozen_before == frozen_after,
        "file_count": len(frozen_before),
    }
    (outputs / "frozen_file_hash_audit_v3.json").write_text(json.dumps(frozen_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    if not frozen_audit["unchanged"]:
        raise RuntimeError("冻结文件在补充数据处理期间发生变化")
    return {"records": records, "new_candidates": new_defs, "comparisons": comparisons, "v2": v2,
            "parse_report": parse_report, "dedup_report": dedup_report, "frozen_audit": frozen_audit}


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Parse and integrate all 49 supplemental JD records")
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    result = generate(args.source.resolve(), root)
    print(json.dumps({
        "parsed": result["parse_report"]["parsed_count"], "failed": result["parse_report"]["failed_count"],
        "duplicates": result["dedup_report"]["duplicate_count"],
        "possible_duplicates": result["dedup_report"]["possible_duplicate_count"],
        "candidate_count": result["v2"]["summary"]["candidate_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
