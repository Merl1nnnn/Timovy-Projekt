"""Адаптер для Profesia MOCK: картки div.list-row, пагінація ul.pagination a.next."""

from dataclasses import dataclass

from playwright.sync_api import Page

from scraper.base import links


@dataclass
class ProfesiaAdapter:
    base_url: str = "http://localhost:8001"
    name: str = "profesia"

    @property
    def start_url(self) -> str:
        return f"{self.base_url}/index.html"

    def detail_links(self, page: Page) -> list[str]:
        return links(page, "#results div.list-row a.title")

    def next_page(self, page: Page) -> str | None:
        found = links(page, "ul.pagination a.next")
        return found[0] if found else None

    def job_id(self, url: str) -> str:
        # .../offer/4508503.html -> 4508503
        return url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".html")
