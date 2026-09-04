import { Activity, BriefcaseBusiness, Database, FileUser, Menu, Network, RadioTower, Sparkles, TrendingUp, UserRoundSearch, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

const items = [
  ["/", "首页 · 求职数据概览", Database, "招聘市场变化驱动的岗位能力图谱"],
  ["/jobs", "岗位", BriefcaseBusiness, "看懂目标岗位的真实要求"],
  ["/multi-source", "多源数据", RadioTower, "查看招聘数据与外部佐证"],
  ["/job-changes", "岗位变化", TrendingUp, "查看岗位演化与能力要求变化"],
  ["/graph", "动态能力图谱", Network, "探索岗位与技能的动态关系"],
  ["/resume-parse", "简历分析", FileUser, "识别个人经历与技能亮点"],
  ["/match", "精准人岗匹配与差距分析", UserRoundSearch, "使用最新图谱评估匹配与能力差距"],
] as const;

export default function Layout() {
  const location = useLocation();
  const current = items.find(([path]) => path === location.pathname) || items[0];
  const [menuOpen, setMenuOpen] = useState(false);
  return <div className="app-shell">
    <button className="mobile-menu" aria-label={menuOpen ? "关闭导航" : "打开导航"} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X /> : <Menu />}</button>
    {menuOpen ? <button className="sidebar-backdrop" aria-label="关闭导航" onClick={() => setMenuOpen(false)} /> : null}
    <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
      <div className="brand-block"><div className="brand-icon"><Network size={22} /></div><div><div className="brand-title">职涌</div><p>岗位能力与智能匹配平台</p></div></div>
      <nav aria-label="主要功能">{items.map(([path, label, Icon]) => <NavLink end={path === "/"} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`} to={path} key={path} onClick={() => setMenuOpen(false)}><Icon size={18} />{label}</NavLink>)}</nav>
      <div className="sidebar-foot"><Activity size={15} /><span>职涌 · 求职决策智能体</span></div>
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
