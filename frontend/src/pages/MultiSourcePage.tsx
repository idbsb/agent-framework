import { useEffect, useState } from "react";
import { Building2, CheckCircle2, Database, FileCheck2, FileText, RadioTower } from "lucide-react";
import { getJson } from "../api";
import { PageIntro, StatusBanner } from "../components/Layout";

type Payload = {
  batch_id: string; graph_version: string; updated_at: string;
  baseline: Record<string, number>; incremental: Record<string, number>; current: Record<string, number>;
  recruitment_sources: Record<string, number>; external_source_counts: Record<string, number>;
  audit: { status_counts: Record<string, number>; inclusion_counts: Record<string, number>; exclusion_reasons: Record<string, number>; audit_record_count: number };
  workbooks: Array<{ file_name: string; sha256: string; sheets: Array<{ sheet_name: string; row_count: number; fields: string[] }> }>;
  external_evidence: Array<{ evidence_id: string; source_type: string; title: string; publisher: string; published_date: string; supports: string; url: string }>;
};

export default function MultiSourcePage() {
  const [data, setData] = useState<Payload | null>(null); const [error, setError] = useState("");
  useEffect(() => { getJson<Payload>("/api/multi-source", "/data/multi_source.json").then(r => setData(r.data)).catch((e: Error) => setError(e.message)); }, []);
  const cards = [
    [data?.current.jd_count, "当前JD总量", Database], [data?.baseline.jd_count, "Baseline JD", FileText],
    [data?.incremental.jd_count, "本批新增JD", RadioTower], [data?.incremental.source_count, "招聘来源平台", FileCheck2],
    [data?.incremental.company_count, "增量企业", Building2], [data?.incremental.dated_jd_count, "有发布日期JD", CheckCircle2],
  ] as const;
  return <><PageIntro kicker="招聘数据源 · 外部佐证 · 真实性审计" title="多源数据采集与质量追溯" description="招聘JD用于数量与岗位变化计算；政策和行业报告仅作为外部趋势佐证，两类口径严格分开。" />
    {error ? <StatusBanner tone="error">数据加载失败：{error}</StatusBanner> : null}
    <StatusBanner>批次 {data?.batch_id || "加载中"} · {data?.graph_version || "—"} · 最近更新 {data?.updated_at || "—"} · 6份工作簿全部逐 Sheet 读取</StatusBanner>
    <section className="metric-grid">{cards.map(([value, label, Icon]) => <article className="metric-card" key={label}><div className="metric-icon"><Icon size={19}/></div><div className="metric-value">{value ?? "—"}</div><div className="metric-label">{label}</div></article>)}</section>
    <section className="three-column-grid">
      <article className="panel"><div className="panel-title"><span>招聘数据源</span><small>只计JD</small></div>{Object.entries(data?.recruitment_sources || {}).sort((a,b)=>b[1]-a[1]).map(([name,count])=><div className="key-value-row" key={name}><span>{name}</span><b>{count} 条</b></div>)}</article>
      <article className="panel"><div className="panel-title"><span>外部佐证数据</span><small>不计入JD</small></div>{Object.entries(data?.external_source_counts || {}).map(([name,count])=><div className="key-value-row" key={name}><span>{name}</span><b>{count} 条</b></div>)}</article>
      <article className="panel"><div className="panel-title"><span>真实性与质量</span><small>{data?.audit.audit_record_count || 0} 条检索审计</small></div>{Object.entries(data?.audit.status_counts || {}).map(([name,count])=><div className="key-value-row" key={name}><span className={`quality-dot ${name.toLowerCase()}`}>{name}</span><b>{count}</b></div>)}{Object.entries(data?.audit.inclusion_counts || {}).map(([name,count])=><div className="key-value-row" key={name}><span>{name}</span><b>{count}</b></div>)}</article>
    </section>
    <article className="panel"><div className="panel-title"><span>6份增量工作簿接入审计</span><small>文件哈希与全部Sheet</small></div><div className="workbook-list">{data?.workbooks.map(book=><details key={book.file_name}><summary><b>{book.file_name}</b><span>{book.sheets.length} 个Sheet · SHA256 {book.sha256.slice(0,12)}…</span></summary>{book.sheets.map(sheet=><div className="sheet-row" key={sheet.sheet_name}><b>{sheet.sheet_name}</b><span>{sheet.row_count} 行 · {sheet.fields.join("、")}</span></div>)}</details>)}</div></article>
    <article className="panel"><div className="panel-title"><span>政策与行业报告证据</span><small>仅用于解释，不替代招聘JD</small></div><div className="evidence-table">{data?.external_evidence.slice(0,10).map(item=><a href={item.url} target="_blank" rel="noreferrer" key={item.evidence_id}><b>{item.evidence_id} · {item.title}</b><span>{item.source_type} · {item.publisher} · {item.published_date || "日期待补"}</span><small>{item.supports}</small></a>)}</div></article>
  </>;
}
