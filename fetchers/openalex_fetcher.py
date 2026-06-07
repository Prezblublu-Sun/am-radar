"""OpenAlex fetcher: pulls papers published in a date window matching
concept IDs or keywords. Free API, no key required (polite pool via email).

Keyword search: each keyword is issued as its OWN OpenAlex `search=` query
and the results are unioned (deduped by work id). This replaces the previous
single OR-joined quoted-phrase search, which OpenAlex's search endpoint
returned 0 results for (quoted-phrase boolean OR is unsupported). Per-keyword
single queries are the reliable path.
"""
from __future__ import annotations

import os
import datetime as dt

import requests

OPENALEX_BASE = "https://api.openalex.org/works"
POLITE_EMAIL = os.environ.get("OPENALEX_EMAIL", "your-email@ucl.ac.uk")


def _abstract_from_inverted_index(inv: dict | None) -> str:
    """OpenAlex returns abstracts as an inverted index. Reconstruct text."""
    if not inv:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)


def _build_filter(concepts: list[str], from_date: str,
                  to_date: str | None = None) -> str:
    parts = [f"from_publication_date:{from_date}", "type:article|review"]
    if to_date:
        parts.append(f"to_publication_date:{to_date}")
    if concepts:
        parts.append("concepts.id:" + "|".join(concepts))
    return ",".join(parts)


def _fetch_one(flt: str, search_query: str | None, per_page: int,
               max_pages: int) -> tuple[list[dict], bool]:
    """One cursor-paginated OpenAlex query → (results, truncated).

    `truncated` is True when the loop hit max_pages while OpenAlex still
    advertised more results via `next_cursor`. The caller logs/surfaces it so
    silent over-cap drops never go unnoticed (ADR-0023).
    """
    results: list[dict] = []
    cursor = "*"
    for _ in range(max_pages):
        params = {
            "filter": flt,
            "per-page": per_page,
            "cursor": cursor,
            "mailto": POLITE_EMAIL,
        }
        if search_query:
            params["search"] = search_query
        r = requests.get(OPENALEX_BASE, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        for work in data.get("results", []):
            results.append(_normalize(work))
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break
    else:
        return results, bool(cursor)
    return results, False


def _emit_truncation(events: list[dict] | None, query_desc: str, n: int) -> None:
    print(f"OpenAlex TRUNCATED at {n} results for query {query_desc}",
          flush=True)
    if events is not None:
        events.append({"query": query_desc, "results_at_cap": n})


def _union(rows_lists: list[list[dict]]) -> list[dict]:
    """Union result lists, dedup by OpenAlex work id, stable first-seen order."""
    seen: set[str] = set()
    merged: list[dict] = []
    for rows in rows_lists:
        for r in rows:
            rid = r.get("id") or ""
            if rid and rid in seen:
                continue
            if rid:
                seen.add(rid)
            merged.append(r)
    return merged


def fetch(
    concepts: list[str],
    keywords: list[str],
    days_back: int = 1,
    per_page: int = 50,
    max_pages: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    truncation_events: list[dict] | None = None,
) -> list[dict]:
    """Returns a list of normalized paper dicts.

    Modes:
      - Daily (default): from_date computed from `days_back`, no upper bound.
        Default `max_pages` is 4 (~200 papers/query/day).
      - Historical (from_date and to_date set as 'YYYY-MM-DD'): both bounds
        passed to the filter. Default `max_pages` bumped to 40.

    Keyword handling: EACH keyword is its own single `search=` query (no quotes,
    no OR-join), results unioned and deduped by work id. Concepts (if any) are
    issued as one concept-filter query. The two signal types are unioned so a
    paper matching either is recovered. `max_pages` caps each sub-query
    independently; over-cap sub-queries are logged + surfaced via
    `truncation_events` (ADR-0023).
    """
    historical = bool(from_date and to_date)
    if historical:
        effective_from = from_date
        effective_to = to_date
        effective_max_pages = max_pages if max_pages is not None else 40
    else:
        effective_from = (dt.date.today() - dt.timedelta(days=days_back)).isoformat()
        effective_to = None
        effective_max_pages = max_pages if max_pages is not None else 4

    rows_lists: list[list[dict]] = []

    # Concept-filter query (if any concepts configured).
    if concepts:
        flt_concepts = _build_filter(concepts, effective_from, effective_to)
        rows, trunc = _fetch_one(flt_concepts, None, per_page, effective_max_pages)
        if trunc:
            _emit_truncation(truncation_events, flt_concepts, len(rows))
        rows_lists.append(rows)

    # One single-search query PER keyword (no quotes, no OR-join).
    flt_no_concepts = _build_filter([], effective_from, effective_to)
    for kw in keywords:
        rows, trunc = _fetch_one(flt_no_concepts, kw, per_page, effective_max_pages)
        if trunc:
            _emit_truncation(truncation_events, f"search={kw}", len(rows))
        rows_lists.append(rows)

    return _union(rows_lists)


def _normalize(work: dict) -> dict:
    doi = work.get("doi") or ""
    if doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]
    authorships = work.get("authorships", [])
    authors = [a.get("author", {}).get("display_name", "") for a in authorships]

    def _aff(a: dict) -> str:
        raw = a.get("raw_affiliation_strings") or []
        if raw:
            return raw[0]
        insts = a.get("institutions") or []
        if insts:
            return insts[0].get("display_name", "")
        return ""

    first_author_affiliation = _aff(authorships[0]) if authorships else ""
    corresponding = [
        {
            "name": a.get("author", {}).get("display_name", ""),
            "affiliation": _aff(a),
        }
        for a in authorships if a.get("is_corresponding")
    ]
    concepts = [
        c.get("display_name", "")
        for c in work.get("concepts", [])
        if c.get("score", 0) > 0.3
    ]
    venue = (work.get("primary_location") or {}).get("source") or {}
    raw_date = work.get("publication_date", "") or ""
    if not raw_date:
        date_str, date_precision = "", "year"
    elif raw_date.endswith("-01-01"):
        date_str, date_precision = raw_date, "year"
    elif raw_date.endswith("-01"):
        date_str, date_precision = raw_date, "month"
    else:
        date_str, date_precision = raw_date, "day"
    return {
        "source": "openalex",
        "id": work.get("id", ""),
        "doi": doi,
        "title": work.get("title", "") or "",
        "abstract": _abstract_from_inverted_index(work.get("abstract_inverted_index")),
        "authors": authors,
        "first_author_affiliation": first_author_affiliation,
        "corresponding_authors": corresponding,
        "venue": venue.get("display_name", ""),
        "year": work.get("publication_year"),
        "date": date_str,
        "date_precision": date_precision,
        "url": work.get("doi") or work.get("id", ""),
        "cited_by_count": work.get("cited_by_count", 0),
        "concepts": concepts,
        "categories": [],
        "raw_type": work.get("type", ""),
    }


if __name__ == "__main__":
    sample = fetch(concepts=[], keywords=["Ti-6Al-4V additive manufacturing fatigue"], days_back=7)
    print(f"Fetched {len(sample)} papers")
    for p in sample[:3]:
        print(f"  - {p['title'][:80]}  [{p['doi']}]")
