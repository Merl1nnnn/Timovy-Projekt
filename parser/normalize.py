"""Deterministic post-LLM normalization: technology aliases, cities, list consistency.

The alias dictionary is separate from the mock site generator (mock_sites/vocab.py) and lists
commonly used name variants, not the generator's specific templates.
"""

import re
import unicodedata

from parser.schema import JobExtraction, JobPosting

# Canonical name -> spelling variants (case-insensitive comparison).
CANONICAL: dict[str, list[str]] = {
    "JavaScript": ["js", "javascript", "java script", "ecmascript", "es6"],
    "TypeScript": ["ts", "typescript"],
    "Python": ["python3", "python 3", "py"],
    "Java": ["java 17", "java 21", "java se"],
    "Kubernetes": ["k8s", "kubernetes", "openshift/kubernetes"],
    "Docker": ["docker", "dockerfile", "containers (docker)"],
    "PostgreSQL": ["postgres", "postgresql", "postgressql", "postgresql database", "psql"],
    "Spring Boot": ["spring boot", "springboot", "spring-boot"],
    "React": ["react", "reactjs", "react.js"],
    "Vue.js": ["vue", "vuejs", "vue.js", "vue 3"],
    "Angular": ["angular", "angularjs"],
    "Next.js": ["nextjs", "next.js"],
    "Node.js": ["node", "nodejs", "node.js"],
    "Apache Spark": ["spark", "apache spark", "pyspark"],
    "Airflow": ["apache airflow", "airflow"],
    "Kafka": ["apache kafka", "kafka"],
    "GitLab CI": ["gitlab ci", "gitlab ci/cd", "gitlab-ci", "gitlab pipelines"],
    "Terraform": ["terraform", "tf"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure", "ms azure", "microsoft azure"],
    "Power BI": ["power bi", "powerbi", "pbi"],
    "SQL": ["sql", "t-sql", "sql queries"],
    "REST API": ["rest", "rest api", "rest apis", "restful", "restful api", "restful apis"],
    "Microservices": ["microservices", "microservice architecture", "mikroslužby", "microservice"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "Selenium": ["selenium", "selenium webdriver"],
    "Linux": ["linux", "unix/linux", "linux/unix"],
    "Bash": ["bash", "shell", "shell scripting", "bash scripting"],
    "Git": ["git", "version control (git)"],
    "Pandas": ["pandas"],
    "Jest": ["jest"],
    "Jenkins": ["jenkins"],
    "Grafana": ["grafana"],
    "Prometheus": ["prometheus"],
    "Ansible": ["ansible"],
    "dbt": ["dbt", "data build tool"],
    "Snowflake": ["snowflake"],
    "Databricks": ["databricks"],
    "Cypress": ["cypress"],
    "Playwright": ["playwright"],
    "Postman": ["postman"],
    "JMeter": ["jmeter", "apache jmeter"],
    "Jira": ["jira"],
    "Redux": ["redux"],
    "Webpack": ["webpack"],
    "Django": ["django"],
    "FastAPI": ["fastapi", "fast api"],
    "Flask": ["flask"],
    "Celery": ["celery"],
    "Redis": ["redis"],
    "Hibernate": ["hibernate", "jpa/hibernate"],
    "Oracle": ["oracle", "oracle db", "oracle database"],
    "Maven": ["maven"],
    # non-technical skills
    "English": ["english", "angličtina", "anglický jazyk", "english language", "fluent english"],
    "Slovak": ["slovak", "slovenčina", "slovak language", "slovak or czech", "slovenský jazyk"],
    "Scrum": ["scrum", "agile", "agile/scrum", "agilný vývoj", "agile scrum", "scrum/agile"],
    "Communication": ["communication", "communication skills", "komunikatívnosť",
                      "komunikačné schopnosti", "strong communication skills"],
}
SOFT_SKILLS = {"English", "Slovak", "Scrum", "Communication"}
# Word stems (without diacritics) for recognising non-technical skills in free-form wording.
SOFT_STEMS: dict[str, list[str]] = {
    "Slovak": ["slovak", "slovensk", "slovencin"],
    "English": ["english", "anglick", "anglictin"],
    "Scrum": ["scrum", "agil"],
    "Communication": ["communicat", "komunika"],
}

_LOOKUP: dict[str, str] = {}
for canon, variants in CANONICAL.items():
    _LOOKUP[canon.lower()] = canon
    for v in variants:
        _LOOKUP[v.lower()] = canon

CITIES = ["Bratislava", "Košice", "Žilina", "Prešov", "Nitra", "Banská Bystrica", "Trnava",
          "Trenčín", "Martin", "Poprad", "Trebišov", "Michalovce", "Zvolen", "Piešťany", "Prievidza",
          "Liptovský Mikuláš", "Ružomberok", "Spišská Nová Ves", "Humenné", "Komárno", "Nové Zámky", "Levice",
          "Lučenec", "Revúca", "Rimavská Sobota", "Považská Bystrica", "Dubnica nad Váhom", "Senica", "Skalica"]
CITY_ABBREV = {"ba": "Bratislava", "ke": "Košice", "za": "Žilina"}
REMOTE_WORDS = ["remote", "home office", "z domu", "anywhere"]


def fold(s: str) -> str:
    """Lowercase without diacritics: 'Košice' -> 'kosice'."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


_CITY_BY_FOLD = {fold(c): c for c in CITIES}


# Marker suffixes the model sometimes copies along with the name: "Flask – a plus", "dbt (výhodou)".
_MARKER_SUFFIX = re.compile(r"\s*[–-]\s*(a plus|nice to have|plus|bonus|výhodou)\s*$", re.IGNORECASE)
# "2-4 years of professional experience", "min. 5 rokov praxe" are not skills.
_EXPERIENCE = re.compile(r"\d+\s*\+?\s*(?:[–-]\s*\d+\s*)?(?:years?|rok|rokov|roky)\b", re.IGNORECASE)


def is_experience(item: str) -> bool:
    return _EXPERIENCE.search(item) is not None


def normalize_skill(name: str) -> str:
    # Keep a leading dot: ".NET".
    raw = _MARKER_SUFFIX.sub("", name.strip().lstrip(",;:").rstrip(".,;:"))
    key = raw.lower()
    if key in _LOOKUP:
        return _LOOKUP[key]
    # "Kubernetes (k8s)", "English (B2+)", "Java 17+" -> retry without parentheses and suffixes
    base = re.sub(r"\s*\(.*?\)\s*", " ", raw).strip()
    base = re.sub(r"\s+[\d.+]+$", "", base).strip()  # only a version after a space: "Java 17+"; "TYPO3" stays intact
    if base.lower() in _LOOKUP:
        return _LOOKUP[base.lower()]
    # Non-technical skills in free text: "great communicator", "práca v Scrum tíme", "angličtina min. B2"
    folded = fold(base)
    for soft, stems in SOFT_STEMS.items():
        if any(stem in folded for stem in stems):
            return soft
    return base or raw


# Whether the page mentions a non-technical skill. Stricter than SOFT_STEMS for Slovak:
# "Slovakia" / "Slovensko" (the country) is not a language requirement.
_SOFT_MENTION: dict[str, re.Pattern[str]] = {
    "Slovak": re.compile(r"slovak(?!ia)|slovencin|slovensk(?:y|eho|om) jazyk"),
    "English": re.compile(r"english|anglick|anglictin"),
    "Scrum": re.compile(r"scrum|agil"),
    "Communication": re.compile(r"communicat|komunika"),
}


def soft_skill_mentioned(skill: str, page_text: str) -> bool:
    return _SOFT_MENTION[skill].search(fold(page_text)) is not None


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item.lower() not in seen:
            seen.add(item.lower())
            out.append(item)
    return out


def normalize_location(location: str | None) -> str | None:
    if not location:
        return None
    for part in re.split(r"[,(/]| - | – ", location):
        key = fold(part).strip()
        if key in _CITY_BY_FOLD:
            return _CITY_BY_FOLD[key]
        if key in CITY_ABBREV:
            return CITY_ABBREV[key]
        for city_key, city in _CITY_BY_FOLD.items():  # "Bratislava - Staré Mesto", "Košice-Juh"
            if key.startswith(city_key):
                return city
    if any(w in fold(location) for w in REMOTE_WORDS):
        return None  # "Slovakia (Remote)", "Práca z domu": no city
    return location.strip()


# Function words for detecting the text language (without diacritics).
SK_STOPWORDS = {"a", "v", "na", "s", "so", "je", "pre", "sa", "z", "za", "do", "od", "aj", "alebo", "ktory",
                "ktora", "budes", "ako", "len", "cez", "sme", "ste", "pri", "po", "k", "vo", "uz", "mas",
                "tvoj", "nas", "nasich"}
EN_STOPWORDS = {"the", "and", "of", "to", "with", "for", "in", "you", "we", "our", "is", "are", "will",
                "your", "an", "at", "from", "who", "what", "or", "as"}
# Slovak text contains almost no English function words, while the Slovak site chrome
# (Profesia) adds SK words to English postings as well. So instead of a majority vote we use
# the share of EN words. On mock data: SK pages <= 0.29, EN pages >= 0.38.
EN_RATIO_THRESHOLD = 0.35


def detect_language(text: str) -> str:
    words = re.findall(r"[a-z]+", fold(text))
    sk = sum(w in SK_STOPWORDS for w in words)
    en = sum(w in EN_STOPWORDS for w in words)
    return "en" if en and en / (en + sk) >= EN_RATIO_THRESHOLD else "sk"


NICE_MARKERS = ["vyhodou", "(plus)", "plusove body", "nice to have", "a plus", "(bonus)", "bonus points"]


def _word_in(phrase: str, text_folded: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(fold(phrase))}(?![a-z0-9])", text_folded) is not None


def move_marked_to_nice(required: list[str], nice: list[str], page_text: str) -> tuple[list[str], list[str]]:
    """A list item marked "(výhodou)", "– a plus" etc. is nice-to-have even if the LLM put it into required.

    Only for bullet lines ("- ..."): in free text a single sentence mixes both kinds.
    """
    bullets = [fold(line) for line in page_text.splitlines() if line.startswith("- ")]
    marked = [b for b in bullets if any(m in b for m in NICE_MARKERS)]
    unmarked = [b for b in bullets if b not in marked]
    keep, moved = [], []
    for skill in required:
        variants = [skill] + CANONICAL.get(skill, [])
        in_marked = any(_word_in(v, b) for v in variants for b in marked)
        in_unmarked = any(_word_in(v, b) for v in variants for b in unmarked)
        (moved if in_marked and not in_unmarked else keep).append(skill)
    return keep, dedupe(nice + moved)


_AMOUNT = r"(\d{1,2}[  .,]?\d{3})"
_SALARY_RANGE = re.compile(_AMOUNT + r"\s*[-–]\s*(?:€\s*)?" + _AMOUNT + r"\s*(?:EUR|€)", re.IGNORECASE)
_SALARY_ONE = re.compile(r"(?:€\s*" + _AMOUNT + r"|" + _AMOUNT + r"\s*(?:EUR|€))", re.IGNORECASE)


def salary_from_text(page_text: str) -> tuple[int | None, int | None]:
    """Rule-based monthly salary: the first line with an EUR amount. A fallback for when the LLM missed it."""
    def num(s: str) -> int:
        return int(re.sub(r"\D", "", s))

    for line in page_text.splitlines():
        if not re.search(r"EUR|€", line, re.IGNORECASE):
            continue
        m = _SALARY_RANGE.search(line)
        if m and 300 <= num(m.group(1)) <= num(m.group(2)):
            return num(m.group(1)), num(m.group(2))
        m = _SALARY_ONE.search(line)
        if m and num(m.group(1) or m.group(2)) >= 300:  # smaller amounts are hourly rates or bonuses
            return num(m.group(1) or m.group(2)), None
    return None, None


MAX_SKILL_WORDS = 5  # a longer "skill" is a duty sentence, not a skill


def normalize(ex: JobExtraction, source_url: str, page_text: str) -> JobPosting:
    """Raw LLM extraction -> final JobPosting (canonical names, consistent lists, derived fields)."""
    def clean(items: list[str]) -> list[str]:
        skills = [normalize_skill(s) for s in items
                  if not is_experience(s) and len(s.split()) <= MAX_SKILL_WORDS]
        # A non-technical skill the page does not mention is a model hallucination.
        return dedupe([s for s in skills if s not in SOFT_SKILLS or soft_skill_mentioned(s, page_text)])

    required = clean(ex.required_skills)
    nice = [s for s in clean(ex.nice_to_have_skills)
            if s.lower() not in {r.lower() for r in required}]  # required takes precedence over nice-to-have
    required, nice = move_marked_to_nice(required, nice, page_text)
    years = ex.min_experience_years
    if years is not None and not 0 <= years <= 40:
        years = None
    salary_min, salary_max, currency = ex.salary_min, ex.salary_max, ex.salary_currency
    rule_min, rule_max = salary_from_text(page_text)
    if salary_min is None and salary_max is None and rule_min is not None:
        salary_min, salary_max, currency = rule_min, rule_max, "EUR"
    elif salary_max is None and rule_max is not None and salary_min == rule_min:
        salary_max = rule_max
    location = normalize_location(ex.location)
    return JobPosting(
        title=ex.title.strip(),
        company=ex.company.strip(),
        # Keep the city even with workplace_type=remote: if the model named one, it is
        # usually on the page, and a wrong "remote" is caught separately by the quality check.
        # (Clearing it used to turn one model error into two: remote + a lost city.)
        location=location,
        remote=ex.workplace_type in ("hybrid", "remote"),
        employment_type=ex.employment_type,
        seniority=ex.seniority,
        specialization=ex.specialization,
        required_skills=required,
        nice_to_have_skills=nice,
        min_experience_years=years,
        education=ex.education,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=currency,
        summary=" ".join(ex.summary.split()),
        language=detect_language(page_text),
        source_url=source_url,
    )
