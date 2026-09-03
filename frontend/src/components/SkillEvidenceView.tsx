import type { SkillEvidence } from "../types";
import { TagList } from "./Layout";

const labels = { affirmed: "正向陈述", negated: "明确否定", planned: "计划/正在学习", other_person: "他人/团队能力", uncertain: "不确定，待复核" };

export default function SkillEvidenceView({ skills }: { skills: SkillEvidence[] }) {
  const accepted = [...new Set(skills.filter(item => item.accepted && item.polarity === "affirmed").map(item => item.standard_skill_name))];
  return <>
    <h3>已识别技能</h3>
    <TagList values={accepted} empty="暂无可接受的正向技能证据" />
    <h3>技能判断依据</h3>
    <p>抽取置信度表示简历或职位文本与技能识别规则的匹配强度，不代表候选人真实掌握该技能的概率。</p>
    {skills.map((item, index) => <div className="evidence-line" key={`${item.skill_id}:${item.source_field}:${item.start}:${index}`}>
      <b>{item.standard_skill_name}</b>
      <span>“{item.evidence}” · {item.source_field} · {labels[item.polarity] || "信息不足，待复核"}{item.need_human_review ? " · 需人工复核" : ""}</span>
      <em>抽取置信度 {Math.round(item.confidence * 100)}%</em>
    </div>)}
  </>;
}
