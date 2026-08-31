"""Deterministic engineering checks, not statistical significance or entity resolution."""
import copy
import hashlib
import re
import unicodedata
from datetime import date, datetime

# Minimal known alias from the existing project, not an external platform registry.
SOURCE_ALIASES = {'BOSS直聘官方招聘': 'BOSS直聘'}
NEAR_DUPLICATE_THRESHOLD = 0.90  # Engineering default, not a calibrated market threshold.


def normalize_source_name(value):
    text = str(value or '').strip()
    return SOURCE_ALIASES.get(text, text)


def normalize_company_name(value):
    # Do not remove legal suffixes: parent/subsidiary relationships are not known.
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', str(value or ''))).strip().casefold()


def _date(value):
    try:
        text = str(value)
        return (date.fromisoformat(text) if len(text) == 10 else datetime.fromisoformat(text).date()).isoformat()
    except (ValueError, TypeError):
        return None


def time_metadata(rows, minimum_coverage=0.60):
    records = []
    for row in rows:
        published, collected = _date(row.get('published_at')), _date(row.get('collected_at'))
        records.append(dict(job_id=row.get('job_id', row.get('jd_id')),
                            published_at=row.get('published_at'), collected_at=row.get('collected_at'),
                            first_seen_at=row.get('first_seen_at'), time_value=published or collected,
                            time_source='published_at' if published else 'collected_at_fallback' if collected else 'unknown'))
    total = len(records)
    published = sum(r['time_source'] == 'published_at' for r in records)
    fallback = sum(r['time_source'] == 'collected_at_fallback' for r in records)
    coverage = published/total if total else None
    quality = 'unknown' if not total else 'high' if coverage == 1 else 'medium' if coverage >= minimum_coverage else 'low'
    return dict(total_jobs=total, published_at_count=published, fallback_count=fallback,
                unknown_time_count=total-published-fallback, published_at_coverage=coverage, time_quality=quality,
                minimum_publish_coverage=minimum_coverage, records=records,
                quality_rule='high: all published; medium: coverage >= configured minimum; low: otherwise; empty: unknown',
                notice='部分记录缺少原始发布时间，趋势计算使用采集时间回退。' if fallback else '未将首次发现或采集时间伪装成招聘发布日期。')


def _normalized_text(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())


def detect_duplicates(rows, threshold=NEAR_DUPLICATE_THRESHOLD):
    if not 0 < threshold <= 1:
        raise ValueError('threshold must be in (0,1]')
    ids = [str(r.get('job_id') or r.get('jd_id') or '') for r in rows]
    if any(not key for key in ids) or len(ids) != len(set(ids)):
        raise ValueError('Each record must have a unique nonempty job id')
    raw = [tuple(str(r.get(k) or '') for k in ('responsibilities', 'required_skills_raw', 'bonus_skills_raw')) for r in rows]
    text = [_normalized_text('\n'.join(parts)) for parts in raw]
    tokens = [{t[i:i+2] for i in range(len(t)-1)} for t in text]
    companies = [normalize_company_name(r.get('company')) for r in rows]
    titles = [_normalized_text(str(r.get('original_title') or r.get('original_job_title') or r.get('standard_job_title') or '')) for r in rows]

    def score(a, b):
        # Same employer and title required; unknown employers are not guessed.
        if not companies[a] or companies[a] != companies[b] or not titles[a] or titles[a] != titles[b] or not tokens[a] or not tokens[b]:
            return 0
        return len(tokens[a] & tokens[b]) / len(tokens[a] | tokens[b])

    clusters = []
    for i in sorted(range(len(rows)), key=lambda n: ids[n]):
        # Complete linkage avoids transitive A~B~C chains merging dissimilar A,C.
        target = next((group for group in clusters if all(score(i, member) >= threshold for member in group)), None)
        if target is None:
            clusters.append([i])
        else:
            target.append(i)
    groups, annotations = [], {key: dict(job_id=key, is_near_duplicate=False, duplicate_type=None,
                                         duplicate_group_id=None, duplicate_score=None, canonical_candidate_id=key) for key in ids}
    exact_extra = 0
    for cluster in clusters:
        if len(cluster) < 2:
            continue
        members = [ids[i] for i in cluster]
        group_id = 'DUP-' + hashlib.sha256('\n'.join(members).encode()).hexdigest()[:16]
        kind = 'exact' if len({raw[i] for i in cluster}) == 1 else 'near'
        similarity = min(score(a, b) for a in cluster for b in cluster if a != b)
        exact_extra += len(cluster) - len({raw[i] for i in cluster})
        groups.append(dict(duplicate_group_id=group_id, job_ids=members, duplicate_type=kind,
                           duplicate_score=similarity, canonical_candidate_id=members[0]))
        for i in cluster:
            annotations[ids[i]].update(is_near_duplicate=kind == 'near', duplicate_type=kind,
                                       duplicate_group_id=group_id, duplicate_score=similarity, canonical_candidate_id=members[0])
    return dict(raw_evidence_count=len(rows), independent_evidence_count=len(clusters), groups=groups,
                exact_duplicate_count=exact_extra, near_duplicate_group_count=sum(g['duplicate_type'] == 'near' for g in groups),
                records=[annotations[key] for key in ids], threshold=threshold,
                independence_notice='保守重复组估计，不代表统计独立性；未删除、合并或改写记录。')


def quality_report(rows, minimum_coverage=0.60):
    times, duplicates = time_metadata(rows, minimum_coverage), detect_duplicates(rows)
    names = [dict(job_id=r.get('job_id', r.get('jd_id')), source_raw=r.get('source'), source_normalized=normalize_source_name(r.get('source')),
                  company_raw=r.get('company'), company_normalized=normalize_company_name(r.get('company'))) for r in rows]
    count = lambda field: len({r[field] for r in names if r[field]})
    return dict(**{k: v for k, v in duplicates.items() if k != 'records'}, time_quality=times,
                source_count_raw=count('source_raw'), source_count_normalized=count('source_normalized'),
                company_count_raw=count('company_raw'), company_count_normalized=count('company_normalized'),
                missing_field_ratio={key: sum(not str(r.get(key) or '').strip() for r in rows)/len(rows) if rows else None
                                     for key in ('company', 'source', 'responsibilities', 'required_skills_raw')},
                records=[dict(n, **{k: v for k, v in t.items() if k != 'job_id'},
                              **{k: v for k, v in d.items() if k != 'job_id'}) for n, t, d in zip(names, times['records'], duplicates['records'])],
                statistics_policy='derived_only_original_counts_and_scores_unchanged')


def guard_evolution(record, minimum):
    """Gate existing classifications, do not regenerate frequencies or market trends."""
    if not isinstance(minimum, int) or minimum < 1:
        raise ValueError('minimum sample must be a positive integer')
    result = copy.deepcopy(record)
    records = result.get('records', [])
    windows = {}
    for row in records:
        window, count = _date(row.get('时间窗口')), row.get('JD数量')
        if window and isinstance(count, int) and count >= 0:
            windows.setdefault(window, set()).add(count)
    counts = {key: next(iter(value)) if len(value) == 1 else 0 for key, value in windows.items()}
    ordered = sorted(counts)
    before = counts[ordered[-2]] if len(ordered) >= 2 else None
    after = counts[ordered[-1]] if ordered else None
    enough = before is not None and after is not None and min(before, after) >= minimum
    result['window_samples'] = dict(before=before, after=after, minimum=minimum)
    result['trend_status'] = 'sample_sufficient' if enough else 'insufficient_sample'
    # Sanitize historical records too, so clients cannot accidentally render unsafe labels.
    for row in records:
        window = _date(row.get('时间窗口'))
        index = ordered.index(window) if window in ordered else -1
        valid = index > 0 and min(counts[ordered[index-1]], counts[ordered[index]]) >= minimum
        if not valid:
            row.update(演化状态='样本不足', 是否样本充分=False, trend_status='insufficient_sample')
    groups = {name: [] for name in ('快速增长', '新增', '稳定', '下降', '样本不足')}
    for row in records:
        if ordered and _date(row.get('时间窗口')) == ordered[-1]:
            groups.setdefault(row.get('演化状态', '样本不足'), []).append(row)
    result['status_summary'] = groups
    return result
