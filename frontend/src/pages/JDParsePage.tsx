import SkillEvidenceView from "../components/SkillEvidenceView";
import { emptyForm, jdPayload } from "../formPayloads";
import { FormEvent, useState } from "react";
import { LoaderCircle, SearchCheck } from "lucide-react";
import { postJson } from "../api";
import { PageIntro, StatusBanner } from "../components/Layout";
import type { SkillEvidence } from "../types";

type Result = { jd_id: string; predicted_standard_job_title: string; job_confidence: number; responsibilities: string; education: string; experience: string; skills: SkillEvidence[]; evidence: string[]; need_human_review: boolean };
const example = { original_job_title: "AI Agent开发工程师", responsibilities: "负责企业级智能体工作流开发，实现任务规划、工具调用与多步推理。", required_skills_raw: "熟悉Python、LangGraph、RAG、MCP和Docker，具备Prompt Engineering经验。", bonus_skills_raw: "有FastAPI与向量数据库项目经验优先。", education: "本科及以上", experience: "2年以上" };

export default function JDParsePage() {
  const [form, setForm] = useState(() => emptyForm(example));
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setLoading(true); setError("");
    try { setResult(await postJson<Result>("/api/jd/parse", jdPayload(form))); }
    catch (reason) { setError((reason as Error).message); }
    finally { setLoading(false); }
  };
  return <>
    <PageIntro kicker="职位要求 · 技能提取 · 信息依据" title="快速看懂一份职位描述" description="填写或粘贴招聘信息，系统将整理岗位名称、技能要求与需要关注的内容。" />
    <div className="workbench-grid">
      <form className="panel form-panel" onSubmit={submit}>
        <div className="panel-title"><span>职位信息</span><small>填写招聘内容</small></div>
        <label>职位名称<input value={form.original_job_title} onChange={(event) => setForm({ ...form, original_job_title: event.target.value })} required /></label>
        <label>工作职责<textarea rows={6} value={form.responsibilities} onChange={(event) => setForm({ ...form, responsibilities: event.target.value })} /></label>
        <label>必备技能<textarea rows={5} value={form.required_skills_raw} onChange={(event) => setForm({ ...form, required_skills_raw: event.target.value })} /></label>
        <label>加分技能原文<textarea rows={4} value={form.bonus_skills_raw} onChange={(event) => setForm({ ...form, bonus_skills_raw: event.target.value })} /></label>
        <div className="form-row"><label>学历要求<input value={form.education} onChange={(event) => setForm({ ...form, education: event.target.value })} /></label><label>经验要求<input value={form.experience} onChange={(event) => setForm({ ...form, experience: event.target.value })} /></label></div>
        <button type="button" disabled={loading} onClick={() => { setForm({ ...example }); setResult(null); setError(""); }}>加载示例</button>
        <button type="button" disabled={loading} onClick={() => { setForm(emptyForm(example)); setResult(null); setError(""); }}>清空内容</button>
        <button className="primary-button" disabled={loading}>{loading ? <LoaderCircle className="spin" /> : <SearchCheck />}解析职位</button>
        {error ? <StatusBanner tone="error">解析失败：{error}</StatusBanner> : null}
      </form>
      <article className="panel result-panel">
        <div className="panel-title"><span>职位解析结果</span><small>基于标准岗位与技能体系</small></div>
        {result ? <><div className="prediction"><span>对应的标准岗位</span><h2>{result.predicted_standard_job_title || "暂未识别"}</h2><b>{Math.round(result.job_confidence * 100)}% 岗位名称匹配强度</b></div><SkillEvidenceView skills={result.skills} /><StatusBanner tone={result.need_human_review ? "warning" : "info"}>{result.need_human_review ? "部分信息需要进一步确认" : "当前信息较为完整"} · {result.evidence.join("；")}</StatusBanner></> : <div className="empty-state">填写职位信息并开始解析后，岗位要求与技能依据将在这里显示。</div>}
      </article>
    </div>
  </>;
}
