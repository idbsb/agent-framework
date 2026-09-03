import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const externalDir = path.join(root, "data", "external");
const outputDir = path.join(root, "outputs");
const previewDir = path.join(root, "reports", "supplemental-jd-v3-workbook-previews");
await fs.mkdir(previewDir, { recursive: true });

const supplemental = JSON.parse(await fs.readFile(path.join(externalDir, "supplemental_jd_v3.json"), "utf8"));
const parseReport = JSON.parse(await fs.readFile(path.join(outputDir, "supplemental_jd_parse_report_v3.json"), "utf8"));
const dedupReport = JSON.parse(await fs.readFile(path.join(outputDir, "supplemental_jd_dedup_report_v3.json"), "utf8"));
const emerging = JSON.parse(await fs.readFile(path.join(outputDir, "emerging_jobs_v2.json"), "utf8"));
const records = supplemental.records;

const text = (value) => {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.join("；");
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return value;
};

const colName = (number) => {
  let result = "";
  while (number > 0) {
    number -= 1;
    result = String.fromCharCode(65 + (number % 26)) + result;
    number = Math.floor(number / 26);
  }
  return result;
};

let tableIndex = 0;
function addSheet(workbook, name, headers, rows, widths = {}) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  const matrix = [headers, ...rows.map((row) => headers.map((header) => text(row[header])))];
  const end = colName(headers.length);
  const range = sheet.getRange(`A1:${end}${matrix.length}`);
  range.values = matrix;
  sheet.getRange(`A1:${end}1`).format = {
    fill: "#0F766E",
    font: { bold: true, color: "#FFFFFF", size: 10 },
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "outside", style: "thin", color: "#0B5F58" },
  };
  sheet.getRange(`A2:${end}${matrix.length}`).format = {
    font: { color: "#374151", size: 9 },
    verticalAlignment: "top",
    borders: { insideHorizontal: { style: "thin", color: "#E5E7EB" } },
  };
  sheet.getRange(`A1:${end}${matrix.length}`).format.rowHeight = 24;
  headers.forEach((header, index) => {
    const column = colName(index + 1);
    const width = widths[header] || (/(原文|职责|要求|理由|技能|说明)/.test(header) ? 42 : 18);
    sheet.getRange(`${column}:${column}`).format.columnWidth = width;
    if (width >= 32) sheet.getRange(`${column}2:${column}${matrix.length}`).format.wrapText = true;
  });
  if (rows.length) {
    const table = sheet.tables.add(`A1:${end}${matrix.length}`, true, `AuditTable${++tableIndex}`);
    table.style = "TableStyleMedium4";
  }
  return sheet;
}

function detailRows() {
  return records.map((row) => ({
    Evidence_ID: row.evidence_id, 源序号: row.source_sequence, 起始行: row.source_start_line, 结束行: row.source_end_line,
    原始岗位名: row.raw_job_title, 清洗岗位名: row.cleaned_job_title, 企业原名: row.company_raw,
    企业规范名: row.company_normalized, 岗位族: row.job_family, 岗位职能: row.job_function,
    技术领域: row.technical_domain, 学历要求: row.education_requirement, 经验要求: row.experience_requirement,
    招聘类型: row.employment_type, 地点: row.location, 必备技能: row.required_skills,
    加分技能: row.preferred_skills, 工具与框架: row.tools_and_frameworks,
    主候选ID: row.primary_emerging_job_id, 支撑候选ID: row.supporting_emerging_job_ids,
    映射类型: row.mapping_type, 映射置信度: row.mapping_confidence, 映射理由: row.mapping_reason,
    去重状态: row.duplicate_status, 重复对象: row.duplicate_of, 是否计入统计: row.count_in_statistics,
    来源验证状态: row.source_verification_status, Evidence可信度: row.evidence_confidence,
    是否人工确认: row.needs_manual_review, 数据版本: row.data_version, 入库时间: row.ingested_at,
  }));
}

const detailHeaders = ["Evidence_ID", "源序号", "起始行", "结束行", "原始岗位名", "清洗岗位名", "企业原名", "企业规范名", "岗位族", "岗位职能", "技术领域", "学历要求", "经验要求", "招聘类型", "地点", "必备技能", "加分技能", "工具与框架", "主候选ID", "支撑候选ID", "映射类型", "映射置信度", "映射理由", "去重状态", "重复对象", "是否计入统计", "来源验证状态", "Evidence可信度", "是否人工确认", "数据版本", "入库时间"];
const rawHeaders = ["Evidence_ID", "原始岗位名", "企业", "源文件起止行", "完整JD原文", "岗位职责原文", "任职要求原文", "加分项原文"];
const rawRows = records.map((row) => ({ Evidence_ID: row.evidence_id, 原始岗位名: row.raw_job_title, 企业: row.company_raw, 源文件起止行: `${row.source_start_line}-${row.source_end_line}`, 完整JD原文: row.raw_text, 岗位职责原文: row.responsibilities_raw, 任职要求原文: row.requirements_raw, 加分项原文: row.bonus_requirements_raw }));
const skillHeaders = ["Evidence_ID", "原始岗位名", "必备技能", "加分技能", "工具与框架", "技能数量"];
const skillRows = records.map((row) => ({ Evidence_ID: row.evidence_id, 原始岗位名: row.raw_job_title, 必备技能: row.required_skills, 加分技能: row.preferred_skills, 工具与框架: row.tools_and_frameworks, 技能数量: new Set([...row.required_skills, ...row.preferred_skills, ...row.tools_and_frameworks]).size }));
const dedupHeaders = ["Evidence_ID", "去重状态", "重复对象", "去重理由", "是否计入统计", "是否人工确认"];
const dedupRows = records.map((row) => ({ Evidence_ID: row.evidence_id, 去重状态: row.duplicate_status, 重复对象: row.duplicate_of, 去重理由: row.duplicate_reason, 是否计入统计: row.count_in_statistics, 是否人工确认: row.needs_manual_review }));
const oldMapHeaders = ["Evidence_ID", "原始岗位名", "企业", "候选ID", "映射类型", "支撑候选", "映射置信度", "映射理由", "去重状态"];
const oldMapRows = records.filter((row) => Number(row.primary_emerging_job_id.split("-")[1]) <= 11).map((row) => ({ Evidence_ID: row.evidence_id, 原始岗位名: row.raw_job_title, 企业: row.company_normalized, 候选ID: row.primary_emerging_job_id, 映射类型: row.mapping_type, 支撑候选: row.supporting_emerging_job_ids, 映射置信度: row.mapping_confidence, 映射理由: row.mapping_reason, 去重状态: row.duplicate_status }));
const newCandidates = emerging.candidates.filter((row) => Number(row.candidate_id.split("-")[1]) > 11);
const newHeaders = ["候选ID", "候选岗位", "聚类Evidence", "去重Evidence数", "企业数", "来源数", "核心技能", "最相近旧候选", "聚类依据", "V2分数", "V2置信度"];
const newRows = newCandidates.map((row) => ({ 候选ID: row.candidate_id, 候选岗位: row.candidate_name, 聚类Evidence: row.evidence_jd_ids, 去重Evidence数: row.counted_evidence_count, 企业数: row.company_count, 来源数: row.source_count, 核心技能: row.core_skills, 最相近旧候选: row.supporting_existing_candidate_ids || row.relation_to_existing_jobs, 聚类依据: row.cluster_reason || row.why_emerging, V2分数: row.emerging_score_v2, V2置信度: row.confidence_v2 }));
const compareHeaders = ["候选ID", "候选岗位", "V1 Evidence", "V2审计Evidence", "V1企业数", "V2企业数", "V1来源数", "V2来源数", "V1分数", "V2分数", "V1置信度", "V2置信度"];
const compareRows = emerging.candidate_statistics_comparison.map((row) => ({ 候选ID: row.candidate_id, 候选岗位: row.candidate_name, "V1 Evidence": row.before_evidence_count, V2审计Evidence: row.after_evidence_count, V1企业数: row.before_company_count, V2企业数: row.after_company_count, V1来源数: row.before_source_count, V2来源数: row.after_source_count, V1分数: row.emerging_score_v1, V2分数: row.emerging_score_v2, V1置信度: row.confidence_v1, V2置信度: row.confidence_v2 }));
const manualHeaders = ["Evidence_ID", "原始岗位名", "企业", "人工确认原因", "去重状态", "来源状态", "映射类型", "映射理由"];
const manualRows = records.filter((row) => row.needs_manual_review).map((row) => ({ Evidence_ID: row.evidence_id, 原始岗位名: row.raw_job_title, 企业: row.company_normalized, 人工确认原因: row.duplicate_status === "possible_duplicate" ? row.duplicate_reason : "原文分段或来源信息需人工确认", 去重状态: row.duplicate_status, 来源状态: row.source_verification_status, 映射类型: row.mapping_type, 映射理由: row.mapping_reason }));

function addNotes(workbook, includeFormulas = false) {
  const sheet = workbook.worksheets.add("数据说明");
  sheet.showGridLines = false;
  sheet.getRange("A1:D1").merge();
  sheet.getRange("A1").values = [["补充JD V3 数据说明"]];
  sheet.getRange("A1:D1").format = { fill: "#0F766E", font: { bold: true, color: "#FFFFFF", size: 16 }, rowHeight: 34 };
  const notes = [
    ["项目", "内容"],
    ["数据版本", supplemental.data_version],
    ["源文件", supplemental.source_file],
    ["源文件SHA-256", supplemental.source_sha256],
    ["源文件行数", parseReport.source_line_count],
    ["预期JD数", parseReport.expected_count],
    ["成功解析", parseReport.parsed_count],
    ["解析失败", parseReport.failed_count],
    ["确定重复", dedupReport.duplicate_count],
    ["疑似重复", dedupReport.possible_duplicate_count],
    ["计入统计", dedupReport.counted_supplemental_count],
    ["生成时间", supplemental.generated_at],
    ["规则", "原191条正式JD与所有standard*_v1.xlsx只读；补充数据独立入库；缺失URL和发布日期不编造。"],
  ];
  sheet.getRange(`A3:B${notes.length + 2}`).values = notes;
  sheet.getRange("A3:B3").format = { fill: "#D1FAE5", font: { bold: true, color: "#065F46" } };
  sheet.getRange(`A4:A${notes.length + 2}`).format.font = { bold: true, color: "#374151" };
  sheet.getRange(`A3:B${notes.length + 2}`).format.borders = { insideHorizontal: { style: "thin", color: "#E5E7EB" } };
  sheet.getRange("A:A").format.columnWidth = 22;
  sheet.getRange("B:B").format.columnWidth = 72;
  sheet.getRange("B3:B20").format.wrapText = true;
  if (includeFormulas) {
    sheet.getRange("D3:E3").values = [["动态校验", "结果"]];
    sheet.getRange("D3:E3").format = { fill: "#D1FAE5", font: { bold: true, color: "#065F46" } };
    sheet.getRange("D4:D7").values = [["明细记录数"], ["确定重复数"], ["疑似重复数"], ["人工确认数"]];
    sheet.getRange("E4:E7").formulas = [["=COUNTA('49条补充JD明细'!A2:A50)"], ["=COUNTIF('去重结果'!B2:B50,\"duplicate\")"], ["=COUNTIF('去重结果'!B2:B50,\"possible_duplicate\")"], ["=COUNTA('人工确认项'!A2:A50)"]];
    sheet.getRange("D:D").format.columnWidth = 20;
    sheet.getRange("E:E").format.columnWidth = 14;
    sheet.getRange("E4:E7").format.numberFormat = "#,##0";
  }
  return sheet;
}

function buildSupplemental() {
  const wb = Workbook.create();
  addSheet(wb, "49条补充JD明细", detailHeaders, detailRows());
  addSheet(wb, "JD原文", rawHeaders, rawRows, { 完整JD原文: 70, 岗位职责原文: 55, 任职要求原文: 55, 加分项原文: 45 });
  addSheet(wb, "技能明细", skillHeaders, skillRows);
  addNotes(wb);
  return wb;
}

function buildMapping() {
  const wb = Workbook.create();
  addSheet(wb, "49条补充JD明细", detailHeaders, detailRows());
  addSheet(wb, "JD原文", rawHeaders, rawRows, { 完整JD原文: 70, 岗位职责原文: 55, 任职要求原文: 55, 加分项原文: 45 });
  addSheet(wb, "技能明细", skillHeaders, skillRows);
  addSheet(wb, "去重结果", dedupHeaders, dedupRows);
  addSheet(wb, "映射到旧候选", oldMapHeaders, oldMapRows);
  addSheet(wb, "新增候选岗位", newHeaders, newRows);
  addSheet(wb, "候选统计前后对照", compareHeaders, compareRows);
  addSheet(wb, "人工确认项", manualHeaders, manualRows.length ? manualRows : [{ Evidence_ID: "无", 人工确认原因: "无人工确认项" }]);
  addNotes(wb, true);
  return wb;
}

function buildEmerging() {
  const wb = Workbook.create();
  const headers = ["候选ID", "候选岗位", "V1分数", "V2分数", "V1置信度", "V2置信度", "Evidence强度V2", "审计Evidence数", "去重Evidence数", "精确Evidence数", "岗位族支撑数", "企业数", "来源数", "核心技能", "差异技能", "发现理由", "与旧岗位关系", "评分版本"];
  const rows = emerging.candidates.map((row) => ({ 候选ID: row.candidate_id, 候选岗位: row.candidate_name, V1分数: row.emerging_score_v1, V2分数: row.emerging_score_v2, V1置信度: row.confidence_v1, V2置信度: row.confidence_v2, Evidence强度V2: row.evidence_strength_v2, 审计Evidence数: row.evidence_count, 去重Evidence数: row.counted_evidence_count, 精确Evidence数: row.exact_evidence_count, 岗位族支撑数: row.supporting_evidence_count, 企业数: row.company_count, 来源数: row.source_count, 核心技能: row.core_skills, 差异技能: row.distinguishing_skills, 发现理由: row.why_emerging, 与旧岗位关系: row.relation_to_existing_jobs, 评分版本: row.score_version }));
  addSheet(wb, "新岗位候选V2", headers, rows);
  const evidenceRows = emerging.candidates.flatMap((candidate) => candidate.evidence_records.map((row) => ({ 候选ID: candidate.candidate_id, 候选岗位: candidate.candidate_name, Evidence_ID: row.evidence_id || row.jd_id, 企业: row.company, 原始岗位名: row.original_job_title, 来源: row.source, URL: row.source_url, 发布日期: row.published_date, 去重状态: row.duplicate_status, 是否计数: row.count_in_statistics, 映射类型: row.mapping_type, 映射理由: row.mapping_reason, Evidence可信度: row.evidence_confidence, 技能: row.skills, 职责: row.responsibilities, 要求: row.required_skills_raw })));
  addSheet(wb, "Evidence明细", ["候选ID", "候选岗位", "Evidence_ID", "企业", "原始岗位名", "来源", "URL", "发布日期", "去重状态", "是否计数", "映射类型", "映射理由", "Evidence可信度", "技能", "职责", "要求"], evidenceRows);
  addSheet(wb, "候选统计前后对照", compareHeaders, compareRows);
  addNotes(wb);
  return wb;
}

async function verifyAndSave(workbook, target, prefix) {
  const sheets = await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 5000 });
  console.log(`${prefix} sheets`, sheets.ndjson);
  const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: `${prefix} formula errors` });
  console.log(`${prefix} errors`, errors.ndjson);
  for (const sheet of workbook.worksheets.items) {
    const used = sheet.getUsedRange(true);
    const rows = Math.min(8, used?.rowCount || 8);
    const cols = Math.min(12, used?.columnCount || 8);
    const range = `A1:${colName(cols)}${rows}`;
    const preview = await workbook.render({ sheetName: sheet.name, range, scale: 1, format: "png" });
    const safeName = sheet.name.replace(/[\\/:*?"<>|]/g, "_");
    await fs.writeFile(path.join(previewDir, `${prefix}-${safeName}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(target);
}

await verifyAndSave(buildSupplemental(), path.join(externalDir, "supplemental_jd_v3.xlsx"), "supplemental");
await verifyAndSave(buildMapping(), path.join(outputDir, "supplemental_jd_mapping_report_v3.xlsx"), "mapping");
await verifyAndSave(buildEmerging(), path.join(outputDir, "emerging_jobs_v2.xlsx"), "emerging");
console.log(JSON.stringify({ outputs: [path.join(externalDir, "supplemental_jd_v3.xlsx"), path.join(outputDir, "supplemental_jd_mapping_report_v3.xlsx"), path.join(outputDir, "emerging_jobs_v2.xlsx")], previewDir }));
