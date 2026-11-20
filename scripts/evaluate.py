"""Evaluates parser output against the hand-annotated gold set of real Profesia postings.

Field accuracy for single-value fields, micro precision / recall / F1 for skills, and a check of
whether the rule-based `confidence` actually separates good records from bad ones.

Usage:
    uv run python -m scripts.evaluate
    uv run python -m scripts.evaluate --pred data/real/parsed/jobs.jsonl --gold data/real/gold --json out.json
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from parser.normalize import fold, normalize_skill  # noqa: E402

from scripts.evaluation_data import (  # noqa: E402
    DatasetError, FIELDS, identity_conflicts, load_gold, load_predictions, read_json, select_gold,
)

LEGAL_FORMS = re.compile(r"\b(spol|s\s*r\s*o|a\s*s|gmbh|ltd|inc|k\s*s|v\s*o\s*s)\b")


def _company_key(name: str) -> str:
    key = re.sub(r"[^a-z0-9 ]", " ", fold(name))
    return " ".join(LEGAL_FORMS.sub(" ", key).split())


def field_equal(field: str, gold: Any, pred: Any) -> bool:
    if field == "title":
        return gold is not None and pred is not None and " ".join(gold.split()) == " ".join(pred.split())
    if field == "company":
        if not gold or not pred:
            return gold == pred
        g, p = _company_key(gold), _company_key(pred)
        return g == p or (bool(g) and bool(p) and (g in p or p in g))  # "X IT Labs" vs "X IT Labs (part of X)"
    return gold == pred


def skill_key(name: str) -> str:
    """Canonical comparison key: parser canonicalisation, then case, diacritics and punctuation removed."""
    return re.sub(r"[^a-z0-9+#.]", "", fold(normalize_skill(name)))


def _keys(items: list[str]) -> set[str]:
    return {k for k in (skill_key(s) for s in items) if k}


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3), "tp": tp, "fp": fp, "fn": fn}


def evaluate(gold: dict[str, dict[str, Any]], pred: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not gold:
        raise DatasetError(["Gold set is empty"])
    ids = sorted(set(gold) & set(pred))
    if pred and not ids:
        raise DatasetError(["Gold and predictions have no matching IDs"])
    conflicts = [f"{jid}: gold/prediction mismatch in {', '.join(identity_conflicts(gold[jid], pred[jid]))}"
                 for jid in ids if identity_conflicts(gold[jid], pred[jid])]
    if conflicts:
        raise DatasetError(conflicts)
    errors_table = []
    field_hits = {f: 0 for f in FIELDS}
    field_errors: dict[str, list[dict[str, Any]]] = {f: [] for f in FIELDS}
    counts = {k: [0, 0, 0] for k in ("required", "nice", "all")}  # tp, fp, fn
    false_pos: Counter[str] = Counter()
    false_neg: Counter[str] = Counter()
    wrong_list = 0
    per_job: list[dict[str, Any]] = []

    for jid in ids:
        g, p = gold[jid], pred[jid]
        errors = 0
        for f in FIELDS:
            if field_equal(f, g.get(f), p.get(f)):
                field_hits[f] += 1
            else:
                errors += 1
                field_errors[f].append({"id": jid, "gold": g.get(f), "pred": p.get(f)})
                errors_table.append({"id": jid, "field": f, "kind": "wrong_value",
                                     "gold": g.get(f), "pred": p.get(f)})

        g_req, g_nice = _keys(g["required_skills"]), _keys(g["nice_to_have_skills"])
        p_req, p_nice = _keys(p["required_skills"]), _keys(p["nice_to_have_skills"])
        for name, gs, ps in (("required", g_req, p_req), ("nice", g_nice, p_nice),
                             ("all", g_req | g_nice, p_req | p_nice)):
            counts[name][0] += len(gs & ps)
            counts[name][1] += len(ps - gs)
            counts[name][2] += len(gs - ps)
            if name != "all":
                for skill in sorted(gs - ps):
                    errors_table.append({"id": jid, "field": name, "kind": "missing_skill",
                                         "gold": skill, "pred": None})
                for skill in sorted(ps - gs):
                    errors_table.append({"id": jid, "field": name, "kind": "extra_skill",
                                         "gold": None, "pred": skill})
        g_all, p_all = g_req | g_nice, p_req | p_nice
        false_pos.update(p_all - g_all)
        false_neg.update(g_all - p_all)
        wrong_list += len((g_req & p_nice) | (g_nice & p_req))
        job_f1 = prf(len(g_all & p_all), len(p_all - g_all), len(g_all - p_all))["f1"]
        per_job.append({"id": jid, "field_errors": errors, "skills_f1": job_f1,
                        "confidence": p.get("confidence"), "low_confidence": p.get("low_confidence")})

    n = len(ids)
    skills = {k: prf(*v) if n else None for k, v in counts.items()}
    end_counts = {k: list(v) for k, v in counts.items()}
    for jid in sorted(set(gold) - set(pred)):
        g = gold[jid]
        required, nice = _keys(g["required_skills"]), _keys(g["nice_to_have_skills"])
        for name, gs in (("required", required), ("nice", nice), ("all", required | nice)):
            end_counts[name][2] += len(gs)
        errors_table.append({"id": jid, "field": "record", "kind": "missing_prediction",
                             "gold": "expected", "pred": None})
    matched = counts["all"][0]
    skills["matched_but_wrong_list"] = {"count": wrong_list, "share": round(wrong_list / matched, 3) if matched else 0.0}

    def group(flag: bool) -> dict[str, Any]:
        rows = [r for r in per_job if r["low_confidence"] is flag]
        if not rows:
            return {"jobs": 0}
        return {"jobs": len(rows), "mean_field_errors": round(mean(r["field_errors"] for r in rows), 2),
                "mean_skills_f1": round(mean(r["skills_f1"] for r in rows), 3)}

    return {
        "jobs_evaluated": n,
        "jobs_gold": len(gold),
        "coverage": round(n / len(gold), 6),
        "extra_prediction_ids": sorted(set(pred) - set(gold)),
        "missing_predictions": sorted(set(gold) - set(pred)),
        "fields": {f: {
            "accuracy": round(field_hits[f] / n, 6) if n else None,
            "correct": field_hits[f], "evaluated": n,
            "end_to_end_accuracy": round(field_hits[f] / len(gold), 6),
            "present_in_gold": sum(gold[jid][f] is not None for jid in ids),
            "accuracy_when_present": (
                round(sum(field_equal(f, gold[jid][f], pred[jid][f]) for jid in ids if gold[jid][f] is not None)
                      / sum(gold[jid][f] is not None for jid in ids), 6)
                if any(gold[jid][f] is not None for jid in ids) else None),
        } for f in FIELDS},
        "field_errors": field_errors,
        "skills": skills,
        "skills_end_to_end": {k: prf(*v) for k, v in end_counts.items()},
        "errors": errors_table,
        "source_verification": {
            "hash_verified_jobs": sum(bool(gold[jid].get("text_hash") and pred[jid].get("text_hash")) for jid in ids),
            "warning": "Matching IDs alone do not verify the source text. Freeze input snapshots; supply matching text_hash values.",
        },
        "unscored_fields": ["specialization", "summary", "salary_currency"],
        "top_false_positive_skills": false_pos.most_common(15),
        "top_missed_skills": false_neg.most_common(15),
        "confidence_check": {"low_confidence": group(True), "confident": group(False),
                             "unknown_jobs": sum(r["low_confidence"] is None for r in per_job)},
        "per_job": per_job,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pred", type=Path, default=ROOT / "data/real/parsed/jobs.jsonl")
    ap.add_argument("--gold", type=Path, default=ROOT / "data/real/gold")
    ap.add_argument("--ids", type=Path, help="Fixed dev/test cohort: JSON list of gold IDs")
    ap.add_argument("--validate-only", action="store_true", help="Validate gold without loading predictions")
    ap.add_argument("--out-dir", type=Path, help="NEW directory for report.json, report.md and errors.csv")
    ap.add_argument("--json", type=Path, help="Save JSON report to a NEW file (legacy option)")
    ap.add_argument("--baseline", type=Path, help="Previous report.json on the same gold and scoring rules")
    ap.add_argument("--run-name", default="unnamed", help="Human-readable experiment name")
    ap.add_argument("--prompt-version", help="Prompt version used when predictions were generated")
    ap.add_argument("--schema-version", help="Extraction schema version used for this run")
    args = ap.parse_args()
    from scripts.evaluation_report import add_metadata, compare_reports, render_markdown, save_report

    try:
        gold = select_gold(load_gold(args.gold), args.ids)
        if args.validate_only:
            print(f"Gold validation passed: {len(gold)} unique jobs. No files changed.")
            return
        pred = load_predictions(args.pred)
        report = evaluate(gold, pred)
        add_metadata(report, gold, pred, args.pred, args.run_name, args.prompt_version, args.schema_version)
        if args.baseline:
            report["comparison"] = compare_reports(read_json(args.baseline), report)
        save_report(report, args.out_dir, args.json, [args.pred, args.ids, args.baseline,
                    *args.gold.glob("gold_*.json")])
        print(render_markdown(report))
    except (DatasetError, OSError, ValueError) as exc:
        ap.exit(2, f"Evaluation stopped:\n{exc}\n")


if __name__ == "__main__":
    main()
