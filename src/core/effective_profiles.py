"""One publication-selection policy shared by matching, job analysis and graph adapters."""
import copy

from ..closure.repository import PublishedProfileRepository, ProfileReadError, closure_database_path


class EffectiveJobProfiles:
    def __init__(self, loader, skill_index, static_profiles, repository=None):
        self.skill_index = skill_index
        self.static_profiles = static_profiles
        self.repository = repository or PublishedProfileRepository(lambda: closure_database_path(loader.project_root))

    def published_profiles(self):
        return self.repository.latest_by_job()

    def get_effective_job_profile(self, job_title, publications=None):
        publications = self.published_profiles() if publications is None else publications
        publication = publications.get(job_title)
        baseline = copy.deepcopy(self.static_profiles.get(job_title))
        if publication is None:
            return dict(job_title=job_title, profile_source="static_baseline", profile_version=None,
                        profile_id=None, profile_fingerprint=None, matching_profile=baseline, definition=None, publication=None)
        definition = copy.deepcopy(publication.get("manual_definition") or publication["auto_definition"])
        required, preferred = {}, {}
        for field, target in (("required_skills", required), ("preferred_skills", preferred)):
            for item in definition[field]:
                sid = item.get("skill_id")
                if not isinstance(sid, str) or sid not in self.skill_index.skills:
                    raise ProfileReadError("Published profile references an unknown standard skill")
                target.setdefault(sid, item)
        preferred = {sid: item for sid, item in preferred.items() if sid not in required}
        # The current P0 algorithm gives one equal contribution per distinct skill.
        # Evidence frequency orders gaps / labels graph edges; it is not mastery probability.
        matching = dict(jd_count=publication["source_job_count"], required_ids=list(required), bonus_ids=list(preferred),
                        required_frequency={sid: item["evidence_count"] for sid, item in required.items()},
                        bonus_frequency={sid: item["evidence_count"] for sid, item in preferred.items()},
                        education_level=(baseline or {}).get("education_level"), experience_years=(baseline or {}).get("experience_years"))
        return dict(job_title=job_title, profile_source="published_dynamic", profile_version=publication["profile_version"],
                    profile_id=publication["entity_id"], profile_fingerprint=publication["fingerprint"],
                    matching_profile=matching, definition=definition, publication=publication)

    @staticmethod
    def metadata(profile):
        return {key: profile[key] for key in ("profile_source", "profile_version", "profile_id", "profile_fingerprint")}
