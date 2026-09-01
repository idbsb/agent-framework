// Explicit payload allowlists: placeholders and unrelated state never become evidence.
export type JDForm = { original_job_title: string; responsibilities: string; required_skills_raw: string; bonus_skills_raw: string; education: string; experience: string };
export type ResumeForm = { education: string; experience: string; work_experience: string; projects: string; skills_raw: string };

export function emptyForm<T extends Record<string, string>>(sample: T): T {
  return Object.fromEntries(Object.keys(sample).map(key => [key, ""])) as T;
}

export function jdPayload(form: JDForm) {
  const { original_job_title, responsibilities, required_skills_raw, bonus_skills_raw, education, experience } = form;
  return { jd_id: "JD-INPUT", original_job_title, responsibilities, required_skills_raw, bonus_skills_raw, education, experience };
}

export function resumePayload(form: ResumeForm, target_job: string) {
  const { education, experience, work_experience, projects, skills_raw } = form;
  return { resume_id: "RESUME-INPUT", target_job, education, experience, work_experience, projects, skills_raw };
}

export function matchPayload(form: ResumeForm, job_title: string) {
  return { job_title, resume: resumePayload(form, job_title) };
}
