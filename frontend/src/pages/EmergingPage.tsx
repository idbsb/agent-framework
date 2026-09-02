import { useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, ShieldAlert, X } from "lucide-react";
import { getJson } from "../api";
import { PageIntro, StatusBanner, TagList } from "../components/Layout";
import type { EmergingCandidate } from "../types";
import ClosurePanel from "../components/ClosurePanel";

type Payload = { available: boolean; notice: string; summary: { candidate_count: number; high_confidence: number; medium_confidence: number; weak_candidate: number }; candidates: EmergingCandidate[] };
export default function EmergingPage() {
  const [data, setData] = useState<Payload | null>(null); const [selected, setSelected] = useState<EmergingCandidate | null>(null); const [fallback, setFallback] = useState(false);
  useEffect(() => { getJson<Payload>("/api/emerging-jobs", "/data/emerging_jobs_v1.json").then((result) => { setData(result.data); setFallback(result.fallback); }); }, []);
  return <><PageIntro kicker="真实标题 · 异常组合 · 多源Evidence" title="新岗位候选发现" description="候选由透明规则发现；单条异常JD不会被包装成高置信新岗位。" index="05" />
    {fallback ? <StatusBanner tone="warning">后端暂不可用，展示程序生成的真实候选JSON。</StatusBanner> : null}<StatusBanner>{data?.notice}</StatusBanner>
    <section className="candidate-summary"><div><b>{data?.summary.candidate_count ?? 0}</b><span>全部候选</span></div><div className="high"><b>{data?.summary.high_confidence ?? 0}</b><span>高置信</span></div><div className="medium"><b>{data?.summary.medium_confidence ?? 0}</b><span>中置信</span></div><div className="weak"><b>{data?.summary.weak_candidate ?? 0}</b><span>弱候选</span></div></section>
    <section className="candidate-grid">{data?.candidates.map((item) => <article className="candidate-card" key={item.candidate_id}><div className="candidate-top"><span>{item.candidate_id}</span><em className={`confidence ${item.confidence_level.startsWith("中") ? "medium" : "weak"}`}>{item.confidence_level}</em></div><div className="score-ring"><b>{item.emerging_score}</b><span>EmergingScore</span></div><h2>{item.candidate_name}</h2><p>{item.why_emerging}</p><div className="candidate-stats"><span>{item.evidence_count}<small>Evidence</small></span><span>{item.company_count}<small>企业</small></span><span>{item.source_count}<small>来源</small></span></div><TagList values={item.core_skills.slice(0, 5)} empty="当前标准技能证据不足" /><button onClick={() => setSelected(item)}>查看完整证据 <ArrowRight size={14} /></button></article>)}</section>
    {selected ? <div className="drawer-backdrop" onClick={() => setSelected(null)}><aside className="detail-drawer" onClick={(event) => event.stopPropagation()}><button className="drawer-close" onClick={() => setSelected(null)} aria-label="关闭"><X /></button><div className="eyebrow">{selected.candidate_id}</div><h1>{selected.candidate_name}</h1><div className="drawer-score">{selected.emerging_score}<span>{selected.confidence_level}</span></div><h3>为何被识别</h3><p>{selected.why_emerging}</p><h3>与已有岗位关系</h3><p>{selected.relation_to_existing_jobs}</p><h3>核心技能</h3><TagList values={selected.core_skills} /><h3>差异技能</h3><TagList values={selected.distinguishing_skills} /><h3>Evidence JD（{selected.evidence_count}）</h3>{selected.representative_evidence.map((item) => <article className="evidence-card" key={item.jd_id}><div><b>{item.jd_id}</b><span>{item.company} · {item.source}</span></div><h4>{item.title}</h4><p>{item.evidence}</p></article>)}<div className="review-note"><ShieldAlert size={16} /> 所有候选均需人工复核；本结果不等同于正式新职业。</div><div className="review-note good"><CheckCircle2 size={16} /> evidence_jd_ids：{selected.evidence_jd_ids.join("、")}</div></aside></div> : null}
    <ClosurePanel />
  </>;
}

