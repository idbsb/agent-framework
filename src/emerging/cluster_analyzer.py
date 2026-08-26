from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass


def _title_grams(value: str) -> Counter[str]:
    compact = re.sub(r"[\s()（）\-_/·—（）【】\[\]（）]+", "", str(value or "").casefold())
    if len(compact) < 2:
        return Counter({compact: 1}) if compact else Counter()
    return Counter(compact[index:index + 2] for index in range(len(compact) - 1))


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    numerator = sum(value * right.get(key, 0) for key, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


@dataclass(frozen=True)
class JobVector:
    jd_id: str
    title: str
    skill_ids: frozenset[str]


class ClusterAnalyzer:
    """Deterministic title/skill clustering without external models or APIs."""

    def __init__(self, config: dict):
        cluster = config["clustering"]
        self.seed_threshold = float(cluster["seed_similarity"])
        self.seed_title_min_similarity = float(cluster["seed_title_min_similarity"])
        self.support_threshold = float(cluster["support_similarity"])
        self.support_title_min_similarity = float(cluster["support_title_min_similarity"])
        self.title_weight = float(cluster["title_weight"])
        self.skill_weight = float(cluster["skill_weight"])

    def similarity(self, left: JobVector, right: JobVector) -> float:
        title_score = _cosine(_title_grams(left.title), _title_grams(right.title))
        skill_score = _jaccard(set(left.skill_ids), set(right.skill_ids))
        return self.title_weight * title_score + self.skill_weight * skill_score

    def components(self, seeds: list[JobVector], support_rows: list[JobVector]) -> list[list[str]]:
        parent = {item.jd_id: item.jd_id for item in seeds}

        def find(value: str) -> str:
            while parent[value] != value:
                parent[value] = parent[parent[value]]
                value = parent[value]
            return value

        def union(left: str, right: str) -> None:
            left_root, right_root = find(left), find(right)
            if left_root != right_root:
                parent[max(left_root, right_root)] = min(left_root, right_root)

        for index, left in enumerate(seeds):
            for right in seeds[index + 1:]:
                title_similarity = _cosine(_title_grams(left.title), _title_grams(right.title))
                if title_similarity >= self.seed_title_min_similarity and self.similarity(left, right) >= self.seed_threshold:
                    union(left.jd_id, right.jd_id)

        grouped: dict[str, list[JobVector]] = {}
        for item in seeds:
            grouped.setdefault(find(item.jd_id), []).append(item)

        assignments: dict[str, list[str]] = {root: [item.jd_id for item in items] for root, items in grouped.items()}
        for support in support_rows:
            best_root, best_score = "", 0.0
            for root, items in grouped.items():
                eligible = [
                    seed for seed in items
                    if _cosine(_title_grams(support.title), _title_grams(seed.title)) >= self.support_title_min_similarity
                ]
                score = max((self.similarity(support, seed) for seed in eligible), default=0.0)
                if score > best_score:
                    best_root, best_score = root, score
            if best_root and best_score >= self.support_threshold:
                assignments[best_root].append(support.jd_id)
        return [sorted(set(ids)) for _, ids in sorted(assignments.items())]

    def consistency(self, items: list[JobVector]) -> float:
        if len(items) < 2:
            return 0.0
        scores = [
            self.similarity(left, right)
            for index, left in enumerate(items)
            for right in items[index + 1:]
        ]
        return sum(scores) / len(scores) if scores else 0.0

    @staticmethod
    def title_similarity(left: str, right: str) -> float:
        return _cosine(_title_grams(left), _title_grams(right))
