"""Tests for pipeline/direction_router.py under the four additive-manufacturing
directions in config/directions.yaml.

Covers:
  * One representative paper per direction routes into exactly that direction.
  * A "total hip arthroplasty" clinical paper does NOT route into
    ti6al4v_postprocess_hip — "HIP" in this radar means *hot isostatic
    pressing*, not the hip joint (the strong keyword is "hot isostatic
    pressing", and clinical hip-joint terms carry no AM strong keyword).
  * A non-AM paper (no strong keyword in any direction) routes to nothing.

All tests load the live config/directions.yaml so the production rule set is
what is being exercised. Each fixture follows the routing contract: its
title+abstract carries a strong_keyword of its target direction AND an
additive-manufacturing term (the realistic shape of a real AM paper).

Run with:
    pytest tests/test_direction_router.py
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
# One routing test per direction
# ============================================================================

def test_mechanical_properties_paper_routes_into_that_direction(
    directions, exclusions
):
    p = _paper(
        "Tensile strength of laser powder bed fusion Ti parts",
        "We measure the ultimate tensile strength and build orientation "
        "anisotropy of selective laser melting additive manufacturing "
        "specimens.",
    )
    direction_router.route(p, directions, exclusions)
    assert p.get("direction") == "mechanical_properties"
    assert "mechanical_properties" in (p.get("directions") or [])


def test_fatigue_paper_routes_into_that_direction(directions, exclusions):
    p = _paper(
        "High cycle fatigue life of SLM components",
        "The fatigue life and fatigue strength of laser powder bed fusion "
        "additive manufacturing parts is governed by process-induced "
        "defects.",
    )
    direction_router.route(p, directions, exclusions)
    assert p.get("direction") == "fatigue"
    assert "fatigue" in (p.get("directions") or [])


def test_ti6al4v_postprocess_hip_paper_routes_into_that_direction(
    directions, exclusions
):
    p = _paper(
        "Hot isostatic pressing of additively manufactured Ti-6Al-4V",
        "Hot isostatic pressing closes porosity in selective laser melting "
        "additive manufacturing Ti-6Al-4V and improves the microstructure.",
    )
    direction_router.route(p, directions, exclusions)
    assert "ti6al4v_postprocess_hip" in (p.get("directions") or [])


def test_am_femoral_stem_paper_routes_into_that_direction(
    directions, exclusions
):
    p = _paper(
        "Lattice femoral stem for cementless total hip replacement",
        "A porous titanium femoral stem produced by electron beam melting "
        "additive manufacturing reduces stress shielding versus a solid hip "
        "stem.",
    )
    direction_router.route(p, directions, exclusions)
    assert "am_femoral_stem" in (p.get("directions") or [])


# ============================================================================
# HIP disambiguation: clinical hip-joint paper must NOT enter the
# hot-isostatic-pressing direction.
# ============================================================================

def test_total_hip_arthroplasty_does_not_route_into_ti6al4v_postprocess_hip(
    directions, exclusions
):
    p = _paper(
        "Ten-year outcomes of total hip arthroplasty",
        "We report patient-reported outcomes and revision rates after total "
        "hip arthroplasty in a cohort of 500 patients.",
    )
    direction_router.route(p, directions, exclusions)
    dirs = p.get("directions") or []
    # "HIP" here is hot isostatic pressing; a clinical hip-joint abstract has
    # no such strong keyword (nor any AM strong keyword), so it routes nowhere.
    assert "ti6al4v_postprocess_hip" not in dirs


def test_non_am_paper_routes_to_nothing(directions, exclusions):
    p = _paper(
        "Bridge structural civil engineering analysis",
        "A finite element study of load distribution in a concrete highway "
        "bridge under traffic.",
    )
    direction_router.route(p, directions, exclusions)
    assert p.get("direction") is None
    assert (p.get("directions") or []) == []


# ============================================================================
# filter_routed drops papers that routed to nothing.
# ============================================================================

def test_filter_routed_keeps_only_routed_papers(directions, exclusions):
    routed = _paper(
        "Fatigue crack growth in WAAM steel",
        "Fatigue crack growth in wire arc additive manufacturing steel.",
    )
    unrouted = _paper(
        "A survey of medieval poetry",
        "An overview of medieval poetry and its forms.",
    )
    direction_router.route(routed, directions, exclusions)
    direction_router.route(unrouted, directions, exclusions)
    kept = direction_router.filter_routed([routed, unrouted])
    assert kept == [routed]
