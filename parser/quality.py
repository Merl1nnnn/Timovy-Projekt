"""Second pass: rule-based quality check of the extraction (no extra LLM call).

Each issue has a weight; confidence = 1 - sum of weights (at least 0).
A record is flagged low_confidence if confidence < LOW_CONFIDENCE_THRESHOLD.
"""

import re

from pydantic import BaseModel

from parser.normalize import CANONICAL, CITY_ABBREV, REMOTE_WORDS, SOFT_SKILLS, fold
from parser.schema import JobPosting

LOW_CONFIDENCE_THRESHOLD = 0.7

SENIORITY_WORDS: dict[str, list[str]] = {
    "junior": ["junior", "jr", "entry-level", "entry level", "zacinajuci", "absolvent", "graduate"],
    "medior": ["medior", "mid-level", "mid level"],
    "senior": ["senior", "sr", "skuseny"],
    "lead": ["lead", "principal", "head of", "veduci"],
}


class QualityReport(BaseModel):
    confidence: float
    low_confidence: bool
    issues: list[str]


def _contains(text_folded: str, phrase: str) -> bool:
    """Searches for a phrase as a whole word (ignoring diacritics and case)."""
    p = re.escape(fold(phrase).strip())
    return re.search(rf"(?<![a-z0-9]){p}(?![a-z0-9])", text_folded) is not None


def _salary_variants(n: int) -> list[str]:
    s = f"{n:,}"
    return [str(n), s, s.replace(",", " "), s.replace(",", "."), s.replace(",", " ")]


def _has_salary_range(page_text: str) -> bool:
    """A line with a currency and two different amounts: "2 000 – 3 000 EUR", "€2,500/month - €3,500/month"."""
    for line in page_text.splitlines():
        if "€" in line or "eur" in line.lower():
            amounts = {int(re.sub(r"\D", "", m)) for m in re.findall(r"\d{1,2}[  .,]?\d{3}", line)}
            if len({a for a in amounts if a >= 300}) >= 2:
                return True
    return False


def check(ex: JobPosting, page_text: str) -> QualityReport:
    t = fold(page_text)
    issues: list[tuple[str, float]] = []

    # Hallucinations: every technical skill must appear in the text (canonical name or alias).
    for skill in ex.required_skills + ex.nice_to_have_skills:
        if skill in SOFT_SKILLS:
            continue  # already filtered in normalize by whether the page mentions them
        variants = [skill] + CANONICAL.get(skill, [])
        if not any(_contains(t, v) for v in variants):
            issues.append((f"skill not found in text: {skill}", 0.15))

    if ex.min_experience_years is not None and not re.search(rf"(?<!\d){ex.min_experience_years}(?!\d)", page_text):
        issues.append((f"experience {ex.min_experience_years} years not found in text", 0.15))

    if not _contains(t, ex.title):
        issues.append(("title not found verbatim in text (translated or invented?)", 0.2))
    if not _contains(t, ex.company):
        issues.append(("company not found in text", 0.2))

    if ex.location:
        abbrevs = [k for k, city in CITY_ABBREV.items() if city == ex.location]
        if not any(_contains(t, v) for v in [ex.location, *abbrevs]):
            issues.append((f"location not found in text: {ex.location}", 0.2))

    remote_hint = any(w in t for w in REMOTE_WORDS + ["hybrid"])
    if ex.remote and not remote_hint:
        issues.append(("remote=true but no remote/hybrid hint in text", 0.35))
    if not ex.remote and remote_hint:
        issues.append(("remote=false but text mentions remote/hybrid/home office", 0.35))

    # Salary: the numbers must be in the text; and vice versa, a salary in the text that was not extracted.
    for n in (ex.salary_min, ex.salary_max):
        if n is not None and not any(v in page_text for v in _salary_variants(n)):
            issues.append((f"salary {n} not found in text", 0.3))
    if ex.salary_min is None and re.search(r"\d[\d  .,]*\s*(€|eur)|€\s*\d", t):
        issues.append(("text looks like it contains a salary, but none extracted", 0.3))
    if ex.salary_min is not None and ex.salary_max is None and _has_salary_range(page_text):
        issues.append(("text has a salary range, but salary_max not extracted", 0.3))

    # Seniority stated explicitly in the title must match the extracted one.
    title_levels = {lvl for lvl, words in SENIORITY_WORDS.items() if any(_contains(fold(ex.title), w) for w in words)}
    if ex.seniority is None:
        issues.append(("seniority missing", 0.1))
    elif title_levels and ex.seniority not in title_levels:
        issues.append((f"seniority '{ex.seniority}' contradicts title ({', '.join(sorted(title_levels))})", 0.3))

    if not ex.required_skills:
        issues.append(("no required skills extracted", 0.3))
    if ex.specialization is None:
        issues.append(("specialization missing", 0.1))
    if ex.employment_type is None:
        issues.append(("employment_type missing", 0.05))

    confidence = round(max(0.0, 1.0 - sum(w for _, w in issues)), 2)
    return QualityReport(confidence=confidence, low_confidence=confidence < LOW_CONFIDENCE_THRESHOLD,
                         issues=[msg for msg, _ in issues])
