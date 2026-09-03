import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { getJson } from "../api";
import { PageIntro, StatusBanner, TagList } from "../components/Layout";
import type { JobOption } from "../types";
import { PublishedProfile } from "../components/ClosurePanel";
import ProfileSourceBadge, { type ProfileSourceInfo } from "../components/ProfileSourceBadge";
import type { ClosureVersion } from "../closure";

type Analysis = ProfileSourceInfo & { published_profile?: ClosureVersion; available: boolean; job_title: string; jd_count: number; core_responsibilities: string; required_skills_text: string; bonus_skills_text: string; project_experience: string; education: string; experience: string; skill_frequencies: Array<{ skill_name: string; frequency: number; importance: string; evidence_jd_ids: string[] }>; graph_source_label: string; message: string };
const focus = ["AI Agent开发工程师", "RAG引擎研发工程师", "AI安全技术工程师"];
const split = (value: string) => value.split(/[；;\n]+/).map((item) => item.replace(/^\d+[.、]\s*/, "").trim()).filter(Boolean).slice(0, 16);

export default function JobAnalysisPage() {
  const [jobs, setJobs] = useState<JobOption[]>([]); const [title, setTitle] = useState(focus[0]); const [data, setData] = useState<Analysis | null>(null); const [message, setMessage] = useState(""); const [fallbackData, setFallbackData] = useState<Analysis[]>([]);
  useEffect(() => {
    getJson<{ jobs: JobOption[] }>("/api/jobs", "/data/jobs.json").then((result) => setJobs(result.data.jobs)).catch(() => setJobs([]));
    // Optional generated fallback is not present in every checkout. Its absence must
    // not reject an unhandled promise while the real API / published profile succeeds.
    getJson<{ jobs: Analysis[] }>("/data/job_analysis_v1.json").then((result) => setFallbackData(result.data.jobs)).catch(() => setFallbackData([]));
  }, []);
  useEffect(() => { setMessage(""); getJson<Analysis>(`/api/job-analysis/${encodeURIComponent(title)}`).then((result) => setData(result.data)).catch(() => { const cached = fallbackData.find((item) => item.job_title === title); if (cached) { setData(cached); setMessage("暂时无法连接实时服务，当前展示最近可用的岗位画像。"); } else { setData(null); setMessage("岗位数据暂时无法加载，请稍后重试。"); } }); }, [title, fallbackData]);
  const option = useMemo(() => ({ grid: { left: 120, right: 24, top: 16, bottom: 25 }, xAxis: { type: "value", max: 1, axisLabel: { color: "#6b7280", formatter: (value: number) => `${Math.round(value * 100)}%` }, axisLine: { lineStyle: { color: "#e5e7eb" } }, splitLine: { lineStyle: { color: "#f0f1f3" } } }, yAxis: { type: "category", inverse: true, data: data?.skill_frequencies.slice(0, 12).map((item) => item.skill_name) || [], axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#374151", width: 105, overflow: "truncate" } }, series: [{ type: "bar", data: data?.skill_frequencies.slice(0, 12).map((item) => item.frequency) || [], barWidth: 11, itemStyle: { color: "#10b981", borderRadius: [0, 6, 6, 0] } }], tooltip: { trigger: "axis", backgroundColor: "#ffffff", borderColor: "#e5e7eb", textStyle: { color: "#111827" }, extraCssText: "box-shadow:0 8px 24px rgba(17,24,39,.10);border-radius:8px" } }), [data]);
  return <><PageIntro kicker="岗位要求 · 技能分布 · 信息依据" title="看懂目标岗位真正需要什么" description="选择一个岗位，查看常见职责、能力要求和技能出现频率。" />
    <div className="toolbar"><label>标准岗位<select value={title} onChange={(event) => setTitle(event.target.value)}>{focus.map((item) => <option key={item}>{item}</option>)}{jobs.filter((item) => !focus.includes(item.standard_job_title)).map((item) => <option key={item.standard_job_title}>{item.standard_job_title}</option>)}</select></label><div className="data-chip">{data?.jd_count ?? 0} 条JD</div><div className="data-chip">{data?.graph_source_label || "正式数据"}</div></div>
    <ProfileSourceBadge info={data}/>
    {message ? <StatusBanner tone="warning">{message}</StatusBanner> : null}{data && !data.available ? <StatusBanner>{data.message}</StatusBanner> : null}
    {data?.available ? <div className="analysis-grid"><article className="panel span-2"><div className="panel-title"><span>岗位技能频率</span><small>出现频率前 12 项</small></div><ReactECharts option={option} style={{ height: 390 }} /></article><article className="panel"><div className="panel-title"><span>岗位要求概览</span><small>招聘信息汇总</small></div><Info label="学历要求" value={data.education} /><Info label="经验要求" value={data.experience} /><Info label="项目经验" value={data.project_experience} /></article><article className="panel span-2"><div className="panel-title"><span>常见工作职责</span><small>来自真实招聘信息</small></div><ol className="detail-list">{split(data.core_responsibilities).map((item) => <li key={item}>{item}</li>)}</ol></article><article className="panel"><div className="panel-title"><span>技能要求</span><small>必备与加分项</small></div><h3>必备技能</h3><TagList values={split(data.required_skills_text)} /><h3>加分技能</h3><TagList values={split(data.bonus_skills_text)} /></article></div> : null}
    <PublishedProfile profile={data?.published_profile}/>
  </>;
}
function Info({ label, value }: { label: string; value: string }) { return <div className="info-row"><span>{label}</span><p>{value || "未明确"}</p></div>; }

