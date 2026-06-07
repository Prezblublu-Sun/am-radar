# ADR-0002: Three-Layer Ti-6Al-4V Structure

## Status
Accepted. Supersedes the four-direction structure of ADR-0001.

## Context
The initial four parallel directions (mechanical_properties, fatigue,
ti6al4v_postprocess_hip, am_femoral_stem) pulled in large volumes of
off-topic noise: non-Ti-6Al-4V alloys, ceramics, ferroelectric/battery
"fatigue", and clinical orthopaedic papers. Keyword/exclusion tuning could
not cleanly separate signal from noise, and the LLM scorer (once retargeted
to AM) correctly marked ~70%+ of routed papers as Exclude.

## Decision
Restructure into three layers, all HARD-anchored to Ti-6Al-4V via
must_pair_with (a paper must mention Ti-6Al-4V / TC4 / Ti64 etc. to route
into any layer). The layers are conceptually nested (L3 ⊂ L2 ⊂ L1) but
processed in parallel by the existing single-assignment router:

- **L1 — Base Mechanical & Fatigue** (`ti6al4v_base_mechanical_fatigue`):
  tensile/yield/UTS, ductility, anisotropy, layer thickness, build
  orientation, defects/porosity, surface roughness, residual stress,
  fatigue life/S-N/crack initiation & growth of AM Ti-6Al-4V.

- **L2 — Post-processing Control** (`ti6al4v_postprocess`):
  effect of heat treatment, stress relief, HIP (hot isostatic pressing,
  NOT hip joint), machining, polishing, shot peening, laser shock peening,
  hirtisation, coatings on Ti-6Al-4V fatigue/mechanical performance.

- **L3 — Femoral Stem Design** (`ti6al4v_femoral_stem`):
  Ti-6Al-4V femoral/hip stem structural design and service — porous stem,
  graded lattice, TPMS, stress shielding, Gruen zones, primary stability,
  micromotion, ISO fatigue testing, FEA + experimental validation.

## Boundary papers
A paper touching several layers (e.g. "HIP effect on Ti-6Al-4V femoral
stem fatigue") is biased toward the DEEPEST applicable layer, because
deeper layers carry more specific high-value keywords and thus accumulate
a higher routing score (stem > post-process > base). Each layer's
llm_prompt_focus also instructs the scorer to defer to the deeper layer.

## Consequences
- Non-Ti-6Al-4V noise is eliminated at routing time, not at scoring time.
- Total corpus is smaller but far more focused; High/Medium papers are all
  genuinely on the user's Ti-6Al-4V research direction.
- Per-day Medium+ density is low (a focused niche), addressed by an unread
  high-priority reading queue rather than by loosening evaluation.
