import SkillEvidenceView from "../components/SkillEvidenceView";
import { emptyForm, resumePayload } from "../formPayloads";
import { ChangeEvent, FormEvent, useState } from "react";
import { FileCheck2, FileUp, LoaderCircle, UserRound } from "lucide-react";
import { postFile, postJson } from "../api";
import { PageIntro, StatusBanner, TagList } from "../components/Layout";
import type { SkillEvidence } from "../types";

type ExperienceSource = "explicit" | "date_range_inferred" | "user_input" | "unknown";
type Result = {
  resume_id: string; name: string; phone: string; email: string; target_job: string; target_job_source: string;
  education: string; degree: string; major: string; experience: string; experience_source: ExperienceSource;
  work_experience: string; projects: string[]; skills: SkillEvidence[];
  core_skills_covered: string[]; bonus_skills_covered: string[]; weak_evidence_skills: string[];
  missing_skills: string[]; coverage_numerator: number; coverage_denominator: number;
  coverage_rate: number | null; need_human_review: boolean;
};
type Extracted = {
  file_name: string; file_type: "pdf" | "docx" | "txt"; raw_text: string; character_count: number;
  name: string; phone: string; email: string; target_job: string; target_job_source: string; education: string; degree: string;
  major: string; experience: string; experience_source: ExperienceSource; work_experience: string;
  projects: string; skills_raw: string; warnings: string[];
};
const example = {
  name: "李明", phone: "13800138000", email: "liming@example.com", target_job: "AI Agent开发工程师", target_job_source: "user_input",
  education: "硕士，人工智能专业", degree: "硕士", major: "人工智能", experience: "2年",
  experience_source: "user_input", work_experience: "负责企业智能体平台研发，使用Python和FastAPI构建后端服务。",
  projects: "使用LangGraph构建客服Agent，集成RAG知识库与向量数据库，并通过Docker部署。了解MCP。",
  skills_raw: "Python、LangGraph、RAG、MCP、FastAPI、Docker、向量数据库、Prompt Engineering",
};

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
      setForm(current => ({ ...current, name: extracted.name, phone: extracted.phone, email: extracted.email,
        target_job: extracted.target_job || current.target_job, target_job_source: extracted.target_job_source,
        education: extracted.education, degree: extracted.degree,
        major: extracted.major, experience: extracted.experience, experience_source: extracted.experience_source,
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
  return <><PageIntro kicker="简历内容 · 能力画像 · 技能依据" title="发现简历中的能力与亮点" description="上传简历或填写经历，快速梳理基本信息、工作与项目经验和可验证的技能信息。" />
    <div className="workbench-grid"><form className="panel form-panel" onSubmit={submit}>
      <div className="panel-title"><span>填写简历信息</span><small>支持文件上传或手动填写</small></div>
      <label className="resume-upload"><FileUp size={24}/><b>{uploading ? "正在提取简历…" : "上传 PDF / DOCX / TXT 简历"}</b><span>最大 8MB；文件仅在内存中解析，不保存到服务器</span><input data-testid="resume-file" type="file" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain" onChange={upload} disabled={uploading || loading}/></label>
      {notice ? <StatusBanner tone="info">{notice}</StatusBanner> : null}
      <div className="form-row"><label>姓名<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label><label>联系电话<input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label></div>
      <label>邮箱<input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
      <div className="form-row"><label>目标岗位<input value={form.target_job} onChange={(event) => setForm({ ...form, target_job: event.target.value, target_job_source: "user_input" })} /></label><label>学历<input value={form.education} onChange={(event) => setForm({ ...form, education: event.target.value })} /></label></div>
      <label>专业<input value={form.major} onChange={(event) => setForm({ ...form, major: event.target.value })} /></label>
      <label>工作经验<input value={form.experience} onChange={(event) => setForm({ ...form, experience: event.target.value, experience_source: "user_input" })} /></label>
      <label>工作经历<textarea rows={5} value={form.work_experience} onChange={(event) => setForm({ ...form, work_experience: event.target.value })} /></label>
      <label>项目经历<textarea rows={6} value={form.projects} onChange={(event) => setForm({ ...form, projects: event.target.value })} /></label>
      <label>技能清单<textarea rows={4} value={form.skills_raw} onChange={(event) => setForm({ ...form, skills_raw: event.target.value })} /></label>
      <button type="button" disabled={loading || uploading} onClick={() => { setForm({ ...example }); setResult(null); setError(""); setNotice(""); }}>加载示例</button>
      <button type="button" disabled={loading || uploading} onClick={() => { setForm(emptyForm(example)); setResult(null); setError(""); setNotice(""); }}>清空内容</button>
      <button className="primary-button" disabled={loading || uploading}>{loading ? <LoaderCircle className="spin" /> : <FileCheck2 />}开始分析</button>
      {error ? <StatusBanner tone="error">分析失败：{error}</StatusBanner> : null}
    </form><article className="panel result-panel"><div className="panel-title"><span>个人能力画像</span><small>基于标准技能体系</small></div>{result ? <>
      <div className="profile-header"><div className="avatar-block"><UserRound size={24} /></div><div><h2>{result.name || "姓名待补充"}</h2><p>{result.target_job || "暂未填写目标岗位"}{result.target_job_source === "content_inferred" || result.target_job_source === "filename_inferred" ? "（系统推断，请核对）" : ""}</p><p>{result.phone || result.email ? [result.phone, result.email].filter(Boolean).join(" · ") : "联系方式待补充"}</p></div></div>
      <div className="resume-summary"><p><b>学历与专业：</b>{result.education || result.degree || "待补充"}{result.major ? ` · ${result.major}` : ""}</p><p><b>工作经验：</b>{result.experience || "待补充"}{result.experience_source === "date_range_inferred" ? "（推算结果，请核对）" : ""}</p></div>
      <h3>工作经历</h3><p className="evidence-copy">{result.work_experience || "简历中未识别到工作或实习经历"}</p>
      <h3>项目经历</h3><ol className="detail-list">{result.projects.length ? result.projects.map((item) => <li key={item}>{item}</li>) : <li>简历中未识别到项目经历</li>}</ol>
      <h3>岗位能力覆盖</h3>{result.coverage_denominator ? <><div className="coverage-score"><b>{Math.round((result.coverage_rate || 0) * 100)}%</b><span>能力覆盖率 · {result.coverage_numerator}/{result.coverage_denominator} 项岗位要求具有可靠Evidence</span></div><div className="capability-grid"><div><h4>已覆盖核心技能</h4><TagList values={result.core_skills_covered} empty="暂无" /></div><div><h4>已覆盖加分技能</h4><TagList values={result.bonus_skills_covered} empty="暂无" /></div><div><h4>弱证据技能</h4><TagList values={result.weak_evidence_skills} empty="暂无" /></div><div><h4>缺失技能</h4><TagList values={result.missing_skills} empty="暂无" /></div></div></> : <StatusBanner tone="warning">当前目标岗位没有可用的标准技能要求，暂不计算能力覆盖率。</StatusBanner>}
      <SkillEvidenceView skills={result.skills} /><StatusBanner tone={result.need_human_review ? "warning" : "info"}>{result.need_human_review ? "部分内容的判断依据有限，建议检查原文" : "分析结果来自简历文本，不代表第三方能力认证"}</StatusBanner>
    </> : <div className="empty-state">上传简历或填写经历后，你的能力画像与技能依据将在这里显示。</div>}</article></div></>;
}
