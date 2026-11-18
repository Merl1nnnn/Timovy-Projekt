"""Unit tests for the gold-set evaluation (tiny hand-made gold and predictions)."""

import json
from pathlib import Path

from scripts.evaluate import evaluate, field_equal, load_gold, prf, skill_key


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
