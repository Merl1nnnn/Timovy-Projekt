"""Versioned local reports and conservative comparison of saved evaluation runs."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.evaluation_data import DatasetError, FIELDS

ROOT = Path(__file__).resolve().parent.parent


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def add_metadata(report: dict, gold: dict, pred: dict, pred_path: Path, run_name: str,
                 prompt_version: str | None, schema_version: str | None) -> None:
    rules = ["scripts/evaluate.py", "scripts/evaluation_data.py", "scripts/evaluation_report.py",
             "parser/normalize.py", "parser/schema.py"]
    report["metadata"] = {
        "report_version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_name": run_name,
        "gold_fingerprint": fingerprint(gold),
        "gold_ids": sorted(gold),
        "prediction_file_sha256": hashlib.sha256(pred_path.read_bytes()).hexdigest(),
        "rules_fingerprint": fingerprint({p: (ROOT / p).read_text(encoding="utf-8") for p in rules}),
        "models": sorted({str(p["model"]) for jid, p in pred.items() if jid in gold and p.get("model")}),
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "version_note": "Prompt/schema versions are user-supplied; missing versions are unknown, not inferred from current code.",
    }


def metric_values(report: dict) -> dict:
    values = {"coverage": report["coverage"]}
    for group in ("required", "nice", "all"):
        for metric in ("precision", "recall", "f1"):
            values[f"skills_end_to_end.{group}.{metric}"] = report["skills_end_to_end"][group][metric]
    for field in FIELDS:
        values[f"fields.{field}.end_to_end_accuracy"] = report["fields"][field]["end_to_end_accuracy"]
    return values


def compare_reports(baseline: dict, current: dict) -> dict:
    if not isinstance(baseline, dict) or not isinstance(baseline.get("metadata"), dict):
        raise DatasetError(["Baseline must be a version 2 evaluation report"])
    for key in ("report_version", "gold_fingerprint", "gold_ids", "rules_fingerprint"):
        if baseline["metadata"].get(key) != current["metadata"][key]:
            raise DatasetError([f"Cannot compare runs: {key} differs. Re-evaluate saved predictions on the same gold and rules."])
    try:
        old, new = metric_values(baseline), metric_values(current)
        deltas = {name: {"baseline": old[name], "current": value,
                         "delta": round(value - old[name], 6)} for name, value in new.items()}
        before = {r["id"]: r for r in baseline["per_job"]}
        after = {r["id"]: r for r in current["per_job"]}
        changes = [{"id": jid, "skills_f1_delta": round(after[jid]["skills_f1"] - before[jid]["skills_f1"], 3),
                    "field_errors_delta": after[jid]["field_errors"] - before[jid]["field_errors"]}
                   for jid in sorted(before.keys() & after.keys())
                   if (after[jid]["skills_f1"], after[jid]["field_errors"]) !=
                      (before[jid]["skills_f1"], before[jid]["field_errors"])]
    except (KeyError, TypeError) as exc:
        raise DatasetError(["Baseline report is incomplete or malformed"]) from exc
    return {"baseline_run": baseline["metadata"].get("run_name"), "metrics": deltas,
            "changed_jobs": changes, "newly_processed_ids": sorted(after.keys() - before.keys()),
            "lost_prediction_ids": sorted(before.keys() - after.keys()),
            "note": "Deltas use the full fixed gold cohort, including missing predictions. Positive field_errors_delta means worse."}


def percent(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1%}"


def render_markdown(report: dict) -> str:
    # Keep vacancy text out of the summary; detailed discrepancies stay in the local CSV/JSON.
    meta = report["metadata"]
    name = str(meta["run_name"]).replace("\n", " ").replace("\r", " ")
    lines = [f"# Extraction evaluation: {name}", "",
             f"Processed **{report['jobs_evaluated']}/{report['jobs_gold']}** gold jobs "
             f"(coverage: **{percent(report['coverage'])}**).", "",
             "## Skills", "",
             "Micro metrics sum TP/FP/FN across jobs. Matched = jobs with predictions; "
             "full cohort = missing predictions count as empty skill lists.", "",
             "| Skills | Matched P | Matched R | Matched F1 | Full P | Full R | Full F1 |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for group in ("required", "nice", "all"):
        matched, full = report["skills"][group], report["skills_end_to_end"][group]
        values = [percent(matched[m]) if matched else "N/A" for m in ("precision", "recall", "f1")]
        values += [percent(full[m]) for m in ("precision", "recall", "f1")]
        lines.append(f"| {group} | " + " | ".join(values) + " |")
    lines += ["", "Empty-set convention: precision/recall with a zero denominator = 1; "
              "both skill sets empty = F1 1. Always read coverage alongside skills.", "",
              "## Fields", "", "Present-only accuracy excludes gold nulls and uses matched jobs.", "",
              "| Field | Matched accuracy | Present-only accuracy (n) | Full-cohort accuracy |",
              "|---|---:|---:|---:|"]
    for field, values in report["fields"].items():
        lines.append(f"| {field} | {percent(values['accuracy'])} | "
                     f"{percent(values['accuracy_when_present'])} ({values['present_in_gold']}) | "
                     f"{percent(values['end_to_end_accuracy'])} |")
    lines += ["", f"Skills assigned to the wrong list: {report['skills']['matched_but_wrong_list']['count']}.",
              f"Extra prediction IDs outside the cohort (not scored): {len(report['extra_prediction_ids'])}.",
              f"Source-text hash verified: {report['source_verification']['hash_verified_jobs']}/{report['jobs_evaluated']} matched jobs.",
              "", report["source_verification"]["warning"], "",
              "Unscored fields: " + ", ".join(report["unscored_fields"]) + ".",
              "", "See errors.csv / report.json for missing predictions and individual discrepancies.",
              "", "## Run provenance", "",
              f"- Gold fingerprint: `{meta['gold_fingerprint']}`",
              f"- Scoring rules fingerprint: `{meta['rules_fingerprint']}`",
              f"- Prediction file SHA-256: `{meta['prediction_file_sha256']}`",
              "- Models: " + (", ".join(meta["models"]) or "unknown"),
              f"- Prompt version: {meta['prompt_version'] or 'unknown'}",
              f"- Extraction schema version: {meta['schema_version'] or 'unknown'}"]
    if "comparison" in report:
        comparison = report["comparison"]
        lines += ["", "## Comparison with baseline", "", comparison["note"], "",
                  "| Metric | Baseline | Current | Change (percentage points) |", "|---|---:|---:|---:|"]
        for name, values in comparison["metrics"].items():
            lines.append(f"| {name} | {percent(values['baseline'])} | {percent(values['current'])} | "
                         f"{values['delta'] * 100:+.2f} |")
        lines += ["", "### Changes on jobs processed in both runs", "",
                  "Positive field-error change means worse; positive F1 change means better.", "",
                  "| Job ID | Skill F1 change (percentage points) | Field-error change |",
                  "|---|---:|---:|"]
        for row in comparison["changed_jobs"]:
            jid = str(row["id"]).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {jid} | {row['skills_f1_delta'] * 100:+.2f} | {row['field_errors_delta']:+d} |")
        lines += ["", f"Newly processed jobs: {len(comparison['newly_processed_ids'])}.",
                  f"Lost predictions: {len(comparison['lost_prediction_ids'])}."]
    return "\n".join(lines) + "\n"


def csv_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    # Spreadsheet apps can interpret extracted text as formulas.
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r")) else text


def save_report(report: dict, out_dir: Path | None, json_path: Path | None, inputs: list) -> None:
    outputs = ([out_dir / name for name in ("report.json", "report.md", "errors.csv")] if out_dir else [])
    if json_path:
        outputs.append(json_path)
    resolved = [p.resolve() for p in outputs]
    if len(set(resolved)) != len(resolved):
        raise DatasetError(["Output paths overlap"])
    protected = {p.resolve() for p in inputs if p is not None}
    if any(p in protected for p in resolved):
        raise DatasetError(["Output must not overwrite an input file"])
    if (out_dir and out_dir.exists()) or any(p.exists() for p in outputs):
        raise DatasetError(["Output already exists. Choose a new run directory/file; previous results are never overwritten."])
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=False)
        with (out_dir / "report.json").open("x", encoding="utf-8") as stream:
            stream.write(payload)
        with (out_dir / "report.md").open("x", encoding="utf-8") as stream:
            stream.write(render_markdown(report))
        with (out_dir / "errors.csv").open("x", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["id", "field", "kind", "gold", "pred"])
            writer.writeheader()
            writer.writerows({k: csv_cell(v) for k, v in row.items()} for row in report["errors"])
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with json_path.open("x", encoding="utf-8") as stream:
            stream.write(payload)
