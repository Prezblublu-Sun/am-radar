# ADR-0001 — AM Radar scope, directions, and source strategy

- **Status:** Accepted
- **Date:** 2026-06-06
- **Context:** AM Radar is a separate radar forked from the original Research
  Radar. It reuses the shared discovery pipeline but tracks a different,
  additive-manufacturing-specific set of research directions. This ADR records
  the scope, the four directions, the OpenAlex source strategy, the HIP
  disambiguation, and the inherited recall-hardening fixes it depends on.

---

## Decision

### 1. Scope

AM Radar is the **discovery layer** for **additive-manufacturing mechanical
performance**: fetch → DOI-dedup → keyword-route → LLM-score → render a daily
digest. Deep parsing, OCR, chunking, embeddings, vector stores, RAG, and
cross-paper synthesis remain out of scope and belong to lit-system (the
deep-parsing / RAG layer). The discovery / deep-parsing contract is inherited
from the original radar; see `SCOPE.md`.

Sister-project topics that do **not** apply here have been removed from the
docs: AI/3D bioprinting, clinical hip-implant outcomes, FEA surrogate modelling,
and the RL world-model direction.

### 2. The four research directions

Defined in `config/directions.yaml`, which is the single source of truth.
`config/directions.yaml` is not modified by routine work, and direction names /
counts are not hardcoded where the code can derive them from config (tabs,
search chips, colors, and the "across N research directions" index subtitle all
read from config).

1. **`mechanical_properties` — AM Mechanical Properties.** Tensile/yield/ultimate
   strength, elongation, ductility, fracture toughness, strain hardening, and
   build-orientation / mechanical anisotropy of AM parts.
2. **`fatigue` — AM Fatigue.** Fatigue life and strength, S-N curves, high- and
   very-high-cycle fatigue, defect-driven fatigue, crack initiation and growth.
3. **`ti6al4v_postprocess_hip` — Ti-6Al-4V Post-processing & HIP.** Hot isostatic
   pressing, heat treatment, and other post-processing of AM Ti-6Al-4V — porosity
   closure, microstructure, and resulting property changes.
4. **`am_femoral_stem` — Femoral Stem (AM + traditional).** Femoral / hip stem
   design, porous-titanium and lattice stems, stress shielding, cementless and
   short stems — covering both additively manufactured and traditional stems.

Each direction routes on a strong keyword that, in a realistic paper, co-occurs
with an additive-manufacturing term (additive manufacturing, selective laser
melting, laser powder bed fusion / LPBF / L-PBF, powder bed fusion, electron beam
melting / EBM, directed energy deposition, wire arc additive / WAAM).

### 3. OpenAlex is keyword-first; `openalex_concepts` is intentionally empty

For every direction, `openalex_concepts: []` and the OpenAlex signal is carried
entirely by `openalex_keywords`.

**Rationale.** In the sister project, concept-id filters routinely returned more
than ~2000 results per query. The OpenAlex fetch is cursor-paginated with a fixed
per-query page budget, so an over-cap concept query silently dropped the overflow
— a direct **recall loss**. Keyword (`search=`) queries are narrower, stay under
the cap, and therefore avoid the silent truncation. Keyword-first is the recall-
safer default for AM Radar, consistent with the recall-over-precision
optimization function (`CLAUDE.md` §1). Concepts must not be re-added without
re-examining this trade-off.

### 4. "HIP" means hot isostatic pressing, not the hip joint

The `ti6al4v_postprocess_hip` direction is about **hot isostatic pressing** of
AM titanium. Its strong keyword is the full phrase `"hot isostatic pressing"`
(plus `"Ti-6Al-4V"` / `"Ti6Al4V"`), never the bare token "hip". A clinical paper
about, e.g., "total hip arthroplasty" carries none of these strong keywords (nor
any AM strong keyword) and therefore routes to nothing — it does not enter this
direction. A regression test asserts this (`tests/test_direction_router.py`).
The `am_femoral_stem` direction is the one that legitimately covers hip-*stem*
hardware.

---

## Inherited fixes this radar relies on (cross-references)

These come from the shared pipeline and prior recall-hardening work and must be
preserved:

- **Per-source zero-return flag** — `<src>_returned_zero` quality flag when a
  fetcher (arxiv / openalex / pubmed) returns no rows (batch 1).
- **OpenAlex truncation flag** — `openalex_truncated` quality flag, raised from
  `truncation_events` when a query hits its `max_pages` cap with `next_cursor`
  still set (batch 1; `fetchers/openalex_fetcher.py`). Tested in
  `tests/test_openalex_fetcher_fanout.py`.
- **Concurrent scorer** — papers are LLM-scored concurrently.
- **Score-before-dedup** — routed candidates are pre-deduped against the corpus
  before scoring, with a write-time first-seen-wins safety net (ADR-0020 lineage;
  `pipeline/run_historical.py`).
- **Retry-aware scorer** — transient LLM failures are retried, not dropped.
- **Era-split search index** — per-year `search-index-YYYY.json` + manifest
  (ADR-0022 lineage; `render/build_pages.py`).

---

## Consequences

- Result counts for directions are driven by keyword breadth; widen
  `openalex_keywords` (not concepts) to recall more.
- The radar is intentionally narrow (discovery only) and cheap to run.
- Corpus persistence is `data/` on `main` only — no Releases archive, no monthly
  archive workflow.
