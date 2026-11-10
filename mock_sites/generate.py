"""Генератор мок-вакансій і статичних мок-сайтів (Profesia-подібний і LinkedIn-подібний).

Спершу випадково обираються структуровані поля (це ground truth), потім вони
рендеряться в «брудний» текст і HTML. Результат детермінований за seed.

Запуск: uv run python -m mock_sites.generate
"""

import argparse
import json
import random
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from mock_sites import vocab as v

ROOT = Path(__file__).resolve().parent.parent
MOCK_ROOT = ROOT / "mock_sites"
GROUND_TRUTH_PATH = ROOT / "data" / "ground_truth.json"

PER_PAGE = 10
BASE_DATE = date(2026, 11, 1)


@dataclass(frozen=True)
class SiteConfig:
    port: int
    en_share: float  # частка вакансій англійською
    salary_share: float  # частка вакансій із зарплатою


SITES: dict[str, SiteConfig] = {
    "profesia": SiteConfig(port=8001, en_share=0.25, salary_share=0.65),
    "linkedin": SiteConfig(port=8002, en_share=0.85, salary_share=0.40),
}


def base_url(site: str) -> str:
    return f"http://localhost:{SITES[site].port}"


def list_path(site: str, page: int) -> str:
    prefix = "" if site == "profesia" else "/jobs/search"
    return f"{prefix}/index.html" if page == 1 else f"{prefix}/page-{page}.html"


def detail_path(site: str, job_id: str) -> str:
    return f"/offer/{job_id}.html" if site == "profesia" else f"/jobs/view/{job_id}.html"


@dataclass
class Job:
    # --- ground truth (ті самі поля, що й у схемі парсера JobPosting) ---
    title: str
    company: str
    location: str | None
    remote: bool
    employment_type: str
    seniority: str
    specialization: str
    required_skills: list[str]
    nice_to_have_skills: list[str]
    technologies: list[str]
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    language: str
    source_url: str
    # --- лише для рендерингу ---
    id: str = ""
    site: str = ""
    location_display: str = ""
    workplace: str = "On-site"  # On-site / Hybrid / Remote
    employment_display: str = ""
    show_employment: bool = True
    salary_display: str | None = None
    salary_in_text: bool = False
    posted: date = BASE_DATE
    intro: str = ""
    duties: list[str] = field(default_factory=list)
    requirements: list[dict[str, Any]] = field(default_factory=list)
    benefits: list[str] = field(default_factory=list)
    extra_lines: list[str] = field(default_factory=list)
    education: str = ""
    linkedin_level: str = ""
    show_criteria: bool = True
    similar: list["Job"] = field(default_factory=list)
    # Складні / навмисно зламані вакансії (mock_sites/edge_cases.py): опис пастки
    # і, за потреби, власний HTML сторінки деталей замість шаблону.
    edge_case: str = ""
    raw_html: str | None = None

    def ground_truth(self) -> dict[str, Any]:
        keys = ["title", "company", "location", "remote", "employment_type", "seniority",
                "specialization", "required_skills", "nice_to_have_skills", "technologies",
                "salary_min", "salary_max", "salary_currency", "language", "source_url"]
        return ({"site": self.site, "id": self.id} | {k: getattr(self, k) for k in keys}
                | {"edge_case": self.edge_case})


# ---------------------------------------------------------------- рендеринг тексту

def render_tech(rng: random.Random, tech: str) -> str:
    """Канонічна назва або аліас (js, k8s, postgres...)."""
    if tech in v.ALIASES and rng.random() < 0.45:
        return rng.choice(v.ALIASES[tech])
    return tech


def join_words(items: list[str], lang: str, rng: random.Random, conj: str | None = None) -> str:
    if rng.random() < 0.2:
        return "/".join(items)
    if len(items) == 1:
        return items[0]
    word = conj or ("a" if lang == "sk" else "and")
    return ", ".join(items[:-1]) + f" {word} " + items[-1]


def make_title(rng: random.Random, spec: str, seniority: str, lang: str, remote: bool) -> str:
    # Часто SK-вакансія має англійський заголовок.
    title_lang = "en" if lang == "sk" and rng.random() < 0.2 else lang
    template = rng.choice(v.TITLE_TEMPLATES[spec][title_lang])
    title = template.format(s=rng.choice(v.SENIORITY_TITLE_WORDS[seniority][title_lang]))
    title = title.replace("()", "")
    title = re.sub(r"\s+", " ", title).strip(" -–")
    if rng.random() < 0.15:
        noise = [n for n in v.TITLE_NOISE if remote or "home office" not in n]
        title += rng.choice(noise)
    return title


def format_salary(lo: int, hi: int | None, lang: str) -> str:
    if lang == "sk":
        def f(x: int) -> str:
            return f"{x:,}".replace(",", " ")
        return f"od {f(lo)} EUR/mesiac" if hi is None else f"{f(lo)} – {f(hi)} EUR/mesiac"
    return f"From €{lo:,}/month" if hi is None else f"€{lo:,}/month - €{hi:,}/month"


def make_requirements(rng: random.Random, lang: str, seniority: str, required_tech: list[str],
                      nice_tech: list[str], soft: list[str]) -> list[dict[str, Any]]:
    """Вимоги в одному з трьох стилів: списки, вільний текст, змішаний список."""
    exp = rng.choice(v.EXPERIENCE_LINES[seniority][lang])
    req = [render_tech(rng, t) for t in required_tech]
    nice = [render_tech(rng, t) for t in nice_tech]
    soft_txt = [rng.choice(v.SOFT_SKILLS[s][lang]) for s in soft]
    style = rng.choice(["lists", "free_text", "mixed"])

    if style == "lists":
        if lang == "sk":
            req_head = rng.choice(["Požadujeme:", "Must have:", "Čo by si mal/a ovládať:"])
            nice_head = rng.choice(["Výhodou je:", "Nice to have:", "Plusové body za:"])
            wrap = ["{t}", "skúsenosti s {t}", "znalosť {t}", "{t} (aktívne)"]
        else:
            req_head = rng.choice(["Requirements:", "Must have:", "What you bring:"])
            nice_head = rng.choice(["Nice to have:", "Bonus points for:"])
            wrap = ["{t}", "experience with {t}", "solid knowledge of {t}", "hands-on {t}"]
        items = [exp] + [rng.choice(wrap).format(t=t) for t in req] + soft_txt
        blocks: list[dict[str, Any]] = [{"kind": "h", "text": req_head}, {"kind": "ul", "items": items}]
        if nice:
            blocks += [{"kind": "h", "text": nice_head}, {"kind": "ul", "items": nice}]
        return blocks

    if style == "free_text":
        if lang == "sk":
            text = (f"Hľadáme posilu do tímu, ktorá má {exp}. "
                    f"Pracovať budeš hlavne s {join_words(req, lang, rng)}. ")
            if soft_txt:
                text += f"Dôležitá je aj {', '.join(soft_txt)}. "
            if nice:
                text += f"Výhodou je znalosť {join_words(nice, lang, rng, 'alebo')}."
        else:
            text = (f"We are looking for someone with {exp}. "
                    f"Your daily stack: {join_words(req, lang, rng)}. ")
            if soft_txt:
                text += f"We also value {', '.join(soft_txt)}. "
            if nice:
                text += f"It's a plus if you know {join_words(nice, lang, rng, 'or')}."
        return [{"kind": "p", "text": text.strip()}]

    # mixed: один список, де «nice to have» позначено лише суфіксом
    suffixes = ["(výhodou)", "– nice to have", "(plus)"] if lang == "sk" else ["(nice to have)", "– a plus", "(bonus)"]
    items = [exp] + req + soft_txt + [f"{t} {rng.choice(suffixes)}" for t in nice]
    first, rest = items[0], items[1:]
    rng.shuffle(rest)
    head = "Požiadavky / Requirements:" if lang == "sk" else "Who we're looking for:"
    return [{"kind": "h", "text": head}, {"kind": "ul", "items": [first] + rest}]


# ---------------------------------------------------------------- вибір полів

def pick_salary(rng: random.Random, seniority: str) -> tuple[int, int | None]:
    low, high = {"junior": (1300, 1900), "medior": (2000, 3000),
                 "senior": (3000, 4500), "lead": (4000, 6000)}[seniority]
    lo = rng.randrange(low, high, 100)
    if rng.random() < 0.3:
        return lo, None  # «od X EUR»
    return lo, lo + rng.randrange(300, 1600, 100)


def make_job(rng: random.Random, site: str, job_id: str) -> Job:
    cfg = SITES[site]
    lang = "en" if rng.random() < cfg.en_share else "sk"
    spec = rng.choice(list(v.SPECIALIZATIONS))
    seniority = rng.choices(["junior", "medior", "senior", "lead"], weights=[25, 30, 30, 15])[0]
    company = rng.choice(v.COMPANIES)

    # Місце роботи: місто (onsite/hybrid) або повністю remote.
    city = rng.choices(["Bratislava", "Košice", "Žilina", None], weights=[45, 20, 15, 20])[0]
    if city is None:
        location, remote, workplace = None, True, "Remote"
        location_display = rng.choice(v.REMOTE_DISPLAY[lang])
    else:
        hybrid = rng.random() < 0.35
        location, remote, workplace = city, hybrid, ("Hybrid" if hybrid else "On-site")
        location_display = rng.choice(v.CITY_DISPLAY[city])

    employment = rng.choices(["full_time", "part_time", "contract"], weights=[75, 10, 15])[0]

    # Технології та навички.
    pool_spec = v.SPECIALIZATIONS[spec]
    core = list(pool_spec["core"]) or [rng.choice(v.QA_CORE_CHOICES)]
    pool = [t for t in pool_spec["pool"] if t not in core]
    rng.shuffle(pool)
    n_req = rng.randint(2, 4)
    required_tech = core + pool[:n_req]
    nice_tech = pool[n_req:n_req + rng.randint(0, 3)]
    soft_names = list(v.SOFT_SKILLS)
    if lang == "sk":
        soft_names.remove("Slovak")  # у словацькій вакансії словацьку не вимагають явно
    soft = rng.sample(soft_names, rng.randint(1, 2))

    salary_min = salary_max = None
    salary_currency = None
    salary_display = None
    salary_in_text = False
    if rng.random() < cfg.salary_share:
        salary_min, salary_max = pick_salary(rng, seniority)
        salary_currency = "EUR"
        salary_display = format_salary(salary_min, salary_max, lang)
        salary_in_text = rng.random() < 0.2  # зарплата лише в тексті, не в окремому полі

    title = make_title(rng, spec, seniority, lang, remote)

    duties = rng.sample(v.DUTIES[spec][lang], 3)
    if seniority == "lead":
        duties.insert(0, v.LEAD_DUTY[lang])

    benefits = rng.sample(v.BENEFITS[lang], rng.randint(3, 5))
    if lang == "en" and rng.random() < 0.2:
        benefits += rng.sample(v.BENEFITS["sk"], 2)  # змішані мови

    intro = rng.choice(v.INTRO_TEMPLATES[lang]).format(
        c=company, k=rng.choice(v.COMPANY_KINDS[lang]), p=rng.choice(v.PRODUCTS[lang]))

    job = Job(
        title=title, company=company, location=location, remote=remote,
        employment_type=employment, seniority=seniority, specialization=spec,
        required_skills=required_tech + soft, nice_to_have_skills=nice_tech,
        technologies=required_tech + nice_tech,
        salary_min=salary_min, salary_max=salary_max, salary_currency=salary_currency,
        language=lang, source_url=base_url(site) + detail_path(site, job_id),
        id=job_id, site=site, location_display=location_display, workplace=workplace,
        employment_display=rng.choice(v.EMPLOYMENT_DISPLAY[employment][lang]),
        show_employment=site == "profesia" or rng.random() < 0.8,
        salary_display=salary_display, salary_in_text=salary_in_text,
        posted=BASE_DATE - timedelta(days=rng.randint(0, 30)),
        intro=intro, duties=duties,
        requirements=make_requirements(rng, lang, seniority, required_tech, nice_tech, soft),
        benefits=benefits,
        education=rng.choice(["vysokoškolské I. stupňa", "vysokoškolské II. stupňa",
                              "stredoškolské s maturitou"]),
        linkedin_level=v.LINKEDIN_LEVEL[seniority],
        show_criteria=rng.random() < 0.7,
    )

    # Факти, які видно лише в тексті опису.
    if salary_in_text and salary_display:
        job.extra_lines.append(f"Mzda: {salary_display}, podľa skúseností." if lang == "sk"
                               else f"Salary: {salary_display}, depending on experience.")
    if not job.show_employment:
        job.extra_lines.append(f"This is a {job.employment_display.lower()} position." if lang == "en"
                               else f"Ide o pracovný pomer: {job.employment_display}.")
    if workplace == "Hybrid":
        job.extra_lines.append("Možnosť home office 2 dni v týždni." if lang == "sk"
                               else "Hybrid setup: 2 days per week from home.")
    if lang == "sk" and rng.random() < 0.25:
        job.extra_lines.append("We are an international team – pohovor môže prebehnúť aj v angličtine.")
    return job


def make_jobs(rng: random.Random, site: str, n: int) -> list[Job]:
    ids: set[str] = set()
    jobs: list[Job] = []
    while len(jobs) < n:
        job_id = str(rng.randint(4_500_000, 4_999_999) if site == "profesia"
                     else rng.randint(3_900_000_000, 4_099_999_999))
        if job_id in ids:
            continue
        ids.add(job_id)
        jobs.append(make_job(rng, site, job_id))
    for job in jobs:
        job.similar = rng.sample([j for j in jobs if j is not job], 3)
    return jobs


# ---------------------------------------------------------------- запис сайтів

def days_ago(d: date) -> str:
    n = (BASE_DATE - d).days
    return "today" if n == 0 else ("1 day ago" if n == 1 else f"{n} days ago")


def write_site(site: str, jobs: list[Job], out_dir: Path) -> None:
    env = Environment(loader=FileSystemLoader(MOCK_ROOT / site / "templates"), autoescape=True)
    env.globals.update(list_path=lambda p: list_path(site, p),
                       detail_path=lambda j: detail_path(site, j.id),
                       days_ago=days_ago)
    if out_dir.exists():
        shutil.rmtree(out_dir)

    pages = [jobs[i:i + PER_PAGE] for i in range(0, len(jobs), PER_PAGE)]
    for n, page_jobs in enumerate(pages, start=1):
        html = env.get_template("list.html").render(jobs=page_jobs, page=n, total_pages=len(pages),
                                                    total_jobs=len(jobs))
        write_file(out_dir / list_path(site, n).lstrip("/"), html)
    for job in jobs:
        html = job.raw_html or env.get_template("detail.html").render(job=job)
        write_file(out_dir / detail_path(site, job.id).lstrip("/"), html)
    if site == "linkedin":
        # Корінь сайту перенаправляє на пошук, як на справжньому сайті.
        write_file(out_dir / "index.html",
                   '<!DOCTYPE html><meta charset="utf-8">'
                   '<meta http-equiv="refresh" content="0; url=/jobs/search/index.html">')


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate(seed: int = 42, n_per_site: int = 45, sites_root: Path = MOCK_ROOT,
             gt_path: Path = GROUND_TRUTH_PATH, edge_cases: bool = True) -> list[dict[str, Any]]:
    from mock_sites.edge_cases import make_edge_cases  # тут, щоб уникнути циклічного імпорту

    rng = random.Random(seed)
    ground_truth: list[dict[str, Any]] = []
    for site in SITES:
        jobs = make_jobs(rng, site, n_per_site)
        if edge_cases:
            # Дописуються в кінець і не чіпають rng: основні вакансії лишаються тими самими.
            edge = make_edge_cases(site)
            for i, job in enumerate(edge):
                job.similar = jobs[i:i + 3]
            jobs += edge
        write_site(site, jobs, sites_root / site / "site")
        ground_truth += [j.ground_truth() for j in jobs]
    gt_path.parent.mkdir(parents=True, exist_ok=True)
    gt_path.write_text(json.dumps(ground_truth, ensure_ascii=False, indent=2), encoding="utf-8")
    return ground_truth


def main() -> None:
    ap = argparse.ArgumentParser(description="Генерує мок-сайти та ground truth.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("-n", type=int, default=45, help="вакансій на кожен сайт")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # консоль Windows у cp1251
    gt = generate(seed=args.seed, n_per_site=args.n)
    for site in SITES:
        print(f"{site}: {sum(1 for r in gt if r['site'] == site)} вакансій -> mock_sites/{site}/site/")
    print(f"ground truth: {GROUND_TRUTH_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
