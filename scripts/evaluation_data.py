"""Validate gold labels and saved predictions."""

import json
from pathlib import Path
from typing import Any

FIELDS = ["title", "company", "location", "remote", "employment_type", "seniority",
          "min_experience_years", "education", "salary_min", "salary_max", "language"]
SKILL_FIELDS = ("required_skills", "nice_to_have_skills")
ENUMS = {
    "employment_type": {"full_time", "part_time", "contract"},
    "seniority": {"junior", "medior", "senior", "lead"},
    "education": {"secondary", "bachelor", "master", "phd"},
    "language": {"sk", "en"},
}


class DatasetError(ValueError):
    """Input validation errors."""

    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("\n".join(issues))


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise DatasetError([f"{path}: cannot read JSON ({type(exc).__name__})"]) from exc


def validate_record(row: Any, where: str) -> list[str]:
    if not isinstance(row, dict):
        return [f"{where}: record must be an object"]
    issues = []
    if not isinstance(row.get("id"), str) or not row["id"].strip():
        issues.append(f"{where}: id must be a non-empty string")
    for field in FIELDS + list(SKILL_FIELDS):
        if field not in row:
            issues.append(f"{where}: missing field {field} (missing is not null)")
            continue
        value = row[field]
        valid = True
        if field in SKILL_FIELDS:
            valid = isinstance(value, list) and all(isinstance(s, str) and s.strip() for s in value)
        elif field in ("title", "company"):
            valid = isinstance(value, str) and bool(value.strip())
        elif field == "location":
            valid = value is None or isinstance(value, str)
        elif field == "remote":
            valid = type(value) is bool
        elif field in ENUMS:
            valid = (value is None and field != "language") or (
                isinstance(value, str) and value in ENUMS[field])
        elif field in ("min_experience_years", "salary_min", "salary_max"):
            valid = value is None or (type(value) is int and value >= 0)
        if not valid:
            issues.append(f"{where}: invalid value/type for {field}")
    lo, hi = row.get("salary_min"), row.get("salary_max")
    if type(lo) is int and type(hi) is int and lo > hi:
        issues.append(f"{where}: salary_min exceeds salary_max")
    for field in ("site", "url", "source_url", "text_hash", "snapshot_id"):
        if field in row and row[field] is not None and (
                not isinstance(row[field], str) or not row[field].strip()):
            issues.append(f"{where}: {field} must be a non-empty string or null")
    if row.get("url") and row.get("source_url") and row["url"] != row["source_url"]:
        issues.append(f"{where}: url and source_url disagree")
    return issues


def identity_conflicts(a: dict, b: dict) -> list[str]:
    fields = [f for f in ("site", "text_hash", "snapshot_id") if a.get(f) and b.get(f) and a[f] != b[f]]
    au, bu = a.get("source_url") or a.get("url"), b.get("source_url") or b.get("url")
    if au and bu and au != bu:
        fields.append("source_url")
    return fields


def load_gold(gold_dir: Path) -> dict[str, dict[str, Any]]:
    paths = sorted(gold_dir.glob("gold_*.json"))
    if not paths:
        raise DatasetError([f"{gold_dir}: no gold_*.json files found"])
    gold: dict[str, dict[str, Any]] = {}
    origins: dict[str, str] = {}
    issues: list[str] = []
    dataset_ids: set[str] = set()
    for path in paths:
        try:
            payload = read_json(path)
        except DatasetError as exc:
            issues.extend(exc.issues)
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            issues.append(f"{path.name}: expected an object with a jobs list")
            continue
        if payload.get("dataset_id") is not None:
            if not isinstance(payload["dataset_id"], str):
                issues.append(f"{path.name}: dataset_id must be a string")
            else:
                dataset_ids.add(payload["dataset_id"])
        for pos, row in enumerate(payload["jobs"], 1):
            where = f"{path.name} record {pos}"
            errors = validate_record(row, where)
            if errors:
                issues.extend(errors)
                continue
            jid = row["id"]
            if jid in gold:
                previous = gold[jid]
                differing = [f for f in FIELDS + ["specialization", "specialization_other"]
                             if previous.get(f) != row.get(f)]
                differing += [f for f in SKILL_FIELDS if set(previous[f]) != set(row[f])]
                differing += identity_conflicts(previous, row)
                if differing:
                    issues.append(f"{jid}: conflicting annotations in {origins[jid]} and {path.name}: "
                                  + ", ".join(sorted(set(differing))))
                else:
                    for field in ("site", "url", "source_url", "text_hash", "snapshot_id"):
                        if not previous.get(field) and row.get(field):
                            previous[field] = row[field]
            else:
                gold[jid], origins[jid] = dict(row), path.name
    if len(dataset_ids) > 1:
        issues.append("Gold files contain different dataset_id values")
    if not gold:
        issues.append("Gold set contains no valid jobs")
    if issues:
        raise DatasetError(issues)
    return gold


def load_predictions(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    issues = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise DatasetError([f"{path}: cannot read predictions ({type(exc).__name__})"]) from exc
    for pos, line in enumerate(lines, 1):
        if not line.strip():
            continue
        where = f"{path.name} line {pos}"
        try:
            row = json.loads(line)
        except ValueError:
            issues.append(f"{where}: invalid JSON")
            continue
        errors = validate_record(row, where)
        if errors:
            issues.extend(errors)
            continue
        if row["id"] in rows:
            issues.append(f"{where}: duplicate prediction id {row['id']}; select one run first")
        else:
            rows[row["id"]] = row
    if issues:
        raise DatasetError(issues)
    return rows


def select_gold(gold: dict, ids_path: Path | None) -> dict:
    if ids_path is None:
        return gold
    ids = read_json(ids_path)
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
        raise DatasetError(["Split manifest must be a non-empty JSON list of string IDs"])
    if len(set(ids)) != len(ids) or set(ids) - set(gold):
        raise DatasetError(["Split manifest contains duplicate or unknown IDs"])
    return {jid: gold[jid] for jid in ids}
