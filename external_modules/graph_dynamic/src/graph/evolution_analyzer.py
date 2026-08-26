from __future__ import annotations

from pathlib import Path
import pandas as pd


def _load_config(path: Path) -> dict:
    """Parse this module's deliberately simple scalar-only YAML config."""
    result = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        if value.lower() in {"true", "false"}:
            result[key] = value.lower() == "true"
        else:
            try: result[key] = int(value)
            except ValueError:
                try: result[key] = float(value)
                except ValueError: result[key] = value.strip("\"'")
    return result


def analyze_evolution(root: Path, graph: dict) -> tuple[pd.DataFrame, dict]:
    cfg = _load_config(root / "config" / "evolution_config.yaml")
    jd = graph["valid_jd"].copy()
    publish = pd.to_datetime(jd["标准发布时间"], errors="coerce")
    collect = pd.to_datetime(jd["采集时间"], errors="coerce")
    coverage = float(publish.notna().mean())
    use_publish = coverage >= float(cfg["publish_time_min_coverage"])
    effective = publish if use_publish else publish.fillna(collect)
    jd["effective_time"] = effective
    jd["time_source"] = "标准发布时间" if use_publish else "标准发布时间（有效时）+采集批次回退"
    if cfg["time_window"] == "month":
        jd["window"] = effective.dt.to_period("M").astype(str)
    elif cfg["time_window"] == "week":
        jd["window"] = effective.dt.to_period("W").astype(str)
    else:
        jd["window"] = effective.dt.strftime("%Y-%m-%d")
    mention = graph["mentions"].merge(jd[["JD编号", "window", "effective_time"]], left_on="jd_id", right_on="JD编号", how="left")
    rows = []
    for title, jg in jd.dropna(subset=["window"]).groupby("标准岗位名称"):
        windows = sorted(jg["window"].unique())
        prev = {}
        skill_ids = sorted(mention.loc[mention.job_title == title, "skill_id"].unique())
        for window in windows:
            wjds = set(jg.loc[jg.window == window, "JD编号"]); n = len(wjds)
            for sid in skill_ids:
                mg = mention[(mention.job_title == title) & (mention.skill_id == sid) & (mention.window == window)]
                ev = sorted(mg.jd_id.unique().tolist()); count = len(ev); freq = count / n if n else 0
                pf = prev.get(sid); delta = None if pf is None else freq - pf
                growth = None if pf in (None, 0) else delta / pf
                sufficient = n >= int(cfg["min_jd_count"])
                if not sufficient:
                    status = "样本不足"
                elif pf is None or (pf == 0 and count >= int(cfg["new_skill_min_count"])):
                    status = "新增"
                elif delta >= float(cfg["growth_threshold"]): status = "快速增长"
                elif delta <= float(cfg["decline_threshold"]): status = "下降"
                else: status = "稳定"
                all_m = mention[(mention.job_title == title) & (mention.skill_id == sid)]
                times = all_m["effective_time"].dropna()
                rows.append({"标准岗位": title, "skill_id": sid, "技能名称": mg.skill_name.iloc[0] if len(mg) else all_m.skill_name.iloc[0],
                    "时间窗口": window, "JD数量": n, "技能出现次数": count, "技能频率": freq, "上一期频率": pf,
                    "变化量": delta, "变化率": growth, "first_seen": times.min().isoformat() if len(times) else "",
                    "last_seen": times.max().isoformat() if len(times) else "", "演化状态": status,
                    "evidence_jd_ids": ev, "是否样本充分": sufficient})
                prev[sid] = freq
    df = pd.DataFrame(rows)
    meta = {"publish_valid": int(publish.notna().sum()), "publish_missing": int(publish.isna().sum()),
            "publish_coverage": coverage, "collection_valid": int(collect.notna().sum()),
            "time_source": jd["time_source"].iloc[0] if len(jd) else "", "strict_long_term_supported": False,
            "effective_start": effective.min().isoformat() if effective.notna().any() else "",
            "effective_end": effective.max().isoformat() if effective.notna().any() else "", "config": cfg}
    return df, meta
