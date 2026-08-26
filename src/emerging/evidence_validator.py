from __future__ import annotations


def validate_candidates(candidates: list[dict], source_jd_ids: set[str]) -> dict[str, object]:
    errors: list[str] = []
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id", ""))
        evidence_ids = [str(value) for value in candidate.get("evidence_jd_ids", [])]
        evidence_records = candidate.get("evidence_records", [])
        record_ids = [str(item.get("jd_id", "")) for item in evidence_records]
        if not candidate_id or not candidate.get("candidate_name"):
            errors.append(f"{candidate_id or '<missing>'}: candidate identity is incomplete")
        if not evidence_ids:
            errors.append(f"{candidate_id}: evidence_jd_ids is empty")
        if set(evidence_ids) - source_jd_ids:
            errors.append(f"{candidate_id}: contains unknown JD ids")
        if set(record_ids) != set(evidence_ids):
            errors.append(f"{candidate_id}: evidence_records do not match evidence_jd_ids")
        if int(candidate.get("jd_count", 0)) != len(evidence_ids):
            errors.append(f"{candidate_id}: jd_count does not match evidence ids")
        if int(candidate.get("jd_count", 0)) <= 1 and candidate.get("confidence_level") != "弱候选/待观察":
            errors.append(f"{candidate_id}: singleton candidate confidence is too high")
        representative_titles = set(candidate.get("representative_titles", []))
        if candidate.get("candidate_name") not in representative_titles:
            errors.append(f"{candidate_id}: candidate name is not a real representative title")
    return {"passed": not errors, "errors": errors, "candidate_count": len(candidates)}

