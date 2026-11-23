import csv
import hashlib
from pathlib import Path

from esco.data import digest, read_json, write_json

DECISIONS = {"unreviewed", "matched", "no_match"}
SPLITS = {"unassigned", "dev", "test"}


def review_template(run):
    return {"format_version": 1, "catalog_fingerprint": run["catalog_fingerprint"],
            "queries_fingerprint": run["queries_fingerprint"],
            "annotations": [{"query_id": row["id"], "skill": row["skill"], "context": row["context"],
                             "decision": "unreviewed", "acceptable_uris": [], "split": "unassigned",
                             "reviewer": "", "note": ""} for row in run["queries"]]}


def validate_gold(gold, run, catalog):
    for field in ("catalog_fingerprint", "queries_fingerprint"):
        if gold.get(field) != run[field]:
            raise ValueError(f"Gold/run mismatch: {field}")
    if gold.get("format_version") != 1 or not isinstance(gold.get("annotations"), list):
        raise ValueError("Invalid mapping gold format")
    valid_uris = {c.uri for c in catalog.concepts}
    queries = {q["id"]: q for q in run["queries"]}
    seen = set()
    for row in gold["annotations"]:
        jid = row.get("query_id")
        if not isinstance(jid, str) or jid not in queries or jid in seen:
            raise ValueError("Unknown or duplicate gold query ID")
        seen.add(jid)
        if row.get("skill") != queries[jid]["skill"] or row.get("context") != queries[jid]["context"]:
            raise ValueError(f"{jid}: gold query text changed")
        decision, split, uris = row.get("decision"), row.get("split"), row.get("acceptable_uris")
        if decision not in DECISIONS or split not in SPLITS:
            raise ValueError(f"{jid}: invalid decision or split")
        if not isinstance(uris, list) or not all(isinstance(u, str) and u in valid_uris for u in uris):
            raise ValueError(f"{jid}: expected ESCO URIs from this catalog")
        if len(set(uris)) != len(uris):
            raise ValueError(f"{jid}: duplicate accepted URI")
        if (decision == "matched") != bool(uris):
            raise ValueError(f"{jid}: matched needs URIs; other decisions require an empty list")
        if decision != "unreviewed" and (not isinstance(row.get("reviewer"), str) or not row["reviewer"].strip()):
            raise ValueError(f"{jid}: reviewed decisions need a reviewer")
    return gold


def import_review(csv_path: Path, run, catalog, out: Path):
    gold = review_template(run)
    by_id = {r["query_id"]: r for r in gold["annotations"]}
    seen = set()
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"query_id", "decision", "acceptable_uris", "split", "reviewer", "note"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Review CSV is missing required columns")
        for row in reader:
            jid = row["query_id"]
            if jid not in by_id or jid in seen:
                raise ValueError("Unknown or duplicate review ID")
            seen.add(jid)
            by_id[jid].update(decision=row["decision"].strip(), split=row["split"].strip(),
                             acceptable_uris=[u.strip() for u in row["acceptable_uris"].split(";") if u.strip()],
                             reviewer=row["reviewer"].strip(), note=row["note"])
    if seen != set(by_id):
        raise ValueError("Review CSV must include every exported query")
    validate_gold(gold, run, catalog)
    write_json(out, gold)
    return gold


def validate_run(run, catalog):
    if run.get("format_version") != 1 or run.get("catalog_fingerprint") != catalog.fingerprint:
        raise ValueError("Mapping run/catalog mismatch")
    from esco.search import Query
    queries = [Query.model_validate(q).model_dump() for q in run["queries"]]
    if len({q["id"] for q in queries}) != len(queries) or not queries:
        raise ValueError("Queries must be non-empty with unique IDs")
    if digest(queries) != run["queries_fingerprint"]:
        raise ValueError("Query fingerprint mismatch")
    by_id = {q["id"]: q for q in queries}
    seen, valid_uris = set(), {c.uri for c in catalog.concepts}
    for row in run["results"]:
        jid = row["id"]
        if jid not in by_id or jid in seen:
            raise ValueError("Unknown or duplicate mapping result")
        seen.add(jid)
        if any(row[f] != by_id[jid][f] for f in ("skill", "context")):
            raise ValueError("Result/query text mismatch")
        uris = [c["uri"] for c in row["candidates"]]
        if len(set(uris)) != len(uris) or not set(uris) <= valid_uris:
            raise ValueError("Invalid or duplicate candidate URIs")
        if len(uris) > run["k"]:
            raise ValueError("Candidate list exceeds run k")
    return run


def evaluate_mapping(gold, run, catalog, split="dev"):
    validate_run(run, catalog)
    validate_gold(gold, run, catalog)
    if split not in ("dev", "test"):
        raise ValueError("Choose dev or test explicitly")
    if run["k"] < 3:
        raise ValueError("Evaluation requires at least three retrieved candidates (k >= 3)")
    rows = [r for r in gold["annotations"] if r["split"] == split and r["decision"] != "unreviewed"]
    if not rows:
        raise ValueError(f"No human-reviewed {split} cases; complete the review first")
    predictions = {r["id"]: r for r in run["results"]}
    matched = [r for r in rows if r["decision"] == "matched"]
    hits1 = hits3 = 0
    reciprocal = 0.0
    errors = []
    for row in matched:
        candidate_ids = [c["uri"] for c in predictions.get(row["query_id"], {}).get("candidates", [])]
        rank = next((i for i, uri in enumerate(candidate_ids, 1) if uri in row["acceptable_uris"]), None)
        hits1 += rank == 1
        hits3 += rank is not None and rank <= 3
        reciprocal += 1 / rank if rank else 0
        if rank != 1:
            errors.append({"query_id": row["query_id"], "skill": row["skill"],
                           "acceptable_uris": row["acceptable_uris"], "candidates": candidate_ids,
                           "first_correct_rank": rank})
    n = len(matched)
    selected_ids = {r["query_id"] for r in rows}
    return {"format_version": 1, "split": split, "method": run["method"], "k": run["k"],
            "catalog_fingerprint": catalog.fingerprint, "queries_fingerprint": run["queries_fingerprint"],
            "gold_fingerprint": digest(gold),
            "scorer_fingerprint": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "embedding": run.get("embedding"),
            "reviewed_cases": len(rows), "matched_cases": n, "no_match_cases": len(rows) - n,
            "unreviewed_cases": sum(r["decision"] == "unreviewed" for r in gold["annotations"]),
            "unassigned_cases": sum(r["split"] == "unassigned" for r in gold["annotations"]),
            "metrics": {"top1_accuracy": hits1 / n if n else None,
                        "hit_at_3": hits3 / n if n else None,
                        "mrr_at_k": reciprocal / n if n else None,
                        "prediction_coverage": len(selected_ids & predictions.keys()) / len(rows)},
            "errors": errors,
            "note": "Candidate retrieval only. No-match cases are counted but excluded from ranking metrics; no automatic acceptance or calibrated no-match detector is implemented."}


def compare_reports(before, after):
    for field in ("format_version", "split", "k", "catalog_fingerprint", "queries_fingerprint",
                  "gold_fingerprint", "scorer_fingerprint"):
        if before.get(field) != after[field]:
            raise ValueError(f"Cannot compare reports: {field} differs")
    return {name: {"before": before["metrics"][name], "after": value,
                   "delta": value - before["metrics"][name] if value is not None and before["metrics"][name] is not None else None}
            for name, value in after["metrics"].items()}


def report_markdown(report):
    lines = ["# ESCO candidate retrieval evaluation", "", f"Method: {report['method']}; split: {report['split']}.",
             f"Reviewed: {report['reviewed_cases']}; matched: {report['matched_cases']}; no match: {report['no_match_cases']}.",
             "", "| Metric | Value |", "|---|---:|"]
    for metric, value in report["metrics"].items():
        lines.append(f"| {metric} | {value:.3f} |" if value is not None else f"| {metric} | N/A |")
    lines += ["", report["note"]]
    if "comparison" in report:
        lines += ["", "| Metric | Before | After | Delta |", "|---|---:|---:|---:|"]
        for name, values in report["comparison"].items():
            lines.append(f"| {name} | {values['before']} | {values['after']} | {values['delta']} |")
    return "\n".join(lines) + "\n"
