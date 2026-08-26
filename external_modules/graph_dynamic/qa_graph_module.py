from __future__ import annotations
import json, zipfile, sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent; OUT=ROOT/"outputs"; sys.path.insert(0,str(ROOT/"src"))
from graph.graph_builder import file_hashes

EXPECTED={
"standardized_jd_dataset_v1.xlsx":"b00a0220fd4b974d8b00bb57d6f0af3bb40f1d92cc7ddd59fcb0ddda9fc90ede",
"standard_job_title_mapping_v1.xlsx":"293b34dbb8e4e6f5689cf58387a38601f30feb759b46e7f34931bc1f6ff859b1",
"standard_skill_dictionary_v1.xlsx":"178c64e654d3534878489e88aafc5a17b98fe361cb38db370f9036d01e5c1055"}
kg=json.loads((OUT/"knowledge_graph_v1.json").read_text(encoding="utf-8"))
ke=json.loads((OUT/"key_job_evolution_v1.json").read_text(encoding="utf-8"))
skill_ids=set(pd.read_excel(ROOT/"standard_skill_dictionary_v1.xlsx",sheet_name="标准技能")["skill_id"].astype(str))
nodes=kg["nodes"]; edges=kg["edges"]; js=[e for e in edges if e.get("edge_type")=="Job_Skill"]
checks={}
checks["frozen_hash_unchanged"]={k:v.lower()==EXPECTED[k] for k,v in file_hashes(ROOT).items()}
checks["node_ids_unique"]=len({n["id"] for n in nodes})==len(nodes)
checks["edge_ids_unique"]=len({e["id"] for e in edges})==len(edges)
checks["all_job_skill_ids_official"]=all(e["target"] in skill_ids for e in js)
checks["all_job_skill_have_evidence"]=all(bool(e.get("evidence_jd_ids")) for e in js)
checks["no_duplicate_job_skill_edges"]=len({(e["source"],e["target"]) for e in js})==len(js)
checks["key_jobs_present"]=all(j in ke["jobs"] and ke["jobs"][j]["current_top"] for j in ["AI Agent开发工程师","RAG引擎研发工程师","AI安全技术工程师"])
checks["strict_long_term_disabled"]=ke["meta"]["strict_long_term_supported"] is False
checks["small_samples_marked"]=all(r["演化状态"]=="样本不足" for v in ke["jobs"].values() for r in v["records"] if r["JD数量"]<3)
for f in ["graph_nodes_v1.xlsx","graph_edges_v1.xlsx","key_job_graph_profiles_v1.xlsx","job_skill_evolution_v1.xlsx"]:
    with zipfile.ZipFile(OUT/f) as z: checks[f+"_valid_xlsx"]=z.testzip() is None
checks["json_meta_counts_match"]=sum(kg["meta"]["node_counts"].values())==len(nodes) and sum(kg["meta"]["edge_counts"].values())==len(edges)
checks["visual_files_present"]=len(list((ROOT/"05_图片"/"图谱动态").glob("*.svg")))>=6
passed=all(v if isinstance(v,bool) else all(v.values()) for v in checks.values())
report={"passed":passed,"checks":checks,"node_count":len(nodes),"edge_count":len(edges),"job_skill_edge_count":len(js)}
(OUT/"qa_report_v1.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2)); raise SystemExit(0 if passed else 1)
