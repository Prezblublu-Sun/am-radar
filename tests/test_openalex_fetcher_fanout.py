"""Tests for the AND→OR fan-out dispatch in fetchers/openalex_fetcher.fetch.

Added after the DOI verifier surfaced 4 must_read papers that were
concept-relevant but slipped past the narrow ``concepts.id`` clause when
combined with ``search=``. When both ``concepts`` AND ``keywords`` are
supplied, ``fetch()`` now issues two queries (concepts-only + search-only)
and unions their results. When only one signal is present, the original
single-query path is preserved (and the existing fetcher tests prove it).

Run with:
    pytest tests/test_openalex_fetcher_fanout.py
"""
from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from fetchers import openalex_fetcher  # noqa: E402


def _install_branching_get(monkeypatch, calls: list[dict]):
    """Stub requests.get that records params and routes by query shape.

    Query A (concepts-only, no search) → returns a paper that the narrow
    concept clause catches.
    Query B (search-only, no concept filter) → returns the verifier-class
    paper that concept-only matching would miss.
    """
    paper_a = {
        "id": "https://openalex.org/W_AAA",
        "doi": "https://doi.org/10.1/concept-hit",
        "title": "Caught by concept clause",
        "publication_year": 2024,
        "publication_date": "2024-05-15",
        "type": "article",
    }
    paper_b = {
        "id": "https://openalex.org/W_BBB",
        "doi": "https://doi.org/10.1038/s41598-024-61305-x",
        "title": "Caught only by search-keyword clause",
        "publication_year": 2024,
        "publication_date": "2024-05-10",
        "type": "article",
    }
    # An overlap paper appears in BOTH responses so we can prove dedup.
    paper_overlap = {
        "id": "https://openalex.org/W_OVR",
        "doi": "https://doi.org/10.1/overlap",
        "title": "Hit by both query A and query B",
        "publication_year": 2024,
        "publication_date": "2024-05-20",
        "type": "article",
    }

    class FakeResp:
        def __init__(self, results):
            self._results = results

        def raise_for_status(self):
            pass

        def json(self):
            return {"results": self._results, "meta": {"next_cursor": None}}

    def fake_get(url, params=None, **kw):
        calls.append(dict(params or {}))
        flt = (params or {}).get("filter", "")
        if "search" in (params or {}):
            return FakeResp([paper_b, paper_overlap])
        if "concepts.id:" in flt:
            return FakeResp([paper_a, paper_overlap])
        return FakeResp([])

    monkeypatch.setattr(openalex_fetcher.requests, "get", fake_get)


def test_fan_out_dispatches_per_keyword_queries_and_unions_results(monkeypatch):
    calls: list[dict] = []
    _install_branching_get(monkeypatch, calls)
    out = openalex_fetcher.fetch(
        concepts=["C3020736514", "C3019025420"],
        keywords=["femoral stem", "stress shielding"],
        from_date="2024-05-01",
        to_date="2024-05-31",
        max_pages=1,
    )
    # New behaviour: one concept-filter query + one single-search query PER
    # keyword (no quotes, no OR-join) = 1 + 2 = 3 queries.
    assert len(calls) == 3
    concept_calls = [c for c in calls if "search" not in c]
    search_calls = [c for c in calls if "search" in c]
    assert len(concept_calls) == 1
    assert len(search_calls) == 2
    assert "concepts.id:" in concept_calls[0]["filter"]
    # each search query is a single bare keyword (no quotes, no " OR ")
    for c in search_calls:
        assert "concepts.id:" not in c["filter"]
        assert " OR " not in c["search"]
        assert '"' not in c["search"]
    assert {c["search"] for c in search_calls} == {"femoral stem", "stress shielding"}

    # Union dedup by OpenAlex id: A returned [paper_a, overlap],
    # B returned [paper_b, overlap] → 3 unique papers.
    dois = [p["doi"] for p in out]
    assert "10.1/concept-hit" in dois
    assert "10.1038/s41598-024-61305-x" in dois  # verifier-class catch
    assert "10.1/overlap" in dois
    assert len(out) == 3  # overlap deduped


def test_single_signal_keeps_single_query_path(monkeypatch):
    """Concepts-only (or keywords-only) keeps the original behaviour: one
    query, no fan-out — so direction configs that intentionally provide
    just one signal aren't double-charged for API calls."""
    calls: list[dict] = []

    class FakeResp:
        def raise_for_status(self): pass
        def json(self):
            return {"results": [], "meta": {"next_cursor": None}}

    def fake_get(url, params=None, **kw):
        calls.append(dict(params or {}))
        return FakeResp()

    monkeypatch.setattr(openalex_fetcher.requests, "get", fake_get)

    openalex_fetcher.fetch(concepts=["C123"], keywords=[],
                           from_date="2024-05-01", to_date="2024-05-31",
                           max_pages=1)
    openalex_fetcher.fetch(concepts=[], keywords=["x"],
                           from_date="2024-05-01", to_date="2024-05-31",
                           max_pages=1)
    # 2 calls total (one per fetch invocation), not 4 — no fan-out fired.
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# ADR-0023: loud truncation flag when a query hits max_pages with OpenAlex
# still advertising more results (the silent over-cap that lost recall).
# ---------------------------------------------------------------------------

def test_truncation_flag_fires_on_over_cap_response(monkeypatch):
    """A stubbed response that always returns a next_cursor forces the
    pagination loop to hit max_pages while OpenAlex still has more rows.
    fetch() must append a record to the caller-supplied truncation_events
    list (and the caller raises `openalex_truncated` off a non-empty list)."""

    class FakeResp:
        def raise_for_status(self): pass
        def json(self):
            # Always advertise more results -> never breaks the loop early.
            return {"results": [], "meta": {"next_cursor": "always-more"}}

    def fake_get(url, params=None, **kw):
        return FakeResp()

    monkeypatch.setattr(openalex_fetcher.requests, "get", fake_get)

    events: list[dict] = []
    # keywords-only (mirrors the AM config: openalex_concepts is empty), so
    # the single-query path runs and caps at max_pages.
    openalex_fetcher.fetch(
        concepts=[], keywords=["additive manufacturing fatigue"],
        from_date="2024-05-01", to_date="2024-05-31",
        max_pages=3, truncation_events=events,
    )
    assert len(events) == 1
    assert events[0]["results_at_cap"] == 0  # FakeResp returns no rows


def test_no_truncation_flag_when_cursor_exhausts(monkeypatch):
    """When OpenAlex stops returning a next_cursor before max_pages, no
    truncation event is recorded."""

    class FakeResp:
        def raise_for_status(self): pass
        def json(self):
            return {"results": [], "meta": {"next_cursor": None}}

    def fake_get(url, params=None, **kw):
        return FakeResp()

    monkeypatch.setattr(openalex_fetcher.requests, "get", fake_get)

    events: list[dict] = []
    openalex_fetcher.fetch(
        concepts=[], keywords=["x"],
        from_date="2024-05-01", to_date="2024-05-31",
        max_pages=40, truncation_events=events,
    )
    assert events == []
