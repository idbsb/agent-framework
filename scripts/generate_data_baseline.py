"""Generate a reproducible count and hash baseline for protected production data."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_loader import DataLoader


PROTECTED_PATHS = (
    "outputs/standardized_jd_dataset_v1.xlsx",
    "outputs/standard_job_title_mapping_v1.xlsx",
    "outputs/standard_skill_dictionary_v1.xlsx",
    "outputs/standardized_resume_testset_v1.xlsx",
    "outputs/emerging_jobs_v1.json",
    "outputs/emerging_jobs_v2.json",
    "data/external/supplemental_jd_v3.json",
    "data/external/supplemental_jd_v3.xlsx",
    "data/external/supplemental_jd_v3_source.txt",
    "multi_source_evidence_v1.json",
    "multi_source_evidence_v1 (1).xlsx",
    "config/skill_dictionary_extensions.json",
    "external_modules/graph_dynamic/outputs/knowledge_graph_v1.json",
    "external_modules/graph_dynamic/outputs/key_job_evolution_v1.json",
    "external_modules/graph_dynamic/outputs/graph_nodes_v1.xlsx",
    "external_modules/graph_dynamic/outputs/graph_edges_v1.xlsx",
    "external_modules/graph_dynamic/outputs/job_skill_evolution_v1.xlsx",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def generate(root: Path) -> dict:
    loader = DataLoader(root / "config" / "data_sources.yaml")
    jds = loader.load_jds()
    frozen_skills, _ = loader.load_skill_dictionary()
    runtime_skills, _ = loader.load_runtime_skill_dictionary()
    graph = load_json(root / "external_modules/graph_dynamic/outputs/knowledge_graph_v1.json")
    emerging = load_json(root / "outputs/emerging_jobs_v2.json")
    supplemental = load_json(root / "data/external/supplemental_jd_v3.json")
    multi_source = load_json(root / "multi_source_evidence_v1.json")
    standard_jobs = {
        str(row.get("standard_job_title", "")).strip()
        for row in jds
        if str(row.get("standard_job_title", "")).strip()
    }
    files = {}
    for relative in PROTECTED_PATHS:
        path = root / relative
        if path.is_file():
            files[relative] = {"sha256": sha256(path), "bytes": path.stat().st_size}
        else:
            files[relative] = {"missing": True}
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "project_root": str(root.resolve()),
        "counts": {
            "jd_count": len(jds),
            "standard_job_count": len(standard_jobs),
            "standard_skill_count": len(runtime_skills),
            "frozen_standard_skill_count": len(frozen_skills),
            "graph_node_count": len(graph.get("nodes", [])),
            "graph_edge_count": len(graph.get("edges", [])),
            "emerging_candidate_count": len(emerging.get("candidates", [])),
            "test_resume_count": len(loader.load_resumes()),
            "multi_source_evidence_count": len(multi_source.get("evidence", [])),
            "supplemental_jd_count": len(supplemental.get("records", supplemental.get("data", []))),
        },
        "core_data_files": files,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = PROJECT_ROOT
    value = generate(root)
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(value["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
