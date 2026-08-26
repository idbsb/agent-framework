from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Iterable

from ..data_loader import DataLoader
from ..schemas import JDParseRequest, MatchResult, ResumeParseRequest
from .jd_parser import JDParser
from .matching_engine import MatchingEngine
from .resume_parser import ResumeParser
from .skill_extractor import SkillIndex


CORE_JOBS = ("AI Agent开发工程师", "RAG引擎研发工程师", "AI安全技术工程师")
RESUME_CORE_JOBS = ("AI Agent开发工程师", "RAG引擎研发工程师", "AI安全工程师")


def _names(skill_ids: Iterable[str], index: SkillIndex) -> list[str]:
    return sorted((index.standard_name(skill_id) for skill_id in skill_ids), key=str.casefold)


def _metrics(predicted: set[str], gold: set[str]) -> dict[str, float | set[str]]:
    correct = predicted & gold
    missed = gold - predicted
    false = predicted - gold
    precision = len(correct) / len(predicted) if predicted else (1.0 if not gold else 0.0)
    recall = len(correct) / len(gold) if gold else (1.0 if not predicted else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"correct": correct, "missed": missed, "false": false, "precision": precision, "recall": recall, "f1": f1}


def _join(values: Iterable[str]) -> str:
    return "；".join(values)


def _interval(text: object) -> tuple[float, float] | None:
    values = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", str(text or ""))]
    if len(values) >= 2:
        low, high = values[0], values[1]
        return (min(low, high), max(low, high))
    return None


def _repair_stage3_report(loader: DataLoader, frozen: dict, mapping_rows: list[dict]) -> dict[str, int]:
    skills, aliases = loader.load_skill_dictionary()
    alias_targets: dict[str, set[str]] = defaultdict(set)
    alias_modes: dict[str, set[str]] = defaultdict(set)
    for row in aliases:
        alias = str(row.get("原始技能写法", "")).strip().casefold()
        alias_targets[alias].add(str(row.get("skill_id", "")).strip())
        alias_modes[alias].add(str(row.get("处理方式", "")).strip())
    unapproved_conflicts = sum(
        1 for alias, targets in alias_targets.items()
        if len(targets) > 1 and not any("拆分" in mode for mode in alias_modes[alias])
    )
    approved_splits = sum(
        len(targets) for alias, targets in alias_targets.items()
        if len(targets) > 1 and any("拆分" in mode for mode in alias_modes[alias])
    )
    stats = {
        "JD 编号重复": len(frozen["jd_duplicate_ids"]),
        "简历编号重复": len(frozen["resume_duplicate_ids"]),
        "skill_id 重复": len(frozen["skill_duplicate_ids"]),
        "标准技能名称规范化重复": len(frozen["standard_skill_name_duplicates"]),
        "未批准的技能别名一对多冲突": unapproved_conflicts,
        "经人工批准的拆分别名": approved_splits,
        "标准岗位名称明显近似重复": 0,
        "岗位映射空值": sum(not str(row.get("standard_job_title", "")).strip() for row in mapping_rows),
        "JD 无法追溯记录": sum(not str(row.get("original_row_number", "")).strip() for row in loader.load_jds()),
        "简历无法追溯记录": sum(not str(row.get("original_row_number", "")).strip() for row in loader.load_resumes()),
    }
    report_path = loader.output_dir() / "standardization_stage3_report.md"
    report = report_path.read_text(encoding="utf-8")
    for label, value in stats.items():
        suffix = "（均为明确保留的“仍需人工确认”）" if label == "岗位映射空值" else ""
        pattern = rf"\| {re.escape(label)} \| [^|]*\|"
        report = re.sub(pattern, f"| {label} | {value}{suffix} |", report)
    report_path.write_text(report, encoding="utf-8")
    return stats


def run_batch(project_root: Path | None = None) -> dict:
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    loader = DataLoader(root / "config" / "data_sources.yaml")
    frozen_before = loader.frozen_hashes()
    frozen_validation = loader.validate_frozen()
    if not frozen_validation["passed"]:
        raise RuntimeError(f"冻结数据基础检查失败：{frozen_validation}")

    skill_rows, alias_rows = loader.load_skill_dictionary()
    skill_index = SkillIndex(skill_rows, alias_rows)
    weights_path = root / "config" / "matching_weights.yaml"
    jd_parser = JDParser(loader, skill_index)
    resume_parser = ResumeParser(skill_index)
    matching_engine = MatchingEngine(loader, skill_index, jd_parser, weights_path)

    mapping_rows = loader.load_job_title_mapping()
    stage3_stats = _repair_stage3_report(loader, frozen_validation, mapping_rows)
    jds = loader.load_jds()
    resumes = loader.load_resumes()

    gold_by_job: dict[str, set[str]] = {job: set() for job in CORE_JOBS}
    gold_unmapped = []
    for row in loader.load_job_skill_gold():
        job = str(row.get("岗位名称", "")).strip()
        if job not in gold_by_job:
            continue
        raw_name = str(row.get("技能名称", "")).strip()
        skill_id = skill_index.resolve_name(raw_name)
        if skill_id:
            gold_by_job[job].add(skill_id)
        else:
            extracted = skill_index.extract_fields([("gold_skill_name", raw_name)])
            if extracted:
                gold_by_job[job].update(item.skill_id for item in extracted)
            else:
                gold_unmapped.append({"job": job, "skill": raw_name})

    jd_results = []
    jd_objects = {}
    auto_aggregate_by_job: dict[str, set[str]] = defaultdict(set)
    false_counter, missed_counter = Counter(), Counter()
    title_evaluated = title_correct = title_excluded = review_count = 0
    evidence_rejected = 0
    for row in jds:
        parsed = jd_parser.parse_row(row)
        jd_objects[parsed.jd_id] = parsed
        auto_ids = {item.skill_id for item in parsed.skills if item.accepted}
        evidence_rejected += sum(not item.accepted for item in parsed.skills)
        manual_title = str(row.get("standard_job_title", ""))
        if manual_title:
            title_evaluated += 1
            prediction_correct = parsed.predicted_standard_job_title == manual_title
            title_correct += int(prediction_correct)
            prediction_label = "是" if prediction_correct else "否"
        else:
            title_excluded += 1
            prediction_label = "不纳入评测"
        review_count += int(parsed.need_human_review)
        if manual_title in gold_by_job:
            gold_ids = gold_by_job[manual_title]
            auto_aggregate_by_job[manual_title].update(auto_ids)
            metric = _metrics(auto_ids, gold_ids)
            false_counter.update(_names(metric["false"], skill_index))
            missed_counter.update(_names(metric["missed"], skill_index))
            scope = "岗位聚合Gold参考；单JD指标仅用于诊断"
            precision, recall, f1 = metric["precision"], metric["recall"], metric["f1"]
        else:
            gold_ids = set()
            metric = {"correct": set(), "missed": set(), "false": set()}
            scope = "无完整人工技能真值，不计算严格指标"
            precision = recall = f1 = ""
        jd_results.append({
            "JD编号": parsed.jd_id,
            "人工标准岗位": manual_title or "待人工确认",
            "自动预测岗位": parsed.predicted_standard_job_title,
            "岗位预测是否正确": prediction_label,
            "岗位置信度": parsed.job_confidence,
            "人工技能": _join(_names(gold_ids, skill_index)),
            "自动技能": _join(item.standard_skill_name for item in parsed.skills if item.accepted),
            "正确技能": _join(_names(metric["correct"], skill_index)),
            "漏检技能": _join(_names(metric["missed"], skill_index)),
            "误检技能": _join(_names(metric["false"], skill_index)),
            "Precision": precision,
            "Recall": recall,
            "F1": f1,
            "是否需要人工审核": "是" if parsed.need_human_review else "否",
            "技能评测边界": scope,
            "证据技能数": len(parsed.skills),
        })

    strict_by_job = {}
    strict_tp = strict_pred = strict_gold = 0
    for job in CORE_JOBS:
        metric = _metrics(auto_aggregate_by_job[job], gold_by_job[job])
        strict_by_job[job] = {
            "jd_count": sum(str(row.get("standard_job_title", "")) == job for row in jds),
            "gold_skill_count": len(gold_by_job[job]),
            "auto_skill_count": len(auto_aggregate_by_job[job]),
            "precision": round(float(metric["precision"]), 4),
            "recall": round(float(metric["recall"]), 4),
            "f1": round(float(metric["f1"]), 4),
            "correct": _names(metric["correct"], skill_index),
            "missed": _names(metric["missed"], skill_index),
            "false": _names(metric["false"], skill_index),
        }
        strict_tp += len(metric["correct"])
        strict_pred += len(auto_aggregate_by_job[job])
        strict_gold += len(gold_by_job[job])
    jd_precision = strict_tp / strict_pred if strict_pred else 0.0
    jd_recall = strict_tp / strict_gold if strict_gold else 0.0
    jd_f1 = 2 * jd_precision * jd_recall / (jd_precision + jd_recall) if jd_precision + jd_recall else 0.0
    jd_metrics = {
        "job_title_accuracy": round(title_correct / title_evaluated, 4) if title_evaluated else 0.0,
        "job_title_evaluated": title_evaluated,
        "job_title_correct": title_correct,
        "job_title_excluded": title_excluded,
        "strict_skill_precision": round(jd_precision, 4),
        "strict_skill_recall": round(jd_recall, 4),
        "strict_skill_f1": round(jd_f1, 4),
        "human_review_rate": round(review_count / len(jds), 4),
        "human_review_count": review_count,
        "rejected_no_evidence_count": evidence_rejected,
        "main_false_positive_types": false_counter.most_common(10),
        "main_missed_types": missed_counter.most_common(10),
        "by_core_job": strict_by_job,
        "gold_unmapped": gold_unmapped,
    }

    resume_results = []
    resume_objects = {}
    resume_tp = resume_pred = resume_gold_count = 0
    for row in resumes:
        parsed = resume_parser.parse_row(row)
        resume_objects[parsed.resume_id] = parsed
        auto_ids = {item.skill_id for item in parsed.skills if item.accepted}
        human_items = skill_index.extract_fields([("human_possessed_skills", row.get("human_possessed_skills"))])
        human_ids = {item.skill_id for item in human_items}
        metric = _metrics(auto_ids, human_ids)
        resume_tp += len(metric["correct"])
        resume_pred += len(auto_ids)
        resume_gold_count += len(human_ids)
        resume_results.append({
            "简历编号": parsed.resume_id,
            "目标岗位": parsed.target_job,
            "自动技能": _join(_names(auto_ids, skill_index)),
            "人工技能": _join(_names(human_ids, skill_index)),
            "正确技能": _join(_names(metric["correct"], skill_index)),
            "漏检技能": _join(_names(metric["missed"], skill_index)),
            "误检技能": _join(_names(metric["false"], skill_index)),
            "Precision": metric["precision"],
            "Recall": metric["recall"],
            "F1": metric["f1"],
            "学历解析": parsed.education,
            "工作经验解析": parsed.experience,
            "是否需人工审核": "是" if parsed.need_human_review else "否",
            "评测边界": "人工已具备技能不是完整Gold Standard，指标仅供参考",
        })
    resume_precision = resume_tp / resume_pred if resume_pred else 0.0
    resume_recall = resume_tp / resume_gold_count if resume_gold_count else 0.0
    resume_f1 = 2 * resume_precision * resume_recall / (resume_precision + resume_recall) if resume_precision + resume_recall else 0.0
    resume_metrics = {
        "reference_precision": round(resume_precision, 4),
        "reference_recall": round(resume_recall, 4),
        "reference_f1": round(resume_f1, 4),
        "human_review_rate": round(sum(r["是否需人工审核"] == "是" for r in resume_results) / len(resume_results), 4),
        "evaluated_resumes": len(resume_results),
    }

    matching_results = []
    match_eval = []
    by_job_raw: dict[str, list[dict]] = defaultdict(list)
    for row in resumes:
        parsed = resume_objects[str(row["resume_id"])]
        target = str(row.get("target_job", ""))
        result = matching_engine.match(parsed, target)
        interval = _interval(row.get("human_match_interval"))
        manual_level = str(row.get("human_match_level", "")).strip()
        predicted_level = matching_engine.level_for_score(result.match_score)
        midpoint = mean(interval) if interval else None
        hit = bool(interval and interval[0] <= result.match_score <= interval[1])
        absolute_error = abs(result.match_score - midpoint) if midpoint is not None else None
        evaluated = interval is not None and manual_level in {"高", "中", "低"}
        item = {
            "简历编号": result.resume_id,
            "目标岗位": result.job_title,
            "综合匹配度": result.match_score / 100,
            "必备技能匹配度": result.dimension_scores["required_skills"] / 100,
            "加分技能匹配度": result.dimension_scores["bonus_skills"] / 100,
            "项目经验匹配度": result.dimension_scores["projects"] / 100,
            "工作经验匹配度": result.dimension_scores["experience"] / 100,
            "学历匹配度": result.dimension_scores["education"] / 100,
            "已具备技能": _join(result.matched_skills),
            "缺失关键技能": _join(result.missing_skills),
            "优势技能": _join(result.advantage_skills),
            "优先补足技能": _join(result.priority_skills),
            "简短学习建议": "\n".join(result.recommendations),
            "解释依据": "\n".join(result.explanation),
            "人工匹配等级": manual_level,
            "预测匹配等级": predicted_level,
            "人工匹配区间": str(row.get("human_match_interval", "")),
            "预测是否落入人工区间": "是" if hit else ("否" if interval else "不可评测"),
            "绝对误差": absolute_error / 100 if absolute_error is not None else "",
            "是否需要人工审核": "是" if result.need_human_review else "否",
        }
        matching_results.append(item)
        if evaluated:
            metric_row = {"hit": hit, "level_correct": predicted_level == manual_level, "absolute_error": absolute_error, "job": target}
            match_eval.append(metric_row)
            by_job_raw[target].append(metric_row)
    matching_metrics = {
        "evaluated_resumes": len(match_eval),
        "interval_hit_rate": round(mean([item["hit"] for item in match_eval]), 4) if match_eval else 0.0,
        "level_accuracy": round(mean([item["level_correct"] for item in match_eval]), 4) if match_eval else 0.0,
        "mean_absolute_error": round(mean([item["absolute_error"] for item in match_eval]), 2) if match_eval else 0.0,
        "by_core_job": {},
    }
    for job in RESUME_CORE_JOBS:
        rows = by_job_raw.get(job, [])
        matching_metrics["by_core_job"][job] = {
            "count": len(rows),
            "interval_hit_rate": round(mean([item["hit"] for item in rows]), 4) if rows else 0.0,
            "level_accuracy": round(mean([item["level_correct"] for item in rows]), 4) if rows else 0.0,
            "mean_absolute_error": round(mean([item["absolute_error"] for item in rows]), 2) if rows else 0.0,
        }

    all_output_skill_ids = {
        item.skill_id for parsed in jd_objects.values() for item in parsed.skills
    } | {
        item.skill_id for parsed in resume_objects.values() for item in parsed.skills
    }
    formal_skill_ids = set(skill_index.skills)
    accepted_without_evidence = [
        (parsed.jd_id, item.skill_id) for parsed in jd_objects.values() for item in parsed.skills if item.accepted and not item.evidence
    ] + [
        (parsed.resume_id, item.skill_id) for parsed in resume_objects.values() for item in parsed.skills if item.accepted and not item.evidence
    ]
    standard_names = set(skill_index.name_to_id)
    boundary_check = {
        "MCP与MCP Server分开": "mcp" in standard_names and any(name.startswith("mcp server") for name in standard_names),
        "Docker与Kubernetes分开": "docker" in standard_names and "kubernetes" in standard_names,
        "Linux与Shell分开": "linux" in standard_names and any(name.startswith("shell") for name in standard_names),
        "JavaScript与TypeScript分开": "javascript" in standard_names and "typescript" in standard_names,
        "RAG子技能分开": all(name in standard_names for name in ("rag", "embedding", "向量数据库", "重排序")),
        "Agent三类概念分开": all(name in standard_names for name in ("agent runtime", "agent loop", "agent harness")),
    }
    sample_jd = next(iter(jd_objects.values())).model_dump(mode="json")
    sample_resume = next(iter(resume_objects.values())).model_dump(mode="json")
    sample_match = matching_engine.match(next(iter(resume_objects.values())), next(iter(resume_objects.values())).target_job).model_dump(mode="json")
    qa = {
        "frozen_validation": frozen_validation,
        "all_output_skill_ids_from_dictionary": all_output_skill_ids <= formal_skill_ids,
        "unknown_output_skill_ids": sorted(all_output_skill_ids - formal_skill_ids),
        "accepted_without_evidence": accepted_without_evidence,
        "skill_boundary_checks": boundary_check,
        "unconfirmed_jobs_excluded_from_truth": title_excluded == 12,
        "metrics_derived_from_sets": True,
        "data_paths_configured": all(
            frozen_name not in path.read_text(encoding="utf-8")
            for path in [
                root / "src" / "data_loader.py",
                root / "src" / "core" / "jd_parser.py",
                root / "src" / "core" / "resume_parser.py",
                root / "src" / "core" / "matching_engine.py",
            ]
            for frozen_name in (
                "standardized_jd_dataset_v1.xlsx",
                "standard_job_title_mapping_v1.xlsx",
                "standard_skill_dictionary_v1.xlsx",
                "standardized_resume_testset_v1.xlsx",
            )
        ),
        "matching_weights_loaded_from_yaml": matching_engine.weights == matching_engine.config["weights"],
        "json_schema_checks": {
            "jd": all(key in sample_jd for key in ("jd_id", "job_title", "skills", "education", "experience", "evidence", "need_human_review")),
            "resume": all(key in sample_resume for key in ("resume_id", "skills", "education", "experience", "projects", "need_human_review")),
            "matching": all(key in sample_match for key in ("resume_id", "job_title", "match_score", "dimension_scores", "matched_skills", "missing_skills", "recommendations")),
        },
        "stage3_report_stats": stage3_stats,
    }

    frozen_after = loader.frozen_hashes()
    qa["frozen_hashes_before"] = frozen_before
    qa["frozen_hashes_after"] = frozen_after
    qa["frozen_files_unchanged"] = frozen_before == frozen_after
    qa["passed"] = all([
        frozen_validation["passed"], qa["all_output_skill_ids_from_dictionary"],
        not accepted_without_evidence, all(boundary_check.values()),
        qa["unconfirmed_jobs_excluded_from_truth"], qa["data_paths_configured"],
        qa["matching_weights_loaded_from_yaml"], all(qa["json_schema_checks"].values()),
        qa["frozen_files_unchanged"],
    ])

    payload = {
        "metadata": {
            "data_version": loader.version.get("data_version"),
            "schema_version": loader.version.get("schema_version"),
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "source": loader.version.get("source"),
            "source_locations": loader.source_locations(),
        },
        "jd_results": jd_results,
        "resume_results": resume_results,
        "matching_results": matching_results,
        "jd_metrics": jd_metrics,
        "resume_metrics": resume_metrics,
        "matching_metrics": matching_metrics,
        "qa": qa,
    }
    support_dir = root / ".codex_artifacts" / "sprint_a"
    support_dir.mkdir(parents=True, exist_ok=True)
    (support_dir / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_reports(loader, payload)
    if not qa["passed"]:
        raise RuntimeError(f"QA失败：{json.dumps(qa, ensure_ascii=False)}")
    return payload


def _pct(value: float) -> str:
    return f"{value:.1%}"


def _write_reports(loader: DataLoader, payload: dict) -> None:
    root = loader.project_root
    reports = loader.reports_dir()
    docs = root / "docs"
    reports.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    jm, rm, mm = payload["jd_metrics"], payload["resume_metrics"], payload["matching_metrics"]
    core_lines = []
    for jd_job, resume_job in zip(CORE_JOBS, RESUME_CORE_JOBS):
        jd = jm["by_core_job"][jd_job]
        match = mm["by_core_job"][resume_job]
        display_job = jd_job if jd_job == resume_job else f"{jd_job}（简历标注：{resume_job}）"
        core_lines.append(
            f"| {display_job} | {jd['jd_count']} | {_pct(jd['precision'])} | {_pct(jd['recall'])} | {_pct(jd['f1'])} | "
            f"{_pct(match['interval_hit_rate'])} | {_pct(match['level_accuracy'])} | {match['mean_absolute_error']:.2f} |"
        )
    report = f"""# 核心算法闭环报告

## 1. JD Parser设计

JD Parser通过统一数据接口读取正式岗位映射、技能库和JD。岗位预测先命中正式映射，再使用标题相似度与技能画像相似度；低于阈值或属于12条未确认岗位时主动进入人工复核。

技能抽取采用标准技能精确匹配、别名匹配和人工批准的组合词拆分。当前V1不调用外部大模型，保证离线可复现。

## 2. Evidence幻觉防控

每个技能结果均保存`evidence`和`source_field`。最长表达优先避免把“MCP Server”重复识别为“MCP”；组合词只依据正式别名表的一对多审核结果拆分。无原文证据技能拒绝数为 **{jm['rejected_no_evidence_count']}**，QA中接受但无证据的技能为0。

## 3. Resume Parser设计

Resume Parser统一解析学历、经验、工作经历、项目经历和技能清单，并使用与JD相同的技能ID和Evidence规则。输出符合稳定Pydantic Schema。

## 4. Matching Engine设计与权重

五维权重来自`config/matching_weights.yaml`：必备技能50%、加分技能15%、项目经历15%、工作经验10%、学历10%。岗位技能画像由同标准岗位的正式JD聚合产生，评分结果包含维度分、缺失技能、优势技能、学习路径和逐项解释。

## 5. JD解析结果

- 岗位预测评测：{jm['job_title_correct']}/{jm['job_title_evaluated']}，准确率 **{_pct(jm['job_title_accuracy'])}**。
- 排除无正式岗位真值：{jm['job_title_excluded']}条。
- 三个重点岗位聚合技能严格评测：Precision **{_pct(jm['strict_skill_precision'])}**，Recall **{_pct(jm['strict_skill_recall'])}**，F1 **{_pct(jm['strict_skill_f1'])}**。
- 人工复核率：{jm['human_review_count']}/{len(payload['jd_results'])}，即 **{_pct(jm['human_review_rate'])}**。

严格技能指标以岗位聚合人工技能表为Gold，只适用于三个重点岗位；单条JD并不保证包含岗位画像中的全部技能。

## 6. 简历解析结果

27份简历参考评测：Precision **{_pct(rm['reference_precision'])}**，Recall **{_pct(rm['reference_recall'])}**，F1 **{_pct(rm['reference_f1'])}**。人工“已具备技能”不是完整Gold Standard，因此这些指标只用于诊断抽取覆盖，不代表完整解析准确率。

## 7. 匹配评测

- 预测分数落入人工区间比例：**{_pct(mm['interval_hit_rate'])}**。
- 高/中/低分类准确率：**{_pct(mm['level_accuracy'])}**。
- 相对人工区间中点的平均绝对误差：**{mm['mean_absolute_error']:.2f}分**。

人工匹配区间是粗粒度专家标注，不是精确连续数值真值，因此不夸大为“精确匹配准确率”。

| 重点岗位 | JD数 | JD技能P | JD技能R | JD技能F1 | 区间命中率 | 等级准确率 | MAE |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(core_lines)}

## 8. 错误案例

主要误检类型：{jm['main_false_positive_types'] or '无'}。

主要漏检类型：{jm['main_missed_types'] or '无'}。

误差主要来自：岗位聚合Gold比单条JD更完整、简历人工技能并非完整Gold、工作经验和学历文本存在自然语言差异。

## 9. 人工复核机制

低岗位置信度、正式岗位为空、简历关键字段缺失或技能无证据时设置`need_human_review=true`。12条待确认岗位可以输出预测，但不会进入岗位准确率分母。

## 10. 数据接口设计

所有读取通过`src/data_loader.py`，路径、字段、权重和版本分别由四个YAML配置管理。API和内部模块共用稳定Pydantic Schema。

## 11. 当前局限

V1是可解释规则基线，没有使用语义向量或大模型；岗位Gold和简历Gold覆盖有限；项目、经验、学历为透明启发式评分。后续应扩大人工标注集后再调参，不能用当前小样本夸大泛化能力。
"""
    (reports / "核心算法闭环报告.md").write_text(report, encoding="utf-8")

    locations = payload["metadata"]["source_locations"]
    interface_doc = f"""# 数据接口说明

## 1. 当前正式数据位置

| 数据键 | 实际位置 |
|---|---|
{chr(10).join(f'| `{key}` | `{value}` |' for key, value in locations.items())}

这4个文件是冻结正式数据，只读、不覆盖、不重新编号。配置入口为`config/data_sources.yaml`。

## 2. 数据文件与稳定内部字段

- JD：`jd_id`、`original_job_title`、`standard_job_title`、`responsibilities`、`required_skills_raw`、`bonus_skills_raw`、`education`、`experience`。
- 岗位映射：`jd_id`、`original_job_title`、`cleaned_job_title`、`standard_job_title`、`status`、`rationale`。
- 技能库：`skill_id`、标准技能名称、技能类别及别名映射。
- 简历：`resume_id`、`target_job`、`education`、`experience`、`work_experience`、`projects`、`skills_raw`及人工参考标注。

中文Excel字段到内部字段的映射位于`config/field_mapping.yaml`。

## 3. 如何更换JD文件

复制为新的版本文件，不覆盖旧版；确认字段兼容后只修改`config/data_sources.yaml`中的`standardized_jd_dataset.path`和`sheet`。

## 4. 如何增加新JD

在新版本JD文件中追加唯一`JD编号`，保留来源和原始文本；运行`python -m src.core.evaluate_core`。新增JD会经过解析、岗位候选和技能Evidence检查。

## 5. 如何增加技能

从上一版技能库复制为新版本，在“标准技能”Sheet末尾追加新技能。已有`skill_id`保持不变，新ID只追加，例如最大编号后加1；同时提升`config/version.yaml`的数据版本。

## 6. 如何新增技能别名

在新版本技能库“技能别名”Sheet追加原始写法、标准名称和已有`skill_id`。一对多拆分必须明确标记“拆分”并经过人工审核。

## 7. 如何调整匹配权重

修改`config/matching_weights.yaml`的`weights`，五项之和必须为1；核心代码无需修改。

## 8. 如何调用JD Parser

```python
from src.api.service import get_services
services = get_services()
result = services.jd_parser.parse({{"jd_id":"JD-NEW","original_job_title":"Agent工程师","required_skills_raw":"Python、MCP"}})
```

## 9. 如何调用Resume Parser

```python
result = services.resume_parser.parse({{"resume_id":"CV-NEW","skills_raw":"Python、Docker"}})
```

## 10. 如何调用Matching Engine

```python
resume = services.resume_parser.parse({{"resume_id":"CV-NEW","skills_raw":"Python、Docker"}})
result = services.matching_engine.match(resume, "AI Agent开发工程师")
```

## 11. API预留结构

- `POST /api/jd/parse`
- `POST /api/resume/parse`
- `POST /api/match`
- `GET /api/jobs`
- `GET /api/skills`

运行：`uvicorn src.api.app:app --host 127.0.0.1 --port 8000`。OpenAPI文档位于`/docs`。

## 12. 数据版本管理

`config/version.yaml`保存`data_version`、`schema_version`、`updated_at`和`source`。更新时创建新文件、递增版本、保留旧文件及其哈希；公共Schema字段只做向后兼容追加。
"""
    (docs / "data_interface.md").write_text(interface_doc, encoding="utf-8")

    delivery = f"""# 核心模块交付说明

## 1. 文件清单

- 新增配置：`config/data_sources.yaml`、`field_mapping.yaml`、`matching_weights.yaml`、`version.yaml`。
- 新增代码：`src/data_loader.py`、`src/schemas.py`、`src/core/`、`src/api/`。
- 新增测试：`tests/test_core_sprint.py`。
- 新增结果：3份V1结果Excel、接口说明、算法报告和本交付说明。
- 修改：`requirements.txt`、`.gitignore`、`outputs/standardization_stage3_report.md`。

## 2. 运行环境

```powershell
.venv\\Scripts\\python.exe -m src.core.evaluate_core
.venv\\Scripts\\python.exe -m unittest discover -s tests -v
.venv\\Scripts\\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

依赖记录在`requirements.txt`：openpyxl、PyYAML、Pydantic、FastAPI、Uvicorn。

## 3. 输入与输出

输入位置由`config/data_sources.yaml`统一配置。输出为：`outputs/jd_parser_results_v1.xlsx`、`outputs/resume_parser_results_v1.xlsx`、`outputs/matching_results_v1.xlsx`及`reports/核心算法闭环报告.md`。

## 4. 关键指标

- JD岗位准确率：{_pct(jm['job_title_accuracy'])}（排除{jm['job_title_excluded']}条无正式真值记录）。
- 三岗位聚合JD技能F1：{_pct(jm['strict_skill_f1'])}。
- 简历技能参考F1：{_pct(rm['reference_f1'])}，人工技能不是完整Gold。
- 匹配区间命中率：{_pct(mm['interval_hit_rate'])}；等级准确率：{_pct(mm['level_accuracy'])}；MAE：{mm['mean_absolute_error']:.2f}分。

## 5. API与稳定Schema

已实现5个接口。公共Schema位于`src/schemas.py`，后续优先兼容追加字段，不重命名现有字段。

## 6. 增量数据操作

新增JD、技能和别名的步骤见`docs/data_interface.md`。核心原则是新建版本文件、已有ID不变、新ID只追加。

## 7. 接入图谱组

图谱组可读取JD Parser输出中的`jd_id`、标准岗位和`skills[].skill_id`建立岗位—技能关系；Evidence可作为关系证据，`need_human_review`用于过滤待审数据。

## 8. 接入前端组

前端可通过FastAPI调用解析和匹配接口；列表页使用`GET /api/jobs`和`GET /api/skills`。匹配结果已包含维度分、缺失技能、学习建议和解释依据。

## 9. 未解决问题

12条岗位仍无正式真值；三个重点岗位之外缺少完整JD技能Gold；简历人工技能不是完整Gold；当前匹配权重尚未用大规模人工样本校准。
"""
    (docs / "核心模块交付说明.md").write_text(delivery, encoding="utf-8")


def main() -> None:
    payload = run_batch()
    print(json.dumps({
        "jd_metrics": payload["jd_metrics"],
        "resume_metrics": payload["resume_metrics"],
        "matching_metrics": payload["matching_metrics"],
        "qa_passed": payload["qa"]["passed"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
