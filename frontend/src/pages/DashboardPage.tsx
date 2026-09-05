import { useEffect, useState } from "react";
import { Blocks, BriefcaseBusiness, Database, FileUser, Network, Radar } from "lucide-react";
import { Link } from "react-router-dom";
import { getJson } from "../api";
import { StatusBanner } from "../components/Layout";

type Overview = { truth_statement: string; metrics: Record<string, number>; top_jobs: Array<{ job_title: string; jd_count: number }>; top_skills: Array<{ skill_name: string; evidence_jd_count: number }>; emerging_summary: Record<string, number>; emerging_candidates: Array<{ candidate_id: string; candidate_name: string; emerging_score: number }> };
const metrics = [["jd_count", "真实JD", Database], ["standard_job_count", "标准岗位", BriefcaseBusiness], ["standard_skill_count", "标准技能", Blocks], ["graph_node_count", "图谱节点", Network], ["graph_edge_count", "图谱关系", Radar], ["resume_count", "测试简历", FileUser]] as const;

export default function DashboardPage() {
  const [data, setData] = useState<Overview | null>(null); const [error, setError] = useState("");
  useEffect(() => { getJson<Overview>("/api/system/overview", "/data/system_overview.json").then((result) => setData(result.data)).catch((reason: Error) => setError(reason.message)); }, []);
  return <>
    {error ? <StatusBanner tone="error">数据加载失败：{error}</StatusBanner> : null}
    <section className="hero-panel"><div><p className="kicker">真实招聘数据 · 招聘市场变化驱动 · 动态岗位能力图谱</p><h2>{data?.truth_statement || "正在读取岗位与技能数据…"}</h2><p>以多源真实证据持续发现岗位变化、更新能力要求，并将最新岗位画像用于简历解析、精准匹配和差距分析。</p></div></section>
    <section className="closure-flow"><Link to="/multi-source">多源数据采集</Link><span>→</span><Link to="/job-changes">新岗位发现与定义 / 既有岗位能力更新</Link><span>→</span><Link to="/graph">动态能力图谱</Link><span>→</span><Link to="/resume-parse">简历解析</Link><span>→</span><Link to="/match">精准匹配与差距分析</Link></section>
    <section className="metric-grid">{metrics.map(([key, label, Icon]) => <article className="metric-card" key={key}><div className="metric-icon"><Icon size={19} /></div><div className="metric-value">{data?.metrics[key] ?? "—"}</div><div className="metric-label">{label}</div></article>)}</section>
    <section className="dashboard-grid">
      <article className="panel"><div className="panel-title"><span>热门岗位</span><small>按招聘信息数量</small></div><div className="rank-list">{data?.top_jobs.slice(0, 6).map((item, index) => <div className="rank-row" key={item.job_title}><b>{String(index + 1).padStart(2, "0")}</b><span>{item.job_title}</span><em>{item.jd_count} 条职位</em></div>)}</div></article>
      <article className="panel"><div className="panel-title"><span>高频技能</span><small>招聘信息覆盖量</small></div><div className="skill-cloud">{data?.top_skills.slice(0, 10).map((item) => <span key={item.skill_name}>{item.skill_name}<b>{item.evidence_jd_count}</b></span>)}</div></article>
      <article className="panel emerging-panel"><div className="panel-title"><span>新岗位机会</span><small>基于多源信息发现</small></div><div className="emerging-number">{data?.emerging_summary.candidate_count ?? "—"}<span>个观察方向</span></div><p>高置信 {data?.emerging_summary.high_confidence ?? "—"} · 中置信 {data?.emerging_summary.medium_confidence ?? "—"} · 持续观察 {data?.emerging_summary.weak_candidate ?? "—"}</p><Link className="text-link" to="/emerging">查看岗位机会与依据 →</Link></article>
    </section>
  </>;
}
