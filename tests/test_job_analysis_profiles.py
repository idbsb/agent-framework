from __future__ import annotations

import json
import unittest
from collections import Counter

from src.api.service import get_services
from src.integration.system_data import SystemDataService


UNKNOWN = "招聘信息未明确"


class JobAnalysisProfileRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        get_services.cache_clear()
        cls.services = get_services()
        cls.system = SystemDataService(cls.services)

    def test_latest_job_analysis_source_conserves_supplemental_records(self):
        base = self.services.loader.load_jds()
        payload = json.loads(
            (self.services.loader.project_root / "data/external/supplemental_jd_v3.json").read_text(encoding="utf-8")
        )
        expected_supplemental = sum(bool(row["count_in_statistics"]) for row in payload["records"])
        analysis_rows = self.services.loader.load_job_analysis_jds()
        self.assertEqual(len(analysis_rows), len(base) + expected_supplemental)
        self.assertEqual(len(payload["records"]), 49)  # PROTECTED_NEW_DATA conservation guard
        self.assertEqual(sum(row["jd_id"].startswith("SUP-JD-") for row in analysis_rows), expected_supplemental)

    def test_every_job_uses_one_traceable_aggregate_profile(self):
        rows = self.services.loader.load_job_analysis_jds()
        counts = Counter(row["standard_job_title"] for row in rows if row["standard_job_title"])
        self.assertGreater(len(counts), 3)
        for title, count in counts.items():
            with self.subTest(title=title):
                result = self.system.job_analysis(title)
                self.assertTrue(result["available"])
                self.assertEqual(result["jd_count"], count)
                for field in (
                    "education",
                    "experience",
                    "project_experience",
                    "core_responsibilities",
                    "required_skills_text",
                    "bonus_skills_text",
                ):
                    self.assertTrue(result[field], field)
                for skill in result["skill_frequencies"]:
                    self.assertEqual(skill["sample_size"], count)
                    self.assertEqual(skill["frequency"], skill["evidence_jd_count"] / count)
                    self.assertEqual(skill["evidence_jd_count"], len(skill["evidence_jd_ids"]))

    def test_small_samples_are_explicit_and_never_smoothed(self):
        rows = self.services.loader.load_job_analysis_jds()
        counts = Counter(row["standard_job_title"] for row in rows if row["standard_job_title"])
        title = next(title for title, count in counts.items() if count == 1)
        result = self.system.job_analysis(title)
        self.assertTrue(result["small_sample"])
        self.assertIn("样本较少", result["sample_notice"])
        for skill in result["skill_frequencies"]:
            self.assertEqual(skill["evidence_jd_count"], 1)
            self.assertEqual(skill["frequency"], 1.0)

    def test_focus_and_new_jobs_are_built_from_their_actual_jds(self):
        rows = self.services.loader.load_job_analysis_jds()
        titles = {row["standard_job_title"] for row in rows}
        expected = {
            "AI Agent开发工程师",
            "RAG引擎研发工程师",
            "AI安全技术工程师",
            "具身智能算法工程师",
            "VLA算法工程师",
            "Agent评测工程师",
            "大模型应用研发工程师",
        }
        self.assertTrue(expected <= titles)
        for title in expected:
            with self.subTest(title=title):
                result = self.system.job_analysis(title)
                self.assertTrue(result["core_responsibilities"])
                self.assertTrue(result["required_skills_text"])
                self.assertTrue(result["education"])
                self.assertTrue(result["experience"])
                self.assertTrue(result["project_experience"])
                self.assertTrue(result["bonus_skills_text"])
                self.assertNotEqual(result["core_responsibilities"], UNKNOWN)


if __name__ == "__main__":
    unittest.main()
