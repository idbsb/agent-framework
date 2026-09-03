"""P0 regressions against real parsers/services; all inputs are synthetic.

Run with the project's unittest runner. No production API or database access.
"""
from __future__ import annotations

import unittest

from src.api.app import match_resume, parse_jd, parse_resume
from src.api.service import get_services
from src.schemas import JDParseRequest, MatchRequest, ResumeParseRequest


JOB = "AI Agent开发工程师"
DEMO = dict(
    education="硕士，人工智能", experience="2年",
    work_experience="负责AI Agent平台研发，使用Python与FastAPI。",
    projects="基于LangGraph开发企业客服Agent，集成RAG、MCP与向量数据库，使用Docker部署。",
    skills_raw="Python、LangGraph、RAG、MCP、FastAPI、Docker、向量数据库、Prompt Engineering",
)


class P0RegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.services = get_services()

    def parse(self, text="", **fields):
        return parse_resume(ResumeParseRequest(skills_raw=text, **fields))

    def match(self, **fields):
        return match_resume(MatchRequest(job_title=JOB, resume=ResumeParseRequest(**fields)))

    def assert_polarities(self, text, expected):
        parsed = self.parse(text)
        actual = {item.standard_skill_name: getattr(item, "polarity", None) for item in parsed.skills}
        self.assertEqual(actual, expected)
        for item in parsed.skills:
            self.assertEqual(item.accepted, expected[item.standard_skill_name] == "affirmed")
        return parsed

    def test_a01_empty_resume_no_demo_skills(self):
        self.assertEqual(self.parse().skills, [])
        result = self.match()
        self.assertEqual(result.matched_skills, [])
        self.assertEqual(result.match_score, 0)

    def test_a02_clerk_jd_no_hidden_bonus(self):
        result = parse_jd(JDParseRequest(original_job_title="文员", responsibilities="整理纸质档案", required_skills_raw="不需要编程技能"))
        self.assertEqual(result.skills, [])

    def test_a03_negation_and_sql(self):
        self.assert_polarities("从未使用Python和Docker，不具备Java经验。仅掌握SQL。不会RAG和LangGraph。", {
            "Python": "negated", "Docker": "negated", "Java": "negated",
            "SQL": "affirmed", "RAG": "negated", "LangGraph": "negated",
        })

    def test_a04_six_explicit_skills(self):
        expected = {name: "affirmed" for name in ("Python", "FastAPI", "LangGraph", "RAG", "MCP", "Docker")}
        self.assert_polarities("Python、FastAPI、LangGraph、RAG、MCP、Docker", expected)

    def test_a05_evidence_sections_retained_without_duplicate_contribution(self):
        parsed = self.parse("Python", projects="使用Python", work_experience="负责Python服务")
        python = [item for item in parsed.skills if item.standard_skill_name == "Python"]
        self.assertEqual({item.source_field for item in python}, {"skills_raw", "projects", "work_experience"})
        self.assertEqual(len(python), 3)
        one = self.match(projects="使用Python")
        many = self.match(skills_raw="Python", projects="使用Python", work_experience="负责Python服务")
        self.assertEqual(one.dimension_scores["required_skills"], many.dimension_scores["required_skills"])
        self.assertEqual(one.dimension_scores["projects"], many.dimension_scores["projects"])

    def test_a06_empty_education_unknown(self):
        result = self.match(skills_raw="Python", experience="2年")
        self.assertIsNone(result.dimension_scores["education"])
        self.assertEqual(result.dimension_status["education"], "unknown")

    def test_a07_empty_experience_unknown(self):
        result = self.match(skills_raw="Python", education="本科")
        self.assertIsNone(result.dimension_scores["experience"])
        self.assertEqual(result.dimension_status["experience"], "unknown")

    def test_a08_dimension_bounds(self):
        cases = [DEMO, {**DEMO, "skills_raw": ""}, {}, {"skills_raw": "不会Python", "education": "高中", "experience": "0年"}]
        for fields in cases:
            with self.subTest(fields=fields):
                for key, value in self.match(**fields).dimension_scores.items():
                    if value is not None:
                        self.assertTrue(0 <= value <= 100, (key, value))

    def test_a09_total_bounds_for_formal_job_profiles(self):
        parsed = self.parse("Python、Docker", projects="使用Python", education="本科", experience="2年")
        for title in self.services.matching_engine.profiles:
            with self.subTest(title=title):
                result = self.services.matching_engine.match(parsed, title)
                self.assertTrue(0 <= result.match_score <= 100)

    def test_a10_removing_skill_list_cannot_create_project_credit(self):
        # Identical project evidence: dropping an earlier section must not change
        # its provenance or switch to the old 4/3 project-coverage denominator.
        full = self.match(**DEMO)
        reduced = self.match(**{**DEMO, "skills_raw": ""})
        self.assertEqual(full.dimension_scores["projects"], reduced.dimension_scores["projects"])
        self.assertLessEqual(reduced.match_score, full.match_score)

    def test_a11_negated_not_matched(self):
        result = self.match(skills_raw="不会Python")
        self.assertNotIn("Python", result.matched_skills)
        self.assertEqual(result.dimension_scores["required_skills"], 0)

    def test_a12_planned_not_matched(self):
        self.assert_polarities("计划学习MCP", {"MCP": "planned"})
        self.assertNotIn("MCP", self.match(skills_raw="计划学习MCP").matched_skills)

    def test_a13_other_person_not_matched(self):
        self.assert_polarities("团队使用Docker，我负责产品设计", {"Docker": "other_person"})
        self.assertNotIn("Docker", self.match(work_experience="团队使用Docker，我负责产品设计").matched_skills)

    def test_a14_html_evidence_preserved_as_data(self):
        text = '<script>alert("synthetic")</script>掌握Python & Docker'
        parsed = self.parse(text)
        self.assertEqual({item.standard_skill_name for item in parsed.skills}, {"Python", "Docker"})
        self.assertTrue(all(item.evidence == text for item in parsed.skills))

    def test_parallel_context_scopes(self):
        cases = [
            ("不会 Python、Docker 和 RAG", {"Python": "negated", "Docker": "negated", "RAG": "negated"}),
            ("从未使用 Python 和 Docker", {"Python": "negated", "Docker": "negated"}),
            ("没有 Python 或 Java 项目经验", {"Python": "negated", "Java": "negated"}),
            ("不具备 Java、MCP、LangGraph 经验", {"Java": "negated", "MCP": "negated", "LangGraph": "negated"}),
            ("只掌握 SQL，不会 Python", {"SQL": "affirmed", "Python": "negated"}),
            ("计划学习 MCP 和 LangGraph", {"MCP": "planned", "LangGraph": "planned"}),
            ("公司采用 Docker", {"Docker": "other_person"}),
            ("同事负责 Java 开发", {"Java": "other_person"}),
            ("正在学习 RAG", {"RAG": "planned"}),
            ("准备了解 MCP", {"MCP": "planned"}),
            ("具有 Java 开发经验", {"Java": "affirmed"}),
            ("熟练使用 Docker", {"Docker": "affirmed"}),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assert_polarities(text, expected)

    def test_uncertain_needs_review_even_with_complete_resume(self):
        result = self.parse("了解过 MCP", education="本科", experience="2年")
        self.assertTrue(result.need_human_review)
        self.assertTrue(result.skills[0].need_human_review)
        self.assertEqual(result.skills[0].polarity, "uncertain")
        self.assertFalse(result.skills[0].accepted)

    def test_aliases_and_word_boundaries(self):
        for text in ("FastAPI", "fastapi", "Fast API"):
            with self.subTest(text=text):
                self.assert_polarities(text, {"FastAPI": "affirmed"})
        self.assert_polarities("仅掌握 sql", {"SQL": "affirmed"})
        self.assertEqual(self.parse("FastAPIish SQLish").skills, [])

    def test_evidence_has_original_text_offsets_and_confidence_semantics(self):
        text = "  不会 Python、Docker 和 RAG  "
        items = self.services.skill_index.extract_fields([("skills_raw", text)])
        for item in items:
            self.assertEqual(text[item.start:item.end], item.matched_text)
            self.assertEqual(item.confidence_semantics, "rule_match_strength_not_mastery_probability")
            self.assertIn(item.matched_text, item.evidence)

    def test_evidence_is_the_smallest_supporting_original_fragment(self):
        text = "基于 LangGraph 设计 Agent 工作流。通过 Function Calling 调用搜索工具。了解 MCP。"
        parsed = self.parse(projects=text)
        evidence = {item.standard_skill_name: item.evidence for item in parsed.skills}
        self.assertEqual(evidence["LangGraph"], "基于 LangGraph 设计 Agent 工作流")
        self.assertEqual(evidence["Function Calling"], "通过 Function Calling 调用搜索工具")
        self.assertEqual(evidence["MCP"], "了解 MCP")
        self.assertNotEqual(evidence["LangGraph"], evidence["MCP"])

    def test_evidence_strength_distinguishes_practice_from_mention(self):
        parsed = self.parse("Python、FastAPI", projects="基于 LangGraph 设计 Agent 工作流。了解 MCP。")
        strengths = {item.standard_skill_name: item.evidence_strength for item in parsed.skills}
        self.assertEqual(strengths["LangGraph"], "strong")
        self.assertEqual(strengths["MCP"], "weak")
        self.assertEqual(strengths["Python"], "medium")

    def test_agent_resume_skills_keep_their_own_supporting_sentences(self):
        text = (
            "使用 Python/FastAPI 完成后端接口与数据处理模块。"
            "基于 LangGraph 设计 Agent 工作流。"
            "通过 Function Calling 调用搜索、计算和数据查询工具。"
            "开发基于 RAG 与 LangChain 的知识库问答系统。"
            "了解 MCP（Model Context Protocol）。"
        )
        parsed = self.parse(projects=text)
        strongest = {}
        rank = {"weak": 0, "medium": 1, "strong": 2}
        for item in parsed.skills:
            if item.standard_skill_name not in strongest or rank[item.evidence_strength] > rank[strongest[item.standard_skill_name].evidence_strength]:
                strongest[item.standard_skill_name] = item
        for name in ("Python", "FastAPI", "RAG", "LangChain", "LangGraph", "Function Calling", "MCP"):
            self.assertIn(name, strongest)
            self.assertIn(name, strongest[name].evidence)
        self.assertEqual(strongest["MCP"].evidence_strength, "weak")
        self.assertEqual(strongest["LangGraph"].evidence_strength, "strong")
        self.assertNotEqual(strongest["RAG"].evidence, strongest["LangGraph"].evidence)
        self.assertNotEqual(strongest["Function Calling"].evidence, strongest["MCP"].evidence)

    def test_resume_api_returns_evidence_based_job_coverage(self):
        result = parse_resume(ResumeParseRequest(
            target_job=JOB, education="硕士", experience="1年",
            projects="基于LangGraph开发Agent工作流。了解MCP。", skills_raw="Python",
        ))
        self.assertIn("Python", result.core_skills_covered)
        self.assertIn("LangGraph", result.core_skills_covered)
        self.assertIn("MCP", result.weak_evidence_skills)
        self.assertNotIn("MCP", result.core_skills_covered)
        self.assertGreater(result.coverage_denominator, 0)
        self.assertAlmostEqual(
            result.coverage_rate,
            result.coverage_numerator / result.coverage_denominator,
        )

    def test_empty_requirements_do_not_grant_free_credit(self):
        self.assertIsNone(self.services.matching_engine._ratio(0, 0))

    def test_unknown_normalization_is_explicit(self):
        result = self.match(skills_raw="Python")
        scores = result.dimension_scores
        weights = self.services.matching_engine.weights
        evaluated = [key for key, score in scores.items() if score is not None]
        self.assertEqual(result.evaluated_dimensions, evaluated)
        expected = sum(scores[key] * weights[key] for key in evaluated) / sum(weights[key] for key in evaluated)
        self.assertAlmostEqual(result.match_score, expected, places=1)

    def test_auxiliary_verbs_do_not_cancel_negation_or_plans(self):
        for text, expected in [
            ("不会使用Python和Docker", {"Python": "negated", "Docker": "negated"}),
            ("正在学习使用Docker", {"Docker": "planned"}),
            ("不会Python但掌握Docker", {"Python": "negated", "Docker": "affirmed"}),
        ]:
            with self.subTest(text=text):
                self.assert_polarities(text, expected)

    def test_conflicting_evidence_is_retained_for_review(self):
        parsed = self.parse("掌握Python", work_experience="不会Python", education="本科", experience="2年")
        self.assertEqual(len(parsed.skills), 2)
        self.assertTrue(parsed.need_human_review)
        self.assertFalse(any(item.accepted for item in parsed.skills))
        result = self.services.matching_engine.match(parsed, JOB)
        self.assertNotIn("Python", result.matched_skills)

    def test_runtime_extension_preserves_frozen_ids(self):
        frozen, _ = self.services.loader.load_skill_dictionary()
        self.assertEqual(len(frozen), 82)
        for row in frozen:
            self.assertEqual(self.services.skill_index.standard_name(row["skill_id"]), row["标准技能名称"])
        self.assertEqual(self.services.skill_index.resolve_name("SQL"), "SKILL-P0-SQL")
        self.assertEqual(self.services.skill_index.resolve_name("FastAPI"), "SKILL-P0-FASTAPI")


if __name__ == "__main__":
    unittest.main()
