"""Direction router: routes papers to research directions based on
strong_keywords, hard-anchored by must_pair_with. Applies universal exclusions.

must_pair_with is a flat list of alternative anchor terms (OR semantics) and is
a HARD GATE: a direction declaring anchors requires at least one anchor term in
the paper text, else the paper scores 0 for that direction and cannot route in.
In this 3-layer Ti-6Al-4V radar every layer anchors on Ti-6Al-4V terms, so
non-Ti-6Al-4V papers route to nothing.

Primary direction uses deepest-layer bias (ADR-0002): config orders directions
shallow->deep (L1 base -> L2 post-processing -> L3 femoral stem), conceptually
nested, so among matched layers the primary `direction` is the DEEPEST one;
`directions` stays score-ordered for display."""
from __future__ import annotations

import re


def _text(paper: dict) -> str:
    return f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()


def _norm(s: str) -> str:
    """Normalize hyphens to spaces so surface variants match: e.g. "3D-printed"
    matches "3d printed", "L-PBF" matches "l pbf". Precise — no stemming or
    substring matching; the word-boundary check below still applies."""
    return s.replace("-", " ")


def _contains(text: str, term: str) -> bool:
    return re.search(
        rf"\b{re.escape(_norm(term.lower()))}\b", _norm(text)
    ) is not None


def _is_excluded(text: str, exclusions: dict) -> bool:
    for term in exclusions.get("hard_exclude_if_only_about", []):
        if _contains(text, term):
            return True
    return False


def _score_direction(text: str, cfg: dict) -> tuple[float, list[str]]:
    # must_pair_with is a flat list of alternative anchor terms (OR). HARD GATE:
    # if a direction declares anchors and none are present, it scores 0 and the
    # paper cannot route into it.
    anchors = cfg.get("must_pair_with", [])
    anchor_hits = [a for a in anchors if _contains(text, a)]
    if anchors and not anchor_hits:
        return 0.0, []

    score = 0.0
    matched: list[str] = list(anchor_hits)
    for kw in cfg.get("strong_keywords", []):
        if _contains(text, kw):
            score += 2.0
            matched.append(kw)
    return score, matched


def route(paper: dict, directions_cfg: dict, exclusions: dict,
          min_score: float = 2.0) -> dict:
    text = _text(paper)
    if _is_excluded(text, exclusions):
        paper["directions"] = []
        paper["direction"] = None
        paper["routing_reason"] = "excluded by hard rule"
        return paper
    scored: list[tuple[str, float, list[str]]] = []
    for dir_key, cfg in directions_cfg.items():
        s, m = _score_direction(text, cfg)
        if s >= min_score:
            scored.append((dir_key, s, m))
    scored.sort(key=lambda x: x[1], reverse=True)
    paper["directions"] = [s[0] for s in scored]
    # ADR-0002 deepest-layer assignment: among matched layers, primary direction
    # is the DEEPEST (config order L1->L2->L3 = shallow->deep). directions list
    # stays score-ordered above for display.
    if scored:
        _order = list(directions_cfg.keys())
        _matched = [s[0] for s in scored]
        paper["direction"] = max(_matched, key=lambda k: _order.index(k))
    else:
        paper["direction"] = None
    paper["direction_name"] = (
        directions_cfg[paper["direction"]]["display_name"] if paper["direction"] else None
    )
    paper["routing_matches"] = {s[0]: s[2] for s in scored}
    return paper


def filter_routed(papers: list[dict]) -> list[dict]:
    return [p for p in papers if p.get("direction")]


def apply_crossover_boost(papers: list[dict]) -> int:
    """ADR-0021: papers routed into BOTH rl_world_model AND fea_surrogate get
    priority bumped one level. Idempotent. Dead under the 3-layer Ti-6Al-4V
    config (those directions no longer exist) but kept because run_daily still
    calls it; it simply never matches."""
    BUMP = {"Low": "Medium", "Medium": "High"}
    boosted = 0
    for p in papers:
        dirs = set(p.get("directions") or [])
        if {"rl_world_model", "fea_surrogate"} <= dirs:
            llm = p.get("llm") or {}
            if llm.get("priority_boosted"):
                continue
            pri = llm.get("priority")
            if pri in BUMP:
                llm["priority_pre_boost"] = pri
                llm["priority"] = BUMP[pri]
                llm["priority_boosted"] = True
                llm["boost_reason"] = "RL × FEA/surrogate crossover (ADR-0021)"
                p["llm"] = llm
                boosted += 1
    return boosted
