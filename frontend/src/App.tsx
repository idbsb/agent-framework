import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const JobAnalysisPage = lazy(() => import("./pages/JobAnalysisPage"));
const GraphPage = lazy(() => import("./pages/GraphPage"));
const EvolutionPage = lazy(() => import("./pages/EvolutionPage"));
const EmergingPage = lazy(() => import("./pages/EmergingPage"));
const JDParsePage = lazy(() => import("./pages/JDParsePage"));
const ResumeParsePage = lazy(() => import("./pages/ResumeParsePage"));
const MatchPage = lazy(() => import("./pages/MatchPage"));
const MultiSourcePage = lazy(() => import("./pages/MultiSourcePage"));
const JobChangesPage = lazy(() => import("./pages/JobChangesPage"));

export default function App() {
  return <Suspense fallback={<div className="empty-state">正在加载页面…</div>}><Routes><Route element={<Layout />}>
    <Route path="/" element={<DashboardPage />} />
    <Route path="/jobs" element={<JobAnalysisPage />} />
    <Route path="/multi-source" element={<MultiSourcePage />} />
    <Route path="/job-changes" element={<JobChangesPage />} />
    <Route path="/graph" element={<GraphPage />} />
    <Route path="/evolution" element={<EvolutionPage />} />
    <Route path="/emerging" element={<EmergingPage />} />
    <Route path="/jd-parse" element={<JDParsePage />} />
    <Route path="/resume-parse" element={<ResumeParsePage />} />
    <Route path="/match" element={<MatchPage />} />
    <Route path="/gap-analysis" element={<MatchPage />} />
  </Route></Routes></Suspense>;
}
