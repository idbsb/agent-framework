import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import DashboardPage from "./pages/DashboardPage";
import JobAnalysisPage from "./pages/JobAnalysisPage";
import GraphPage from "./pages/GraphPage";
import EvolutionPage from "./pages/EvolutionPage";
import EmergingPage from "./pages/EmergingPage";
import JDParsePage from "./pages/JDParsePage";
import ResumeParsePage from "./pages/ResumeParsePage";
import MatchPage from "./pages/MatchPage";

export default function App() {
  return <Routes><Route element={<Layout />}>
    <Route path="/" element={<DashboardPage />} />
    <Route path="/jobs" element={<JobAnalysisPage />} />
    <Route path="/graph" element={<GraphPage />} />
    <Route path="/evolution" element={<EvolutionPage />} />
    <Route path="/emerging" element={<EmergingPage />} />
    <Route path="/jd-parse" element={<JDParsePage />} />
    <Route path="/resume-parse" element={<ResumeParsePage />} />
    <Route path="/match" element={<MatchPage />} />
  </Route></Routes>;
}
