import copy
import csv
import json
import subprocess
import sys

import pytest

from esco.data import Catalog, Concept, Labels, digest, write_json
from esco.evaluate import compare_reports, evaluate_mapping, import_review, review_template
from esco.run import export_mapping
from esco.search import Matcher, Query


def scenario():
    concepts = [Concept(uri=f"http://data.europa.eu/esco/skill/00000000-0000-0000-0000-{i:012}",
                        labels={"en": Labels(preferred=name)}) for i, name in [(1, "Python"), (2, "SQL"), (3, "Java")]]
    catalog = Catalog(esco_version="synthetic-test", concepts=concepts)
    queries = [Query(id="q1", skill="Python"), Query(id="q2", skill="SQL")]
    query_rows = [q.model_dump() for q in queries]
    run = {"format_version": 1, "catalog_fingerprint": catalog.fingerprint,
           "queries_fingerprint": digest(query_rows), "method": "lexical", "k": 3,
           "queries": query_rows, "results": [Matcher(catalog).search(q) for q in queries]}
    gold = review_template(run)
    for row, concept in zip(gold["annotations"], concepts):
        row.update(decision="matched", acceptable_uris=[concept.uri], reviewer="synthetic-test", split="dev")
    return catalog, run, gold


def test_correct_candidate_metrics():
    catalog, run, gold = scenario()
    report = evaluate_mapping(gold, run, catalog)
    assert report["metrics"] == {"top1_accuracy": 1, "hit_at_3": 1, "mrr_at_k": 1, "prediction_coverage": 1}
    assert report["errors"] == []


def test_ranking_errors_and_missing_results_are_counted():
    catalog, run, gold = scenario()
    candidates = run["results"][0]["candidates"]
    candidates.insert(0, copy.deepcopy(run["results"][1]["candidates"][0]))
    run["results"].pop()
    report = evaluate_mapping(gold, run, catalog)
    assert report["metrics"] == {"top1_accuracy": 0, "hit_at_3": 0.5, "mrr_at_k": 0.25, "prediction_coverage": 0.5}
    assert report["errors"][0]["first_correct_rank"] == 2
    assert report["errors"][1]["first_correct_rank"] is None


def test_template_is_unreviewed_and_cannot_be_scored():
    catalog, run, _ = scenario()
    template = review_template(run)
    assert all(r["decision"] == "unreviewed" and not r["acceptable_uris"] for r in template["annotations"])
    with pytest.raises(ValueError, match="No human-reviewed"):
        evaluate_mapping(template, run, catalog)


def test_no_match_is_not_confused_with_unreviewed():
    catalog, run, gold = scenario()
    gold["annotations"][0].update(decision="no_match", acceptable_uris=[])
    report = evaluate_mapping(gold, run, catalog)
    assert report["no_match_cases"] == 1
    assert report["matched_cases"] == 1
    assert report["metrics"]["top1_accuracy"] == 1
    gold["annotations"][1].update(decision="no_match", acceptable_uris=[])
    report = evaluate_mapping(gold, run, catalog)
    assert report["metrics"]["top1_accuracy"] is None


def test_dev_and_test_are_scored_separately():
    catalog, run, gold = scenario()
    gold["annotations"][1]["split"] = "test"
    run["results"].pop()
    assert evaluate_mapping(gold, run, catalog, "dev")["metrics"]["top1_accuracy"] == 1
    assert evaluate_mapping(gold, run, catalog, "test")["metrics"]["top1_accuracy"] == 0


@pytest.mark.parametrize("change", ["uri", "reviewer", "query", "duplicate", "fingerprint"])
def test_invalid_gold_is_rejected(change):
    catalog, run, gold = scenario()
    if change == "uri":
        gold["annotations"][0]["acceptable_uris"] = ["invented"]
    elif change == "reviewer":
        gold["annotations"][0]["reviewer"] = ""
    elif change == "query":
        gold["annotations"][0]["skill"] = "changed"
    elif change == "duplicate":
        gold["annotations"].append(gold["annotations"][0])
    else:
        gold["catalog_fingerprint"] = "changed"
    with pytest.raises(ValueError):
        evaluate_mapping(gold, run, catalog)


def test_review_csv_roundtrip_and_unknown_uri_rejection(tmp_path):
    catalog, run, _ = scenario()
    out = tmp_path / "mapping"
    export_mapping(run, out)
    with (out / "review.csv").open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    rows[0].update(decision="matched", acceptable_uris=catalog.concepts[0].uri, split="dev", reviewer="synthetic-test")
    edited = tmp_path / "reviewed.csv"
    with edited.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    result = import_review(edited, run, catalog, tmp_path / "gold.json")
    assert result["annotations"][0]["decision"] == "matched"
    assert result["annotations"][1]["decision"] == "unreviewed"


def test_comparison_requires_same_gold_queries_catalog_and_split():
    catalog, run, gold = scenario()
    baseline = evaluate_mapping(gold, run, catalog)
    changed = copy.deepcopy(run)
    changed["results"].pop()
    report = evaluate_mapping(gold, changed, catalog)
    assert compare_reports(baseline, report)["top1_accuracy"]["delta"] == -0.5
    report["catalog_fingerprint"] = "different"
    with pytest.raises(ValueError, match="catalog_fingerprint"):
        compare_reports(baseline, report)


def test_cli_lexical_mapping_evaluation_and_input_preservation(tmp_path):
    catalog, run, gold = scenario()
    catalog_path, queries_path, gold_path = [tmp_path / name for name in ("catalog.json", "queries.json", "gold.json")]
    write_json(catalog_path, catalog.model_dump())
    write_json(queries_path, {"queries": run["queries"]})
    write_json(gold_path, gold)
    before = {p: p.read_bytes() for p in (catalog_path, queries_path, gold_path)}
    def cli(*args):
        return subprocess.run([sys.executable, "-m", "esco.run", *map(str, args)], capture_output=True, text=True)
    out = tmp_path / "mapping"
    result = cli("map", "--catalog", catalog_path, "--queries", queries_path, "--out-dir", out)
    assert result.returncode == 0, result.stderr
    assert cli("map", "--catalog", catalog_path, "--queries", queries_path, "--out-dir", out).returncode == 2
    report_dir = tmp_path / "report"
    result = cli("evaluate", "--catalog", catalog_path, "--run", out / "mapping.json", "--gold", gold_path,
                 "--split", "dev", "--out-dir", report_dir)
    assert result.returncode == 0, result.stderr
    report = json.loads((report_dir / "report.json").read_text())
    assert report["metrics"]["top1_accuracy"] == 1
    assert {p: p.read_bytes() for p in before} == before
