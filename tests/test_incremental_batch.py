from __future__ import annotations

import unittest

from src.api.app import app, job_changes, match_resume, multi_source
from src.api.integration_service import get_system_data
from src.api.service import get_services
from src.schemas import MatchRequest


class IncrementalBatchIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.services = get_services()
        cls.system = get_system_data()

    def test_all_six_workbooks_and_every_sheet_are_loaded(self):
        payload = self.system.multi_source()
        self.assertEqual(payload["files_loaded"], 6)
        self.assertEqual(sum(len(book["sheets"]) for book in payload["workbooks"]), 11)
        self.assertTrue(all(book["sha256"] and len(book["sha256"]) == 64 for book in payload["workbooks"]))

    def test_baseline_incremental_and_dedup_are_separate(self):
        payload = self.system.multi_source()
        self.assertEqual(payload["baseline"]["jd_count"], 237)
        self.assertEqual(payload["incremental"]["raw_jd_count"], 42)
        self.assertEqual(payload["incremental"]["jd_count"], 40)
        self.assertEqual(payload["incremental"]["duplicate_excluded_count"], 2)
        self.assertEqual(payload["incremental"]["cross_source_duplicate_excluded_count"], 1)
        self.assertEqual(payload["current"]["jd_count"], 277)

    def test_cautious_sample_conclusions_are_preserved(self):
        changes = self.system.job_changes()["capability_changes"]
        self.assertEqual(len(changes), 3)
        insufficient = [item for item in changes if item["sample_insufficient"]]
        self.assertTrue(insufficient)
        self.assertTrue(all("不形成显著趋势判断" in item["sample_status"] for item in insufficient))

    def test_job_change_contains_real_time_window_comparison(self):
        changes = {item["job_title"]: item for item in self.system.job_changes()["capability_changes"]}
        self.assertEqual(changes["Java开发工程师"]["early_period"]["jd_count"], 1)
        self.assertEqual(changes["Java开发工程师"]["recent_period"]["jd_count"], 2)
        self.assertEqual(changes["数据分析师"]["early_period"]["company_count"], 2)
        self.assertEqual(changes["数据分析师"]["recent_period"]["company_count"], 3)
        new_java_clues = [item["skill_name"] for item in changes["Java开发工程师"]["skill_changes"] if item["early_count"] == 0 and item["recent_count"] > 0]
        self.assertIn("AI", new_java_clues)

    def test_graph_v2_and_latest_profiles_feed_match(self):
        graph = self.system.graph.load()
        self.assertEqual(graph["graph_version"], "Graph V2")
        self.assertGreater(graph["graph_change"]["new_job_node_count"], 0)
        self.assertGreater(graph["graph_change"]["new_skill_node_count"], 0)
        self.assertGreater(graph["graph_change"]["new_relation_count"], 0)
        profile = self.system.job_analysis("AI Agent工程师")
        self.assertEqual(profile["jd_count"], 4)  # 5 raw rows, one duplicate excluded from statistics
        response = match_resume(MatchRequest.model_validate({"job_title": "AI Agent工程师", "resume": {
            "resume_id": "INC-QA", "target_job": "AI Agent工程师", "education": "本科", "experience": "2年",
            "work_experience": "使用Python开发服务", "projects": "使用RAG和MCP构建Agent", "skills_raw": "Python; RAG; MCP"
        }}))
        self.assertEqual(response.profile_source, "static_baseline")
        self.assertIn("RAG", response.matched_skills)

    def test_new_read_endpoints_are_live(self):
        self.assertTrue(multi_source())
        self.assertTrue(job_changes())
