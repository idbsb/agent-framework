from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..api.service import get_services
from .emerging_job_detector import EmergingJobDetector


def build_report(result: dict) -> str:
    summary = result["summary"]
    lines = [
        "# 新岗位发现报告",
        "",
        "## 1. 什么叫“新岗位候选”",
        "",
        "本报告中的新岗位候选，是由真实招聘JD中的新颖岗位名称、稳定技能组合及与现有岗位画像的差异共同支持的观察对象。它不是由大模型创造的岗位名称，也不等同于正式职业分类。",
        "",
        "## 2. 为什么离群JD不能直接当作新岗位",
        "",
        "单条离群JD可能来自企业内部命名、招聘文案差异或数据噪声。因此单条记录强制标记为弱候选/待观察；只有重复Evidence、技能一致性和多源支持共同增强时，置信度才可能提高。",
        "",
        "## 3. 使用的信号",
        "",
        "- 岗位标题相对现有标准岗位体系的新颖性。",
        "- 标准技能组合相对现有岗位画像的差异。",
        "- 同簇JD之间的标题与技能一致性。",
        "- Evidence数量、招聘来源数量、企业数量。",
        "- 有正式发布时间时的近期信号；缺失日期不补造。",
        "",
        "## 4. EmergingScore计算",
        "",
        "总分为各信号归一化到0–1后按 `config/emerging_job_config.yaml` 权重加权，再乘100。单条JD候选有49分上限，不能进入中高置信等级。",
        "",
        "## 5. 候选概览",
        "",
        f"共发现 {summary['candidate_count']} 个候选：高置信 {summary['high_confidence']} 个，中置信 {summary['medium_confidence']} 个，弱候选/待观察 {summary['weak_candidate']} 个。",
        "",
        "## 6. 候选与真实Evidence",
        "",
    ]
    for item in result["candidates"]:
        lines.extend([
            f"### {item['candidate_id']} {item['candidate_name']}",
            "",
            f"- EmergingScore：{item['emerging_score']}（{item['confidence_level']}）",
            f"- Evidence数量：{item['evidence_count']}；JD：{', '.join(item['evidence_jd_ids'])}",
            f"- 来源/企业：{item['source_count']} / {item['company_count']}",
            f"- 代表真实标题：{'；'.join(item['representative_titles'])}",
            f"- 核心技能：{'；'.join(item['core_skills']) or '当前标准技能证据不足'}",
            f"- 差异技能：{'；'.join(item['distinguishing_skills']) or '未形成稳定差异技能'}",
            f"- 与已有岗位关系：{item['relation_to_existing_jobs']}",
            f"- 新兴原因：{item['why_emerging']}",
            "",
        ])
    weak = [item for item in result["candidates"] if item["confidence_level"] == "弱候选/待观察"]
    lines.extend([
        "## 7. 弱候选",
        "",
        ("弱候选包括：" + "、".join(item["candidate_name"] for item in weak)) if weak else "本轮没有弱候选。",
        "",
        "## 8. 数据限制",
        "",
        "当前数据共191条JD，部分岗位仅有单条样本，部分JD没有正式发布时间。技能识别受冻结标准技能词典覆盖范围约束，来源名称也可能代表同一平台的不同写法。评分只反映当前样本范围内的证据强弱。",
        "",
        "## 9. 与国家正式新职业的区别",
        "",
        "本结果仅用于招聘市场中的候选信号发现，未经职业分类主管部门论证、标准制定或正式发布，不能宣传为国家职业分类中的“新职业”。",
        "",
        "## 10. 动态更新方式",
        "",
        "新增JD按既有标准化流程写入新版本数据后，重新运行检测与导出命令即可。候选编号、分数和Evidence将基于当期真实数据重新计算；历史结果应按版本归档，不覆盖冻结源数据。",
        "",
    ])
    return "\n".join(lines)


def export_json_and_report(project_root: Path) -> dict:
    services = get_services()
    result = EmergingJobDetector(services.loader, services.skill_index).detect()
    outputs = project_root / "outputs"
    reports = project_root / "reports"
    outputs.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    (outputs / "emerging_jobs_v1.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (reports / "新岗位发现报告.md").write_text(build_report(result), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="生成新岗位候选JSON和报告")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    result = export_json_and_report(args.project_root.resolve())
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
