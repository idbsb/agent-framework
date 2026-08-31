"""Use the existing read-only data gateway, preserving raw cell values for quality checks."""


def load_quality_records(loader):
    key = 'standardized_jd_dataset'
    rows = loader.read_sheet(loader.resolve_path(key), loader.sources[key]['sheet'])
    mapping = loader.field_mapping[key]
    result = []
    for raw in rows:
        row = {internal: raw.get(column) for internal, column in mapping.items()}
        result.append(dict(row, job_id=row.get('jd_id'), original_title=row.get('original_job_title'),
                           published_at=raw.get('标准发布时间') or None,
                           collected_at=raw.get('采集时间') or None, first_seen_at=raw.get('首次发现时间') or None))
    return result
