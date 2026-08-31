"""SYNTHETIC TEST DATA / NOT REAL RECRUITMENT DATA. No real people or employers."""
import copy

MARKER = 'SYNTHETIC TEST DATA / NOT REAL RECRUITMENT DATA'


def jd(number=1, **overrides):
    return dict(dict(job_id=f'SYNTHETIC-JD-{number:03}', original_title='合成测试岗位',
                     company='测试企业A', source='synthetic_source_1',
                     responsibilities='维护测试服务，处理测试请求，记录测试运行日志。',
                     required_skills_raw='掌握 Python 和 SQL', bonus_skills_raw='',
                     published_at='2026-01-01', collected_at='2026-01-02',
                     first_seen_at=None, dataset_notice=MARKER), **overrides)


def evolution(before=1, after=11):
    rows = [dict(skill_id='SYNTHETIC-SKILL-1', 技能名称='Python', 时间窗口=day, JD数量=count,
                 技能频率=freq, 演化状态=status, 是否样本充分=True)
            for day, count, freq, status in [('2026-01-01', before, 1.0, '稳定'), ('2026-01-02', after, 0.8, '下降')]]
    return dict(records=rows, status_summary={'下降': [copy.deepcopy(rows[-1])]},
                support_jd_count=before+after, current_top=[], time_range=['2026-01-01', '2026-01-02'])


GOLD = [dict(id='SYNTHETIC-RESUME-1', skills=[dict(skill='Python', polarity='affirmed'), dict(skill='Docker', polarity='negated')],
             fields=dict(education='本科', experience=None), dataset_notice=MARKER)]
PREDICTION = [dict(id='SYNTHETIC-RESUME-1', skills=[dict(skill='Python', polarity='affirmed'), dict(skill='Docker', polarity='affirmed')],
                   fields=dict(education='本科', experience='1年'))]
