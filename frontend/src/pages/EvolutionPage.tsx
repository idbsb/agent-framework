import { useEffect, useState } from "react";
import { Clock3, DatabaseZap } from "lucide-react";
import { getJson } from "../api";
import { PageIntro, StatusBanner, TagList } from "../components/Layout";
import ClosurePanel from "../components/ClosurePanel";

type Evolution = { available: boolean; status: string; job_title: string; message: string; notice: string; time_range: string[] | null; support_jd_count: number; sample_insufficient: boolean; sample_notice: string; core_skills: string[]; growing_skills: string[]; new_skills: string[]; stable_skills: string[]; declining_skills: string[]; sample_insufficient_skills: string[] };
type EvolutionSource = Evolution | { jobs: Record<string, Evolution> };
type Overview = { metrics: { jd_count: number } };
type Jobs = { jobs: Array<{ standard_job_title: string; jd_count: number }> };
const focus = ["AI Agent开发工程师", "RAG引擎研发工程师", "AI安全技术工程师"];
export default function EvolutionPage() {
  const [title, setTitle] = useState(focus[0]); const [data, setData] = useState<Evolution | null>(null);
  const [systemJdCount, setSystemJdCount] = useState(0); const [jobJdCount, setJobJdCount] = useState(0);
  useEffect(() => {
    void getJson<Overview>("/api/system/overview", "/data/system_overview.json").then(result => setSystemJdCount(result.data.metrics.jd_count));
    void getJson<Jobs>("/api/jobs", "/data/jobs.json").then(result => setJobJdCount(result.data.jobs.find(job => job.standard_job_title === title)?.jd_count || 0));
  }, [title]);
  useEffect(() => {
    let cancelled = false;
    let recoveryTimer: ReturnType<typeof setTimeout> | undefined;
    const load = () => getJson<EvolutionSource>(`/api/evolution/job/${encodeURIComponent(title)}`, "/data/evolution_status.json").then((result) => {
      if (cancelled) return;
      const value = "jobs" in result.data ? result.data.jobs[title] : result.data;
      setData(value ? { ...value, job_title: title } : null);
      if (result.fallback) recoveryTimer = setTimeout(load, 15_000);
    });
    void load();
    return () => { cancelled = true; if (recoveryTimer) clearTimeout(recoveryTimer); };
  }, [title]);
  return <><PageIntro kicker="技能变化 · 时间趋势 · 样本说明" title="关注岗位能力要求的变化" description="了解不同岗位的核心技能、增长技能与新出现的能力要求。" />
    <div className="toolbar"><label>重点岗位<select value={title} onChange={(event) => setTitle(event.target.value)}>{focus.map((item) => <option key={item}>{item}</option>)}</select></label></div>
    {!data?.available ? <section className="missing-module"><div className="missing-icon"><DatabaseZap size={34} /></div><h2>{data?.message || "暂时没有可展示的趋势数据"}</h2><p>{data?.notice || "该岗位需要积累更多跨时间招聘样本后才能形成可靠趋势。"}</p><small><Clock3 size={14} /> 数据满足分析条件后将自动更新</small></section> : <><StatusBanner>{data.notice}</StatusBanner><div className="toolbar evolution-meta"><div className="data-chip">系统总JD {systemJdCount || "加载中"} 条</div><div className="data-chip">当前岗位JD {jobJdCount || data.support_jd_count} 条</div><div className="data-chip">演化有效样本 {data.support_jd_count} 条</div><div className="data-chip">观察时间 {data.time_range?.map((item) => item.slice(0, 10)).join(" 至 ") || "未标注"}</div></div><StatusBanner tone={data.sample_insufficient ? "warning" : "info"}>{data.sample_notice} 系统总JD与当前岗位、演化有效样本采用不同统计口径。</StatusBanner><div className="evolution-grid">{[["核心技能", data.core_skills], ["增长技能", data.growing_skills], ["新增技能", data.new_skills], ["稳定技能", data.stable_skills], ["下降技能", data.declining_skills]].map(([label, values]) => <article className="panel" key={label as string}><div className="panel-title"><span>{label as string}</span><small>{(values as string[]).length} 项</small></div><TagList values={values as string[]} empty="暂无可靠结果" /></article>)}{data.sample_insufficient ? <article className="panel"><div className="panel-title"><span>仍需更多样本</span><small>{data.sample_insufficient_skills.length} 项</small></div><TagList values={data.sample_insufficient_skills} empty="无" /></article> : null}</div></>}
    <ClosurePanel key={title} jobTitle={title} />
  </>;
}
