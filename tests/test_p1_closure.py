"""P1 acceptance: real extractor, discovery and transactional local store; synthetic JD only."""
import copy
import tempfile
import unittest
from pathlib import Path

from src.api.service import get_services
from src.closure.service import ClosureError, ClosureService


JOB = "AI Agent开发工程师"


def jd(identifier, skills="Python RAG", day="2026-08-01", title=JOB, **extra):
    return dict(job_id=identifier, original_title=title or "量子服务工程师",
                standard_job_title=title, responsibilities="开发服务", required_skills_raw=skills,
                company="合成测试企业", source="合成测试来源", published_at=day,
                url="https://example.test/jobs/" + identifier, **extra)


class ClosureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = get_services()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "closure.sqlite3"
        self.base = [jd(f"b{i}") for i in range(3)]
        self.service = ClosureService(self.core, self.path, base_records=self.base)

    def tearDown(self):
        self.tmp.cleanup()

    def candidate(self, **overrides):
        for i in range(3):
            row = jd(f"c{i}", title="")
            row.update(overrides)
            self.service.add_evidence(row)
        return self.service.discover()[0]

    def action(self, item, action):
        return self.service.action(item["kind"], item["id"], action,
            expected_version=item["version"], expected_revision=item["revision"],
            reviewer="本地测试审核员", note="已核对真实证据并确认缺失字段", acknowledge_gaps=True)

    def approved(self, item):
        return self.action(self.action(item, "submit"), "approve")

    def update(self, skills="Python LangGraph", count=3):
        for i in range(count):
            self.service.add_evidence(jd(f"n{i}", skills, "2026-08-02"))
        return self.service.run_update(JOB)

    def test_a01_five_elements(self):
        d = self.candidate()["auto_definition"]
        self.assertTrue({"job_name", "core_responsibilities", "required_skills", "preferred_skills", "application_scenarios"} <= d.keys())
        self.assertTrue(d["required_skills"][0]["supporting_job_ids"])

    def test_a02_no_invented_responsibilities(self):
        self.assertEqual(self.candidate(responsibilities="")["auto_definition"]["core_responsibilities"], [])

    def test_a03_no_invented_scenarios(self):
        self.assertEqual(self.candidate()["auto_definition"]["application_scenarios"], [])

    def test_a04_manual_preserves_auto(self):
        item = self.candidate()
        manual = copy.deepcopy(item["auto_definition"])
        manual["job_name"] += "（人工修订）"
        edited = self.service.edit("candidate", item["id"], manual, item["version"], item["revision"])
        self.assertEqual(edited["auto_definition"], item["auto_definition"])
        self.assertNotEqual(edited["auto_definition"], edited["manual_definition"])
        self.assertEqual(self.service.discover()[0]["version"], edited["version"])

    def test_a05_approve_persists(self):
        item = self.approved(self.candidate())
        reopened = ClosureService(self.core, self.path, base_records=self.base)
        self.assertEqual(reopened.get("candidate", item["id"])["status"], "approved")

    def test_a06_reject_persists(self):
        item = self.action(self.candidate(), "reject")
        reopened = ClosureService(self.core, self.path, base_records=self.base)
        self.assertEqual(reopened.get("candidate", item["id"])["status"], "rejected")

    def test_a07_publish_requires_approval(self):
        with self.assertRaises(ClosureError) as caught:
            self.action(self.candidate(), "publish")
        self.assertEqual(caught.exception.status, 409)

    def test_a08_identical_evidence_idempotent(self):
        item = self.candidate()
        again = self.service.discover()[0]
        self.assertEqual((item["id"], item["version"]), (again["id"], again["version"]))

    def test_a09_a10_a11_new_evidence_version_and_diff(self):
        item = self.candidate()
        for i in range(3, 7):
            self.service.add_evidence(jd(f"c{i}", "Python RAG LangGraph", title=""))
        updated = self.service.discover()[0]
        self.assertEqual(updated["id"], item["id"])
        self.assertEqual(updated["previous_version"], item["version"])
        diff = self.service.diff("candidate", item["id"], item["version"], updated["version"])
        self.assertIn("LangGraph", [s["skill_name"] for s in diff["added_skills"]])

    def test_a12_evidence_trace(self):
        item = self.candidate()
        for evidence in item["evidence"]:
            self.assertEqual(self.service.evidence(evidence["job_id"])["job_id"], evidence["job_id"])

    def test_b01_b02_b03_b04_changes(self):
        # Three later JDs: Python frequency changes from 1 to 2/3, RAG disappears.
        for i in range(3):
            self.service.add_evidence(jd(f"n{i}", "Python LangGraph" if i < 2 else "LangGraph", "2026-08-02"))
        changes = self.service.run_update(JOB)["change_set"]
        self.assertEqual([s["skill_name"] for s in changes["added_skills"]], ["LangGraph"])
        self.assertEqual([s["skill_name"] for s in changes["removed_skills"]], ["RAG"])
        self.assertEqual([s["skill_name"] for s in changes["modified_skills"]], ["Python"])
        self.assertTrue(changes["removed_skills"][0]["before_evidence"])

    def test_b05_pending_does_not_change_publication(self):
        item = self.update()
        self.assertEqual(item["status"], "pending_review")
        self.assertEqual(self.service.published("profile", JOB)["profile_version"], 1)

    def test_b06_approve_publish(self):
        item = self.action(self.update(), "approve")
        self.action(item, "publish")
        self.assertEqual(self.service.published("profile", JOB)["profile_version"], 2)

    def test_b07_reject_preserves_profile(self):
        item = self.update()
        before = self.service.published("profile", JOB)
        self.action(item, "reject")
        self.assertEqual(self.service.published("profile", JOB), before)

    def test_b08_before_window_insufficient(self):
        self.service = ClosureService(self.core, self.path, base_records=self.base[:1])
        self.assertEqual(self.update()["change_set"]["status"], "insufficient_sample")

    def test_b09_after_window_insufficient(self):
        item = self.update(count=1)
        self.assertEqual(item["change_set"]["status"], "insufficient_sample")
        self.assertEqual(item["change_set"]["added_skills"], [])
        with self.assertRaises(ClosureError):
            self.action(item, "approve")

    def test_b10_collection_fallback_labelled(self):
        self.service.add_evidence(dict(job_id="time", original_title=JOB, collected_at="2026-08-02"))
        evidence = self.service.evidence("time")
        self.assertIsNone(evidence["published_at"])
        self.assertEqual(evidence["time_source"], "collected_at_fallback")

    def test_version_conflict_and_invalid_action(self):
        item = self.candidate()
        self.action(item, "submit")
        with self.assertRaises(ClosureError) as caught:
            self.action(item, "approve")
        self.assertEqual(caught.exception.status, 409)
        with self.assertRaises(ClosureError):
            self.service.get("candidate", "unknown")

    def test_p0_negation_never_required(self):
        item = self.candidate(required_skills_raw="不会 Python，计划学习 RAG，掌握 SQL")
        self.assertEqual([s["skill_name"] for s in item["auto_definition"]["required_skills"]], ["SQL"])

    def test_unbacked_manual_skill_rejected(self):
        item = self.candidate()
        manual = copy.deepcopy(item["auto_definition"])
        manual["required_skills"][0]["skill_id"] = "made-up"
        with self.assertRaises(ClosureError) as caught:
            self.service.edit("candidate", item["id"], manual, item["version"], item["revision"])
        self.assertEqual(caught.exception.status, 422)

    def test_duplicate_jd_does_not_overwrite(self):
        self.service.add_evidence(jd("extra"))
        self.service.add_evidence(jd("extra"))
        with self.assertRaises(ClosureError) as caught:
            self.service.add_evidence(jd("extra", "Docker"))
        self.assertEqual(caught.exception.status, 409)

    def test_html_and_urls_are_data(self):
        self.service.add_evidence(dict(job_id="html", original_title="<script>alert(1)</script>", url="javascript:alert(1)"))
        evidence = self.service.evidence("html")
        self.assertEqual(evidence["original_title"], "<script>alert(1)</script>")
        self.assertIsNone(evidence["safe_url"])

    def test_identical_manual_save_no_version(self):
        item = self.candidate()
        edited = self.service.edit("candidate", item["id"], item["auto_definition"], item["version"], item["revision"])
        self.assertEqual(item["version"], edited["version"])

    def test_unchanged_profile_cannot_publish_another_version(self):
        item = self.service.run_update(JOB)
        self.assertEqual(item["change_set"]["status"], "no_changes")
        with self.assertRaises(ClosureError):
            self.action(item, "approve")

    def test_same_day_evidence_revision_not_market_trend(self):
        self.service.add_evidence(jd("same-day", "Python LangGraph"))
        item = self.service.run_update(JOB)
        self.assertEqual(item["change_set"]["mode"], "snapshot_revision")
        self.assertEqual(item["change_set"]["added_skills"], [])  # one JD below existing min2
        self.assertNotIn("LangGraph", [s["skill_name"] for s in item["auto_definition"]["required_skills"]])

    def test_published_snapshot_survives_new_candidate_evidence(self):
        item = self.action(self.approved(self.candidate()), "publish")
        published = self.service.published("candidate", item["id"])
        self.service.add_evidence(jd("c-more", "Python RAG LangGraph", title=""))
        self.service.discover()
        self.assertEqual(self.service.published("candidate", item["id"]), published)


if __name__ == "__main__":
    unittest.main()
