# AM Radar

Daily paper digest for **additive-manufacturing mechanical performance**, across four research directions:

- **AM Mechanical Properties** — tensile/yield strength, ductility, anisotropy, build orientation
- **AM Fatigue** — fatigue life/strength, S-N behaviour, defect-driven and crack-growth fatigue
- **Ti-6Al-4V Post-processing & HIP** — hot isostatic pressing, heat treatment, post-processing of AM Ti-6Al-4V
- **Femoral Stem (AM + traditional)** — femoral/hip stem design, porous/lattice stems, stress shielding

> "HIP" in this radar means **hot isostatic pressing**, not the hip joint. See `decisions/ADR-0001-am-radar-scope.md`.

Pulls from arXiv + OpenAlex + PubMed, dedups by DOI, scores each paper with DeepSeek (priority + structured Chinese summary + tags), and publishes to GitHub Pages.

Runs daily via GitHub Actions. Zero server cost, low LLM cost (~¥0.5–2/day).

## Scope

AM Radar is the **discovery** layer only (find + route + score + digest). Deep parsing, RAG, embeddings, and cross-paper synthesis belong to lit-system. See `SCOPE.md` and `CLAUDE.md`.

The corpus (`data/`) lives on the `main` branch **only** — it is never split across `main` + GitHub Releases, and there is no monthly-archive workflow.

## Source strategy

OpenAlex is **keyword-first**: `openalex_concepts` is intentionally empty for every direction and `openalex_keywords` carries the whole signal. Concept-id queries can exceed ~2000 results and get silently truncated by the page cap (which lost papers in the sister project); keyword queries stay under the cap, and any query that still hits the cap raises a loud `openalex_truncated` quality flag.

## Setup

See `TODO.md` for the full first-time setup checklist.

Quick reference:

- Direction config: `config/directions.yaml` (single source of truth — four directions)
- Active scorer prompt: `prompts/scorer_v3.txt` (versioned; never overwritten in place)
- Main entry: `python -m pipeline.run_daily`
- Local dry-run without Zotero: `python -m pipeline.run_daily 1 --skip-zotero`
- Run the test suite: `OPENAI_API_KEY=dummy .venv/bin/pytest -q`

## Required GitHub Secrets

- `OPENAI_API_KEY` — DeepSeek API key
- `OPENAI_BASE_URL` — `https://api.deepseek.com`

## Required GitHub Variables

- `MODEL_NAME` — `deepseek-v4-flash`
- `OPENALEX_EMAIL` — Your email (polite pool)
- `PUBMED_EMAIL` — Your email (NCBI required)

## Version governance

Every daily run is reproducible:

- `data/manifests/YYYY-MM-DD.json` — git commit, config hashes, model snapshot
- `CHANGELOG.md` — auto-updated when config or prompt changes
- `prompts/scorer_vN.txt` — versioned scorer prompts (never overwritten)

## License

MIT. Original UI inspiration from dw-dengwei/daily-arXiv-ai-enhanced.
