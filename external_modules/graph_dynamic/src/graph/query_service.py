from __future__ import annotations
import json
from pathlib import Path


class GraphQueryService:
    def __init__(self, root: str | Path):
        out = Path(root) / "outputs"
        self.graph = json.loads((out / "knowledge_graph_v1.json").read_text(encoding="utf-8"))
        self.evolution = json.loads((out / "key_job_evolution_v1.json").read_text(encoding="utf-8"))

    def get_job_graph(self, job_title):
        jobs = [n for n in self.graph["nodes"] if n.get("label") == job_title and n.get("type") == "Job"]
        if not jobs: return {"job": None, "skills": [], "edges": []}
        jid = jobs[0]["id"]; edges = [e for e in self.graph["edges"] if e["source"] == jid]
        ids = {e["target"] for e in edges}; return {"job": jobs[0], "skills": [n for n in self.graph["nodes"] if n["id"] in ids], "edges": edges}

    def get_job_skills(self, job_title): return self.get_job_graph(job_title)["skills"]
    def get_skill_jobs(self, skill_id):
        edges = [e for e in self.graph["edges"] if e["target"] == skill_id and e["source"].startswith("JOB-")]
        ids = {e["source"] for e in edges}; return {"jobs": [n for n in self.graph["nodes"] if n["id"] in ids], "edges": edges}
    def get_job_evolution(self, job_title): return self.evolution.get("jobs", {}).get(job_title, {})
    def get_skill_evolution(self, skill_id):
        return {j: [r for r in v.get("records", []) if r["skill_id"] == skill_id] for j, v in self.evolution.get("jobs", {}).items()}


_service = None
def configure(root):
    global _service; _service = GraphQueryService(root); return _service
def get_job_graph(job_title): return _service.get_job_graph(job_title)
def get_job_skills(job_title): return _service.get_job_skills(job_title)
def get_skill_jobs(skill_id): return _service.get_skill_jobs(skill_id)
def get_job_evolution(job_title): return _service.get_job_evolution(job_title)
def get_skill_evolution(skill_id): return _service.get_skill_evolution(skill_id)
