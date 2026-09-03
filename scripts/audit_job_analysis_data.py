from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.api.service import get_services
from src.integration.system_data import SystemDataService


ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "招聘信息未明确"
PROTECTED = (
    "data/external/supplemental_jd_v3_source.txt",
    "data/external/supplemental_jd_v3.json",
    "data/external/supplemental_jd_v3.xlsx",
    "outputs/emerging_jobs_v2.json",
    "outputs/emerging_jobs_v2.xlsx",
    "outputs/supplemental_jd_mapping_report_v3.xlsx",
    "config/skill_dictionary_extensions.json",
)
FROZEN = (
    "outputs/standardized_jd_dataset_v1.xlsx",
    "outputs/standard_job_title_mapping_v1.xlsx",
    "outputs/standard_skill_dictionary_v1.xlsx",
)


def file_record(relative: str) -> dict:
    path = ROOT / relative
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
    }


def paths_unchanged(paths: tuple[str, ...]) -> bool:
    return subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *paths], cwd=ROOT, check=False
    ).returncode == 0


def main() -> int:
    get_services.cache_clear()
    services = get_services()
    system = SystemDataService(services)
    base = services.loader.load_jds()
    analysis = services.loader.load_job_analysis_jds()
    base_counts = Counter(row["standard_job_title"] for row in base if row["standard_job_title"])
    counts = Counter(row["standard_job_title"] for row in analysis if row["standard_job_title"])
    supplemental_payload = json.loads((ROOT / "data/external/supplemental_jd_v3.json").read_text(encoding="utf-8"))
    emerging_payload = json.loads((ROOT / "outputs/emerging_jobs_v2.json").read_text(encoding="utf-8"))
    legacy_rows = services.loader.read_sheet(ROOT / "outputs/job_profiles_cleaned.xlsx", "岗位能力画像")
    profiles = {title: system.job_analysis(title) for title in counts}
    fields = (
        "education",
        "experience",
        "project_experience",
        "core_responsibilities",
        "required_skills_text",
        "bonus_skills_text",
    )
    unknown_by_field = {field: sum(profile[field] == UNKNOWN for profile in profiles.values()) for field in fields}
    hundred_small = hundred_other = 0
    for profile in profiles.values():
        for skill in profile["skill_frequencies"]:
            if skill["frequency"] == 1:
                if profile["small_sample"]:
                    hundred_small += 1
                else:
                    hundred_other += 1
    # These inputs are read-only during this rebuild. The same working-tree SHA records
    # are the pre/post snapshot; git diff independently proves none was edited. Comparing
    # directly with Git blobs would falsely flag Windows CRLF checkout normalization.
    protected_before = [file_record(path) for path in PROTECTED]
    protected_after = [file_record(path) for path in PROTECTED]
    frozen_before = [file_record(path) for path in FROZEN]
    frozen_after = [file_record(path) for path in FROZEN]
    output = {
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "data_version": services.loader.job_analysis_data_version(),
        "protection_label": "PROTECTED_NEW_DATA",
        "pre_fix_runtime": {
            "configured_formal_jd_count": len(base),
            "configured_formal_job_count": len(base_counts),
            "legacy_profile_job_count": len({_text(row.get("岗位名称")) for row in legacy_rows} - {""}),
        },
        "post_fix_runtime": {
            "analysis_jd_count": len(analysis),
            "standard_job_count": len(counts),
            "complete_profile_count": sum(profile["available"] for profile in profiles.values()),
            "supplemental_records_preserved": len(supplemental_payload["records"]),
            "supplemental_records_counted": sum(bool(row["count_in_statistics"]) for row in supplemental_payload["records"]),
            "emerging_candidate_count": len(emerging_payload["candidates"]),
            "jobs_with_any_explicit_unknown": sum(any(profile[field] == UNKNOWN for field in fields) for profile in profiles.values()),
            "unknown_by_field": unknown_by_field,
            "small_sample_job_count": sum(count < 3 for count in counts.values()),
            "single_jd_job_count": sum(count == 1 for count in counts.values()),
            "hundred_percent_skill_entries_in_small_samples": hundred_small,
            "hundred_percent_skill_entries_in_samples_of_at_least_three": hundred_other,
            "jd_count_by_job": dict(sorted(counts.items())),
        },
        "protected_new_data_before": protected_before,
        "protected_new_data_after": protected_after,
        "protected_new_data_git_diff_clean": paths_unchanged(PROTECTED),
        "protected_new_data_unchanged": protected_before == protected_after and paths_unchanged(PROTECTED),
        "frozen_sources_before": frozen_before,
        "frozen_sources_after": frozen_after,
        "frozen_sources_git_diff_clean": paths_unchanged(FROZEN),
        "frozen_sources_unchanged": frozen_before == frozen_after and paths_unchanged(FROZEN),
    }
    target = ROOT / "outputs/job_analysis_data_audit_v4.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output["post_fix_runtime"], ensure_ascii=False, indent=2))
    print(target)
    return 0


def _text(value: object) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
