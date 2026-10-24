import pandas as pd

from exodiff.triage import (AGREES, EXPLAINED_STELLAR, NOT_CHECKABLE, NOT_COMPARABLE, PLAUSIBLY_STELLAR, UNEXPLAINED,
                              classify_pair, triage_pairs)


def pair(**over):
    base = {
        "pl_name": "P b", "reference_a": "A", "reference_b": "B", "intervals_overlap": False,
        "both_rows_transiting": True, "stellar_rescaling_outcome": "consistent_after_stellar_rescaling",
        "published_rp_rs_intervals_overlap": True, "stellar_refs_match_planet_refs": True,
    }
    base.update(over)
    return base


def test_overlapping_pairs_are_not_discrepancies():
    assert classify_pair(pair(intervals_overlap=True), set()) == AGREES


def test_non_transiting_row_is_not_comparable():
    assert classify_pair(pair(both_rows_transiting=False), set()) == NOT_COMPARABLE


def test_unknown_transit_flag_is_not_set_aside():
    assert classify_pair(pair(both_rows_transiting=None), set()) == EXPLAINED_STELLAR
    assert classify_pair(pair(both_rows_transiting=float("nan"), stellar_rescaling_outcome="persists_after_stellar_rescaling"), set()) == UNEXPLAINED


def test_explained_requires_every_published_condition():
    assert classify_pair(pair(), set()) == EXPLAINED_STELLAR
    assert classify_pair(pair(published_rp_rs_intervals_overlap=None), set()) == PLAUSIBLY_STELLAR
    assert classify_pair(pair(published_rp_rs_intervals_overlap=False), set()) == PLAUSIBLY_STELLAR
    assert classify_pair(pair(stellar_refs_match_planet_refs=False), set()) == PLAUSIBLY_STELLAR


def test_self_inconsistent_row_blocks_explanation():
    assert classify_pair(pair(), {("P b", "B")}) == PLAUSIBLY_STELLAR


def test_rescaling_failure_is_unexplained():
    for outcome in ("persists_after_stellar_rescaling", "partly_consistent_after_stellar_rescaling",
                    "same_stellar_radius"):
        assert classify_pair(pair(stellar_rescaling_outcome=outcome), set()) == UNEXPLAINED


def test_missing_stellar_radius_is_not_checkable_not_unexplained():
    assert classify_pair(pair(stellar_rescaling_outcome="stellar_radius_unavailable"), set()) == NOT_CHECKABLE


def test_triage_pairs_counts_and_flags():
    pairs = pd.DataFrame([pair(), pair(pl_name="Q b", stellar_rescaling_outcome="persists_after_stellar_rescaling"),
                          pair(pl_name="R b", intervals_overlap=True)])
    rows = pd.DataFrame([
        {"pl_name": "Q b", "pl_refname": "A", "is_lead": True, "beyond_rounding_and_units": True},
        {"pl_name": "P b", "pl_refname": "A", "is_lead": False, "beyond_rounding_and_units": False},
        {"pl_name": "P b", "pl_refname": "B", "is_lead": False, "beyond_rounding_and_units": False},
    ])
    out, stats = triage_pairs(pairs, rows)
    assert stats["tiers_non_overlapping_pairs"] == {EXPLAINED_STELLAR: 1, UNEXPLAINED: 1}
    assert stats["pairs_involving_self_inconsistent_row"] == 1
    assert out.set_index("pl_name").loc["P b", "triage_set_aside"]
    assert not out.set_index("pl_name").loc["Q b", "triage_set_aside"]


def test_explained_requires_both_rows_self_consistent_within_rounding():
    assert classify_pair(pair(), set(), consistent_rows={("P b", "A")}) == PLAUSIBLY_STELLAR
    assert classify_pair(pair(), set(), consistent_rows={("P b", "A"), ("P b", "B")}) == EXPLAINED_STELLAR


def test_nasa_documented_radius_issue_sets_pair_aside():
    from exodiff.triage import DOCUMENTED
    notes = {"P b": [{"parameter": "Planet Radius", "category": "radius", "notes": "x", "reference": "y"}]}
    other = {"P b": [{"parameter": "Transit Midpoint", "category": "other", "notes": "x", "reference": "y"}]}
    persists = pair(stellar_rescaling_outcome="persists_after_stellar_rescaling")
    assert classify_pair(persists, set(), notes=notes) == DOCUMENTED
    assert classify_pair(persists, set(), notes=other) == UNEXPLAINED
