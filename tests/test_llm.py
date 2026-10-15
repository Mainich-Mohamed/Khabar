import json

import httpx
import pytest

from app import llm
from app.llm import (GeminiClient, LLMError, QuotaExhausted, Summarizer, Usage, _retry_delay,
                     _to_gemini_schema, format_articles, format_previous, make_summarizer, parse_json_text,
                     parse_stories)


# --------------------------------------------------------------------------- format_articles
def test_format_articles_numbers_from_one_and_prefers_lead(article):
    arts = [article(10, source="BBC", lead="Lead text", summary="rss"),
            article(11, source="DW", summary="RSS snippet"),
            article(12, summary="")]
    out = format_articles(arts)
    assert "[1] Source: BBC" in out and "Text: Lead text" in out
    assert "[2] Source: DW" in out and "Text: RSS snippet" in out
    assert "[3]" in out and "(headline only)" in out
    assert "[0]" not in out


def test_format_articles_truncates_body(article):
    out = format_articles([article(1, lead="x" * 50)], lead_chars=10)
    assert out.endswith("Text: " + "x" * 10)


# --------------------------------------------------------------------------- parse_json_text
@pytest.mark.parametrize("text", [
    '{"stories": []}',
    '```json\n{"stories": []}\n```',
    '<think>let me {think}</think>\n{"stories": []}',
    'Sure! Here you go: {"stories": []} Hope it helps.',
])
def test_parse_json_text_tolerates_wrappers(text):
    assert parse_json_text(text) == {"stories": []}


@pytest.mark.parametrize("text", ["", None, "no json", "{broken", '{"a": }'])
def test_parse_json_text_errors(text):
    with pytest.raises(LLMError):
        parse_json_text(text)


# --------------------------------------------------------------------------- parse_stories
@pytest.fixture
def arts(article):
    return [article(101, source="BBC"), article(102, source="DW"), article(103, source="BBC")]


def test_parse_stories_maps_numbers_to_real_urls(arts):
    raw = [{"title": "T", "summary": "S", "article_ids": [1, 2, 3]}]
    [st] = parse_stories(raw, arts, 5)
    assert st.article_ids == [101, 102, 103]
    # one link per outlet: the second BBC article is not repeated
    assert st.sources == [{"name": "BBC", "url": "https://example.com/101"},
                          {"name": "DW", "url": "https://example.com/102"}]
    assert st.single_source is False


def test_parse_stories_single_source_flag(arts):
    [st] = parse_stories([{"title": "T", "summary": "S", "article_ids": [1, 3]}], arts, 5)
    assert st.single_source is True
    assert st.article_ids == [101, 103]


def test_parse_stories_drops_invalid_ids(arts):
    raw = [{"title": "T", "summary": "S", "article_ids": [0, 4, -1, True, 2.0, "x", " 2 ", 2, None]}]
    [st] = parse_stories(raw, arts, 5)
    assert st.article_ids == [102]          # "2" accepted once, everything else dropped


@pytest.mark.parametrize("raw", [
    {"title": "", "summary": "S", "article_ids": [1]},
    {"title": "T", "summary": "  ", "article_ids": [1]},
    {"title": "T", "summary": "S", "article_ids": []},
    {"title": "T", "summary": "S", "article_ids": [9]},   # hallucinated article number
    {"title": "T", "summary": "S"},
    "not a dict",
])
def test_parse_stories_drops_ungrounded(arts, raw):
    assert parse_stories([raw], arts, 5) == []


def test_parse_stories_non_list_input(arts):
    assert parse_stories(None, arts, 5) == []
    assert parse_stories({"title": "T"}, arts, 5) == []


def test_parse_stories_caps_and_keeps_order(arts):
    raw = [{"title": f"T{i}", "summary": "S", "article_ids": [1]} for i in range(5)]
    stories = parse_stories(raw, arts, 2)
    assert [s.title for s in stories] == ["T0", "T1"]


def test_parse_stories_strips_whitespace(arts):
    [st] = parse_stories([{"title": "  T ", "summary": " S\n", "article_ids": [1]}], arts, 5)
    assert (st.title, st.summary) == ("T", "S")
    assert st.to_dict()["title"] == "T"


# --------------------------------------------------------------------------- update detection
PREVIOUS = [{"title": "Ceasefire agreed", "summary": "Both sides agreed."},
            {"title": "Rates held", "summary": None}]


def test_format_previous_numbers_from_p1_and_skips_missing_summary():
    assert format_previous(PREVIOUS) == "P1. Ceasefire agreed | Both sides agreed.\nP2. Rates held"


def test_parse_stories_update_and_repeat_point_at_previous(arts):
    raw = [{"title": "Ceasefire broken", "summary": "S", "article_ids": [1], "status": "update", "previous": 1},
           {"title": "Rates still held", "summary": "S", "article_ids": [2], "status": "repeat", "previous": "2"}]
    up, rep = parse_stories(raw, arts, 5, PREVIOUS)
    assert (up.status, up.previous_title) == ("update", "Ceasefire agreed")
    assert (rep.status, rep.previous_title) == ("repeat", "Rates held")
    assert up.to_dict()["previous_title"] == "Ceasefire agreed"


@pytest.mark.parametrize("status,previous", [
    ("repeat", None), ("repeat", 0), ("repeat", 3), ("repeat", True), ("repeat", "x"),   # no real previous
    ("update", None), ("bogus", 1), ("", 1), ("new", 1),
])
def test_parse_stories_doubtful_cases_are_kept_as_new(arts, status, previous):
    raw = [{"title": "T", "summary": "S", "article_ids": [1], "status": status, "previous": previous}]
    [st] = parse_stories(raw, arts, 5, PREVIOUS)
    assert (st.status, st.previous_title) == ("new", None)


def test_parse_stories_without_history_everything_is_new(arts):
    raw = [{"title": "T", "summary": "S", "article_ids": [1], "status": "repeat", "previous": 1}]
    [st] = parse_stories(raw, arts, 5)
    assert st.status == "new"


def test_parse_stories_repeats_do_not_count_toward_cap(arts):
    raw = [{"title": f"R{i}", "summary": "S", "article_ids": [1], "status": "repeat", "previous": 1}
           for i in range(3)] + [{"title": "N", "summary": "S", "article_ids": [2], "status": "new"}]
    stories = parse_stories(raw, arts, 1, PREVIOUS)
    assert [s.title for s in stories] == ["R0", "R1", "R2", "N"]


# --------------------------------------------------------------------------- schema / retry helpers
def test_to_gemini_schema_uppercases_nested_types():
    out = _to_gemini_schema(llm.STORIES_SCHEMA)
    assert out["type"] == "OBJECT"
    story = out["properties"]["stories"]["items"]
    assert out["properties"]["stories"]["type"] == "ARRAY"
    assert story["properties"]["article_ids"]["items"]["type"] == "INTEGER"
    assert story["required"] == ["title", "summary", "article_ids", "status"]
    assert story["properties"]["status"] == {
        "type": "STRING", "enum": ["new", "update", "repeat"],
        "description": "new, update or repeat, compared with previously sent stories."}
    assert llm.STORIES_SCHEMA["type"] == "object"     # original left untouched


def test_retry_delay():
    body = {"error": {"details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure"},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"},
    ]}}
    assert _retry_delay(body) == 37.0
    assert _retry_delay({}) is None
    assert _retry_delay({"error": {"details": None}}) is None
    bad = {"error": {"details": [{"@type": "x.RetryInfo", "retryDelay": "soon"}]}}
    assert _retry_delay(bad) is None


# --------------------------------------------------------------------------- GeminiClient
def ok_response(payload: dict, finish="STOP", thought: str | None = None) -> httpx.Response:
    parts = [{"text": thought, "thought": True}] if thought else []
    parts.append({"text": json.dumps(payload)})
    return httpx.Response(200, json={
        "candidates": [{"content": {"parts": parts}, "finishReason": finish}],
        "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20, "thoughtsTokenCount": 5},
    })


def gemini(mock_client, handler) -> GeminiClient:
    return GeminiClient("secret", "gemini-test", client=mock_client(handler))


def test_gemini_requires_key():
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        GeminiClient("", "m")


def test_gemini_success_sends_expected_request(mock_client):
    seen = {}

    def handler(req):
        seen["url"], seen["key"], seen["body"] = str(req.url), req.headers["x-goog-api-key"], json.loads(req.content)
        return ok_response({"stories": []}, thought="internal reasoning {not json}")

    data, usage = gemini(mock_client, handler).generate("SYS", "PROMPT")
    assert data == {"stories": []}
    assert (usage.input_tokens, usage.output_tokens) == (100, 25)   # thinking tokens counted as output
    assert seen["url"].endswith("/models/gemini-test:generateContent")
    assert seen["key"] == "secret"
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "SYS"
    assert seen["body"]["contents"][0]["parts"][0]["text"] == "PROMPT"
    assert seen["body"]["generationConfig"]["responseSchema"]["type"] == "OBJECT"


def test_gemini_daily_quota_raises_immediately(mock_client):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(429, json={"error": {"message": "Quota exceeded: GenerateRequestsPerDay"}})

    with pytest.raises(QuotaExhausted):
        gemini(mock_client, handler).generate("s", "p")
    assert len(calls) == 1


def test_gemini_per_minute_limit_retries(mock_client):
    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": {"message": "per minute",
                                                       "details": [{"@type": "x.RetryInfo", "retryDelay": "3s"}]}})
        return ok_response({"stories": []})

    data, _ = gemini(mock_client, handler).generate("s", "p")
    assert data == {"stories": []} and len(calls) == 2


def test_gemini_per_minute_limit_gives_up_after_3(mock_client):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(429, json={"error": {"message": "slow down"}})

    with pytest.raises(LLMError, match="429") as exc:
        gemini(mock_client, handler).generate("s", "p")
    assert not isinstance(exc.value, QuotaExhausted)
    assert len(calls) == 3


def test_gemini_server_error_retries(mock_client):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(503, text="unavailable") if len(calls) < 3 else ok_response({"stories": []})

    gemini(mock_client, handler).generate("s", "p")
    assert len(calls) == 3


def test_gemini_transport_error_retries_then_fails(mock_client):
    def handler(req):
        raise httpx.ConnectError("offline")

    with pytest.raises(LLMError, match="unreachable"):
        gemini(mock_client, handler).generate("s", "p")


@pytest.mark.parametrize("status, body, hint", [
    (404, {"error": {"message": "models/x is not found"}}, "check GEMINI_MODEL"),
    (400, {"error": {"message": "API key not valid"}}, "check GEMINI_API_KEY"),
    (403, {"error": {"message": "permission denied"}}, "check GEMINI_API_KEY"),
])
def test_gemini_config_errors_have_hints(mock_client, status, body, hint):
    with pytest.raises(LLMError, match=hint):
        gemini(mock_client, lambda req: httpx.Response(status, json=body)).generate("s", "p")


def test_gemini_non_json_error_body(mock_client):
    with pytest.raises(LLMError, match="HTTP 400: plain text"):
        gemini(mock_client, lambda req: httpx.Response(400, text="plain text")).generate("s", "p")


def test_gemini_max_tokens(mock_client):
    with pytest.raises(LLMError, match="MAX_TOKENS"):
        gemini(mock_client, lambda req: ok_response({"stories": []}, finish="MAX_TOKENS")).generate("s", "p")


def test_gemini_blocked_prompt(mock_client):
    resp = httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(LLMError, match="SAFETY"):
        gemini(mock_client, lambda req: resp).generate("s", "p")


def test_gemini_no_candidates(mock_client):
    with pytest.raises(LLMError, match="no candidates"):
        gemini(mock_client, lambda req: httpx.Response(200, json={"candidates": []})).generate("s", "p")


# --------------------------------------------------------------------------- Summarizer
class FakeClient:
    model = "fake-model"

    def __init__(self, data):
        self.data, self.calls = data, []

    def generate(self, system, prompt):
        self.calls.append((system, prompt))
        if isinstance(self.data, Exception):
            raise self.data
        return self.data, Usage(10, 5)


def summarizer(client, **kw) -> Summarizer:
    opts = dict(language="French", max_stories=3, max_input=2, lead_chars=900, interval=0)
    opts.update(kw)
    return Summarizer(client, **opts)


def test_summarizer_builds_prompt_and_stories(article):
    client = FakeClient({"stories": [{"title": "T", "summary": "S", "article_ids": [1, 2]}]})
    arts = [article(1), article(2), article(3)]
    stories, usage = summarizer(client).summarize("Geopolitics", arts)

    system, prompt = client.calls[0]
    assert "in French" in system
    assert "Category: Geopolitics" in prompt and "at most 3 stories" in prompt
    assert "[2]" in prompt and "[3]" not in prompt          # capped at max_input
    assert stories[0].article_ids == [1, 2]
    assert (usage.input_tokens, usage.output_tokens) == (10, 5)


def test_summarizer_no_valid_stories_raises(article):
    client = FakeClient({"stories": [{"title": "T", "summary": "S", "article_ids": [99]}]})
    with pytest.raises(LLMError, match="no valid stories"):
        summarizer(client).summarize("X", [article(1)])


def test_summarizer_sends_history_only_when_given(article):
    client = FakeClient({"stories": [{"title": "T", "summary": "S", "article_ids": [1], "status": "new"}]})
    z = summarizer(client)
    z.summarize("X", [article(1)])
    z.summarize("X", [article(1)], PREVIOUS)
    assert "Previously sent" not in client.calls[0][1]
    assert "P1. Ceasefire agreed" in client.calls[1][1]


def test_summarizer_all_repeats_is_not_an_error(article):
    client = FakeClient({"stories": [{"title": "T", "summary": "S", "article_ids": [1],
                                      "status": "repeat", "previous": 1}]})
    [st] = summarizer(client).summarize("X", [article(1)], PREVIOUS)[0]
    assert st.status == "repeat"      # the pipeline drops it; no fallback to headlines


def test_summarizer_missing_stories_key_raises(article):
    with pytest.raises(LLMError):
        summarizer(FakeClient({})).summarize("X", [article(1)])


def test_summarizer_spaces_out_calls(monkeypatch, article):
    sleeps, clock = [], iter([100.0, 101.0, 102.0, 103.0])
    monkeypatch.setattr(llm.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    z = summarizer(FakeClient({"stories": [{"title": "T", "summary": "S", "article_ids": [1]}]}), interval=7)
    z.summarize("A", [article(1)])          # first call: no wait; last_call = 100
    z.summarize("B", [article(1)])          # now = 101 -> wait 6s
    assert sleeps == [6.0]


def test_summarizer_records_call_time_even_on_failure(article):
    z = summarizer(FakeClient(LLMError("boom")))
    with pytest.raises(LLMError):
        z.summarize("A", [article(1)])
    assert z._last_call is not None


def test_make_summarizer_uses_settings(settings):
    z = make_summarizer(settings)
    assert z.label == "gemini:gemini-test"
    assert (z.max_stories, z.max_input, z.language) == (6, 25, "English")
