import json
from pathlib import Path
from typing import Any

import pytest

from parser.extract import ExtractionError, extract
from parser.html_text import html_to_text
from parser.normalize import detect_language, move_marked_to_nice, normalize, normalize_location, normalize_skill
from parser.quality import check
from parser.run import run
from parser.schema import JobExtraction, llm_json_schema

PAGE_TEXT = """Senior Java vývojár (m/ž)
TatraSoft s.r.o.
Miesto práce
Bratislava - Staré Mesto
Základná zložka mzdy (brutto)
3 000 – 4 200 EUR/mesiac
Požadujeme:
- min. 5 rokov praxe
- Java, spring boot, k8s
- English (B2+)
Výhodou je: Kafka
Možnosť home office 2 dni v týždni."""

GOOD: dict[str, Any] = {
    "title": "Senior Java vývojár (m/ž)", "company": "TatraSoft s.r.o.", "location": "Bratislava - Staré Mesto",
    "workplace_type": "hybrid", "employment_type": "full_time", "seniority": "senior", "specialization": "Java",
    "required_skills": ["Java", "spring boot", "Kubernetes (k8s)", "English (B2+)"],
    "nice_to_have_skills": ["Kafka"], "technologies": ["Java", "Spring Boot"],
    "salary_min": 3000, "salary_max": 4200, "salary_currency": "eur",
}


class FakeClient:
    """Повертає заздалегідь задані відповіді й запам'ятовує запити."""

    name = "fake"

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, system: str, messages: list[dict[str, str]], schema: dict[str, Any]) -> str:
        self.calls.append(list(messages))
        return self.replies.pop(0)


# ------------------------------------------------------------------ extract + retry

def test_extract_valid_first_try() -> None:
    client = FakeClient([json.dumps(GOOD)])
    posting, attempts = extract(client, PAGE_TEXT, "http://x/1")
    assert attempts == 1
    assert posting.source_url == "http://x/1"
    assert posting.location == "Bratislava"
    assert posting.salary_currency == "EUR"
    assert posting.remote is True and posting.language == "sk"
    assert posting.required_skills == ["Java", "Spring Boot", "Kubernetes", "English"]
    assert posting.technologies == ["Java", "Spring Boot", "Kubernetes", "Kafka"]


def test_extract_retries_on_invalid_json_and_feeds_error_back() -> None:
    bad_salary = GOOD | {"salary_min": 5000, "salary_max": 1000}
    client = FakeClient(["not json at all", json.dumps(bad_salary), json.dumps(GOOD)])
    posting, attempts = extract(client, PAGE_TEXT, "http://x/1")
    assert attempts == 3
    assert posting.salary_min == 3000
    last_call = client.calls[-1]
    assert last_call[-2]["role"] == "assistant"
    assert "salary_min must be <= salary_max" in last_call[-1]["content"]


def test_extract_gives_up_after_max_retries() -> None:
    client = FakeClient(['{"title": 1}'] * 3)
    with pytest.raises(ExtractionError) as err:
        extract(client, PAGE_TEXT, "http://x/1")
    assert err.value.attempts == 3


def test_schema_is_strict_for_structured_output() -> None:
    schema = llm_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


# ------------------------------------------------------------------ normalize

@pytest.mark.parametrize("raw, canon", [
    ("js", "JavaScript"), ("JS", "JavaScript"), ("k8s", "Kubernetes"), ("postgres", "PostgreSQL"),
    ("React.js", "React"), ("HTML5", "HTML"), ("Kubernetes (k8s)", "Kubernetes"), ("Java 17+", "Java"),
    ("English (B2+)", "English"), ("angličtina min. B2", "English"), ("Agile/Scrum", "Scrum"),
    ("great communicator", "Communication"), ("dobré komunikačné schopnosti", "Communication"),
    ("práca v Scrum tíme", "Scrum"), ("fluent Slovak or Czech", "Slovak"),
    ("SomethingNew", "SomethingNew"),
])
def test_normalize_skill(raw: str, canon: str) -> None:
    assert normalize_skill(raw) == canon


@pytest.mark.parametrize("raw, city", [
    ("BA", "Bratislava"), ("Kosice", "Košice"), ("Košice - Juh", "Košice"), ("Zilina", "Žilina"),
    ("Bratislava, Bratislavský kraj, Slovakia", "Bratislava"), ("Slovakia (Remote)", None),
    ("Práca z domu", None), (None, None),
])
def test_normalize_location(raw: str | None, city: str | None) -> None:
    assert normalize_location(raw) == city


def test_normalize_lists_consistency() -> None:
    ex = JobExtraction(**(GOOD | {"required_skills": ["js", "Communication skills", "JavaScript"],
                                  "nice_to_have_skills": ["javascript", "ts"], "technologies": []}))
    n = normalize(ex, "u", PAGE_TEXT + "\n- dobré komunikačné schopnosti")
    assert n.required_skills == ["JavaScript", "Communication"]
    assert n.nice_to_have_skills == ["TypeScript"]  # дубль обов'язкового прибрано
    assert n.technologies == ["JavaScript", "TypeScript"]  # без soft skills


def test_workplace_type_maps_to_remote_and_location() -> None:
    # повністю remote без міста -> location null
    p, _ = extract(FakeClient([json.dumps(GOOD | {"workplace_type": "remote", "location": "Slovakia (Remote)"})]),
                   PAGE_TEXT, "u")
    assert p.remote is True and p.location is None
    # модель сказала remote, але назвала місто -> місто зберігаємо (помилку remote ловить quality)
    p, _ = extract(FakeClient([json.dumps(GOOD | {"workplace_type": "remote", "location": "Košice, Slovakia"})]),
                   PAGE_TEXT, "u")
    assert p.remote is True and p.location == "Košice"
    p, _ = extract(FakeClient([json.dumps(GOOD | {"workplace_type": "on-site"})]), PAGE_TEXT, "u")
    assert p.remote is False and p.location == "Bratislava"


def test_detect_language_ignores_slovak_site_chrome() -> None:
    chrome = "Miesto práce\nDruh pracovného pomeru\nSvoj životopis posielajte cez tlačidlo na ponuku a len vybraných.\n"
    english = ("- build and maintain backend services\n- write tests and do code reviews\n"
               "We are looking for someone with 5+ years of experience. Your daily stack: Java and Kafka.")
    assert detect_language(chrome + english) == "en"
    assert detect_language(chrome + "Hľadáme posilu do tímu, ktorá má prax. Pracovať budeš s Java a Kafka.") == "sk"


def test_marked_bullets_move_to_nice_to_have() -> None:
    text = "Who we're looking for:\n- Azure\n- dbt – a plus\n- Airflow (bonus)\n- Kafka (výhodou)\n- SQL"
    req, nice = move_marked_to_nice(["Azure", "dbt", "Airflow", "Kafka", "SQL"], ["Python"], text)
    assert req == ["Azure", "SQL"]
    assert nice == ["Python", "dbt", "Airflow", "Kafka"]
    # у вільному тексті не чіпаємо: там одне речення містить і обов'язкові, і бажані
    req, nice = move_marked_to_nice(["Java"], [], "Pracovať budeš s Java. Výhodou je Kafka.")
    assert req == ["Java"]


def test_drops_invented_soft_skills_experience_and_markers() -> None:
    reply = GOOD | {"required_skills": ["Java", "English", "Slovak", "Scrum", "5+ years of hands-on experience"],
                    "nice_to_have_skills": ["Kafka – a plus"], "technologies": ["2-4 roky praxe"]}
    text = PAGE_TEXT + "\nTatraSoft je firma so sídlom na Slovensku, offices in Slovakia."
    p, _ = extract(FakeClient([json.dumps(reply)]), text, "u")
    assert p.required_skills == ["Java", "English"]  # Slovak/Scrum на сторінці не згадані
    assert p.nice_to_have_skills == ["Kafka"]
    assert p.technologies == ["Java", "Kafka"]


# ------------------------------------------------------------------ quality

def test_quality_good_extraction_is_confident() -> None:
    posting, _ = extract(FakeClient([json.dumps(GOOD)]), PAGE_TEXT, "u")
    report = check(posting, PAGE_TEXT)
    assert report.issues == []
    assert report.confidence == 1.0 and not report.low_confidence


def test_quality_flags_hallucinations() -> None:
    bad = GOOD | {"title": "Senior Java Developer", "technologies": ["Java", "Rust"],
                  "salary_min": 9999, "salary_max": None, "seniority": "junior", "workplace_type": "on-site"}
    posting, _ = extract(FakeClient([json.dumps(bad)]), PAGE_TEXT, "u")
    report = check(posting, PAGE_TEXT)
    text = " | ".join(report.issues)
    assert report.low_confidence
    for expected in ["Rust", "title", "9999", "seniority 'junior'", "remote=false"]:
        assert expected in text


def test_quality_flags_missing_salary_max_and_remote_contradiction() -> None:
    reply = GOOD | {"salary_max": None, "workplace_type": "on-site"}
    posting, _ = extract(FakeClient([json.dumps(reply)]), PAGE_TEXT, "u")
    report = check(posting, PAGE_TEXT)
    assert any("salary_max" in i for i in report.issues)
    assert report.low_confidence  # суперечність remote сама по собі вже робить запис сумнівним


def test_quality_flags_missed_salary() -> None:
    no_salary = GOOD | {"salary_min": None, "salary_max": None, "salary_currency": None}
    posting, _ = extract(FakeClient([json.dumps(no_salary)]), PAGE_TEXT, "u")
    assert any("salary" in i for i in check(posting, PAGE_TEXT).issues)


# ------------------------------------------------------------------ html + run

def test_html_to_text_drops_chrome() -> None:
    html = ("<html><head><style>.x{}</style><title>T</title></head><body><nav>Menu</nav>"
            "<h1>Senior QA</h1><ul><li>Selenium</li><li>Jira</li></ul><footer>©</footer></body></html>")
    assert html_to_text(html) == "Senior QA\n- Selenium\n- Jira"


def test_run_writes_jsonl_and_resumes(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    (raw / "profesia").mkdir(parents=True)
    (raw / "profesia" / "1.html").write_text(f"<p>{PAGE_TEXT}</p>", encoding="utf-8")
    (raw / "profesia" / "index.json").write_text(json.dumps([
        {"site": "profesia", "id": "1", "url": "http://localhost:8001/offer/1.html", "file": "profesia/1.html"},
    ]), encoding="utf-8")
    out = tmp_path / "parsed"

    assert run(FakeClient([json.dumps(GOOD)]), raw_dir=raw, out_dir=out) == (1, 0)
    rec = json.loads((out / "jobs.jsonl").read_text(encoding="utf-8"))
    assert rec["source_url"] == "http://localhost:8001/offer/1.html"
    assert rec["model"] == "fake" and rec["confidence"] == 1.0

    assert run(FakeClient([]), raw_dir=raw, out_dir=out) == (0, 0)  # уже розпарсено -> пропуск
    assert run(FakeClient(["broken"] * 3), raw_dir=raw, out_dir=out, force=True) == (0, 1)
    assert (out / "errors.jsonl").exists()
