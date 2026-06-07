"""Tests for pipeline/direction_router.py under the three-layer Ti-6Al-4V
structure in config/directions.yaml (ADR-0002).

Directions:
  * ti6al4v_base_mechanical_fatigue (L1)
  * ti6al4v_postprocess             (L2)
  * ti6al4v_femoral_stem            (L3)

All three layers are hard-anchored to Ti-6Al-4V via must_pair_with, so a
paper must mention Ti-6Al-4V (or TC4 / Ti64 ...) AND a layer strong_keyword
to route in. Non-Ti-6Al-4V papers route to nothing. Clinical-only papers are
hard-excluded. Tests load the live config so the production rule set is what
is exercised.
"""
from __future__ import annotations
import pathlib
import sys
import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import direction_router  # noqa: E402

CFG_PATH = ROOT / "config" / "directions.yaml"


@pytest.fixture(scope="module")
def cfg():
    return yaml.safe_load(CFG_PATH.read_text())


@pytest.fixture(scope="module")
def directions(cfg):
    return cfg["directions"]


@pytest.fixture(scope="module")
def exclusions(cfg):
    return cfg.get("exclusions", {})


def _paper(title: str, abstract: str) -> dict:
    return {"title": title, "abstract": abstract}


# ============================================================================
# One routing test per layer (each carries a Ti-6Al-4V term + a layer keyword)
# ============================================================================
def test_L1_base_mechanical_fatigue_routes(directions, exclusions):
    p = _paper(
        "Fatigue life of LPBF Ti-6Al-4V",
        "We measure the fatigue life and fatigue crack initiation of "
        "laser powder bed fusion Ti-6Al-4V as a function of build orientation.",
    )
    direction_router.route(p, directions, exclusions)
    assert p["direction"] == "ti6al4v_base_mechanical_fatigue"


def test_L2_postprocess_routes(directions, exclusions):
    p = _paper(
        "Effect of hot isostatic pressing on Ti-6Al-4V",
        "Hot isostatic pressing and subsequent heat treatment close porosity "
        "and improve the fatigue performance of additively manufactured Ti-6Al-4V.",
    )
    direction_router.route(p, directions, exclusions)
    assert p["direction"] == "ti6al4v_postprocess"


def test_L3_femoral_stem_routes(directions, exclusions):
    p = _paper(
        "Porous Ti-6Al-4V femoral stem design",
        "A graded lattice porous Ti-6Al-4V femoral stem is designed to reduce "
        "stress shielding, evaluated by finite element analysis and ISO fatigue testing.",
    )
    direction_router.route(p, directions, exclusions)
    assert p["direction"] == "ti6al4v_femoral_stem"


# ============================================================================
# Ti-6Al-4V hard anchoring: non-Ti-6Al-4V papers route to nothing
# ============================================================================
def test_non_ti6al4v_alloy_routes_to_nothing(directions, exclusions):
    # Has a strong fatigue keyword + AM context but is AlSi10Mg, not Ti-6Al-4V.
    p = _paper(
        "Fatigue of AlSi10Mg",
        "The fatigue life and S-N curve of laser powder bed fusion AlSi10Mg "
        "are reported as a function of build orientation and porosity.",
    )
    direction_router.route(p, directions, exclusions)
    assert p["direction"] is None


def test_generic_non_am_paper_routes_to_nothing(directions, exclusions):
    p = _paper(
        "A study of soil microbiology",
        "We characterise microbial communities in agricultural soil.",
    )
    direction_router.route(p, directions, exclusions)
    assert p["direction"] is None


# ============================================================================
# Deepest-layer bias: a paper touching multiple layers prefers the deeper one
# ============================================================================
def test_stem_paper_with_fatigue_prefers_L3_over_L1(directions, exclusions):
    # Mentions fatigue (L1) AND post-processing (L2) AND a stem (L3) for Ti-6Al-4V;
    # should land in the deepest layer that applies.
    p = _paper(
        "HIP and fatigue of a porous Ti-6Al-4V femoral stem",
        "A porous Ti-6Al-4V femoral stem with a graded lattice is hot isostatic "
        "pressed; its fatigue life and stress shielding are evaluated.",
    )
    direction_router.route(p, directions, exclusions)
    assert p["direction"] == "ti6al4v_femoral_stem"


# ============================================================================
# Clinical-only papers are hard-excluded
# ============================================================================
def test_clinical_case_report_is_excluded(directions, exclusions):
    p = _paper(
        "A case report of a Ti-6Al-4V hip stem",
        "We present a case report and surgical technique for a Ti-6Al-4V hip "
        "stem; this is a single-patient clinical case series.",
    )
    direction_router.route(p, directions, exclusions)
    assert p.get("routing_reason") == "excluded by hard rule"
    assert p["direction"] is None


# ============================================================================
# _contains hyphen tolerance (precise, not substring)
# ============================================================================
def test_contains_is_hyphen_tolerant_but_still_precise():
    # "3D-printed" should match "3d printed" after hyphen normalization.
    assert direction_router._contains("a 3d printed part", "3D-printed")
    # but must remain word-boundary precise: "stem" should not match "system".
    assert not direction_router._contains("a control system", "stem")


# ============================================================================
# filter_routed keeps only routed papers
# ============================================================================
def test_filter_routed_keeps_only_routed_papers(directions, exclusions):
    p_routed = _paper(
        "Fatigue of LPBF Ti-6Al-4V",
        "Fatigue life of laser powder bed fusion Ti-6Al-4V with build orientation effects.",
    )
    p_unrouted = _paper("Soil microbiology", "Microbial communities in soil.")
    for p in (p_routed, p_unrouted):
        direction_router.route(p, directions, exclusions)
    kept = direction_router.filter_routed([p_routed, p_unrouted])
    assert p_routed in kept
    assert p_unrouted not in kept
