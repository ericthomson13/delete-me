"""Per-broker audit adapter tests.

Each adapter is a thin subclass of PeopleSearchAdapter — the heavy
behavioral testing lives in test_people_search_base.py. These tests
verify the per-adapter URL template + result-card pattern by feeding a
canned HTML response.

Real-world validation against the live broker sites is out of scope
(would require network + fragile selectors); the adapters are marked
experimental for that reason and the orchestrator degrades gracefully.
"""

from __future__ import annotations

import httpx
import pytest
from delete_me.audit.orchestrator import production_registry
from delete_me.audit.sources.base import AuditQuery
from delete_me.audit.sources.beenverified import BeenVerifiedAdapter
from delete_me.audit.sources.familytreenow import FamilyTreeNowAdapter
from delete_me.audit.sources.fastpeoplesearch import FastPeopleSearchAdapter
from delete_me.audit.sources.instantcheckmate import InstantCheckmateAdapter
from delete_me.audit.sources.intelius import InteliusAdapter
from delete_me.audit.sources.mylife import MyLifeAdapter
from delete_me.audit.sources.nuwber import NuwberAdapter
from delete_me.audit.sources.peekyou import PeekYouAdapter
from delete_me.audit.sources.peoplefinder import PeopleFinderAdapter
from delete_me.audit.sources.peoplelooker import PeopleLookerAdapter
from delete_me.audit.sources.radaris import RadarisAdapter
from delete_me.audit.sources.spokeo import SpokeoAdapter
from delete_me.audit.sources.thatsthem import ThatsThemAdapter
from delete_me.audit.sources.truepeoplesearch import TruePeopleSearchAdapter
from delete_me.audit.sources.truthfinder import TruthFinderAdapter
from delete_me.audit.sources.whitepages import WhitepagesAdapter


class _FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[str] = []

    def get(self, url):
        self.calls.append(url)
        return self.responses.pop(0)


def _response(status: int, body: str = "") -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=body.encode(),
        request=httpx.Request("GET", "https://example.com/test"),
    )


def _query() -> AuditQuery:
    return AuditQuery(
        full_name="Jane Doe", current_city="Portland", current_state="OR", dob_year=None
    )


@pytest.mark.parametrize(
    ("adapter_cls", "url_substring", "card_html"),
    [
        (
            TruePeopleSearchAdapter,
            "truepeoplesearch.com/results?name=",
            '<div class="card">Jane Doe — Portland, OR</div>',
        ),
        (
            FastPeopleSearchAdapter,
            "fastpeoplesearch.com/results?name=",
            '<div class="card">Jane Doe in Portland, OR</div>',
        ),
        (
            FamilyTreeNowAdapter,
            "familytreenow.com/search/genealogy/results?first=Jane&last=Doe",
            '<div class="result-row">Jane Doe</div>',
        ),
        (
            NuwberAdapter,
            "nuwber.com/search?name=",
            '<div class="person-card">Jane Doe</div>',
        ),
        (
            ThatsThemAdapter,
            "thatsthem.com/name/Jane-Doe",
            '<div class="result-record-row">Jane Doe</div>',
        ),
        (
            SpokeoAdapter,
            "spokeo.com/Jane+Doe/Portland%2C+OR",
            '<li class="single-column-list-item-block">Jane Doe</li>',
        ),
        (
            WhitepagesAdapter,
            "whitepages.com/name/Jane-Doe",
            '<div class="search-result-row">Jane Doe — Portland, OR</div>',
        ),
        (
            BeenVerifiedAdapter,
            "beenverified.com/app/search/person?fname=",
            '<div class="person-result">Jane Doe</div>',
        ),
        (
            PeopleFinderAdapter,
            "peoplefinders.com/people/Jane+Doe",
            '<div class="result-row">Jane Doe</div>',
        ),
        (
            InteliusAdapter,
            "intelius.com/people-search/Jane+Doe",
            '<div class="person-result">Jane Doe</div>',
        ),
        (
            RadarisAdapter,
            "radaris.com/p/Jane/Doe",
            '<div class="person-list-item">Jane Doe</div>',
        ),
        (
            InstantCheckmateAdapter,
            "instantcheckmate.com/people/Jane+Doe",
            '<div class="search-result">Jane Doe</div>',
        ),
        (
            PeopleLookerAdapter,
            "peoplelooker.com/app/search/person?fname=",
            '<div class="person-result">Jane Doe</div>',
        ),
        (
            TruthFinderAdapter,
            "truthfinder.com/people-search/Jane+Doe",
            '<div class="search-result">Jane Doe</div>',
        ),
        (
            PeekYouAdapter,
            "peekyou.com/jane_doe",
            '<div class="listing-card">Jane Doe</div>',
        ),
        (
            MyLifeAdapter,
            "mylife.com/pub-people-search.pubview?search=",
            '<div class="people-card-row">Jane Doe</div>',
        ),
    ],
)
def test_adapter_url_and_found_path(adapter_cls, url_substring, card_html):
    adapter = adapter_cls(client=_FakeClient([_response(200, card_html)]))
    adapter.MIN_INTERVAL_S = 0
    result = adapter.search(_query())
    assert url_substring in adapter.client.calls[0], (
        f"{adapter_cls.__name__}: expected {url_substring!r} in {adapter.client.calls[0]!r}"
    )
    assert result.found is True, f"{adapter_cls.__name__} should match its own card HTML"
    assert result.inconclusive is False


@pytest.mark.parametrize(
    "adapter_cls",
    [
        TruePeopleSearchAdapter,
        FastPeopleSearchAdapter,
        FamilyTreeNowAdapter,
        NuwberAdapter,
        ThatsThemAdapter,
        SpokeoAdapter,
        WhitepagesAdapter,
        BeenVerifiedAdapter,
        PeopleFinderAdapter,
        InteliusAdapter,
        RadarisAdapter,
        InstantCheckmateAdapter,
        PeopleLookerAdapter,
        TruthFinderAdapter,
        PeekYouAdapter,
        MyLifeAdapter,
    ],
)
def test_adapter_403_is_inconclusive(adapter_cls):
    adapter = adapter_cls(client=_FakeClient([_response(403)]))
    adapter.MIN_INTERVAL_S = 0
    result = adapter.search(_query())
    assert result.inconclusive is True
    assert result.found is False


def test_spokeo_perimeterx_marker_is_inconclusive():
    body = "<html>...Please verify you are a human...</html>"
    adapter = SpokeoAdapter(client=_FakeClient([_response(200, body)]))
    adapter.MIN_INTERVAL_S = 0
    result = adapter.search(_query())
    assert result.inconclusive is True


def test_familytreenow_handles_single_name_query():
    """A single-word full_name should still produce a workable URL."""
    adapter = FamilyTreeNowAdapter(client=_FakeClient([_response(200, "")]))
    adapter.MIN_INTERVAL_S = 0
    result = adapter.search(
        AuditQuery(full_name="Cher", current_city=None, current_state=None, dob_year=None)
    )
    assert "last=Cher" in adapter.client.calls[0]
    assert result.inconclusive is False  # 200 + no card match → not_found, not inconclusive


def test_production_registry_wires_every_adapter():
    reg = production_registry()
    assert set(reg.keys()) == {
        "truepeoplesearch_search",
        "fastpeoplesearch_search",
        "familytreenow_search",
        "nuwber_search",
        "thatsthem_search",
        "spokeo_search",
        "whitepages_search",
        "beenverified_search",
        "peoplefinder_search",
        "intelius_search",
        "radaris_search",
        "instantcheckmate_search",
        "peoplelooker_search",
        "truthfinder_search",
        "peekyou_search",
        "mylife_search",
    }
