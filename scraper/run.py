"""Playwright-скрапер мок-сайтів: обхід списку й пагінації, збереження raw HTML деталей.

Результат: data/raw/<site>/<id>.html і data/raw/<site>/index.json (url -> файл).
Запуск (сайти мають бути запущені через mock_sites.serve):
    uv run python -m scraper.run [--site profesia|linkedin]
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

from scraper.base import SiteAdapter
from scraper.linkedin import LinkedInAdapter
from scraper.profesia import ProfesiaAdapter

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
MAX_LIST_PAGES = 50  # запобіжник від нескінченної пагінації


def goto(page: Page, url: str, retries: int = 2) -> None:
    for attempt in range(retries + 1):
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=15_000)
            if resp is None or not resp.ok:
                raise RuntimeError(f"HTTP {resp.status if resp else '?'} для {url}")
            return
        except Exception:
            if attempt == retries:
                raise


def collect_detail_urls(page: Page, adapter: SiteAdapter) -> list[str]:
    urls: list[str] = []
    seen_pages: set[str] = set()
    url: str | None = adapter.start_url
    while url and url not in seen_pages and len(seen_pages) < MAX_LIST_PAGES:
        seen_pages.add(url)
        goto(page, url)
        for link in adapter.detail_links(page):
            if link not in urls:
                urls.append(link)
        url = adapter.next_page(page)
    return urls


def scrape_site(browser: Browser, adapter: SiteAdapter, raw_dir: Path = RAW_DIR) -> list[dict[str, Any]]:
    # Пишемо в тимчасову теку й підміняємо лише після успіху,
    # щоб невдалий запуск не стер попередні дані.
    out_dir = raw_dir / adapter.name
    tmp_dir = raw_dir / f"{adapter.name}.tmp"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)

    page = browser.new_page()
    index: list[dict[str, Any]] = []
    try:
        for url in collect_detail_urls(page, adapter):
            goto(page, url)
            job_id = adapter.job_id(url)
            (tmp_dir / f"{job_id}.html").write_text(page.content(), encoding="utf-8")
            index.append({
                "site": adapter.name,
                "id": job_id,
                "url": url,
                "file": f"{adapter.name}/{job_id}.html",  # відносно data/raw
                "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
        (tmp_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    except BaseException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    finally:
        page.close()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    tmp_dir.rename(out_dir)
    return index


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description="Скрапить мок-сайти вакансій у data/raw/.")
    ap.add_argument("--site", choices=["profesia", "linkedin"], help="лише один сайт")
    args = ap.parse_args()

    adapters: list[SiteAdapter] = [ProfesiaAdapter(), LinkedInAdapter()]
    if args.site:
        adapters = [a for a in adapters if a.name == args.site]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for adapter in adapters:
                try:
                    index = scrape_site(browser, adapter)
                except Exception as e:
                    raise SystemExit(f"{adapter.name}: помилка ({e}). Чи запущено mock_sites.serve?")
                print(f"{adapter.name}: збережено {len(index)} вакансій -> data/raw/{adapter.name}/")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
