export type Snippet = { job_id: string; source_field: string; text: string };
export type TextEvidence = { text: string; supporting_job_ids: string[]; evidence_snippets: Snippet[] };
export type SkillSupport = { skill_id: string; skill_name: string; coverage: number; evidence_count: number; supporting_job_ids: string[]; evidence_snippets: Snippet[] };
export type Definition = { job_name: string; job_name_supporting_job_ids?: string[]; core_responsibilities: TextEvidence[]; required_skills: SkillSupport[]; preferred_skills: SkillSupport[]; application_scenarios: TextEvidence[] };
export type JDEvidence = { job_id: string; original_title: string; company?: string; source?: string; published_at?: string | null; collected_at?: string | null; first_seen_at?: string | null; time_source?: string; url?: string; responsibilities?: string; required_skills_raw?: string; bonus_skills_raw?: string; industry?: string; scenario?: string; business_context?: string; skill_evidence?: Array<{skill_id: string; standard_skill_name: string; accepted: boolean; polarity: string}> };
export type Change = { skill_id: string; skill_name: string; before: number; after: number; before_role: string; after_role: string; before_evidence: JDEvidence[]; after_evidence: JDEvidence[] };
export type ChangeSet = { status: string; before_count: number; after_count: number; minimum_sample: number; mode: string; before_window: string; after_window: string; added_skills: Change[]; removed_skills: Change[]; modified_skills: Change[]; withheld_skills: SkillSupport[]; notice: string; excluded_undated_job_ids: string[] };
export type ClosureVersion = { kind: 'candidate' | 'profile'; id: string; version: number; previous_version: number | null; revision: number; status: string; created_at: string; fingerprint: string; auto_definition: Definition; manual_definition: Definition | null; evidence: JDEvidence[]; source_job_count: number; discovery_score?: number; company_count?: number; source_count?: number; change_set: ChangeSet | null; profile_version?: number; origin?: string; reviewer?: string; reviewed_at?: string; review_note?: string };
export type History = { versions: ClosureVersion[]; publications: ClosureVersion[]; events: Array<{event: string; version: number; at: string; reviewer?: string; note?: string}> };
export type VersionDiff = { added_skills: SkillSupport[]; removed_skills: SkillSupport[]; modified_skills: Array<{skill_id: string; before: SkillSupport; after: SkillSupport}>; responsibilities_changed: boolean; scenarios_changed: boolean; job_name_changed: boolean; evidence_count_before: number; evidence_count_after: number };
export const statusLabel: Record<string, string> = { candidate: '候选', pending_review: '待审核', approved: '已批准', rejected: '已驳回', published: '已发布' };

export function safeEvidenceUrl(value?: string): string | null {
  if (!value || /[\x00-\x20\\]/.test(value) || !/^https?:\/\//i.test(value)) return null;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && url.hostname && !url.username && !url.password ? value : null;
  } catch { return null; }
}
