"""SYNTHETIC TEST DATA / NOT REAL RECRUITMENT DATA. Actual service regression."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from fixtures.p2_synthetic.synthetic_fixture import jd, evolution
from src.quality.science import normalize_source_name, normalize_company_name, time_metadata, quality_report, detect_duplicates, guard_evolution
from src.integration.evolution_adapter import EvolutionAdapter


class QualityTest(unittest.TestCase):
    def test_a01_before_insufficient(self):
        value = guard_evolution(evolution(1, 11), 3)
        self.assertEqual(value['trend_status'], 'insufficient_sample')
        self.assertEqual(value['status_summary']['下降'], [])
        self.assertEqual(value['window_samples'], {'before': 1, 'after': 11, 'minimum': 3})

    def test_a02_after_insufficient(self):
        self.assertEqual(guard_evolution(evolution(11, 1), 3)['trend_status'], 'insufficient_sample')

    def test_a03_sufficient_allows_existing_classification(self):
        self.assertEqual(guard_evolution(evolution(3, 4), 3)['trend_status'], 'sample_sufficient')
        self.assertEqual(len(guard_evolution(evolution(3, 4), 3)['status_summary']['下降']), 1)

    def test_a04_time_fallback_and_missing(self):
        row = jd(published_at=None)
        self.assertEqual(time_metadata([row])['records'][0]['time_source'], 'collected_at_fallback')
        row['collected_at'] = None
        row['first_seen_at'] = '2026-01-03'
        self.assertEqual(time_metadata([row])['records'][0]['time_source'], 'unknown')
        self.assertEqual(time_metadata([jd(published_at='invalid')])['published_at_count'], 0)
        self.assertEqual(time_metadata([jd(published_at='2026-01-01FAKE')])['published_at_count'], 0)

    def test_a05_coverage(self):
        result = time_metadata([jd(), jd(2, published_at=None)])
        self.assertEqual(result['published_at_coverage'], .5)
        self.assertEqual(result['fallback_count'], 1)
        self.assertEqual(result['time_quality'], 'low')

    def test_a06_source_equivalence(self):
        self.assertEqual(normalize_source_name('BOSS直聘官方招聘'), 'BOSS直聘')

    def test_a07_unknown_source_not_guessed(self):
        self.assertEqual(normalize_source_name('synthetic_unknown官方招聘'), 'synthetic_unknown官方招聘')

    def test_a08_company_format(self):
        self.assertEqual(normalize_company_name('  测试企业Ａ  '), normalize_company_name('测试企业A'))

    def test_a09_different_companies(self):
        self.assertNotEqual(normalize_company_name('测试企业A有限公司'), normalize_company_name('测试企业B有限公司'))
        self.assertNotEqual(normalize_company_name('测试企业A'), normalize_company_name('测试企业A有限公司'))

    def test_a10_exact_duplicate(self):
        result = detect_duplicates([jd(), jd(2, source='synthetic_source_2')])
        self.assertEqual(result['groups'][0]['duplicate_type'], 'exact')
        self.assertEqual(result['exact_duplicate_count'], 1)

    def test_a11_near_duplicate(self):
        result = detect_duplicates([jd(), jd(2, responsibilities='维护测试服务 处理测试请求 记录测试运行日志')])
        self.assertEqual(result['groups'][0]['duplicate_type'], 'near')

    def test_a12_different_jobs(self):
        other = jd(2, responsibilities='整理纸质档案和寄送测试信函', required_skills_raw='档案整理')
        self.assertEqual(detect_duplicates([jd(), other])['groups'], [])
        self.assertEqual(detect_duplicates([jd(), jd(2, company='测试企业B')])['groups'], [])

    def test_a13_input_immutable(self):
        rows = [jd(), jd(2)]
        before = copy.deepcopy(rows)
        quality_report(rows)
        self.assertEqual(rows, before)

    def test_a14_raw_count(self):
        self.assertEqual(quality_report([jd(), jd(2)])['raw_evidence_count'], 2)

    def test_a15_independent_count(self):
        self.assertEqual(quality_report([jd(), jd(2), jd(3, company='测试企业B')])['independent_evidence_count'], 2)

    def test_empty_text_is_not_duplicate(self):
        self.assertEqual(detect_duplicates([jd(responsibilities='', required_skills_raw=''), jd(2, responsibilities='', required_skills_raw='')])['groups'], [])

    def test_raw_names_preserved(self):
        value = quality_report([jd(company='  测试企业Ａ  ', source='BOSS直聘官方招聘')])['records'][0]
        self.assertEqual(value['company_raw'], '  测试企业Ａ  ')
        self.assertEqual(value['source_raw'], 'BOSS直聘官方招聘')
        self.assertEqual(value['source_normalized'], 'BOSS直聘')

    def test_loader_retains_whitespace_invalid_dates_and_first_seen(self):
        from types import SimpleNamespace
        from src.quality.loader import load_quality_records
        raw = {'编号': 'SYNTHETIC-JD-RAW', '企业': '  测试企业Ａ  ', '来源': ' synthetic_source_1 ',
               '标准发布时间': 'invalid', '采集时间': '2026-01-01', '首次发现时间': '2026-01-02'}
        loader = SimpleNamespace(sources={'standardized_jd_dataset': {'sheet': 'synthetic'}},
                                 field_mapping={'standardized_jd_dataset': {'jd_id': '编号', 'company': '企业', 'source': '来源'}},
                                 resolve_path=lambda key: None, read_sheet=lambda path, sheet: [raw])
        value = load_quality_records(loader)[0]
        self.assertEqual(value['company'], raw['企业'])
        self.assertEqual(value['source'], raw['来源'])
        self.assertEqual(value['published_at'], 'invalid')
        self.assertEqual(value['first_seen_at'], '2026-01-02')

    def test_no_window_counts_fails_closed(self):
        value = evolution()
        value['records'] = []
        self.assertEqual(guard_evolution(value, 3)['trend_status'], 'insufficient_sample')

    def test_adapter_uses_both_windows_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root/'key_job_evolution_v1.json'
            payload = {'meta': {'config': {'min_jd_count': 3}}, 'jobs': {'合成测试岗位': evolution()}}
            path.write_text(json.dumps(payload), encoding='utf-8')
            original = path.read_bytes()
            result = EvolutionAdapter(root).for_job('合成测试岗位')
            self.assertTrue(result['sample_insufficient'])
            self.assertEqual(result['declining_skills'], [])
            self.assertEqual(path.read_bytes(), original)
