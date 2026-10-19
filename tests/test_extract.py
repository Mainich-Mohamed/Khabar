import threading
from concurrent.futures import ThreadPoolExecutor

import httpx

from app import extract
from app.extract import LEAD_CHARS, _fetch_one, _lead_from_html, extract_leads

PARA = ("The central bank raised its benchmark interest rate by half a point on Tuesday, "
        "citing persistent inflation in food and energy prices across the region.")

ARTICLE_HTML = f"""<html><head><title>Rates</title></head><body>
<nav>Home | World | Business | Sport</nav>
<article>
  <h1>Central bank raises rates</h1>
  <p>{PARA}</p>
  <p>{PARA.replace("Tuesday", "Wednesday")}</p>
  <p>{PARA.replace("Tuesday", "Thursday")}</p>
</article>
<footer>Copyright 2026. All rights reserved.</footer>
</body></html>"""


# --------------------------------------------------------------------------- _lead_from_html
def test_lead_from_html_extracts_article_text():
    lead = _lead_from_html(ARTICLE_HTML)
    assert lead and "benchmark interest rate" in lead
    assert "All rights reserved" not in lead


def test_lead_from_html_respects_budget():
    long_html = "<html><body><article>" + "".join(
        f"<p>{PARA} Paragraph number {i}.</p>" for i in range(30)) + "</article></body></html>"
    lead = _lead_from_html(long_html)
    assert lead
    # stops adding paragraphs once the budget is reached (one paragraph may be added in full)
    assert len(lead) <= LEAD_CHARS + 200


def test_lead_from_html_nothing_to_extract():
    assert _lead_from_html("<html><body></body></html>") is None


def test_lead_from_html_parses_one_page_at_a_time(monkeypatch):
    inside, peak, guard = 0, 0, threading.Lock()

    def fake_extract(html, **kw):
        nonlocal inside, peak
        with guard:
            inside += 1
            peak = max(peak, inside)
        threading.Event().wait(0.01)   # long enough for the other threads to try to enter (conftest turns time.sleep into a no-op)
        with guard:
            inside -= 1
        return PARA

    monkeypatch.setattr(extract.trafilatura, "extract", fake_extract)
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(_lead_from_html, ["<html></html>"] * 16))
    assert peak == 1


# --------------------------------------------------------------------------- _fetch_one
def test_fetch_one_skips_google_news(mock_client):
    def handler(req):
        raise AssertionError("must not fetch")

    a = {"id": 1, "url": "https://news.google.com/rss/articles/abc"}
    assert _fetch_one(mock_client(handler), a) == (1, None, "skipped")


def test_fetch_one_ok(mock_client):
    client = mock_client(lambda req: httpx.Response(
        200, text=ARTICLE_HTML, headers={"content-type": "text/html; charset=utf-8"}))
    id_, lead, status = _fetch_one(client, {"id": 7, "url": "https://site.test/a"})
    assert (id_, status) == (7, "ok")
    assert "benchmark" in lead


def test_fetch_one_non_200(mock_client):
    client = mock_client(lambda req: httpx.Response(403, text="nope", headers={"content-type": "text/html"}))
    assert _fetch_one(client, {"id": 2, "url": "https://site.test/a"}) == (2, None, "failed")


def test_fetch_one_not_html(mock_client):
    client = mock_client(lambda req: httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"}))
    assert _fetch_one(client, {"id": 3, "url": "https://site.test/a.pdf"}) == (3, None, "failed")


def test_fetch_one_network_error_is_failed_not_raised(mock_client):
    def handler(req):
        raise httpx.ConnectError("down")

    assert _fetch_one(mock_client(handler), {"id": 4, "url": "https://site.test/a"}) == (4, None, "failed")


# --------------------------------------------------------------------------- extract_leads
def test_extract_leads_only_fetches_new_and_syncs_rows(monkeypatch):
    articles = [
        {"id": 1, "url": "https://a", "lead": "cached", "lead_status": "ok"},
        {"id": 2, "url": "https://b", "lead": None, "lead_status": None},
        {"id": 3, "url": "https://c", "lead": None, "lead_status": None},
    ]
    fetched = []

    def fake_fetch_one(client, a):
        fetched.append(a["id"])
        return (a["id"], "new lead", "ok") if a["id"] == 2 else (a["id"], None, "failed")

    monkeypatch.setattr(extract, "_fetch_one", fake_fetch_one)
    saved = []
    extract_leads("conn", articles, lambda conn, i, lead, status: saved.append((conn, i, lead, status)))

    assert sorted(fetched) == [2, 3]
    assert sorted(saved) == [("conn", 2, "new lead", "ok"), ("conn", 3, None, "failed")]
    assert articles[1]["lead"] == "new lead" and articles[1]["lead_status"] == "ok"
    assert articles[2]["lead_status"] == "failed"
    assert articles[0]["lead"] == "cached"


def test_extract_leads_nothing_to_do(monkeypatch):
    monkeypatch.setattr(extract, "make_client", lambda: (_ for _ in ()).throw(AssertionError("no client")))
    extract_leads(None, [{"id": 1, "lead_status": "failed"}], lambda *a: None)
