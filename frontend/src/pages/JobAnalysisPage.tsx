import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { getJson } from "../api";
import { PageIntro, StatusBanner, TagList } from "../components/Layout";
import type { JobOption } from "../types";

type Analysis = { available: boolean; job_title: string; jd_count: number; core_responsibilities: string; required_skills_text: string; bonus_skills_text: string; project_experience: string; education: string; experience: string; skill_frequencies: Array<{ skill_name: string; frequency: number; importance: string; evidence_jd_ids: string[] }>; graph_source_label: string; message: string };
const focus = ["AI Agent开发工程师", "RAG引擎研发工程师", "AI安全技术工程师"];
const split = (value: string) => value.split(/[；;\n]+/).map((item) => item.replace(/^\d+[.、]\s*/, "").trim()).filter(Boolean).slice(0, 16);

export default function JobAnalysisPage() {
  const [jobs, setJobs] = useState<JobOption[]>([]); const [title, setTitle] = useState(focus[0]); const [data, setData] = useState<Analysis | null>(null); const [message, setMessage] = useState(""); const [fallbackData, setFallbackData] = useState<Analysis[]>([]);
  useEffect(() => {
    getJson<{ jobs: JobOption[] }>("/api/jobs", "/data/jobs.json").then((result) => setJobs(result.data.jobs));
    // This optional generated fallback may be absent in a clean checkout.
    getJson<{ jobs: Analysis[] }>("/data/job_analysis_v1.json").then((result) => setFallbackData(result.data.jobs)).catch(() => setFallbackData([]));
  }, []);
  useEffect(() => { setMessage(""); getJson<Analysis>(`/api/job-analysis/${encodeURIComponent(title)}`).then((result) => setData(result.data)).catch(() => { const cached = fallbackData.find((item) => item.job_title === title); if (cached) { setData(cached); setMessage("后端暂不可用，展示程序生成的真实岗位画像。"); } else { setData(null); setMessage("后端服务未启动，请启动FastAPI服务。"); } }); }, [title, fallbackData]);
  const option = useMemo(() => ({ grid: { left: 120, right: 24, top: 16, bottom: 25 }, xAxis: { type: "value", max: 1, axisLabel: { color: "#78909e", formatter: (value: number) => `${Math.round(value * 100)}%` }, splitLine: { lineStyle: { color: "#17303e" } } }, yAxis: { type: "category", inverse: true, data: data?.skill_frequencies.slice(0, 12).map((item) => item.skill_name) || [], axisLabel: { color: "#b5cad4", width: 105, overflow: "truncate" } }, series: [{ type: "bar", data: data?.skill_frequencies.slice(0, 12).map((item) => item.frequency) || [], barWidth: 10, itemStyle: { color: "#45c9a6", borderRadius: [0, 6, 6, 0] } }], tooltip: { trigger: "axis", backgroundColor: "#102633", textStyle: { color: "#e6f5f2" } } }), [data]);
  return <><PageIntro kicker="岗位画像 · 真实频率 · 能力结构" title="从真实JD聚合岗位能力画像" description="选择标准岗位，查看职责、技能频率和Evidence来源。" index="02" />
    <div className="toolbar"><label>标准岗位<select value={title} onChange={(event) => setTitle(event.target.value)}>{focus.map((item) => <option key={item}>{item}</option>)}{jobs.filter((item) => !focus.includes(item.standard_job_title)).map((item) => <option key={item.standard_job_title}>{item.standard_job_title}</option>)}</select></label><div className="data-chip">{data?.jd_count ?? 0} 条JD</div><div className="data-chip">{data?.graph_source_label || "正式数据"}</div></div>
    {message ? <StatusBanner tone="warning">{message}</StatusBanner> : null}{data && !data.available ? <StatusBanner>{data.message}</StatusBanner> : null}
    {data?.available ? <div className="analysis-grid"><article className="panel span-2"><div className="panel-title"><span>技能频率</span><small>Top 12</small></div><ReactECharts option={option} style={{ height: 390 }} /></article><article className="panel"><div className="panel-title"><span>能力画像</span><small>结构化结果</small></div><Info label="学历" value={data.education} /><Info label="经验" value={data.experience} /><Info label="项目经历" value={data.project_experience} /></article><article className="panel span-2"><div className="panel-title"><span>核心职责</span><small>真实聚合</small></div><ol className="detail-list">{split(data.core_responsibilities).map((item) => <li key={item}>{item}</li>)}</ol></article><article className="panel"><div className="panel-title"><span>技能结构</span><small>必备 / 加分</small></div><h3>必备技能</h3><TagList values={split(data.required_skills_text)} /><h3>加分技能</h3><TagList values={split(data.bonus_skills_text)} /></article></div> : null}
  </>;
}
function Info({ label, value }: { label: string; value: string }) { return <div className="info-row"><span>{label}</span><p>{value || "未明确"}</p></div>; }

