from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


supplemental = load("data/external/supplemental_jd_v3.json")
parse_report = load("outputs/supplemental_jd_parse_report_v3.json")
dedup = load("outputs/supplemental_jd_dedup_report_v3.json")
v2 = load("outputs/emerging_jobs_v2.json")
frozen = load("outputs/frozen_file_hash_audit_v3.json")
records = supplemental["records"]

lines = [
    "# 补充 JD V3 完整交付报告", "",
    f"生成时间：{supplemental['generated_at']}  ",
    f"数据版本：`{supplemental['data_version']}`  ",
    f"源文件 SHA-256：`{supplemental['source_sha256']}`", "",
    "## 1–3. 解析结果与 SUP-JD-001～049 完整清单", "",
    f"成功解析：**{parse_report['parsed_count']}**；失败：**{parse_report['failed_count']}**；数量守恒：**{parse_report['conservation_passed']}**；Evidence ID 连续：**{parse_report['evidence_ids_continuous']}**。", "",
    "| Evidence ID | 源行 | 岗位 | 企业 | 映射结论 | 去重结论 |", "|---|---:|---|---|---|---|",
]
for row in records:
    lines.append(f"| {row['evidence_id']} | {row['source_start_line']}-{row['source_end_line']} | {row['raw_job_title']} | {row['company_normalized']} | {row['primary_emerging_job_id']} / {row['mapping_type']} | {row['duplicate_status']}{' → ' + row['duplicate_of'] if row['duplicate_of'] else ''} |")

lines += ["", "## 4. 重复与疑似重复", ""]
for row in records:
    if row["duplicate_status"] != "unique":
        lines.append(f"- `{row['evidence_id']}`：{row['duplicate_status']}，关联 `{row['duplicate_of']}`；{row['duplicate_reason']}；计入统计={str(row['count_in_statistics']).lower()}。")

lines += ["", "## 5. 映射到旧候选", ""]
for row in records:
    if int(row["primary_emerging_job_id"].split("-")[-1]) <= 11:
        lines.append(f"- `{row['evidence_id']}` → `{row['primary_emerging_job_id']}`（{row['mapping_type']}，{row['mapping_confidence']:.2f}）：{row['mapping_reason']}")

lines += ["", "## 6–7. 新候选与聚类依据", ""]
for candidate in v2["candidates"][11:]:
    lines.append(f"- `{candidate['candidate_id']}` {candidate['candidate_name']}：{candidate.get('cluster_reason', candidate['why_emerging'])} Evidence：{', '.join(candidate['evidence_jd_ids'])}；去重计数 {candidate['counted_evidence_count']}；V2 {candidate['emerging_score_v2']} / {candidate['confidence_v2']}。")

lines += ["", "## 8. 候选统计前后对照", "", "| 候选 | Evidence V1→V2审计 | 企业 V1→V2 | 来源 V1→V2 | 分数 V1→V2 | 置信度 V1→V2 |", "|---|---:|---:|---:|---:|---|"]
for row in v2["candidate_statistics_comparison"]:
    lines.append(f"| {row['candidate_id']} {row['candidate_name']} | {row['before_evidence_count']}→{row['after_evidence_count']} | {row['before_company_count']}→{row['after_company_count']} | {row['before_source_count']}→{row['after_source_count']} | {row['emerging_score_v1'] if row['emerging_score_v1'] is not None else '—'}→{row['emerging_score_v2']} | {row['confidence_v1']}→{row['confidence_v2']} |")

missing_url = [row["evidence_id"] for row in records if not row["source_url"]]
missing_date = [row["evidence_id"] for row in records if not row["publish_date"]]
manual = [row for row in records if row["needs_manual_review"]]
lines += [
    "", "## 9. 缺少 URL 或发布日期", "",
    f"- 缺少 URL（{len(missing_url)} 条）：{', '.join(missing_url)}。",
    f"- 缺少发布日期（{len(missing_date)} 条）：{', '.join(missing_date)}。",
    "- 所有缺失字段均留空，页面显示“来源链接待补”，未编造招聘状态。",
    "", "## 10. 人工确认项", "",
]
for row in manual:
    lines.append(f"- `{row['evidence_id']}` {row['raw_job_title']}：{row['duplicate_reason']}")

lines += [
    "", "## 11. 输出文件", "",
    "- `data/external/supplemental_jd_v3.json`",
    "- `data/external/supplemental_jd_v3.xlsx`",
    "- `outputs/supplemental_jd_parse_report_v3.json`",
    "- `outputs/supplemental_jd_dedup_report_v3.json`",
    "- `outputs/supplemental_jd_mapping_report_v3.xlsx`",
    "- `outputs/emerging_jobs_v2.json`",
    "- `outputs/emerging_jobs_v2.xlsx`",
    "- `outputs/frozen_file_hash_audit_v3.json`",
    "", "## 12. 修改与新增文件", "",
    "- 新增：`src/emerging/supplemental_pipeline.py`、`scripts/build_supplemental_workbooks.mjs`、`tests/test_supplemental_jd_v3.py`。",
    "- 修改：`src/integration/system_data.py`、`src/integration/export_frontend_data.py`、`frontend/src/types.ts`、`frontend/src/pages/EmergingPage.tsx`、`frontend/src/styles.css`。",
    "- 兼容性文案修复：`frontend/src/pages/EvolutionPage.tsx`。",
    "- 构建同步：`frontend/public/data/emerging_jobs_v1.json`、`frontend/public/data/emerging_jobs_v2.json`、`frontend/dist/`。",
    "", "## 13–14. API 与构建回归", "",
    "- `GET /api/emerging-jobs`：HTTP 200；`data_version=supplemental_jd_v3`；32 个候选；加载 `emerging_jobs_v2.json`。",
    "- `GET /api/emerging-jobs/EMERGING-012`：HTTP 200；返回“具身智能数据Infra负责人”及完整 Evidence。",
    "- `/emerging`：HTTP 200；浏览器控制台错误 0。",
    "- Python：126 项测试全部通过；前端：21 项测试全部通过。",
    "- `npm run build`：成功；现有主包 1,444.55 kB，Vite 给出代码分包性能提示，不影响功能。",
    "", "## 15. 页面截图", "",
    "- `reports/ui-supplemental-jd-v3/emerging-v2-page.png`",
    "- `reports/ui-supplemental-jd-v3/emerging-v2-evidence-expanded.png`",
    "", "## 16. 冻结文件 SHA-256 前后对照", "", "| 路径 | 大小 | SHA-256（前） | SHA-256（后） |", "|---|---:|---|---|",
]
after_by_path = {row["path"]: row for row in frozen["after"]}
for before in frozen["before"]:
    after = after_by_path[before["path"]]
    lines.append(f"| {before['path']} | {before['size_bytes']} | `{before['sha256']}` | `{after['sha256']}` |")
lines += ["", f"结论：**{frozen['file_count']} 个冻结文件前后完全一致={str(frozen['unchanged']).lower()}**。", "", "## 17. 未完成项与已知限制", "", "- 49 条 TXT 均无可核验 URL 和发布日期，需后续补充来源后才能提高 Evidence 可信度。", "- `SUP-JD-026` 与原 `JD-081` 为疑似重复，保留计数并进入人工确认，未擅自删除。", "- V2 分数为当前样本内的确定性证据评分，不代表国家正式职业认定。", "- 前端生产包已有体积偏大提示，后续可按路由拆包优化；本次未扩大到页面重构。", ""]

target = ROOT / "reports/supplemental_jd_v3_delivery.md"
target.write_text("\n".join(lines), encoding="utf-8")
print(target)
