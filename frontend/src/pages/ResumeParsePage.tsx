import SkillEvidenceView from "../components/SkillEvidenceView";
import { emptyForm, resumePayload } from "../formPayloads";
import { ChangeEvent, FormEvent, useState } from "react";
import { FileCheck2, FileUp, LoaderCircle } from "lucide-react";
import { postFile, postJson } from "../api";
import { PageIntro, StatusBanner } from "../components/Layout";
import type { SkillEvidence } from "../types";

type Result = { resume_id: string; target_job: string; education: string; experience: string; work_experience: string; projects: string[]; skills: SkillEvidence[]; need_human_review: boolean };
type Extracted = { file_name: string; file_type: "pdf" | "docx" | "txt"; raw_text: string; character_count: number; education: string; experience: string; work_experience: string; projects: string; skills_raw: string; warnings: string[] };
const example = { target_job: "AI Agent开发工程师", education: "硕士，人工智能", experience: "2年", work_experience: "负责企业智能体平台研发，使用Python和FastAPI构建后端服务。", projects: "使用LangGraph构建客服Agent，集成RAG知识库、MCP工具调用与向量数据库，并通过Docker部署。", skills_raw: "Python、LangGraph、RAG、MCP、FastAPI、Docker、向量数据库、Prompt Engineering" };

export default function ResumeParsePage() {
  const [form, setForm] = useState(() => emptyForm(example));
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  const upload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploading(true); setError(""); setNotice(""); setResult(null);
    try {
      const extracted = await postFile<Extracted>("/api/resume/extract", file);
      setForm(current => ({ ...current, education: extracted.education, experience: extracted.experience,
        work_experience: extracted.work_experience, projects: extracted.projects, skills_raw: extracted.skills_raw }));
      const warning = extracted.warnings.length ? ` ${extracted.warnings.join("；")}` : "";
      setNotice(`已从 ${extracted.file_name} 提取 ${extracted.character_count} 个字符。请检查下方内容后再分析。${warning}`);
    } catch (reason) { setError((reason as Error).message); }
    finally { setUploading(false); }
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setLoading(true); setError("");
    try { setResult(await postJson<Result>("/api/resume/parse", resumePayload(form, form.target_job))); }
    catch (reason) { setError((reason as Error).message); }
    finally { setLoading(false); }
  };
  return <><PageIntro kicker="文件上传 · 能力画像 · Evidence输出" title="简历智能分析" description="支持PDF、DOCX、TXT简历文本提取；确认内容后进入标准技能解析。" index="07" />
    <div className="workbench-grid"><form className="panel form-panel" onSubmit={submit}>
      <div className="panel-title"><span>简历输入</span><small>文件 / 文本</small></div>
      <label className="resume-upload"><FileUp size={24}/><b>{uploading ? "正在提取简历…" : "上传 PDF / DOCX / TXT 简历"}</b><span>最大 8MB；文件仅在内存中解析，不保存到服务器</span><input data-testid="resume-file" type="file" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain" onChange={upload} disabled={uploading || loading}/></label>
      {notice ? <StatusBanner tone="info">{notice}</StatusBanner> : null}
      <div className="form-row"><label>目标岗位<input value={form.target_job} onChange={(event) => setForm({ ...form, target_job: event.target.value })} /></label><label>学历<input value={form.education} onChange={(event) => setForm({ ...form, education: event.target.value })} /></label></div>
      <label>工作经验<input value={form.experience} onChange={(event) => setForm({ ...form, experience: event.target.value })} /></label>
      <label>工作经历<textarea rows={5} value={form.work_experience} onChange={(event) => setForm({ ...form, work_experience: event.target.value })} /></label>
      <label>项目经历<textarea rows={6} value={form.projects} onChange={(event) => setForm({ ...form, projects: event.target.value })} /></label>
      <label>技能清单<textarea rows={4} value={form.skills_raw} onChange={(event) => setForm({ ...form, skills_raw: event.target.value })} /></label>
      <button type="button" disabled={loading || uploading} onClick={() => { setForm({ ...example }); setResult(null); setError(""); setNotice(""); }}>加载示例</button>
      <button type="button" disabled={loading || uploading} onClick={() => { setForm(emptyForm(example)); setResult(null); setError(""); setNotice(""); }}>清空</button>
      <button className="primary-button" disabled={loading || uploading}>{loading ? <LoaderCircle className="spin" /> : <FileCheck2 />}分析简历</button>
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
    </form><article className="panel result-panel"><div className="panel-title"><span>能力画像</span><small>标准技能体系</small></div>{result ? <><div className="profile-header"><div className="avatar-block">CV</div><div><h2>{result.target_job || "未指定目标岗位"}</h2><p>{result.education || "学历信息不足 / 待补充"} · {result.experience || "经验信息不足 / 待补充"}</p></div></div><h3>项目经历</h3><ol className="detail-list">{result.projects.map((item) => <li key={item}>{item}</li>)}</ol><SkillEvidenceView skills={result.skills} /><StatusBanner tone={result.need_human_review ? "warning" : "info"}>{result.need_human_review ? "存在低确定性信息，建议人工复核" : "已按文本证据解析，不代表实际能力认证"}</StatusBanner></> : <div className="empty-state">上传文件或填写简历文本后，能力画像与技能Evidence将在这里显示。</div>}</article></div></>;
}
