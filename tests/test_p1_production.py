"""Production permission and storage regressions; isolated synthetic companion stores."""
import asyncio
import copy
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.api.app import app
from src.api.closure import get_closure
from src.closure.service import ClosureService
from src.closure.repository import PublishedProfileRepository
from src.closure.settings import closure_database_path, validate_auth, production, ProfileReadError
from src.core.effective_profiles import EffectiveJobProfiles
from src.core.matching_engine import MatchingEngine
from src.integration.graph_adapter import GraphAdapter
from src.schemas import ResumeParseRequest
import test_p1_closure as fixtures


async def request(method, path, body=None, headers=()):
    messages = []
    async def receive():
        return {"type": "http.request", "body": json.dumps(body or {}).encode(), "more_body": False}
    async def send(message):
        messages.append(message)
    await app(dict(type="http", asgi={"version":"3.0", "spec_version":"2.4"}, http_version="1.1",
        method=method, scheme="https", path=path, raw_path=path.encode(), query_string=b"", root_path="",
        headers=[(b"content-type", b"application/json"), *headers],
        client=("203.0.113.7", 1000), server=("api.example.test",443)), receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    data = json.loads(b"".join(m.get("body",b"") for m in messages if m["type"] == "http.response.body"))
    return start["status"], data, dict(start["headers"])


class ProductionTest(unittest.TestCase):
    setUpClass = fixtures.ClosureTest.__dict__["setUpClass"]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "closure.sqlite3"
        self.env = patch.dict(os.environ, P1_ENV="production", RENDER="false", P1_CLOSURE_WRITES="1",
            P1_STORAGE_DIR=self.tmp.name, P1_CLOSURE_DB=str(self.path), P1_INITIALIZE_DB="1",
            P1_ADMIN_TOKEN="synthetic-test-credential-not-a-real-secret", P1_ADMIN_NAME="test-admin",
            CORS_ORIGINS="https://ui.example.test")
        self.env.start()
        self.service = ClosureService(self.core, closure_database_path(self.core.loader.project_root), base_records=[])
        os.environ["P1_INITIALIZE_DB"] = "0"
        app.dependency_overrides[get_closure] = lambda: self.service

    def tearDown(self):
        app.dependency_overrides.clear()
        self.env.stop()
        self.tmp.cleanup()

    def call(self, method, path, body=None, token=True, origin="https://ui.example.test", extra=()):
        headers = list(extra)
        if token:
            headers.append((b"authorization", ("Bearer " + os.environ["P1_ADMIN_TOKEN"]).encode()))
        if origin:
            headers.append((b"origin", origin.encode()))
        return asyncio.run(request(method, path, body, headers))

    def test_remote_writes_require_bearer_even_with_spoofed_loopback(self):
        for endpoint, body in [("/evidence",fixtures.jd("j1")), ("/discovery/run",{}),
                ("/profiles/run",{"job_title":"x"}), ("/candidate/x/manual",{}), ("/candidate/x/actions",{}), ("/access/verify",{})]:
            status, _, headers = self.call("POST", "/api/closure"+endpoint,body, token=False,
                extra=[(b"x-forwarded-for",b"127.0.0.1")])
            self.assertEqual(status,401,endpoint)
            self.assertEqual(headers[b"cache-control"],b"no-store")
        self.assertEqual(self.call("POST","/api/closure/evidence",fixtures.jd("j1"))[0],200)

    def test_wrong_token_and_untrusted_origin(self):
        for token in [b"Bearer wrong", b"Basic invalid", "Bearer 中文".encode()]:
            expected = 403 if token.startswith(b"Bearer ") else 401
            self.assertEqual(self.call("POST","/api/closure/access/verify",token=False,extra=[(b"authorization",token)])[0],expected)
        for origin in ["null","https://evil.example.test","https://ui.example.test.attacker.test"]:
            self.assertEqual(self.call("POST","/api/closure/access/verify",origin=origin)[0],403)
        self.assertEqual(self.call("POST","/api/closure/access/verify",origin=None)[0],200)

    def test_write_kill_switch_preserves_public_reads(self):
        with patch.dict(os.environ,P1_CLOSURE_WRITES="0"):
            self.assertEqual(self.call("POST","/api/closure/access/verify")[0],403)
            self.assertEqual(self.call("GET","/api/closure/candidates",token=False)[0],200)

    def test_server_actor_cannot_be_spoofed(self):
        for i in range(3):
            self.call("POST","/api/closure/evidence",fixtures.jd(f"s{i}",title=""))
        item = self.call("POST","/api/closure/discovery/run")[1][0]
        for action in ["submit","approve","publish"]:
            status,item,_ = self.call("POST",f'/api/closure/candidate/{item["id"]}/actions',dict(
                action=action,expected_version=item["version"],expected_revision=item["revision"],
                reviewer="spoofed",note="synthetic evidence checked",acknowledge_gaps=True))
            self.assertEqual(status,200)
        published = self.call("GET",f'/api/closure/candidate/{item["id"]}/published',token=False)[1]
        self.assertEqual(published["reviewer"],"test-admin")
        self.assertEqual(published["profile_version"],1)

    def test_storage_external_and_shared_by_writer_and_reader(self):
        self.assertEqual(closure_database_path(self.core.loader.project_root),self.service.db_path.resolve())
        self.service.check_storage()
        self.assertEqual(PublishedProfileRepository(self.path).latest_by_job(),{})
        self.assertEqual(self.call("GET","/api/health/ready",token=False)[0],200)

    def test_invalid_paths_are_rejected(self):
        root = self.core.loader.project_root
        for env in [dict(P1_CLOSURE_DB="relative.sqlite3"),dict(P1_STORAGE_DIR="relative"),
                    dict(P1_CLOSURE_DB=str(root/"outside.sqlite3")),dict(P1_STORAGE_DIR=str(root)),
                    dict(P1_CLOSURE_DB=str(Path(self.tmp.name)/"wrong.db")),dict(P1_STORAGE_DIR=str(Path(self.tmp.name)/"absent"))]:
            with patch.dict(os.environ,env), self.assertRaises(ProfileReadError):
                closure_database_path(root)

    def test_render_requires_actual_mount_and_cannot_downgrade_to_local(self):
        with patch.dict(os.environ,RENDER="true",P1_ENV="local"), patch("os.path.ismount",return_value=False):
            self.assertTrue(production())
            with self.assertRaises(ProfileReadError):
                closure_database_path(self.core.loader.project_root)

    def test_missing_store_never_silently_reverts_to_static_or_recreates(self):
        self.path.unlink()
        with self.assertRaises(ProfileReadError):
            PublishedProfileRepository(self.path).latest_by_job()
        with self.assertRaises(ProfileReadError):
            ClosureService(self.core,self.path,base_records=[])
        self.assertEqual(self.call("GET","/api/health/ready",token=False)[0],503)
        self.assertEqual(self.call("POST","/api/closure/evidence",fixtures.jd("lost"))[0],503)
        self.assertFalse(self.path.exists())

    def test_corrupt_store_health_fails_without_disclosing_path(self):
        self.path.write_bytes(b"not a sqlite database")
        status, data, _ = self.call("GET","/api/health/ready",token=False)
        self.assertEqual(status,503)
        self.assertNotIn(self.tmp.name,json.dumps(data))

    def test_bad_auth_configuration_fails_closed(self):
        for env in [dict(P1_ADMIN_TOKEN=""),dict(P1_ADMIN_TOKEN="short"),dict(P1_ADMIN_NAME=""),
                dict(CORS_ORIGINS="*"),dict(CORS_ORIGINS="http://ui.example.test"),
                dict(CORS_ORIGINS="https://ui.example.test/path"),dict(CORS_ORIGINS="")]:
            with patch.dict(os.environ,env), self.assertRaises(ProfileReadError):
                validate_auth()

    def test_stale_revision_cannot_overwrite_committed_review(self):
        for i in range(3): self.service.add_evidence(fixtures.jd(f"c{i}",title=""))
        item = self.service.discover()[0]
        body=dict(action="submit",expected_version=item["version"],expected_revision=item["revision"])
        endpoint=f'/api/closure/candidate/{item["id"]}/actions'
        self.assertEqual(self.call("POST",endpoint,body)[0],200)
        self.assertEqual(self.call("POST",endpoint,body)[0],409)
        self.assertEqual(len(self.service.history("candidate",item["id"])["events"]),2)

    def test_backup_restore_preserves_published_history_and_refuses_overwrite(self):
        from src.closure.backup import backup_database
        for i in range(3): self.service.add_evidence(fixtures.jd(f"backup{i}",title=""))
        item = self.service.discover()[0]
        for action in ["submit","approve","publish"]:
            item = self.service.action("candidate",item["id"],action,expected_version=item["version"],
                expected_revision=item["revision"],reviewer="test-admin",note="test backup",acknowledge_gaps=True)
        destination=Path(self.tmp.name)/"backup.sqlite3"
        self.assertEqual(backup_database(self.path,destination),{"evidence_count":3,"entity_count":1})
        restored=ClosureService(self.core,destination,base_records=[])
        self.assertEqual(restored.history("candidate",item["id"]),self.service.history("candidate",item["id"]))
        self.assertEqual(PublishedProfileRepository(destination).latest_by_job(),PublishedProfileRepository(self.path).latest_by_job())
        for target in [destination,self.path]:
            with self.assertRaises(ValueError): backup_database(self.path,target)

    def test_existing_production_database_with_missing_schema_is_not_reinitialized(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("DROP TABLE entities")
        conn.close()
        with patch.dict(os.environ,P1_INITIALIZE_DB="1"), self.assertRaises(sqlite3.Error):
            ClosureService(self.core,self.path,base_records=[])
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT name FROM sqlite_master WHERE name='entities'").fetchall(),[])
        conn.close()

    def test_prod_04_07_08_09_11_valid_admin_flow_and_no_token_in_responses(self):
        token = os.environ["P1_ADMIN_TOKEN"]
        status, created, headers = self.call("POST", "/api/closure/evidence", fixtures.jd("prod-flow", title=""))
        self.assertEqual(status, 200)
        self.assertEqual(created["job_id"], "prod-flow")
        rendered = json.dumps([created, {k.decode(): v.decode() for k, v in headers.items()}], ensure_ascii=False)
        self.assertNotIn(token, rendered)

        for i in range(1, 3):
            self.call("POST", "/api/closure/evidence", fixtures.jd(f"prod-flow-{i}", title=""))
        item = self.call("POST", "/api/closure/discovery/run")[1][0]
        manual = copy.deepcopy(item["auto_definition"])
        manual["job_name"] = "SYNTHETIC_PRODUCTION_AUTH_FLOW"
        item = self.call("POST", f'/api/closure/candidate/{item["id"]}/manual', dict(
            definition=manual, expected_version=item["version"], expected_revision=item["revision"]))[1]
        for action in ["submit", "approve", "publish"]:
            status, item, _ = self.call("POST", f'/api/closure/candidate/{item["id"]}/actions', dict(
                action=action, expected_version=item["version"], expected_revision=item["revision"],
                note="synthetic production authorization test", acknowledge_gaps=True))
            self.assertEqual(status, 200)
        self.assertEqual(item["status"], "published")

    def test_prod_05_06_anonymous_cannot_approve_or_publish(self):
        for action in ["approve", "publish"]:
            status, data, _ = self.call("POST", "/api/closure/candidate/synthetic/actions", dict(
                action=action, expected_version=1, expected_revision=0), token=False)
            self.assertEqual(status, 401)
            self.assertNotIn(os.environ["P1_ADMIN_TOKEN"], json.dumps(data))

    def test_prod_13_to_20_file_restart_preserves_flow_and_downstream_isolation(self):
        title = "SYNTHETIC_RESTART_PERSISTENCE_PROFILE"
        first_id = "synthetic-restart-0"
        for i in range(3):
            self.service.add_evidence(dict(
                job_id=f"synthetic-restart-{i}", original_title=title,
                responsibilities="operate synthetic restart service",
                required_skills_raw="Python RAG LangGraph", scenario="synthetic validation",
                company="synthetic company", source="synthetic fixture", published_at="2026-08-31"))
        item = next(value for value in self.service.discover() if value["auto_definition"]["job_name"] == title)
        manual = copy.deepcopy(item["auto_definition"])
        manual["core_responsibilities"][0]["text"] = "manually reviewed synthetic restart responsibility"
        item = self.service.edit("candidate", item["id"], manual, item["version"], item["revision"])
        for action in ["submit", "approve", "publish"]:
            item = self.service.action("candidate", item["id"], action,
                expected_version=item["version"], expected_revision=item["revision"],
                reviewer="synthetic-admin", note="synthetic restart verification", acknowledge_gaps=True)
        history_a = self.service.history("candidate", item["id"])

        service_b = ClosureService(self.core, self.path, base_records=[])
        self.assertEqual(service_b.evidence(first_id)["job_id"], first_id)
        self.assertEqual(service_b.history("candidate", item["id"]), history_a)
        self.assertEqual(service_b.published("candidate", item["id"])["profile_version"], 1)
        app.dependency_overrides[get_closure] = lambda: service_b
        self.assertEqual(self.call("GET", f"/api/closure/evidence/{first_id}", token=False)[1]["job_id"], first_id)
        self.assertEqual(self.call("GET", f'/api/closure/candidate/{item["id"]}/versions', token=False)[1], history_a)

        reader = EffectiveJobProfiles(self.core.loader, self.core.skill_index,
            self.core.matching_engine.profiles, PublishedProfileRepository(self.path))
        engine = MatchingEngine(self.core.loader, self.core.skill_index, self.core.jd_parser, effective_profiles=reader)
        graph = GraphAdapter(self.core.loader, self.core.skill_index, effective_profiles=reader)
        resume = self.core.resume_parser.parse(ResumeParseRequest(skills_raw="Python RAG", projects="synthetic project"))
        published_match = engine.match(resume, title).model_dump()
        published_graph = graph.for_job(title)
        self.assertEqual(published_match["profile_source"], "published_dynamic")
        self.assertEqual(published_match["profile_version"], 1)
        self.assertEqual(published_graph["profile_version"], 1)
        self.assertEqual(published_match["profile_fingerprint"], published_graph["profile_fingerprint"])

        draft_manual = copy.deepcopy(item["manual_definition"])
        draft_manual["core_responsibilities"][0]["text"] = "new unpublished synthetic responsibility"
        draft = service_b.edit("candidate", item["id"], draft_manual, item["version"], item["revision"])
        for action in [None, "submit", "approve", "reject"]:
            if action:
                draft = service_b.action("candidate", draft["id"], action,
                    expected_version=draft["version"], expected_revision=draft["revision"],
                    reviewer="synthetic-admin", note="unpublished isolation", acknowledge_gaps=True)
            self.assertEqual(engine.match(resume, title).model_dump(), published_match)
            self.assertEqual(graph.for_job(title), published_graph)
