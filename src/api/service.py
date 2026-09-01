from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..core.jd_parser import JDParser
from ..core.matching_engine import MatchingEngine
from ..core.resume_parser import ResumeParser
from ..core.skill_extractor import SkillIndex
from ..data_loader import DataLoader


@dataclass
class CoreServices:
    loader: DataLoader
    skill_index: SkillIndex
    jd_parser: JDParser
    resume_parser: ResumeParser
    matching_engine: MatchingEngine


@lru_cache(maxsize=1)
def get_services() -> CoreServices:
    loader = DataLoader()
    skills, aliases = loader.load_runtime_skill_dictionary()
    skill_index = SkillIndex(skills, aliases)
    jd_parser = JDParser(loader, skill_index)
    resume_parser = ResumeParser(skill_index)
    matching_engine = MatchingEngine(loader, skill_index, jd_parser)
    return CoreServices(loader, skill_index, jd_parser, resume_parser, matching_engine)

