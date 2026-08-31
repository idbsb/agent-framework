import { useEffect, useState } from "react";
import { Clock3, DatabaseZap } from "lucide-react";
import { getJson } from "../api";
import { PageIntro, StatusBanner, TagList } from "../components/Layout";
import ClosurePanel from "../components/ClosurePanel";

type Evolution = { available: boolean; status: string; job_title: string; message: string; notice: string; time_range: string[] | null; support_jd_count: number; sample_insufficient: boolean; sample_notice: string; core_skills: string[]; growing_skills: string[]; new_skills: string[]; stable_skills: string[]; declining_skills: string[]; sample_insufficient_skills: string[] };
type EvolutionSource = Evolution | { jobs: Record<string, Evolution> };
const focus = ["AI Agent开发工程师", "RAG引擎研发工程师", "AI安全技术工程师"];
export default function EvolutionPage() {
  const [title, setTitle] = useState(focus[0]); const [data, setData] = useState<Evolution | null>(null); const [fallback, setFallback] = useState(false);
  useEffect(() => { getJson<EvolutionSource>(`/api/evolution/job/${encodeURIComponent(title)}`, "/data/evolution_status.json").then((result) => { const value = "jobs" in result.data ? result.data.jobs[title] : result.data; setData(value ? { ...value, job_title: title } : null); setFallback(result.fallback); }); }, [title]);
  return <><PageIntro kicker="近期观察 · 时间范围 · 样本约束" title="岗位技能动态演化" description="只展示组员A正式演化结果；不根据当前数据自行生成趋势。" index="04" />
    <div className="toolbar"><label>重点岗位<select value={title} onChange={(event) => setTitle(event.target.value)}>{focus.map((item) => <option key={item}>{item}</option>)}</select></label></div>
    {fallback ? <StatusBanner tone="warning">后端暂不可用，已读取静态正式演化结果。</StatusBanner> : null}
    {!data?.available ? <section className="missing-module"><div className="missing-icon"><DatabaseZap size={34} /></div><div className="eyebrow">ADAPTER READY</div><h2>{data?.message || "动态演化数据尚未接入"}</h2><p>{data?.notice}</p><div className="adapter-flow"><span>key_job_evolution_v1.json</span><b>→</b><span>Evolution Adapter</span><b>→</b><span>当前页面</span></div><small><Clock3 size={14} /> 文件补入后无需修改前端页面</small></section> : <><StatusBanner>{data.notice}</StatusBanner><div className="toolbar evolution-meta"><div className="data-chip">样本量 {data.support_jd_count} 条JD</div><div className="data-chip">时间范围 {data.time_range?.map((item) => item.slice(0, 10)).join(" 至 ") || "未标注"}</div></div><StatusBanner tone={data.sample_insufficient ? "warning" : "info"}>{data.sample_notice}</StatusBanner><div className="evolution-grid">{[["核心技能", data.core_skills], ["增长技能", data.growing_skills], ["新增技能", data.new_skills], ["稳定技能", data.stable_skills], ["下降技能", data.declining_skills]].map(([label, values]) => <article className="panel" key={label as string}><div className="panel-title"><span>{label as string}</span><small>{(values as string[]).length}</small></div><TagList values={values as string[]} empty="暂无正式结果" /></article>)}{data.sample_insufficient ? <article className="panel"><div className="panel-title"><span>样本不足</span><small>{data.sample_insufficient_skills.length}</small></div><TagList values={data.sample_insufficient_skills} empty="无" /></article> : null}</div></>}
    <ClosurePanel key={title} jobTitle={title} />
  </>;
}
