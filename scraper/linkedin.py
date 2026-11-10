"""Адаптер для LinkedIn MOCK: ul.jobs-search__results-list, пагінація a.pagination-next."""

from dataclasses import dataclass

from playwright.sync_api import Page

from scraper.base import links


@dataclass
class LinkedInAdapter:
    base_url: str = "http://localhost:8002"
    name: str = "linkedin"

    @property
    def start_url(self) -> str:
        # Корінь сайту робить meta-refresh; ідемо одразу на пошук, щоб уникнути гонки.
        return f"{self.base_url}/jobs/search/index.html"

    def detail_links(self, page: Page) -> list[str]:
        return links(page, "ul.jobs-search__results-list div.base-card[data-job-id] a.base-card__full-link")

    def next_page(self, page: Page) -> str | None:
        found = links(page, "a.pagination-next")
        return found[0] if found else None

    def job_id(self, url: str) -> str:
        # .../jobs/view/3924272172.html -> 3924272172
        return url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".html")
