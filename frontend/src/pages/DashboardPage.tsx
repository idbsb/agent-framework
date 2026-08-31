import { useEffect, useState } from "react";
import { Blocks, BriefcaseBusiness, Database, FileUser, Network, Radar } from "lucide-react";
import { Link } from "react-router-dom";
import { getJson } from "../api";
import DataQualityPanel from "../components/DataQuality";
import { StatusBanner } from "../components/Layout";

type Overview = { truth_statement: string; metrics: Record<string, number>; top_jobs: Array<{ job_title: string; jd_count: number }>; top_skills: Array<{ skill_name: string; evidence_jd_count: number }>; emerging_summary: Record<string, number>; emerging_candidates: Array<{ candidate_id: string; candidate_name: string; emerging_score: number }> };
const metrics = [["jd_count", "真实JD", Database], ["standard_job_count", "标准岗位", BriefcaseBusiness], ["standard_skill_count", "标准技能", Blocks], ["graph_node_count", "图谱节点", Network], ["graph_edge_count", "图谱关系", Radar], ["resume_count", "测试简历", FileUser]] as const;

export default function DashboardPage() {
  const [data, setData] = useState<Overview | null>(null); const [error, setError] = useState(""); const [fallback, setFallback] = useState(false);
  useEffect(() => { getJson<Overview>("/api/system/overview", "/data/system_overview.json").then((result) => { setData(result.data); setFallback(result.fallback); }).catch((reason: Error) => setError(reason.message)); }, []);
  return <>
    {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}{fallback ? <StatusBanner tone="warning">后端暂不可用，当前展示程序生成的真实静态结果。</StatusBanner> : null}
    <section className="hero-panel"><div><p className="kicker">真实数据 · 标准体系 · Evidence可追溯</p><h2>{data?.truth_statement || "正在读取真实招聘数据…"}</h2><p>从招聘JD到岗位能力图谱，再到简历解析、人岗匹配与新岗位候选发现。</p></div><div className="hero-index">01<span>/ 08</span></div></section>
    <section className="metric-grid">{metrics.map(([key, label, Icon]) => <article className="metric-card" key={key}><div className="metric-icon"><Icon size={19} /></div><div className="metric-value">{data?.metrics[key] ?? "—"}</div><div className="metric-label">{label}</div></article>)}</section>
    <DataQualityPanel />
    <section className="dashboard-grid">
      <article className="panel"><div className="panel-title"><span>重点岗位</span><small>按真实JD数量</small></div><div className="rank-list">{data?.top_jobs.slice(0, 6).map((item, index) => <div className="rank-row" key={item.job_title}><b>0{index + 1}</b><span>{item.job_title}</span><em>{item.jd_count} JD</em></div>)}</div></article>
      <article className="panel"><div className="panel-title"><span>热门技能</span><small>Evidence覆盖</small></div><div className="skill-cloud">{data?.top_skills.slice(0, 10).map((item) => <span key={item.skill_name}>{item.skill_name}<b>{item.evidence_jd_count}</b></span>)}</div></article>
      <article className="panel emerging-panel"><div className="panel-title"><span>新岗位候选</span><small>审慎发现</small></div><div className="emerging-number">{data?.emerging_summary.candidate_count ?? "—"}<span>个观察候选</span></div><p>高置信 {data?.emerging_summary.high_confidence ?? "—"} · 中置信 {data?.emerging_summary.medium_confidence ?? "—"} · 弱候选 {data?.emerging_summary.weak_candidate ?? "—"}</p><Link className="text-link" to="/emerging">查看候选 Evidence →</Link></article>
    </section>
  </>;
}

