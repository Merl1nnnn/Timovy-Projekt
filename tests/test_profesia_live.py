"""Tests for the real Profesia scraper on synthetic HTML (same structure as the site, no network)."""

import json
from pathlib import Path

import httpx
import pytest

from parser.html_text import html_to_text
from scraper import profesia_live as pl

ROW = ('<li class="list-row"><h2><a  id="offer{id}" href="&#x2F;praca&#x2F;firma-{id}&#x2F;O{id}&#x3F;'
       'search_id&#x3D;abc"><span class=\'title\'>Python developer {id}</span></a></h2>'
       '<a href="/praca/firma-{id}/O{id}?search_id=abc" class="half-margin-on-right">2 000 EUR</a></li>')


def list_page(ids: list[int], next_num: int | None) -> str:
    nxt = (f'<ul class="pagination"><li><a href="&#x2F;praca&#x2F;informacne-technologie&#x2F;&#x3F;page_num'
           f'&#x3D;{next_num}" class="next">Ďalšia</a></li></ul>') if next_num else ""
    return f"<html><body><ul>{''.join(ROW.format(id=i) for i in ids)}</ul>{nxt}</body></html>"


def detail_page(job: int) -> str:
    return f"""<html><head><title>x</title></head><body><header>menu</header>
<main id="detail" class="col-sm-8" itemscope itemtype="http://schema.org/JobPosting">
<h1>Python developer {job}</h1><span>Firma {job} s.r.o.</span>
<h4>Požiadavky na zamestnanca</h4><div class='details-desc'>Python, Django. CV posielajte na hr.osoba@firma.sk
alebo volajte +421 911 525 022.</div>
<h4>Počet zamestnancov</h4><div class='details-desc'>50-99 zamestnancov</div>
<h4>Kontakt</h4><div class='details-desc'>Kontaktná osoba: Ing. Jana Nováková<br />Tel.: 02/123 456</div>
<ul><li>Facebook</li></ul>ID: {job}
</main><footer>päta</footer></body></html>"""


def test_detail_links_strip_tracking_and_dedupe() -> None:
    html = list_page([5381471, 5387487], next_num=2)
    assert pl.detail_links(html) == ["https://www.profesia.sk/praca/firma-5381471/O5381471",
                                     "https://www.profesia.sk/praca/firma-5387487/O5387487"]
    assert pl.next_page(html) == "https://www.profesia.sk/praca/informacne-technologie/?page_num=2"
    assert pl.next_page(list_page([1], None)) is None
    assert pl.job_id("https://www.profesia.sk/praca/firma/O5381471") == "5381471"


def test_extract_detail_removes_contacts_and_personal_data() -> None:
    content = pl.extract_detail(detail_page(7))
    assert content is not None
    text = html_to_text(content)
    assert "Python developer 7" in text and "Python, Django" in text
    assert "Nováková" not in text and "Kontakt" not in text  # contact section removed
    assert "hr.osoba@firma.sk" not in text and "911 525 022" not in text
    assert "[email removed]" in text and "[phone removed]" in text
    assert "menu" not in text and "päta" not in text  # only <main>
    assert pl.extract_detail("<html><body><div>інший шаблон</div></body></html>") is None


@pytest.mark.parametrize("salary", ["2 000 - 2 500 EUR/mesiac", "5 000 - 6 000 €", "Od 1 000 EUR", "12 000 000 EUR"])
def test_salary_is_not_taken_for_phone(salary: str) -> None:
    assert pl.redact(f"Mzda: {salary}") == f"Mzda: {salary}"
    assert pl.redact(f"{salary}, tel. 00421 905 123 456") == f"{salary}, tel. [phone removed]"


def test_branded_template_contact_name_removed() -> None:
    page = ('<main id="detail"><h1>Web developer</h1><div class="row"><div class="col-md-2">'
            '<p class="mb-0">Kontaktná osoba</p></div>\n<div class="col-md-6">\n  <p class=mb-0">Jana Nováková</p>'
            '</div></div></main>')
    text = html_to_text(pl.extract_detail(page) or "")
    assert "Nováková" not in text and "[name removed]" in text and "Web developer" in text


class FakeSite:
    """Two list pages with 3 postings each; one posting uses a non-standard template."""

    def __init__(self, status: int = 200) -> None:
        self.requests: list[str] = []
        self.status = status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url)
        if self.status != 200 and "/O" in url:
            return httpx.Response(self.status)
        if url.endswith("/praca/informacne-technologie/"):
            return httpx.Response(200, text=list_page([1, 2, 3], next_num=2))
        if url.endswith("page_num=2"):
            return httpx.Response(200, text=list_page([4, 5, 6], next_num=None))
        job = int(url.rsplit("/O", 1)[1])
        body = "<html><body>custom</body></html>" if job == 2 else detail_page(job)
        return httpx.Response(200, text=body)


def client(site: FakeSite) -> pl.PoliteClient:
    return pl.PoliteClient(delay=0, http=httpx.Client(transport=httpx.MockTransport(site)), check_robots=False)


def test_scrape_is_limited_and_incremental(tmp_path: Path) -> None:
    site = FakeSite()
    added = pl.scrape(client(site), raw_dir=tmp_path, limit=3, log=lambda *_: None)
    assert [e["id"] for e in added] == ["1", "3", "4"]  # 2 has an unknown template and is skipped
    index = json.loads((tmp_path / "profesia" / "index.json").read_text(encoding="utf-8"))
    assert index == added
    assert (tmp_path / "profesia" / "1.html").exists()

    site2 = FakeSite()  # second run: old postings (and the skipped one) are not downloaded again
    added2 = pl.scrape(client(site2), raw_dir=tmp_path, limit=10, log=lambda *_: None)
    assert [e["id"] for e in added2] == ["5", "6"]
    assert not any(u.endswith(("/O1", "/O2", "/O3", "/O4")) for u in site2.requests)
    assert len(json.loads((tmp_path / "profesia" / "index.json").read_text(encoding="utf-8"))) == 5


def test_refresh_overwrites_known_postings(tmp_path: Path) -> None:
    pl.scrape(client(FakeSite()), raw_dir=tmp_path, limit=2, log=lambda *_: None)
    (tmp_path / "profesia" / "1.html").write_text("stale", encoding="utf-8")
    site = FakeSite()
    assert pl.refresh(client(site), ["1"], raw_dir=tmp_path, log=lambda *_: None) == ["1"]
    assert "Python developer 1" in (tmp_path / "profesia" / "1.html").read_text(encoding="utf-8")
    assert site.requests == ["https://www.profesia.sk/praca/firma-1/O1"]  # no list pages, only the posting
    with pytest.raises(ValueError):
        pl.refresh(client(site), ["999"], raw_dir=tmp_path, log=lambda *_: None)


def test_refresh_keeps_file_of_expired_posting(tmp_path: Path) -> None:
    pl.scrape(client(FakeSite()), raw_dir=tmp_path, limit=1, log=lambda *_: None)
    gone = pl.PoliteClient(delay=0, check_robots=False,
                           http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))))
    assert pl.refresh(gone, ["1"], raw_dir=tmp_path, log=lambda *_: None) == []
    assert "Python developer 1" in (tmp_path / "profesia" / "1.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("status", [403, 429])
def test_scrape_stops_when_blocked(tmp_path: Path, status: int) -> None:
    with pytest.raises(pl.Blocked):
        pl.scrape(client(FakeSite(status)), raw_dir=tmp_path, limit=5, log=lambda *_: None)


def test_robots_txt_is_respected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="User-agent: *\nDisallow: /praca/\n")

    c = pl.PoliteClient(delay=0, http=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(PermissionError):
        c.get("https://www.profesia.sk/praca/informacne-technologie/")
