from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd


FROZEN_FILES = (
    "standardized_jd_dataset_v1.xlsx",
    "standard_job_title_mapping_v1.xlsx",
    "standard_skill_dictionary_v1.xlsx",
)


def file_hashes(root: Path) -> dict[str, str]:
    return {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in FROZEN_FILES
    }


def _clean(value) -> str:
    return "" if pd.isna(value) else str(value).strip()


def _contains(text: str, alias: str) -> bool:
    if not alias:
        return False
    text_l, alias_l = text.casefold(), alias.casefold()
    if len(alias_l) <= 2 and alias_l.isascii() and alias_l.isalnum():
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(alias_l)}(?![A-Za-z0-9])", text_l) is not None
    return alias_l in text_l


def load_sources(root: Path):
    jd = pd.read_excel(root / FROZEN_FILES[0], sheet_name="标准化JD")
    jobs = pd.read_excel(root / FROZEN_FILES[1], sheet_name="岗位名称映射")
    skills = pd.read_excel(root / FROZEN_FILES[2], sheet_name="标准技能")
    aliases = pd.read_excel(root / FROZEN_FILES[2], sheet_name="技能别名")
    human = pd.read_excel(root / "重要岗位技能分析表.xlsx", sheet_name="Sheet1")
    human["岗位名称"] = human["岗位名称"].ffill()
    return jd, jobs, skills, aliases, human


def _company_id(name: str) -> str:
    return "COMPANY-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:12].upper()


def _job_id(title: str) -> str:
    return "JOB-" + hashlib.sha1(title.encode("utf-8")).hexdigest()[:12].upper()


def _domain_id(name: str) -> str:
    return "DOMAIN-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:12].upper()


def build_graph(root: Path) -> dict:
    jd, mapping, skills, aliases, human = load_sources(root)
    alias_map: dict[str, list[str]] = defaultdict(list)
    for _, row in aliases.iterrows():
        sid, alias = _clean(row.get("skill_id")), _clean(row.get("原始技能写法"))
        if sid and alias and alias not in alias_map[sid]:
            alias_map[sid].append(alias)
    for _, row in skills.iterrows():
        sid, name = _clean(row["skill_id"]), _clean(row["标准技能名称"])
        if name and name not in alias_map[sid]:
            alias_map[sid].append(name)

    valid_jd = jd[jd["标准岗位名称"].notna()].copy()
    valid_jd["标准岗位名称"] = valid_jd["标准岗位名称"].astype(str).str.strip()
    skill_meta = {str(r["skill_id"]): r for _, r in skills.iterrows()}
    human_map = {}
    for _, r in human.iterrows():
        key = (_clean(r.get("岗位名称")), _clean(r.get("技能名称")).casefold())
        if all(key):
            human_map[key] = {
                "importance": _clean(r.get("重要程度")),
                "skill_level": _clean(r.get("技能层次")),
                "human_frequency": None if pd.isna(r.get("出现频率")) else float(r.get("出现频率")),
            }

    mentions = []
    for _, row in valid_jd.iterrows():
        required = _clean(row.get("必备技能原文"))
        bonus = _clean(row.get("加分技能原文"))
        all_text = "\n".join([_clean(row.get("工作职责")), required, bonus])
        for sid, als in alias_map.items():
            req_hit = any(_contains(required, a) for a in als)
            bonus_hit = any(_contains(bonus, a) for a in als)
            any_hit = req_hit or bonus_hit or any(_contains(all_text, a) for a in als)
            if any_hit:
                relation = "REQUIRES" if req_hit else ("BONUS_SKILL" if bonus_hit else "MENTIONS")
                mentions.append({
                    "jd_id": _clean(row["JD编号"]), "job_title": _clean(row["标准岗位名称"]),
                    "skill_id": sid, "skill_name": _clean(skill_meta[sid]["标准技能名称"]),
                    "relation_type": relation,
                })

    mention_df = pd.DataFrame(mentions)
    nodes = {"Jobs": [], "Skills": [], "JDs": [], "Companies": [], "Domains": []}
    edges = {"Job_Skill": [], "JD_Job": [], "JD_Skill": [], "Job_Domain": [], "Company_JD": []}
    for title, group in valid_jd.groupby("标准岗位名称"):
        first = group.iloc[0]
        domains = sorted({d.strip() for x in group["技术领域"].dropna().astype(str) for d in re.split(r"[,，;；]", x) if d.strip()})
        nodes["Jobs"].append({"job_id": _job_id(title), "standard_job_title": title, "job_family": _clean(first.get("岗位族")), "technical_domain": ",".join(domains)})
        for domain in domains:
            edges["Job_Domain"].append({"source": _job_id(title), "target": _domain_id(domain), "relation": "BELONGS_TO"})
    domain_names = sorted({e["target"] for e in edges["Job_Domain"]})
    domain_label = {}
    for n in nodes["Jobs"]:
        for d in n["technical_domain"].split(",") if n["technical_domain"] else []:
            domain_label[_domain_id(d)] = d
    nodes["Domains"] = [{"domain_id": did, "domain_name": domain_label[did]} for did in domain_names]
    for _, r in skills.iterrows():
        nodes["Skills"].append({"skill_id": _clean(r["skill_id"]), "standard_skill_name": _clean(r["标准技能名称"]), "skill_category": _clean(r.get("技能类别")), "technical_domain": _clean(r.get("技术领域"))})
    companies = {}
    for _, r in valid_jd.iterrows():
        jdid, title, company = _clean(r["JD编号"]), _clean(r["标准岗位名称"]), _clean(r.get("企业名称"))
        nodes["JDs"].append({
            "jd_id": jdid, "original_job_title": _clean(r.get("原始岗位名称")), "standard_job_title": title,
            "company": company, "city": _clean(r.get("城市")), "publish_time": _clean(r.get("标准发布时间")),
            "collection_time": _clean(r.get("采集时间")), "recruitment_source": _clean(r.get("招聘来源")), "source_url": _clean(r.get("原始链接")),
        })
        edges["JD_Job"].append({"source": jdid, "target": _job_id(title), "relation": "INSTANCE_OF"})
        if company:
            cid = _company_id(company); companies[cid] = company
            edges["Company_JD"].append({"source": cid, "target": jdid, "relation": "RECRUITS"})
    nodes["Companies"] = [{"company_id": cid, "company_name": name} for cid, name in sorted(companies.items())]
    for _, r in mention_df.iterrows():
        edges["JD_Skill"].append({"source": r.jd_id, "target": r.skill_id, "relation": "MENTIONS", "relation_type": r.relation_type})
    if not mention_df.empty:
        job_counts = valid_jd.groupby("标准岗位名称")["JD编号"].nunique().to_dict()
        for (title, sid), g in mention_df.groupby(["job_title", "skill_id"]):
            evidence = sorted(g["jd_id"].unique().tolist())
            rel_counts = g["relation_type"].value_counts().to_dict()
            relation = "REQUIRES" if rel_counts.get("REQUIRES", 0) else ("BONUS_SKILL" if rel_counts.get("BONUS_SKILL", 0) else "MENTIONS")
            sm = skill_meta[sid]; h = human_map.get((title, _clean(sm["标准技能名称"]).casefold()), {})
            edges["Job_Skill"].append({
                "source": _job_id(title), "target": sid, "skill_id": sid, "job_title": title, "skill_name": _clean(sm["标准技能名称"]),
                "relation": relation, "relation_type": relation, "mention_count": len(g), "source_count": len(evidence),
                "frequency": len(evidence) / job_counts[title], "evidence_jd_ids": evidence,
                "first_seen": "", "last_seen": "", "importance": h.get("importance", ""),
                "skill_level": h.get("skill_level", ""), "confidence": 1.0,
            })
    return {"nodes": nodes, "edges": edges, "mentions": mention_df, "valid_jd": valid_jd, "skills": skills, "human": human}
