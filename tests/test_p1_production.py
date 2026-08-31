"""Production permission and storage regressions; isolated synthetic companion stores."""
import asyncio
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
            self.assertEqual(self.call("POST","/api/closure/access/verify",token=False,extra=[(b"authorization",token)])[0],401)
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
