"""Deterministic text-claim classification, not a mastery assessment.

Cues apply across coordinated skills until a clause boundary or a new cue.
Unsupported ambiguity remains reviewable; this is not unrestricted NLP.
"""
from __future__ import annotations

import re


# Longer phrases are consumed before their component verbs (e.g. 从未使用
# must never be overwritten by the 使用 inside that same phrase).
CUES = {
    "negated": r"从未(?:使用|掌握|学习)?|未曾(?:使用)?|尚未(?:掌握|使用)?|不(?:会|具备|掌握|熟悉|了解|需要|使用|擅长)(?:使用|开发|掌握)?|没有|缺乏",
    "planned": r"(?:正在|计划|准备|打算|希望|想要)(?:学习|了解|掌握|使用)(?:使用|开发)?|学习中",
    "uncertain": r"了解过|接触过|略懂|听说过|可能(?:会|掌握)?|不确定|是否|能否",
    "affirmed": r"掌握|熟练(?:使用)?|熟悉|具备|具有|擅长",
}
CUE_PATTERN = re.compile("|".join(f"(?P<{name}>{rule})" for name, rule in CUES.items()))
SUBJECT = re.compile(r"团队|公司|同事|他人|客户|我(?:本人)?|本人")
BOUNDARY = re.compile(r"[，,。；;\n！？!?]|但是|但|不过|然而")
PERSON_FIELDS = {"skills_raw", "projects", "work_experience", "text"}


def classify(text: str, start: int, end: int, source_field: str) -> str:
    left = 0
    for boundary in BOUNDARY.finditer(text, 0, start):
        left = boundary.end()
    next_boundary = BOUNDARY.search(text, end)
    right = next_boundary.start() if next_boundary else len(text)
    prefix, suffix = text[left:start], text[end:right]
    subjects = list(SUBJECT.finditer(prefix))
    if source_field in PERSON_FIELDS and subjects and subjects[-1].group() not in {"我", "我本人", "本人"}:
        return "other_person"
    cues = list(CUE_PATTERN.finditer(prefix))
    polarity = cues[-1].lastgroup if cues else "affirmed"
    # Common postposed claims: “Python 不会”, “Docker 正在学习”.
    trailing = CUE_PATTERN.match(suffix.lstrip())
    if trailing and trailing.lastgroup != "affirmed":
        polarity = trailing.lastgroup
    return polarity or "uncertain"
