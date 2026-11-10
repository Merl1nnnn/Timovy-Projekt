"""HTML -> чистий текст для LLM (stdlib html.parser, без BeautifulSoup).

Викидаємо службові частини сторінки (head, script, style, nav, header, footer),
блокові теги перетворюємо на переноси рядків, пункти списку — на "- ".
"""

import re
from html.parser import HTMLParser

SKIP_TAGS = {"head", "script", "style", "noscript", "nav", "header", "footer", "svg", "button", "input"}
BLOCK_TAGS = {"p", "div", "section", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "main"}
VOID_TAGS = {"br", "input", "img", "meta", "link", "hr"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS and tag not in VOID_TAGS:
            self.skip_depth += 1
        elif self.skip_depth == 0 and tag in BLOCK_TAGS:
            self.parts.append("\n- " if tag == "li" else "\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and tag not in VOID_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif self.skip_depth == 0 and tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth == 0:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts)
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.split("\n")]
    out: list[str] = []
    for line in lines:
        if line in ("", "-"):
            continue
        out.append(line)
    return "\n".join(out)
