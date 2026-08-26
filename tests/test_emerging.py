from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from src.emerging.cluster_analyzer import ClusterAnalyzer, JobVector


class EmergingClusterTest(unittest.TestCase):
    def setUp(self):
        config_path = Path(__file__).resolve().parents[1] / "config" / "emerging_job_config.yaml"
        self.analyzer = ClusterAnalyzer(yaml.safe_load(config_path.read_text(encoding="utf-8")))

    def test_generic_engineering_skills_do_not_merge_unrelated_titles(self):
        rows = [
            JobVector("JD-A", "AI数据工程师", frozenset({"Python", "Java", "RAG"})),
            JobVector("JD-B", "攻防红队工程师", frozenset({"Python", "Java", "RAG"})),
        ]
        self.assertEqual(self.analyzer.components(rows, []), [["JD-A"], ["JD-B"]])

    def test_semantically_consistent_security_titles_can_merge(self):
        rows = [
            JobVector("JD-A", "安全专家（AI方向）", frozenset({"Python", "RAG"})),
            JobVector("JD-B", "AI安全专家", frozenset({"Python", "PyTorch"})),
        ]
        self.assertEqual(self.analyzer.components(rows, []), [["JD-A", "JD-B"]])

    def test_generic_confirmed_support_does_not_attach_by_skills_alone(self):
        seed = JobVector("JD-A", "自动驾驶感知测试开发工程师", frozenset({"C++", "Python", "Linux"}))
        support = JobVector("JD-B", "AI端侧大模型开发工程师", frozenset({"C++", "Python", "Linux"}))
        self.assertEqual(self.analyzer.components([seed], [support]), [["JD-A"]])


if __name__ == "__main__":
    unittest.main()
