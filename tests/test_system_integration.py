from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.api.app import app
from src.api.integration_service import get_system_data
from src.api.service import get_services


class SystemIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.services = get_services()
        cls.system = get_system_data()
        cls.root = Path(__file__).resolve().parents[1]

    def test_original_and_new_routes_are_registered(self):
        paths = set(app.openapi()["paths"])
        original = {"/api/jd/parse", "/api/resume/parse", "/api/match", "/api/jobs", "/api/skills"}
        added = {
            "/api/system/overview", "/api/job-analysis/{job_title}", "/api/graph/job/{job_title}",
            "/api/graph/skill/{skill_id}", "/api/evolution/job/{job_title}", "/api/emerging-jobs",
            "/api/emerging-jobs/{candidate_id}",
        }
        self.assertTrue(original | added <= paths)

    def test_formal_graph_matches_teammate_a_qa_report(self):
        graph = self.system.graph.load()
        self.assertTrue(graph["available"])
        self.assertEqual(graph["status"], "connected")
        self.assertEqual(graph["source_type"], "formal_json")
        self.assertEqual(graph["summary"]["node_count"], 490)
        self.assertEqual(graph["summary"]["edge_count"], 2012)
        self.assertEqual(graph["summary"]["job_skill_edge_count"], 633)
        job_skill_edges = [edge for edge in graph["edges"] if edge.get("edge_type") == "Job_Skill"]
        self.assertEqual(len(job_skill_edges), 633)
        self.assertTrue(all(edge["evidence_jd_ids"] for edge in job_skill_edges))
        self.assertTrue(all(edge["evidence_count"] == len(edge["evidence_jd_ids"]) for edge in job_skill_edges))

    def test_focus_job_graphs_are_available(self):
        for title in ["AI Agent开发工程师", "RAG引擎研发工程师", "AI安全技术工程师"]:
            with self.subTest(title=title):
                value = self.system.graph.for_job(title)
                self.assertTrue(value["available"])
                self.assertGreater(len(value["edges"]), 0)
                self.assertTrue(all(edge.get("edge_type") == "Job_Skill" for edge in value["edges"]))
                self.assertTrue(all(edge.get("evidence_jd_ids") for edge in value["edges"]))

    def test_formal_evolution_is_separated_by_job_and_preserves_sample_warnings(self):
        expected_samples = {"AI Agent开发工程师": 12, "RAG引擎研发工程师": 2, "AI安全技术工程师": 9}
        for title, sample_count in expected_samples.items():
            with self.subTest(title=title):
                value = self.system.evolution.for_job(title)
                self.assertTrue(value["available"])
                self.assertEqual(value["status"], "connected")
                self.assertEqual(value["support_jd_count"], sample_count)
                self.assertEqual(value["time_range"], ["2026-04-14T00:00:00", "2026-08-15T00:00:00"])
                self.assertIn("不代表多年长期产业趋势", value["notice"])
                self.assertIn("status_summary", value)
        # P2 intentionally corrects the old one-sided guard: 1 -> 11 is insufficient.
        agent = self.system.evolution.for_job("AI Agent开发工程师")
        self.assertTrue(agent["sample_insufficient"])
        self.assertEqual(agent["window_samples"], {"before": 1, "after": 11, "minimum": 3})
        self.assertEqual(agent["declining_skills"], [])
        self.assertTrue(self.system.evolution.for_job("RAG引擎研发工程师")["sample_insufficient"])
        self.assertTrue(self.system.evolution.for_job("AI安全技术工程师")["sample_insufficient"])

    def test_evolution_fallback_copy_describes_formal_static_results(self):
        source = (self.root / "frontend" / "src" / "pages" / "EvolutionPage.tsx").read_text(encoding="utf-8")
        self.assertNotIn("静态缺失状态", source)
        self.assertIn("静态正式演化结果", source)

    def test_emerging_candidates_have_complete_evidence(self):
        value = json.loads((self.root / "outputs" / "emerging_jobs_v1.json").read_text(encoding="utf-8"))
        self.assertTrue(value["validation"]["passed"])
        for item in value["candidates"]:
            self.assertEqual(item["jd_count"], len(item["evidence_jd_ids"]))
            self.assertEqual(set(item["evidence_jd_ids"]), {record["jd_id"] for record in item["evidence_records"]})
            if item["jd_count"] == 1:
                self.assertEqual(item["confidence_level"], "弱候选/待观察")


if __name__ == "__main__":
    unittest.main()
