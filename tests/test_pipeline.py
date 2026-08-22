import tempfile, unittest
from pathlib import Path
from agent_framework.core import AgentPipeline, Database

class PipelineTest(unittest.TestCase):
    def test_import_profile_match_and_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "test.db"); db.init(); pipeline = AgentPipeline(db)
            pipeline.import_jobs([{"id":"JD1", "原始岗位名":"Agent开发工程师", "岗位簇":"AI Agent开发工程师", "职责摘要":"构建Agent工作流与工具调用", "技能摘要":"Python；RAG；LangGraph；Docker"}])
            p = pipeline.build_profile("AI Agent开发工程师")
            self.assertIn("Python", [x["skill"] for x in p["skills"]])
            result = pipeline.match("AI Agent开发工程师", "Python; LangGraph; RAG")
            self.assertGreater(result["score"], 0)
            pipeline.review("JD1", "Kubernetes", "add", "tester")
            p2 = pipeline.build_profile("AI Agent开发工程师")
            self.assertIn("Kubernetes", [x["skill"] for x in p2["skills"]])
            db.close()

    def test_incremental_update_replaces_auto_skills_and_keeps_human_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "test.db"); db.init(); pipeline = AgentPipeline(db)
            first = pipeline.import_jobs([{"id": "JD1", "原始岗位名": "Agent工程师", "岗位簇": "智能体", "技能摘要": "Python；RAG"}])
            pipeline.review("JD1", "Kubernetes", "add", "reviewer")
            second = pipeline.import_jobs([{"id": "JD1", "原始岗位名": "Agent工程师", "岗位簇": "智能体", "技能摘要": "Java"}])
            names = {row[0] for row in db.conn.execute("""SELECT s.canonical_name FROM job_skills js
                JOIN skills s ON s.skill_id=js.skill_id WHERE js.job_id='JD1'""")}
            self.assertEqual(first["added"], 1)
            self.assertEqual(second["updated"], 1)
            self.assertEqual(db.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 1)
            self.assertIn("Java", names)
            self.assertIn("Kubernetes", names)
            self.assertNotIn("Python", names)
            self.assertNotIn("RAG", names)
            db.close()

    def test_reimport_of_identical_job_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "test.db"); db.init(); pipeline = AgentPipeline(db)
            row = {"id": "JD1", "原始岗位名": "Agent工程师", "岗位簇": "智能体", "企业": 360, "技能摘要": "Python"}
            pipeline.import_jobs([row])
            result = pipeline.import_jobs([row])
            self.assertEqual(result["unchanged"], 1)
            self.assertEqual(result["added"], 0)
            self.assertEqual(result["updated"], 0)
            db.close()

if __name__ == "__main__": unittest.main()
