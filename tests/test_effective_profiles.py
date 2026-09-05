"""Published snapshots drive both real matching and graph adapters; no fake scoring."""
import copy
import tempfile
import unittest
from pathlib import Path

from src.api.service import get_services
from src.closure.service import ClosureService
from src.closure.repository import PublishedProfileRepository
from src.core.effective_profiles import EffectiveJobProfiles
from src.core.matching_engine import MatchingEngine
from src.integration.graph_adapter import GraphAdapter
from src.schemas import ResumeParseRequest


TITLE = "本地发布画像集成测试岗位"
STATIC_JOB = "AI Agent开发工程师"


class EffectiveProfileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = get_services()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "profiles.sqlite3"
        self.store = ClosureService(self.core, self.path, base_records=[])
        self.reader = EffectiveJobProfiles(self.core.loader, self.core.skill_index,
            self.core.matching_engine.profiles, PublishedProfileRepository(self.path))
        self.engine = MatchingEngine(self.core.loader, self.core.skill_index, self.core.jd_parser, effective_profiles=self.reader)
        self.graph = GraphAdapter(self.core.loader, self.core.skill_index, effective_profiles=self.reader)
        self.resume = self.core.resume_parser.parse(ResumeParseRequest(skills_raw="Python RAG", projects="使用 Python RAG 开发服务"))

    def tearDown(self):
        self.tmp.cleanup()

    def action(self, item, action):
        return self.store.action(item["kind"], item["id"], action, expected_version=item["version"], expected_revision=item["revision"],
                                 reviewer="合成验收员", note="仅合成JD测试，确认缺口", acknowledge_gaps=True)

    def seed(self, title=TITLE):
        for i in range(3):
            self.store.add_evidence(dict(job_id=f"SYN-{i}", original_title=title, responsibilities="维护合成测试服务", required_skills_raw="Python RAG LangGraph Docker", published_at="2026-08-31"))
        item = next(i for i in self.store.discover() if i["auto_definition"]["job_name"] == title)
        return self.edit_skills(item, ["Python", "RAG"])

    def edit_skills(self, item, required, preferred=()):
        d = copy.deepcopy(item["auto_definition"])
        all_skills = d["required_skills"] + d["preferred_skills"]
        d["required_skills"] = [s for s in all_skills if s["skill_name"] in required]
        d["preferred_skills"] = [s for s in all_skills if s["skill_name"] in preferred]
        return self.store.edit("candidate", item["id"], d, item["version"], item["revision"])

    def publish(self, item):
        return self.action(self.action(self.action(item, "submit"), "approve"), "publish")

    def names(self, graph):
        return sorted(n["name"] for n in graph["nodes"] if n["type"] == "skill")

    def test_01_no_publication_matches_p0_exactly(self):
        old = self.core.matching_engine.match(self.resume, STATIC_JOB).model_dump()
        new = self.engine.match(self.resume, STATIC_JOB).model_dump()
        self.assertEqual(old, new)
        self.assertEqual(new["profile_source"], "static_baseline")
        self.assertIsNone(new["profile_version"])

    def test_02_published_v1_used_by_real_match(self):
        self.publish(self.seed())
        match = self.engine.match(self.resume, TITLE)
        self.assertEqual(match.profile_version, 1)
        self.assertEqual(match.profile_source, "published_dynamic")
        self.assertEqual(match.dimension_scores["required_skills"], 100)
        self.assertEqual(match.missing_skills, [])

    def test_03_latest_v2_adds_langgraph_to_match(self):
        v1 = self.publish(self.seed())
        v2 = self.publish(self.edit_skills(v1, ["Python", "RAG", "LangGraph"]))
        match = self.engine.match(self.resume, TITLE)
        self.assertEqual(match.profile_version, 2)
        self.assertEqual(match.missing_skills, ["LangGraph"])
        self.assertEqual(match.dimension_scores["required_skills"], 66.67)
        self.assertEqual(self.reader.get_effective_job_profile(TITLE)["profile_fingerprint"], v2["fingerprint"])

    def test_04_05_pending_approved_rejected_v3_do_not_change_downstream(self):
        v1 = self.publish(self.seed())
        v2 = self.publish(self.edit_skills(v1, ["Python", "RAG", "LangGraph"]))
        expected_match = self.engine.match(self.resume, TITLE).model_dump()
        expected_graph = self.graph.for_job(TITLE)
        v3 = self.edit_skills(v2, ["Python", "RAG", "LangGraph", "Docker"])
        for action in (None, "submit", "approve", "reject"):
            if action:
                v3 = self.action(v3, action)
            self.assertEqual(self.engine.match(self.resume, TITLE).model_dump(), expected_match)
            self.assertEqual(self.graph.for_job(TITLE), expected_graph)

    def test_06_preferred_and_p0_polarity_bounds(self):
        item = self.seed()
        self.publish(self.edit_skills(item, ["Python", "RAG"], ["LangGraph"]))
        resume = self.core.resume_parser.parse(ResumeParseRequest(skills_raw="掌握Python，计划学习RAG，不会LangGraph，团队使用Docker"))
        match = self.engine.match(resume, TITLE)
        self.assertEqual(match.matched_skills, ["Python"])
        self.assertEqual(match.dimension_scores["bonus_skills"], 0)
        self.assertIsNone(match.dimension_scores["education"])
        self.assertIsNone(match.dimension_scores["experience"])
        self.assertTrue(all(v is None or 0 <= v <= 100 for v in match.dimension_scores.values()))

    def test_07_no_publication_graph_static_unchanged(self):
        raw = GraphAdapter(self.core.loader, self.core.skill_index, effective_profiles=self.reader)
        before = raw.for_job(STATIC_JOB)
        self.seed()  # an unpublished candidate cannot change any official graph
        self.assertEqual(self.graph.for_job(STATIC_JOB), before)
        self.assertEqual(before["profile_source"], "jd_aggregate")
        self.assertEqual(self.graph.load_effective()["edges"], self.graph.load()["edges"])

    def test_08_graph_v2_and_reverse_skill_lookup(self):
        item = self.publish(self.seed())
        self.assertEqual(self.names(self.graph.for_job(TITLE)), ["Python", "RAG"])
        self.publish(self.edit_skills(item, ["Python", "RAG", "LangGraph"]))
        result = self.graph.for_job(TITLE)
        self.assertEqual(result["profile_version"], 2)
        self.assertEqual(self.names(result), ["LangGraph", "Python", "RAG"])
        self.assertTrue(all(e["evidence_jd_ids"] for e in result["edges"]))
        reverse = self.graph.for_skill(self.core.skill_index.resolve_name("LangGraph"))
        self.assertIn(TITLE, [n["name"] for n in reverse["nodes"] if n["type"] == "job"])

    def test_09_only_job_skill_edges_replaced(self):
        original = self.graph.load()
        self.publish(self.seed(STATIC_JOB))
        effective = self.graph.load_effective()
        other = lambda g: [e for e in g["edges"] if e.get("edge_type") != "Job_Skill"]
        self.assertEqual(other(original), other(effective))
        self.assertEqual(original, self.graph.load())  # no mutation of formal files
        self.assertEqual(self.names(self.graph.for_job(STATIC_JOB)), ["Python", "RAG"])

    def test_10_legacy_baseline_is_not_a_publish_action(self):
        self.store = ClosureService(self.core, self.path)
        self.store.run_update(STATIC_JOB)
        self.assertEqual(self.reader.get_effective_job_profile(STATIC_JOB)["profile_source"], "static_baseline")
        self.assertEqual(self.graph.load_effective()["edges"], self.graph.load()["edges"])

    def test_11_missing_database_is_not_created_on_read(self):
        absent = Path(self.tmp.name) / "absent.sqlite3"
        reader = EffectiveJobProfiles(self.core.loader, self.core.skill_index, self.core.matching_engine.profiles, PublishedProfileRepository(absent))
        self.assertEqual(reader.get_effective_job_profile(STATIC_JOB)["profile_source"], "static_baseline")
        self.assertFalse(absent.exists())

    def test_12_publish_visible_without_restart_and_with_writes_disabled(self):
        import os
        from unittest.mock import patch
        self.assertEqual(self.reader.get_effective_job_profile(TITLE)["profile_source"], "static_baseline")
        self.publish(self.seed())
        with patch.dict(os.environ, P1_CLOSURE_WRITES="0"):
            self.assertEqual(self.engine.match(self.resume, TITLE).profile_version, 1)

    def test_13_standard_profile_update_publishes_to_both_consumers(self):
        baseline = [dict(job_id=f"BASE-{i}", original_title=STATIC_JOB, standard_job_title=STATIC_JOB,
                         responsibilities="维护合成服务", required_skills_raw="Python RAG", published_at="2026-08-01") for i in range(3)]
        self.store = ClosureService(self.core, self.path, base_records=baseline)
        old = self.engine.match(self.resume, STATIC_JOB).model_dump()
        for i in range(3):
            self.store.add_evidence(dict(job_id=f"NEW-{i}", original_title=STATIC_JOB, standard_job_title=STATIC_JOB,
                responsibilities="维护合成服务", required_skills_raw="Python RAG LangGraph", published_at="2026-08-02"))
        pending = self.store.run_update(STATIC_JOB)
        self.assertEqual(self.engine.match(self.resume, STATIC_JOB).model_dump(), old)
        approved = self.action(pending, "approve")
        self.assertEqual(self.engine.match(self.resume, STATIC_JOB).model_dump(), old)
        self.action(approved, "publish")
        match = self.engine.match(self.resume, STATIC_JOB)
        self.assertEqual(match.profile_version, 2)  # legacy baseline occupies version 1, but is never activated
        self.assertEqual(match.missing_skills, ["LangGraph"])
        self.assertEqual(self.names(self.graph.for_job(STATIC_JOB)), ["LangGraph", "Python", "RAG"])
        self.assertEqual(self.reader.get_effective_job_profile(STATIC_JOB)["matching_profile"]["education_level"],
                         self.core.matching_engine.profiles[STATIC_JOB]["education_level"])

    def test_14_corrupt_store_does_not_silently_fallback(self):
        import sqlite3
        from src.closure.repository import ProfileReadError
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT INTO entities VALUES ('profile','broken','not-json')")
        conn.close()
        with self.assertRaises(ProfileReadError):
            self.reader.get_effective_job_profile(STATIC_JOB)
