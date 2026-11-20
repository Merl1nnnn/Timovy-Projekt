"""Unit tests for the gold-set evaluation (tiny hand-made gold and predictions)."""

import copy
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.evaluate import evaluate, field_equal, load_gold, prf, skill_key
from scripts.evaluation_data import DatasetError, load_predictions, select_gold
from scripts.evaluation_report import add_metadata, compare_reports, save_report


def job(**kw):
    base = {"title": "Java Developer", "company": "Firma s.r.o.", "location": "Bratislava", "remote": False,
            "employment_type": "full_time", "seniority": None, "min_experience_years": None, "education": None,
            "salary_min": 2000, "salary_max": None, "language": "sk", "required_skills": [], "nice_to_have_skills": []}
    return base | kw


def test_prf_handles_empty_sets() -> None:
    assert prf(0, 0, 0)["f1"] == 1.0
    assert prf(1, 1, 1) == {"precision": 0.5, "recall": 0.5, "f1": 0.5, "tp": 1, "fp": 1, "fn": 1}


def test_field_equal_rules() -> None:
    assert field_equal("title", "Java  Developer", "Java Developer")
    assert not field_equal("title", "Java Developer (m/ž)", "Java Developer")
    assert field_equal("company", "Alanata a. s.", "Alanata a.s.")
    assert field_equal("company", "Multitude IT Labs", "Multitude IT Labs (part of Multitude Group)")
    assert not field_equal("company", "Henkel", "Erste Digital")
    assert field_equal("min_experience_years", None, None) and not field_equal("min_experience_years", 0, None)


def test_skill_key_uses_parser_aliases() -> None:
    assert skill_key("k8s") == skill_key("Kubernetes")
    assert skill_key("RESTful API") == skill_key("REST API")
    assert skill_key("C#") != skill_key("C++")


def test_evaluate_counts_skills_lists_and_fields() -> None:
    gold = {"1": job(required_skills=["Java", "SQL"], nice_to_have_skills=["Docker"]),
            "2": job(title="QA Tester", required_skills=["Selenium"])}
    pred = {"1": job(required_skills=["java", "Docker", "Kafka"], confidence=0.9, low_confidence=False),
            "2": job(title="Tester", required_skills=["Selenium"], confidence=0.5, low_confidence=True)}
    r = evaluate(gold, pred)
    assert r["jobs_evaluated"] == 2
    assert r["fields"]["title"]["correct"] == 1
    assert r["skills"]["all"] == prf(3, 1, 1)           # java, docker, selenium found; kafka extra; sql missed
    assert r["skills"]["matched_but_wrong_list"]["count"] == 1  # docker: nice in gold, required in pred
    assert r["confidence_check"]["low_confidence"]["jobs"] == 1


def test_load_gold_keeps_one_copy_of_control_jobs(tmp_path: Path) -> None:
    for name in ("a", "b"):
        (tmp_path / f"gold_{name}.json").write_text(json.dumps({"jobs": [job(id="7"), job(id=name)]}), encoding="utf-8")
    assert sorted(load_gold(tmp_path)) == ["7", "a", "b"]




def write_gold(path, rows, name="gold_a.json"):
    path.mkdir(exist_ok=True)
    file = path / name
    file.write_text(json.dumps({"jobs": rows}), encoding="utf-8")
    return file


def test_conflicting_controls_report_fields_without_choosing_a_winner(tmp_path):
    write_gold(tmp_path, [job(id="1")])
    write_gold(tmp_path, [job(id="1", education="master")], "gold_b.json")
    with pytest.raises(DatasetError, match="conflicting annotations.*education"):
        load_gold(tmp_path)


def test_control_skill_order_is_not_a_conflict(tmp_path):
    write_gold(tmp_path, [job(id="1", required_skills=["SQL", "Java"])])
    write_gold(tmp_path, [job(id="1", required_skills=["Java", "SQL"])], "gold_b.json")
    assert len(load_gold(tmp_path)) == 1


@pytest.mark.parametrize("update", [
    {"remote": "false"}, {"min_experience_years": True}, {"required_skills": "Python"},
    {"nice_to_have_skills": [None]}, {"salary_min": -1}, {"education": "university"},
    {"title": ""}, {"salary_min": 3000, "salary_max": 2000}, {"id": 1},
])
def test_rejects_invalid_gold_types(tmp_path, update):
    write_gold(tmp_path, [job(id="1") | update])
    with pytest.raises(DatasetError):
        load_gold(tmp_path)


def test_missing_field_is_not_a_correct_null(tmp_path):
    row = job(id="1")
    del row["education"]
    write_gold(tmp_path, [row])
    with pytest.raises(DatasetError, match="missing field education"):
        load_gold(tmp_path)


def test_rejects_absent_empty_and_malformed_gold(tmp_path):
    with pytest.raises(DatasetError, match="no gold_"):
        load_gold(tmp_path)
    write_gold(tmp_path, [])
    with pytest.raises(DatasetError, match="no valid jobs"):
        load_gold(tmp_path)
    (tmp_path / "gold_a.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(DatasetError, match="cannot read JSON"):
        load_gold(tmp_path)


def test_rejects_duplicate_or_malformed_predictions(tmp_path):
    path = tmp_path / "pred.jsonl"
    path.write_text((json.dumps(job(id="1")) + "\n") * 2, encoding="utf-8")
    with pytest.raises(DatasetError, match="duplicate prediction"):
        load_predictions(path)
    path.write_text("broken\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="line 1"):
        load_predictions(path)


def test_missing_predictions_cannot_hide_behind_matched_f1():
    gold = {"1": job(required_skills=["Python"]), "2": job(required_skills=["SQL"])}
    result = evaluate(gold, {"1": gold["1"]})
    assert result["coverage"] == 0.5
    assert result["skills"]["all"]["f1"] == 1
    assert result["skills_end_to_end"]["all"] == prf(1, 0, 1)
    assert result["fields"]["title"]["end_to_end_accuracy"] == 0.5
    assert result["missing_predictions"] == ["2"]
    assert result["errors"][-1]["kind"] == "missing_prediction"


def test_no_predictions_has_no_matched_metrics():
    result = evaluate({"1": job(required_skills=["Python"])}, {})
    assert result["coverage"] == 0
    assert result["skills"]["all"] is None
    assert result["skills_end_to_end"]["all"]["f1"] == 0
    assert result["fields"]["title"]["accuracy"] is None
    with pytest.raises(DatasetError, match="no matching IDs"):
        evaluate({"1": job()}, {"wrong": job()})


def test_present_only_accuracy_does_not_reward_nulls():
    gold = {"1": job(education="master"), "2": job(education=None)}
    result = evaluate(gold, {"1": job(education=None), "2": job(education=None)})
    assert result["fields"]["education"]["accuracy"] == 0.5
    assert result["fields"]["education"]["accuracy_when_present"] == 0
    assert result["fields"]["education"]["present_in_gold"] == 1


@pytest.mark.parametrize("field", ["text_hash", "snapshot_id", "source_url", "site"])
def test_source_identity_mismatch_stops_evaluation(field):
    with pytest.raises(DatasetError, match=field):
        evaluate({"1": job(**{field: "old"})}, {"1": job(**{field: "new"})})


def test_gold_provenance_from_second_control_is_retained(tmp_path):
    write_gold(tmp_path, [job(id="1")])
    write_gold(tmp_path, [job(id="1", text_hash="frozen")], "gold_b.json")
    assert load_gold(tmp_path)["1"]["text_hash"] == "frozen"


def test_cohort_manifest_is_explicit_and_validated(tmp_path):
    path = tmp_path / "dev.json"
    path.write_text('["1"]', encoding="utf-8")
    assert list(select_gold({"1": job(), "2": job()}, path)) == ["1"]
    path.write_text('["1", "1"]', encoding="utf-8")
    with pytest.raises(DatasetError, match="duplicate or unknown"):
        select_gold({"1": job()}, path)


def make_report(tmp_path, predictions=None):
    gold = {"1": job(required_skills=["Python"]), "2": job(required_skills=["SQL"])}
    pred = gold if predictions is None else predictions
    path = tmp_path / "pred.jsonl"
    path.write_text("\n".join(json.dumps(row | {"id": jid}) for jid, row in pred.items()), encoding="utf-8")
    result = evaluate(gold, pred)
    add_metadata(result, gold, pred, path, "test", "prompt-v1", "schema-v1")
    return result


def test_comparison_accounts_for_lost_predictions(tmp_path):
    before = make_report(tmp_path)
    after = make_report(tmp_path, {"1": job(required_skills=["Python"])})
    comparison = compare_reports(before, after)
    assert comparison["metrics"]["coverage"]["delta"] == -0.5
    assert comparison["metrics"]["skills_end_to_end.all.recall"]["delta"] == -0.5
    assert comparison["lost_prediction_ids"] == ["2"]


@pytest.mark.parametrize("key", ["gold_fingerprint", "rules_fingerprint", "gold_ids", "report_version"])
def test_comparison_rejects_incompatible_reports(tmp_path, key):
    report = make_report(tmp_path)
    baseline = copy.deepcopy(report)
    baseline["metadata"][key] = "different"
    with pytest.raises(DatasetError, match=key):
        compare_reports(baseline, report)


def test_reports_preserve_inputs_and_existing_outputs(tmp_path):
    result = make_report(tmp_path, {"1": job(required_skills=["=formula()"], title="Other")})
    source = tmp_path / "pred.jsonl"
    original = source.read_bytes()
    out = tmp_path / "run-1"
    save_report(result, out, None, [source])
    assert {p.name for p in out.iterdir()} == {"report.json", "report.md", "errors.csv"}
    assert source.read_bytes() == original
    with (out / "errors.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert any(row["kind"] == "missing_prediction" for row in rows)
    with pytest.raises(DatasetError, match="already exists"):
        save_report(result, out, None, [source])
    with pytest.raises(DatasetError, match="overwrite an input"):
        save_report(result, None, source, [source])
    assert source.read_bytes() == original


def test_csv_formula_escape():
    from scripts.evaluation_report import csv_cell
    assert csv_cell("=1+1") == "'=1+1"
    assert csv_cell("  @SUM(A1)") == "'  @SUM(A1)"
    assert csv_cell("Python") == "Python"


def test_cli_validate_report_and_compare(tmp_path):
    gold_dir = tmp_path / "gold"
    write_gold(gold_dir, [job(id="1", required_skills=["Python"])])
    pred = tmp_path / "pred.jsonl"
    pred.write_text(json.dumps(job(id="1", required_skills=["Python"])), encoding="utf-8")
    base = [sys.executable, "-m", "scripts.evaluate", "--gold", str(gold_dir), "--pred", str(pred)]
    def run(*args):
        return subprocess.run(base + list(args), capture_output=True, text=True)
    assert run("--validate-only").returncode == 0
    first, second = tmp_path / "first", tmp_path / "second"
    completed = run("--out-dir", str(first))
    assert completed.returncode == 0, completed.stderr
    completed = run("--baseline", str(first / "report.json"), "--out-dir", str(second))
    assert completed.returncode == 0, completed.stderr
    report = json.loads((second / "report.json").read_text())
    assert report["comparison"]["metrics"]["coverage"]["delta"] == 0
    assert run("--out-dir", str(first)).returncode == 2
