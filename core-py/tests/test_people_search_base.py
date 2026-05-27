"""Tests for the shared PeopleSearchAdapter base.

These tests cover the base class via a minimal subclass and a fake
httpx.Client. The real broker adapters reuse this code paths-for-paths,
so the per-broker tests can stay terse.
"""

from __future__ import annotations

import httpx
import pytest
from delete_me.audit.sources._people_search_base import PeopleSearchAdapter
from delete_me.audit.sources.base import AuditQuery


class _FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[str] = []

    def get(self, url):
        self.calls.append(url)
        if not self.responses:
            raise AssertionError("unexpected extra request")
        return self.responses.pop(0)


def _response(status: int, body: str = "", headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=body.encode(),
        headers=headers or {},
        request=httpx.Request("GET", "https://example.com/test"),
    )


class _StubAdapter(PeopleSearchAdapter):
    source_id = "stub"
    SEARCH_URL_TEMPLATE = "https://example.com/search?name={name}&loc={location}"
    MIN_INTERVAL_S = 0  # don't sleep in tests


def _query(name: str = "Jane Q. Doe") -> AuditQuery:
    return AuditQuery(full_name=name, current_city="Portland", current_state="OR", dob_year=None)


def test_subclass_must_set_required_attrs():
    class _Broken(PeopleSearchAdapter):
        pass

    with pytest.raises(TypeError, match="source_id"):
        _Broken()


def test_build_url_includes_name_and_location_urlencoded():
    adapter = _StubAdapter(client=_FakeClient([_response(200, "")]))
    url = adapter.build_url(_query())
    assert "name=Jane+Q.+Doe" in url
    assert "loc=Portland%2C+OR" in url


def test_found_when_name_in_card_block():
    body = '<div class="card-result"><h3>Jane Q. Doe</h3><span>Portland, OR</span></div>'
    adapter = _StubAdapter(client=_FakeClient([_response(200, body)]))
    result = adapter.search(_query())
    assert result.found is True
    assert result.inconclusive is False
    assert result.listings_url


def test_not_found_when_name_outside_card_block():
    body = '<header>Jane Q. Doe is a popular name</header><div class="card">someone else</div>'
    adapter = _StubAdapter(client=_FakeClient([_response(200, body)]))
    result = adapter.search(_query())
    assert result.found is False
    assert result.inconclusive is False


def test_403_returns_inconclusive_with_block_note():
    adapter = _StubAdapter(client=_FakeClient([_response(403, "Forbidden")]))
    result = adapter.search(_query())
    assert result.found is False
    assert result.inconclusive is True
    assert "blocked" in (result.notes or "").lower()


def test_429_returns_inconclusive():
    adapter = _StubAdapter(client=_FakeClient([_response(429)]))
    result = adapter.search(_query())
    assert result.inconclusive is True


def test_500_returns_inconclusive_with_http_note():
    adapter = _StubAdapter(client=_FakeClient([_response(500)]))
    result = adapter.search(_query())
    assert result.inconclusive is True
    assert "HTTP 500" in (result.notes or "")


def test_cloudflare_block_page_detected():
    body = "<html><body>Just a moment...<div>checking your browser</div></body></html>"
    adapter = _StubAdapter(client=_FakeClient([_response(200, body)]))
    result = adapter.search(_query())
    assert result.inconclusive is True
    assert "bot-block" in (result.notes or "")


def test_network_error_returns_inconclusive():
    class _BrokenClient:
        def get(self, url):
            raise httpx.ConnectError("dns fail")

    adapter = _StubAdapter(client=_BrokenClient())
    result = adapter.search(_query())
    assert result.inconclusive is True
    assert "network error" in (result.notes or "")


def test_custom_card_class_pattern():
    class _Custom(PeopleSearchAdapter):
        source_id = "stub2"
        SEARCH_URL_TEMPLATE = "https://example.com/?n={name}&l={location}"
        MIN_INTERVAL_S = 0
        CARD_CLASS_PATTERN = "person-row"

    body = '<li class="person-row"><a>Jane Q. Doe</a></li>'
    adapter = _Custom(client=_FakeClient([_response(200, body)]))
    result = adapter.search(_query())
    assert result.found is True


def test_extra_block_markers_per_subclass():
    class _Custom(PeopleSearchAdapter):
        source_id = "stub3"
        SEARCH_URL_TEMPLATE = "https://example.com/?n={name}&l={location}"
        MIN_INTERVAL_S = 0
        BLOCK_MARKERS = ("our internal block string",)

    body = "<html>Some content with our INTERNAL block string in it.</html>"
    adapter = _Custom(client=_FakeClient([_response(200, body)]))
    result = adapter.search(_query())
    assert result.inconclusive is True
