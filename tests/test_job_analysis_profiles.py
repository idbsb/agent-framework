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
        expected_incremental = len(self.services.loader.load_incremental_jds())
        analysis_rows = self.services.loader.load_job_analysis_jds()
        audit = self.services.loader.job_analysis_audit()
        self.assertEqual(audit["raw_source_record_count"], len(base) + expected_supplemental + expected_incremental)
        self.assertEqual(len(analysis_rows), audit["raw_source_record_count"] - audit["cross_source_duplicate_excluded_count"])
        self.assertEqual(audit["effective_jd_count"], 277)
        self.assertEqual(audit["physical_source_record_count"], 282)
        self.assertEqual(len(payload["records"]), 49)  # PROTECTED_NEW_DATA conservation guard
        self.assertEqual(sum(row["jd_id"].startswith("SUP-JD-") for row in analysis_rows), expected_supplemental)
        self.assertEqual(sum(row["jd_id"].startswith("BATCH-20260904-") for row in analysis_rows), expected_incremental - audit["cross_source_duplicate_excluded_count"])
        self.assertEqual(audit["protected_incremental_counted_record_count"], expected_incremental)
        self.assertEqual(audit["protected_incremental_record_count"], 42)

    def test_every_job_uses_one_traceable_aggregate_profile(self):
        rows = self.services.loader.load_job_analysis_jds()
        counts = self.services.loader.job_analysis_counts()
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
                if result["required_skills_jd_count"]:
                    self.assertNotEqual(result["required_skills_text"], UNKNOWN)
                if result["bonus_skills_jd_count"]:
                    self.assertNotEqual(result["bonus_skills_text"], UNKNOWN)
                for skill in result["skill_frequencies"]:
                    self.assertEqual(skill["sample_size"], count)
                    self.assertEqual(skill["frequency"], skill["evidence_jd_count"] / count)
                    self.assertEqual(skill["evidence_jd_count"], len(skill["evidence_jd_ids"]))

    def test_official_focus_groups_and_ai_security_evidence_are_active(self):
        counts = self.services.loader.job_analysis_counts()
        self.assertEqual(counts["AI Agent开发工程师"], 25)
        self.assertEqual(counts["RAG引擎研发工程师"], 10)
        self.assertEqual(counts["AI安全技术工程师"], 30)
        result = self.system.job_analysis("AI安全验证工程师")
        self.assertTrue(result["small_sample"])
        self.assertTrue(result["skill_frequencies"])
        self.assertIn("AI安全", {item["skill_name"] for item in result["skill_frequencies"]})
        self.assertTrue(all(item["evidence_jd_ids"] == ["JD-025"] for item in result["skill_frequencies"]))

    def test_every_real_jd_job_has_a_graph_job_node(self):
        graph = self.system.graph.load()
        graph_jobs = {node.get("name") for node in graph["nodes"] if node.get("type") == "job"}
        self.assertTrue(set(self.services.loader.job_analysis_counts()) <= graph_jobs)

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
