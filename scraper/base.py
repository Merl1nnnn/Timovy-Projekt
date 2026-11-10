"""Спільний інтерфейс адаптера сайту для скрапера."""

from typing import Protocol

from playwright.sync_api import Page


class SiteAdapter(Protocol):
    name: str
    base_url: str

    @property
    def start_url(self) -> str:
        """Перша сторінка списку вакансій."""
        ...

    def detail_links(self, page: Page) -> list[str]:
        """Абсолютні URL сторінок деталей на поточній сторінці списку."""
        ...

    def next_page(self, page: Page) -> str | None:
        """URL наступної сторінки списку або None, якщо це остання."""
        ...

    def job_id(self, url: str) -> str:
        """Ідентифікатор вакансії з URL деталей (ім'я файлу в data/raw)."""
        ...


def links(page: Page, selector: str) -> list[str]:
    """Абсолютні href усіх елементів за селектором (браузер сам розв'язує відносні шляхи)."""
    return page.eval_on_selector_all(selector, "els => els.map(e => e.href)")
