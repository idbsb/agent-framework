from __future__ import annotations

import unittest

from src.api.app import app
from src.api.service import get_services
from src.schemas import JDParseRequest, ResumeParseRequest


class CoreSprintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.services = get_services()

    def test_frozen_data_ids_and_counts(self):
        result = self.services.loader.validate_frozen()
        self.assertTrue(result["passed"])
        self.assertEqual(result["row_counts"]["jds"], 191)
        self.assertEqual(result["row_counts"]["resumes"], 27)
        self.assertEqual(result["row_counts"]["skills"], 82)

    def test_skill_boundaries_and_evidence(self):
        items = self.services.skill_index.extract_fields([(
            "required_skills_raw",
            "开发MCP Server，使用Docker和Kubernetes部署；熟悉Linux与Shell；使用JavaScript和TypeScript。",
        )])
        names = {item.standard_skill_name for item in items}
        self.assertIn("MCP Server开发", names)
        self.assertNotIn("MCP", names)
        self.assertTrue({"Docker", "Kubernetes", "Linux", "Shell脚本", "JavaScript", "TypeScript"} <= names)
        self.assertTrue(all(item.evidence and item.skill_id.startswith("SKILL-") for item in items))

    def test_combination_split(self):
        names = {item.standard_skill_name for item in self.services.skill_index.extract_fields([
            ("required_skills_raw", "熟悉C/C++与Docker/Kubernetes")
        ])}
        self.assertTrue({"C", "C++", "Docker", "Kubernetes"} <= names)

    def test_jd_and_resume_schema(self):
        jd = self.services.jd_parser.parse(JDParseRequest(
            jd_id="JD-NEW", original_job_title="AI Agent开发工程师",
            required_skills_raw="Python、LangGraph、MCP", responsibilities="开发Agent工具调用工作流",
        ))
        self.assertTrue(jd.predicted_standard_job_title)
        self.assertIn("jd_id", jd.model_dump())
        resume = self.services.resume_parser.parse(ResumeParseRequest(
            resume_id="CV-NEW", target_job="AI Agent开发工程师",
            education="本科", experience="2年", projects="使用LangGraph开发Agent", skills_raw="Python、Docker",
        ))
        match = self.services.matching_engine.match(resume, "AI Agent开发工程师")
        self.assertIn("dimension_scores", match.model_dump())
        self.assertGreaterEqual(match.match_score, 0)

    def test_unconfirmed_job_requires_review(self):
        row = next(row for row in self.services.loader.load_jds() if row["jd_id"] == "JD-067")
        result = self.services.jd_parser.parse_row(row)
        self.assertTrue(result.need_human_review)

    def test_weights_are_configuration_driven(self):
        weights = self.services.matching_engine.weights
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertEqual(set(weights), {"required_skills", "bonus_skills", "projects", "experience", "education"})

    def test_fastapi_routes_and_openapi(self):
        paths = app.openapi()["paths"]
        self.assertTrue({"/api/jd/parse", "/api/resume/parse", "/api/match", "/api/jobs", "/api/skills"} <= set(paths))


if __name__ == "__main__":
    unittest.main()
