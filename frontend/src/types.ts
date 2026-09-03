export type JobOption = { standard_job_title: string; jd_count: number; profile_source?: string; profile_version?: number | null };
export type SkillEvidence = { skill_id: string; standard_skill_name: string; skill_type: string; confidence: number; evidence: string; source_field: string; accepted: boolean; polarity: "affirmed" | "negated" | "planned" | "other_person" | "uncertain"; matched_text: string; start: number | null; end: number | null; need_human_review: boolean; confidence_semantics: string; evidence_strength: "strong" | "medium" | "weak" };
export type GraphNode = { id: string; name: string; type: string; formal_type?: string; category?: string; standard_job_title?: string; standard_skill_name?: string; job_family?: string; technical_domain?: string; skill_category?: string };
export type GraphEdge = { id: string; source: string; target: string; frequency: number; edge_type?: string; relation?: string; relation_type?: string; job_title?: string; skill_name?: string; mention_count?: number; source_count?: number; confidence?: number; importance?: string; skill_level?: string; evidence?: string; evidence_jd_ids: string[]; evidence_count: number };
export type GraphPayload = { profile_source?: string; profile_version?: number | null; profile_id?: string | null; profile_fingerprint?: string | null; available: boolean; status: string; source_type?: string; source_label: string; source_file?: string; notice: string; nodes: GraphNode[]; edges: GraphEdge[]; summary: Record<string, number>; job_title?: string };
export type EmergingCandidate = {
  candidate_id: string; candidate_name: string; emerging_score: number; confidence_level: string; representative_titles: string[];
  core_skills: string[]; distinguishing_skills: string[]; jd_count: number; evidence_count: number; evidence_jd_ids: string[];
  representative_evidence: Array<{ jd_id: string; title: string; company: string; source: string; evidence: string; mapping_type?: string }>;
  evidence_records?: Array<{
    jd_id: string; evidence_id?: string; original_job_title: string; company: string; source: string; source_url: string;
    published_date: string; responsibilities: string; required_skills_raw: string; bonus_skills_raw: string;
    skills?: string[]; tools_and_frameworks?: string[]; mapping_type?: string; mapping_reason?: string;
    duplicate_status?: string; duplicate_of?: string; count_in_statistics?: boolean;
    source_verification_status?: string; evidence_confidence?: number;
  }>;
  source_count: number; company_count: number; relation_to_existing_jobs: string; why_emerging: string; need_human_review: boolean;
  counted_evidence_count?: number; exact_evidence_count?: number; supporting_evidence_count?: number;
  emerging_score_v1?: number | null; confidence_v1?: string; emerging_score_v2?: number; confidence_v2?: string;
  evidence_strength_v2?: number; score_version?: string;
};
