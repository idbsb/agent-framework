import type { SkillEvidence } from "../types";
import { TagList } from "./Layout";

const labels = { affirmed: "正向陈述", negated: "明确否定", planned: "计划/正在学习", other_person: "他人/团队能力", uncertain: "不确定，待复核" };
const strengthLabels = { strong: "强 Evidence", medium: "中等 Evidence", weak: "弱 Evidence" };

export default function SkillEvidenceView({ skills }: { skills: SkillEvidence[] }) {
  const accepted = [...new Set(skills.filter(item => item.accepted && item.polarity === "affirmed").map(item => item.standard_skill_name))];
  return <>
    <h3>已识别技能</h3>
    <TagList values={accepted} empty="暂无可接受的正向技能证据" />
    <h3>技能判断依据</h3>
    <p>Evidence强度根据简历原文中的实践行为、技能陈述和提及语气判定。系统内部的规则匹配强度不代表技能熟练度、岗位胜任概率或录用概率。</p>
    {skills.map((item, index) => <div className="evidence-line" key={`${item.skill_id}:${item.source_field}:${item.start}:${index}`}>
      <b>{item.standard_skill_name}</b>
      <span>“{item.evidence}” · {item.source_field} · {labels[item.polarity] || "信息不足，待复核"}{item.need_human_review ? " · 需人工复核" : ""}</span>
      <em className={`evidence-strength evidence-${item.evidence_strength}`}>{strengthLabels[item.evidence_strength]}</em>
    </div>)}
  </>;
}
