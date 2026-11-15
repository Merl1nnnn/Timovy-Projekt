"""Common site adapter interface for the scraper."""

from typing import Protocol

from playwright.sync_api import Page


class SiteAdapter(Protocol):
    name: str
    base_url: str

    @property
    def start_url(self) -> str:
        """First page of the job list."""
        ...

    def detail_links(self, page: Page) -> list[str]:
        """Absolute detail-page URLs on the current list page."""
        ...

    def next_page(self, page: Page) -> str | None:
        """URL of the next list page, or None if this is the last one."""
        ...

    def job_id(self, url: str) -> str:
        """Job ID from the detail URL (the file name in data/raw)."""
        ...


def links(page: Page, selector: str) -> list[str]:
    """Absolute hrefs of all elements matching the selector (the browser resolves relative paths)."""
    return page.eval_on_selector_all(selector, "els => els.map(e => e.href)")
