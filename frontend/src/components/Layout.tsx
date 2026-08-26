import { Activity, Blocks, BriefcaseBusiness, Database, FileSearch, FileUser, Network, Radar, Sparkles, TrendingUp, UserRoundSearch } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

const items = [
  ["/", "数据驾驶舱", Database],
  ["/jobs", "岗位分析", BriefcaseBusiness],
  ["/graph", "能力图谱", Network],
  ["/evolution", "动态演化", TrendingUp],
  ["/emerging", "新岗位发现", Sparkles],
  ["/jd-parse", "JD智能解析", FileSearch],
  ["/resume-parse", "简历智能分析", FileUser],
  ["/match", "人岗匹配", UserRoundSearch],
] as const;

export default function Layout() {
  const location = useLocation();
  const current = items.find(([path]) => path === location.pathname) || items[0];
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand-mark"><Sparkles size={19} /> TALENT GRAPH</div>
      <div className="brand-title">岗位与能力图谱<br />智能系统</div>
      <nav>{items.map(([path, label, Icon], index) => <NavLink end={path === "/"} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`} to={path} key={path}><span>0{index + 1}</span><Icon size={15} />{label}</NavLink>)}</nav>
      <div className="sidebar-foot"><Activity size={15} /> Evidence-bound AI</div>
    </aside>
    <main>
      <header className="topbar">
        <div><div className="eyebrow">MULTI-SOURCE TALENT INTELLIGENCE</div><h1>{current[1]}</h1></div>
        <div className="service-pill"><span />真实数据驱动</div>
      </header>
      <Outlet />
    </main>
  </div>;
}

export function PageIntro({ kicker, title, description, index }: { kicker: string; title: string; description: string; index: string }) {
  return <section className="hero-panel compact"><div><p className="kicker">{kicker}</p><h2>{title}</h2><p>{description}</p></div><div className="hero-index">{index}<span>/ 08</span></div></section>;
}

export function StatusBanner({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "warning" | "error" }) {
  return <div className={`status-banner ${tone}`}>{children}</div>;
}

export function TagList({ values, empty = "暂无" }: { values: string[]; empty?: string }) {
  return <div className="tag-list">{values.length ? values.map((item) => <span key={item}>{item}</span>) : <em>{empty}</em>}</div>;
}

