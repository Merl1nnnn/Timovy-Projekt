"""Скрапер РЕАЛЬНОЇ Profesia.sk (категорія «Informačné technológie»).

На відміну від мок-скрапера:
- звичайний HTTP (httpx) замість Playwright: Profesia рендерить сторінки на сервері;
- «ввічливий» режим: затримка між запитами, чесний User-Agent, перевірка robots.txt,
  зупинка на 403/429, обмеження кількості нових вакансій за запуск;
- інкрементальність: уже завантажені вакансії не завантажуються повторно;
- зберігається лише блок <main id="detail"> без розділу «Kontakt» (контактна особа, телефон),
  а email і телефони в решті тексту замінюються заглушками — менше персональних даних на диску.

Дані лежать окремо від мок-даних: data/real/raw/profesia/ (index.json у тому ж форматі).
Запуск:
    uv run python -m scraper.profesia_live --limit 20
"""

import argparse
import html as htmllib
import json
import random
import re
import sys
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
REAL_RAW_DIR = ROOT / "data" / "real" / "raw"

BASE_URL = "https://www.profesia.sk"
START_PATH = "/praca/informacne-technologie/"
SITE = "profesia"
USER_AGENT = "SkillMiner/0.1 (TUKE student team project; +https://github.com/Merl1nnnn/Timovy-Projekt)"

# Посилання на деталі в рядку списку: <li class="list-row"><h2><a id="offer123" href="/praca/firma/O123?search_id=...">
_DETAIL_LINK = re.compile(r'<a\s[^>]*id="offer\d+"[^>]*href="([^"]+)"')
_NEXT_LINK = re.compile(r'<a\s[^>]*href="([^"]+)"[^>]*class="next"')
_JOB_ID = re.compile(r"/O(\d+)(?:[/?#]|$)")
_MAIN = re.compile(r'<main\b[^>]*\bid="detail"[^>]*>.*?</main>', re.S)
# Розділ контактів і все після нього (кнопки «поділитися», службові мітки) — до кінця <main>.
_CONTACT = re.compile(r"<h4>\s*(?:Kontakt|Contact|Kapcsolat)\s*</h4>.*(?=</main>)", re.S)
# Брендовані шаблони компаній мають власну розмітку: ім'я йде одразу після мітки (можливо, через теги).
_CONTACT_NAME = re.compile(r"((?:Kontaktná osoba|Contact person|Kapcsolattartó)\s*:?)((?:\s*<[^>]+>)*)\s*([^<]{2,80})")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<![\w/])(?:\+|00)\d[\d ()/-]{7,}\d")


class Blocked(RuntimeError):
    """Сайт відповів 403/429 — далі не продовжуємо, щоб не створювати навантаження."""


def detail_links(list_html: str) -> list[str]:
    """Абсолютні URL деталей без трекінгових параметрів (?search_id=...), у порядку появи."""
    out: list[str] = []
    for href in _DETAIL_LINK.findall(list_html):
        path = htmllib.unescape(href).split("?", 1)[0]
        url = BASE_URL + path if path.startswith("/") else path
        if url not in out:
            out.append(url)
    return out


def next_page(list_html: str) -> str | None:
    m = _NEXT_LINK.search(list_html)
    if not m:
        return None
    href = htmllib.unescape(m.group(1))
    return BASE_URL + href if href.startswith("/") else href


def job_id(url: str) -> str:
    m = _JOB_ID.search(url)
    if not m:
        raise ValueError(f"не вдалося визначити ID вакансії з {url}")
    return m.group(1)


def redact(text: str) -> str:
    return _PHONE.sub("[phone removed]", _EMAIL.sub("[email removed]", text))


def extract_detail(page_html: str) -> str | None:
    """Мінімальний HTML для парсера: лише <main id="detail"> без контактів. None — невідомий шаблон."""
    m = _MAIN.search(page_html)
    if not m:
        return None
    main = _CONTACT_NAME.sub(r"\1\2[name removed]", _CONTACT.sub("", m.group(0)))
    main = redact(main)
    return f'<!doctype html>\n<html><head><meta charset="utf-8"></head><body>\n{main}\n</body></html>\n'


class PoliteClient:
    """HTTP-клієнт із затримкою між запитами та перевіркою robots.txt."""

    def __init__(self, delay: float = 3.0, http: httpx.Client | None = None, check_robots: bool = True) -> None:
        self.delay = delay
        self.http = http or httpx.Client(headers={"User-Agent": USER_AGENT, "Accept-Language": "sk,en;q=0.8"},
                                         timeout=30, follow_redirects=True)
        self._last = 0.0
        self.robots: urllib.robotparser.RobotFileParser | None = None
        if check_robots:
            self.robots = urllib.robotparser.RobotFileParser()
            self.robots.parse(self._fetch(BASE_URL + "/robots.txt").splitlines())

    def _fetch(self, url: str) -> str:
        wait = self.delay * random.uniform(1.0, 1.5) - (time.monotonic() - self._last)
        if wait > 0 and self._last:
            time.sleep(wait)
        self._last = time.monotonic()
        resp = self.http.get(url)
        if resp.status_code in (403, 429):
            raise Blocked(f"HTTP {resp.status_code} для {url}: сайт обмежив доступ, зупиняємось")
        resp.raise_for_status()
        return resp.text

    def get(self, url: str) -> str:
        if self.robots and not self.robots.can_fetch(USER_AGENT, url):
            raise PermissionError(f"robots.txt забороняє {url}")
        return self._fetch(url)


def _load_index(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _save_index(path: Path, index: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def scrape(client: PoliteClient, raw_dir: Path = REAL_RAW_DIR, limit: int = 20, max_pages: int = 5,
           log: Any = print) -> list[dict[str, Any]]:
    """Завантажує до `limit` НОВИХ вакансій. Повертає лише нові записи індексу.

    Індекс зберігається після кожної вакансії: перерваний запуск не втрачає вже завантажене.
    """
    out_dir = raw_dir / SITE
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "index.json"
    index = _load_index(index_path)
    skipped = _load_index(out_dir / "skipped.json")
    known = {e["url"] for e in index} | {e["url"] for e in skipped}
    added: list[dict[str, Any]] = []

    url: str | None = BASE_URL + START_PATH
    pages = 0
    while url and pages < max_pages and len(added) < limit:
        pages += 1
        list_html = client.get(url)
        links = [u for u in detail_links(list_html) if u not in known]
        log(f"сторінка списку {pages}: нових посилань {len(links)}")
        for detail_url in links:
            if len(added) >= limit:
                break
            known.add(detail_url)
            content = extract_detail(client.get(detail_url))
            if content is None:  # нестандартний шаблон — запам'ятовуємо, щоб не качати знову
                skipped.append({"url": detail_url, "reason": "no <main id=detail>"})
                _save_index(out_dir / "skipped.json", skipped)
                log(f"  пропущено (невідомий шаблон): {detail_url}")
                continue
            jid = job_id(detail_url)
            (out_dir / f"{jid}.html").write_text(content, encoding="utf-8")
            entry = {"site": SITE, "id": jid, "url": detail_url, "file": f"{SITE}/{jid}.html",
                     "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            index.append(entry)
            added.append(entry)
            _save_index(index_path, index)
            log(f"  [{len(added)}/{limit}] {detail_url}")
        url = next_page(list_html)
    return added


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description="Завантажує IT-вакансії з реальної Profesia.sk у data/real/raw/.")
    ap.add_argument("--limit", type=int, default=20, help="максимум НОВИХ вакансій за запуск (default 20)")
    ap.add_argument("--max-pages", type=int, default=5, help="максимум сторінок списку (по 20 вакансій)")
    ap.add_argument("--delay", type=float, default=3.0, help="мінімальна пауза між запитами, с (не менше 1)")
    args = ap.parse_args()
    if args.delay < 1:
        raise SystemExit("--delay має бути не менше 1 секунди")
    try:
        added = scrape(PoliteClient(delay=args.delay), limit=args.limit, max_pages=args.max_pages)
    except (Blocked, PermissionError, httpx.HTTPError) as e:
        raise SystemExit(f"Зупинено: {e}. Уже завантажене збережено в data/real/raw/.")
    print(f"Нових вакансій: {len(added)} -> data/real/raw/{SITE}/")


if __name__ == "__main__":
    main()
