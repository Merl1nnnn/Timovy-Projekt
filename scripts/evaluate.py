"""Evaluates parser output against the hand-annotated gold set of real Profesia postings.

Field accuracy for single-value fields, micro precision / recall / F1 for skills, and a check of
whether the rule-based `confidence` actually separates good records from bad ones.

Usage:
    uv run python -m scripts.evaluate
    uv run python -m scripts.evaluate --pred data/real/parsed/jobs.jsonl --gold data/real/gold --json out.json
"""

import argparse
import json
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

# Compared exactly (after light normalisation). specialization is left out on purpose: the gold set uses
# "other" for 34 of 60 records, which the parser's six-value list cannot express yet.
FIELDS = ["title", "company", "location", "remote", "employment_type", "seniority",
          "min_experience_years", "education", "salary_min", "salary_max", "language"]
LEGAL_FORMS = re.compile(r"\b(spol|s\s*r\s*o|a\s*s|gmbh|ltd|inc|k\s*s|v\s*o\s*s)\b")


def load_gold(gold_dir: Path) -> dict[str, dict[str, Any]]:
    """One record per job ID. Control jobs appear in two files; after adjudication the copies agree."""
    gold: dict[str, dict[str, Any]] = {}
    for path in sorted(gold_dir.glob("gold_*.json")):
        for job in json.loads(path.read_text(encoding="utf-8"))["jobs"]:
            gold.setdefault(job["id"], job)
    return gold


def load_predictions(path: Path) -> dict[str, dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {r["id"]: r for r in rows}


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
    ids = sorted(set(gold) & set(pred))
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

        g_req, g_nice = _keys(g["required_skills"]), _keys(g["nice_to_have_skills"])
        p_req, p_nice = _keys(p["required_skills"]), _keys(p["nice_to_have_skills"])
        for name, gs, ps in (("required", g_req, p_req), ("nice", g_nice, p_nice),
                             ("all", g_req | g_nice, p_req | p_nice)):
            counts[name][0] += len(gs & ps)
            counts[name][1] += len(ps - gs)
            counts[name][2] += len(gs - ps)
        g_all, p_all = g_req | g_nice, p_req | p_nice
        false_pos.update(p_all - g_all)
        false_neg.update(g_all - p_all)
        wrong_list += len((g_req & p_nice) | (g_nice & p_req))
        job_f1 = prf(len(g_all & p_all), len(p_all - g_all), len(g_all - p_all))["f1"]
        per_job.append({"id": jid, "field_errors": errors, "skills_f1": job_f1,
                        "confidence": p.get("confidence"), "low_confidence": p.get("low_confidence")})

    n = len(ids)
    skills = {k: prf(*v) for k, v in counts.items()}
    matched = counts["all"][0]
    skills["matched_but_wrong_list"] = {"count": wrong_list, "share": round(wrong_list / matched, 3) if matched else 0.0}

    def group(flag: bool) -> dict[str, Any]:
        rows = [r for r in per_job if bool(r["low_confidence"]) == flag]
        if not rows:
            return {"jobs": 0}
        return {"jobs": len(rows), "mean_field_errors": round(mean(r["field_errors"] for r in rows), 2),
                "mean_skills_f1": round(mean(r["skills_f1"] for r in rows), 3)}

    return {
        "jobs_evaluated": n,
        "missing_predictions": sorted(set(gold) - set(pred)),
        "fields": {f: {"accuracy": round(field_hits[f] / n, 3) if n else 0.0, "correct": field_hits[f]} for f in FIELDS},
        "field_errors": field_errors,
        "skills": skills,
        "top_false_positive_skills": false_pos.most_common(15),
        "top_missed_skills": false_neg.most_common(15),
        "confidence_check": {"low_confidence": group(True), "confident": group(False)},
        "per_job": per_job,
    }


def print_report(r: dict[str, Any]) -> None:
    print(f"Вакансій в оцінці: {r['jobs_evaluated']}" +
          (f"  (без передбачення: {', '.join(r['missing_predictions'])})" if r["missing_predictions"] else ""))
    print("\nПоля (точність):")
    for f, v in r["fields"].items():
        print(f"  {f:22} {v['accuracy']:6.1%}  ({v['correct']}/{r['jobs_evaluated']})")
    print("\nНавички (micro):")
    for k in ("required", "nice", "all"):
        s = r["skills"][k]
        print(f"  {k:9} P={s['precision']:.3f}  R={s['recall']:.3f}  F1={s['f1']:.3f}   tp={s['tp']} fp={s['fp']} fn={s['fn']}")
    w = r["skills"]["matched_but_wrong_list"]
    print(f"  знайдено, але не в тому списку (required↔nice): {w['count']} ({w['share']:.1%} знайдених)")
    print("\nНайчастіше зайві навички:", ", ".join(f"{s} ({c})" for s, c in r["top_false_positive_skills"][:10]))
    print("Найчастіше пропущені:   ", ", ".join(f"{s} ({c})" for s, c in r["top_missed_skills"][:10]))
    c = r["confidence_check"]
    print("\nЧи відрізняє confidence погані записи:")
    for name, label in (("low_confidence", "low_confidence"), ("confident", "решта")):
        g = c[name]
        if g["jobs"]:
            print(f"  {label:15} {g['jobs']:3} вакансій: помилок у полях {g['mean_field_errors']:.2f}, F1 навичок {g['mean_skills_f1']:.3f}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pred", type=Path, default=ROOT / "data" / "real" / "parsed" / "jobs.jsonl")
    ap.add_argument("--gold", type=Path, default=ROOT / "data" / "real" / "gold")
    ap.add_argument("--json", type=Path, help="зберегти повний звіт (з усіма помилками) у JSON")
    args = ap.parse_args()
    report = evaluate(load_gold(args.gold), load_predictions(args.pred))
    print_report(report)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nПовний звіт: {args.json}")


if __name__ == "__main__":
    main()
