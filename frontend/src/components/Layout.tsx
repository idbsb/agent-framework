import { Activity, BriefcaseBusiness, Database, FileSearch, FileUser, Menu, Network, Sparkles, TrendingUp, UserRoundSearch, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

const items = [
  ["/", "求职数据概览", Database, "了解岗位与技能趋势"],
  ["/jobs", "岗位分析", BriefcaseBusiness, "看懂目标岗位的真实要求"],
  ["/graph", "岗位能力图谱", Network, "探索岗位与技能之间的关系"],
  ["/evolution", "技能趋势", TrendingUp, "关注岗位能力要求的变化"],
  ["/emerging", "新岗位机会", Sparkles, "发现正在形成的职业方向"],
  ["/jd-parse", "职位解析", FileSearch, "快速提取职位核心要求"],
  ["/resume-parse", "简历分析", FileUser, "识别个人经历与技能亮点"],
  ["/match", "人岗匹配", UserRoundSearch, "评估差距并规划提升路径"],
] as const;

export default function Layout() {
  const location = useLocation();
  const current = items.find(([path]) => path === location.pathname) || items[0];
  const [menuOpen, setMenuOpen] = useState(false);
  return <div className="app-shell">
    <button className="mobile-menu" aria-label={menuOpen ? "关闭导航" : "打开导航"} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X /> : <Menu />}</button>
    {menuOpen ? <button className="sidebar-backdrop" aria-label="关闭导航" onClick={() => setMenuOpen(false)} /> : null}
    <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
      <div className="brand-block"><div className="brand-icon"><Network size={22} /></div><div><div className="brand-title">岗位能力图谱</div><p>岗位能力与智能匹配平台</p></div></div>
      <nav aria-label="主要功能">{items.map(([path, label, Icon]) => <NavLink end={path === "/"} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`} to={path} key={path} onClick={() => setMenuOpen(false)}><Icon size={18} />{label}</NavLink>)}</nav>
      <div className="sidebar-foot"><Activity size={15} /><span>求职决策辅助</span></div>
    </aside>
    <main><header className="topbar"><div><h1>{current[1]}</h1><p>{current[3]}</p></div><div className="service-pill"><span />真实数据依据</div></header><div className="page-content"><Outlet /></div></main>
  </div>;
}

export function PageIntro({ kicker, title, description }: { kicker: string; title: string; description: string }) {
  return <section className="page-intro"><div className="intro-icon"><Sparkles size={18} /></div><div><p className="kicker">{kicker}</p><h2>{title}</h2><p>{description}</p></div></section>;
}

export function StatusBanner({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "warning" | "error" }) {
  return <div className={`status-banner ${tone}`} role={tone === "error" ? "alert" : "status"}>{children}</div>;
}

export function TagList({ values, empty = "暂无" }: { values: string[]; empty?: string }) {
  return <div className="tag-list">{values.length ? values.map((item) => <span key={item}>{item}</span>) : <em>{empty}</em>}</div>;
}
