from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import yaml
from openpyxl import load_workbook


class DataConfigurationError(RuntimeError):
    pass


def _scalar(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return "" if value is None else value


class DataLoader:
    """Single configurable read-only gateway for all formal datasets."""

    FROZEN_KEYS = (
        "standardized_jd_dataset",
        "standard_job_title_mapping",
        "standard_skill_dictionary",
        "standardized_resume_testset",
    )

    def __init__(self, config_path: str | Path | None = None):
        default = Path(__file__).resolve().parents[1] / "config" / "data_sources.yaml"
        self.config_path = Path(config_path or default).resolve()
        self.project_root = self.config_path.parents[1]
        self.sources = self._read_yaml(self.config_path)
        self.field_mapping = self._read_yaml(self.project_root / "config" / "field_mapping.yaml")
        self.version = self._read_yaml(self.project_root / "config" / "version.yaml")

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise DataConfigurationError(f"配置文件不存在：{path}")
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(value, dict):
            raise DataConfigurationError(f"配置文件顶层必须为对象：{path}")
        return value

    def resolve_path(self, source_key: str) -> Path:
        source = self.sources.get(source_key)
        if not isinstance(source, dict) or not source.get("path"):
            raise DataConfigurationError(f"数据源未配置 path：{source_key}")
        path = Path(source["path"])
        return path.resolve() if path.is_absolute() else (self.project_root / path).resolve()

    def output_dir(self) -> Path:
        path = Path(self.sources.get("outputs_dir", "outputs"))
        return path.resolve() if path.is_absolute() else (self.project_root / path).resolve()

    def reports_dir(self) -> Path:
        path = Path(self.sources.get("reports_dir", "reports"))
        return path.resolve() if path.is_absolute() else (self.project_root / path).resolve()

    @staticmethod
    def read_sheet(path: Path, sheet_name: str) -> list[dict[str, Any]]:
        if not path.exists():
            raise DataConfigurationError(f"数据文件不存在：{path}")
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            if sheet_name not in workbook.sheetnames:
                raise DataConfigurationError(f"{path.name} 中不存在工作表：{sheet_name}")
            sheet = workbook[sheet_name]
            iterator = sheet.iter_rows(values_only=True)
            try:
                headers = [str(x).strip() if x is not None else "" for x in next(iterator)]
            except StopIteration:
                return []
            rows = []
            for excel_row, values in enumerate(iterator, start=2):
                row = {headers[i]: _scalar(value) for i, value in enumerate(values) if i < len(headers) and headers[i]}
                if any(value not in (None, "") for value in row.values()):
                    row["_excel_row"] = excel_row
                    rows.append(row)
            return rows
        finally:
            workbook.close()

    def _load_mapped(self, source_key: str) -> list[dict[str, Any]]:
        source = self.sources[source_key]
        raw = self.read_sheet(self.resolve_path(source_key), source["sheet"])
        mapping = self.field_mapping.get(source_key, {})
        if not mapping:
            raise DataConfigurationError(f"字段映射不存在：{source_key}")
        missing = [column for column in mapping.values() if raw and column not in raw[0]]
        if missing:
            raise DataConfigurationError(f"{source_key} 缺少字段：{missing}")
        return [
            {**{internal: row.get(column, "") for internal, column in mapping.items()}, "_excel_row": row["_excel_row"]}
            for row in raw
        ]

    def load_jds(self) -> list[dict[str, Any]]:
        return self._load_mapped("standardized_jd_dataset")

    def load_job_title_mapping(self) -> list[dict[str, Any]]:
        return self._load_mapped("standard_job_title_mapping")

    def load_resumes(self) -> list[dict[str, Any]]:
        return self._load_mapped("standardized_resume_testset")

    def load_skill_dictionary(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        source = self.sources["standard_skill_dictionary"]
        path = self.resolve_path("standard_skill_dictionary")
        skills = self.read_sheet(path, source["standard_skills_sheet"])
        aliases = self.read_sheet(path, source["aliases_sheet"])
        return skills, aliases

    def load_job_skill_gold(self) -> list[dict[str, Any]]:
        source = self.sources.get("job_skill_gold")
        if not source:
            return []
        return self.read_sheet(self.resolve_path("job_skill_gold"), source["sheet"])

    def source_locations(self) -> dict[str, str]:
        return {key: str(self.resolve_path(key)) for key in self.FROZEN_KEYS}

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest().upper()

    def frozen_hashes(self) -> dict[str, str]:
        return {key: self.sha256(self.resolve_path(key)) for key in self.FROZEN_KEYS}

    @staticmethod
    def duplicate_values(rows: Iterable[dict[str, Any]], key: str) -> list[str]:
        seen, duplicates = set(), set()
        for row in rows:
            value = str(row.get(key, "")).strip()
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        return sorted(duplicates)

    def validate_frozen(self) -> dict[str, Any]:
        jds = self.load_jds()
        resumes = self.load_resumes()
        skills, aliases = self.load_skill_dictionary()
        skill_ids = {str(row.get("skill_id", "")).strip() for row in skills}
        alias_unknown = sorted({str(row.get("skill_id", "")).strip() for row in aliases} - skill_ids - {""})
        result = {
            "jd_duplicate_ids": self.duplicate_values(jds, "jd_id"),
            "resume_duplicate_ids": self.duplicate_values(resumes, "resume_id"),
            "skill_duplicate_ids": self.duplicate_values(skills, "skill_id"),
            "standard_skill_name_duplicates": self.duplicate_values(skills, "标准技能名称"),
            "alias_unknown_skill_ids": alias_unknown,
            "row_counts": {"jds": len(jds), "resumes": len(resumes), "skills": len(skills), "aliases": len(aliases)},
            "source_locations": self.source_locations(),
            "data_version": self.version.get("data_version"),
            "schema_version": self.version.get("schema_version"),
        }
        result["passed"] = not any(result[key] for key in (
            "jd_duplicate_ids", "resume_duplicate_ids", "skill_duplicate_ids",
            "standard_skill_name_duplicates", "alias_unknown_skill_ids",
        ))
        return result

