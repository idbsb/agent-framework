from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from ..schemas import SkillEvidence
from .skill_context import classify


EVIDENCE_BOUNDARY = re.compile(r"[。！？!?；;\n]")
PRACTICE_CUES = re.compile(
    r"使用|开发|实现|搭建|设计|部署|负责|构建|完成|集成|调用|优化|维护|基于|应用|参与"
)
WEAK_CUES = re.compile(r"了解(?:过)?|学习过|接触过|简单提及|初步了解|略懂|听说过")


def normalize(text: object) -> str:
    value = str(text or "").strip().casefold()
    value = value.replace("（", "(").replace("）", ")").replace("／", "/")
    value = re.sub(r"\s+", " ", value)
    return value


def _pattern(phrase: str) -> re.Pattern[str]:
    escaped = re.escape(phrase)
    if re.fullmatch(r"[A-Za-z0-9_+#. /-]+", phrase):
        return re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def _minimal_evidence(text: str, start: int, end: int) -> str:
    left = 0
    for boundary in EVIDENCE_BOUNDARY.finditer(text, 0, start):
        left = boundary.end()
    next_boundary = EVIDENCE_BOUNDARY.search(text, end)
    right = next_boundary.start() if next_boundary else len(text)
    return text[left:right].strip(" \t\r\n，,。；;！？!?")


def _evidence_strength(source_field: str, evidence: str, polarity: str) -> str:
    if polarity != "affirmed" or WEAK_CUES.search(evidence):
        return "weak"
    if source_field in {"projects", "work_experience"} and PRACTICE_CUES.search(evidence):
        return "strong"
    return "medium"


@dataclass(frozen=True)
class SkillRecord:
    skill_id: str
    name: str
    category: str


class SkillIndex:
    """Frozen standard skill and alias index with evidence-bound extraction."""

    def __init__(self, standard_rows: list[dict], alias_rows: list[dict]):
        self.skills: dict[str, SkillRecord] = {}
        self.name_to_id: dict[str, str] = {}
        for row in standard_rows:
            skill_id = str(row.get("skill_id", "")).strip()
            name = str(row.get("标准技能名称", "")).strip()
            if not skill_id or not name:
                continue
            record = SkillRecord(skill_id, name, str(row.get("技能类别", "未分类") or "未分类"))
            self.skills[skill_id] = record
            self.name_to_id[normalize(name)] = skill_id

        expression_to_ids: dict[str, list[str]] = defaultdict(list)
        expression_display: dict[str, str] = {}
        for record in self.skills.values():
            key = normalize(record.name)
            expression_to_ids[key].append(record.skill_id)
            expression_display[key] = record.name
        for row in alias_rows:
            phrase = str(row.get("原始技能写法", "")).strip()
            skill_id = str(row.get("skill_id", "")).strip()
            if phrase and skill_id in self.skills:
                key = normalize(phrase)
                if skill_id not in expression_to_ids[key]:
                    expression_to_ids[key].append(skill_id)
                expression_display[key] = phrase

        self.expressions = []
        for key, skill_ids in expression_to_ids.items():
            phrase = expression_display[key]
            if len(phrase.strip()) < 1:
                continue
            self.expressions.append((phrase, tuple(skill_ids), _pattern(phrase)))
        self.expressions.sort(key=lambda item: (len(item[0]), item[0]), reverse=True)

    def resolve_name(self, value: str) -> str | None:
        return self.name_to_id.get(normalize(value))

    def standard_name(self, skill_id: str) -> str:
        return self.skills[skill_id].name

    def extract_fields(self, fields: Iterable[tuple[str, object]]) -> list[SkillEvidence]:
        evidence: dict[tuple, SkillEvidence] = {}
        for source_field, raw_value in fields:
            text = str(raw_value or "")
            if not text.strip():
                continue
            used_spans: list[tuple[int, int, set[str]]] = []
            for phrase, skill_ids, pattern in self.expressions:
                for match in pattern.finditer(text):
                    span = (match.start(), match.end())
                    overlapping = [entry for entry in used_spans if not (span[1] <= entry[0] or span[0] >= entry[1])]
                    if overlapping and not all(set(skill_ids).issubset(entry[2]) for entry in overlapping):
                        continue
                    multi = len(skill_ids) > 1
                    for skill_id in skill_ids:
                        record = self.skills[skill_id]
                        exact = normalize(match.group(0)) == normalize(record.name)
                        confidence = 0.98 if exact else (0.90 if multi else 0.93)
                        polarity = classify(text, span[0], span[1], source_field)
                        evidence_text = _minimal_evidence(text, span[0], span[1])
                        item = SkillEvidence(
                            skill_id=skill_id,
                            standard_skill_name=record.name,
                            skill_type=record.category,
                            confidence=confidence,
                            evidence=evidence_text,
                            source_field=source_field,
                            matched_text=match.group(0),
                            start=span[0], end=span[1],
                            polarity=polarity,
                            accepted=polarity == "affirmed",
                            need_human_review=polarity == "uncertain",
                            evidence_strength=_evidence_strength(source_field, evidence_text, polarity),
                        )
                        key = (skill_id, source_field, text, span)
                        prior = evidence.get(key)
                        if prior is None or item.confidence > prior.confidence:
                            evidence[key] = item
                    used_spans.append((span[0], span[1], set(skill_ids)))
        return sorted(evidence.values(), key=lambda item: (item.source_field, item.start, item.standard_skill_name))

    def extract_names(self, text: str, source_field: str = "text") -> set[str]:
        return {item.standard_skill_name for item in self.extract_fields([(source_field, text)]) if item.accepted}

