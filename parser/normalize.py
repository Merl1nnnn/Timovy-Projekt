"""Детермінована нормалізація після LLM: аліаси технологій, міста, узгодженість списків.

Словник аліасів — окремий від генератора мок-сайтів (mock_sites/vocab.py) і описує
загальновживані варіанти назв, а не конкретні шаблони генератора.
"""

import re
import unicodedata

from parser.schema import JobExtraction, JobPosting

# Канонічна назва -> варіанти написання (порівняння без урахування регістру).
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
    # нетехнічні навички
    "English": ["english", "angličtina", "anglický jazyk", "english language", "fluent english"],
    "Slovak": ["slovak", "slovenčina", "slovak language", "slovak or czech", "slovenský jazyk"],
    "Scrum": ["scrum", "agile", "agile/scrum", "agilný vývoj", "agile scrum", "scrum/agile"],
    "Communication": ["communication", "communication skills", "komunikatívnosť",
                      "komunikačné schopnosti", "strong communication skills"],
}
SOFT_SKILLS = {"English", "Slovak", "Scrum", "Communication"}
# Основи слів (без діакритики) для розпізнавання нетехнічних навичок у вільному формулюванні.
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
          "Trenčín", "Martin", "Poprad"]
CITY_ABBREV = {"ba": "Bratislava", "ke": "Košice", "za": "Žilina"}
REMOTE_WORDS = ["remote", "home office", "z domu", "anywhere"]


def fold(s: str) -> str:
    """Нижній регістр без діакритики: 'Košice' -> 'kosice'."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


_CITY_BY_FOLD = {fold(c): c for c in CITIES}


# Хвости-позначки, які модель іноді копіює разом із назвою: "Flask – a plus", "dbt (výhodou)".
_MARKER_SUFFIX = re.compile(r"\s*[–-]\s*(a plus|nice to have|plus|bonus|výhodou)\s*$", re.IGNORECASE)
# "2-4 years of professional experience", "min. 5 rokov praxe" — це не навичка.
_EXPERIENCE = re.compile(r"\d+\s*\+?\s*(?:[–-]\s*\d+\s*)?(?:years?|rok|rokov|roky)\b", re.IGNORECASE)


def is_experience(item: str) -> bool:
    return _EXPERIENCE.search(item) is not None


def normalize_skill(name: str) -> str:
    raw = _MARKER_SUFFIX.sub("", name.strip().strip(".,;:"))
    key = raw.lower()
    if key in _LOOKUP:
        return _LOOKUP[key]
    # "Kubernetes (k8s)", "English (B2+)", "Java 17+" -> пробуємо без дужок і хвостів
    base = re.sub(r"\s*\(.*?\)\s*", " ", raw).strip()
    base = re.sub(r"\s*[\d.+]+$", "", base).strip()
    if base.lower() in _LOOKUP:
        return _LOOKUP[base.lower()]
    # Нетехнічні навички довільним текстом: "great communicator", "práca v Scrum tíme", "angličtina min. B2"
    folded = fold(base)
    for soft, stems in SOFT_STEMS.items():
        if any(stem in folded for stem in stems):
            return soft
    return base or raw


# Чи згадує сторінка нетехнічну навичку. Для Slovak суворіше, ніж SOFT_STEMS:
# "Slovakia" / "Slovensko" (країна) — не вимога знати мову.
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
        return None  # "Slovakia (Remote)", "Práca z domu" — міста немає
    return location.strip()


# Службові слова для визначення мови тексту (без діакритики).
SK_STOPWORDS = {"a", "v", "na", "s", "so", "je", "pre", "sa", "z", "za", "do", "od", "aj", "alebo", "ktory",
                "ktora", "budes", "ako", "len", "cez", "sme", "ste", "pri", "po", "k", "vo", "uz", "mas",
                "tvoj", "nas", "nasich"}
EN_STOPWORDS = {"the", "and", "of", "to", "with", "for", "in", "you", "we", "our", "is", "are", "will",
                "your", "an", "at", "from", "who", "what", "or", "as"}
# Словацький текст майже не містить англійських службових слів, тоді як словацьке оформлення
# сайту (Profesia) додає SK-слова й до англійських вакансій. Тому порівнюємо не більшість,
# а частку EN-слів. На мок-даних: SK-сторінки <= 0.29, EN-сторінки >= 0.38.
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
    """Пункт списку з позначкою «(výhodou)», «– a plus» тощо — бажаний, навіть якщо LLM поклала його в обов'язкові.

    Лише для рядків-пунктів ("- ..."): у вільному тексті одне речення змішує обидва типи.
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


def normalize(ex: JobExtraction, source_url: str, page_text: str) -> JobPosting:
    """Сирий витяг LLM -> фінальний JobPosting (канонічні назви, узгоджені списки, похідні поля)."""
    def clean(items: list[str]) -> list[str]:
        skills = [normalize_skill(s) for s in items if not is_experience(s)]
        # Нетехнічна навичка, про яку сторінка не згадує, — вигадка моделі.
        return dedupe([s for s in skills if s not in SOFT_SKILLS or soft_skill_mentioned(s, page_text)])

    required = clean(ex.required_skills)
    nice = [s for s in clean(ex.nice_to_have_skills)
            if s.lower() not in {r.lower() for r in required}]  # обов'язкове важливіше за бажане
    required, nice = move_marked_to_nice(required, nice, page_text)
    # technologies = усі технічні навички з обох списків + те, що LLM поклала лише сюди.
    tech = dedupe(clean(ex.technologies) + required + nice)
    tech = [t for t in tech if t not in SOFT_SKILLS]
    location = normalize_location(ex.location)
    return JobPosting(
        title=ex.title.strip(),
        company=ex.company.strip(),
        # Місто не обнуляємо навіть при workplace_type=remote: якщо модель його назвала, воно
        # зазвичай є на сторінці, а помилкове "remote" окремо ловить перевірка якості.
        # (Раніше обнуляли — і одна помилка моделі ставала двома: remote + втрачене місто.)
        location=location,
        remote=ex.workplace_type in ("hybrid", "remote"),
        employment_type=ex.employment_type,
        seniority=ex.seniority,
        specialization=ex.specialization,
        required_skills=required,
        nice_to_have_skills=nice,
        technologies=tech,
        salary_min=ex.salary_min,
        salary_max=ex.salary_max,
        salary_currency=ex.salary_currency,
        language=detect_language(page_text),
        source_url=source_url,
    )
