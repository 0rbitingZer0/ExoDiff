from __future__ import annotations

import pandas as pd

from .known_notes import documented, load_all_notes

AGREES = "agrees_within_reported_errors"
NOT_COMPARABLE = "not_comparable_non_transiting"
EXPLAINED_STELLAR = "explained_stellar_radius_published_values"
PLAUSIBLY_STELLAR = "plausibly_stellar_radius_archive_only"
UNEXPLAINED = "unexplained"
NOT_CHECKABLE = "not_checkable_no_stellar_radius"
DOCUMENTED = "documented_by_nasa"

SET_ASIDE = {NOT_COMPARABLE, EXPLAINED_STELLAR, DOCUMENTED}

REASONS = {
    AGREES: "Reported intervals overlap; not a discrepancy for this site.",
    NOT_COMPARABLE: "At least one row has tran_flag = 0, so its radius is not a transit measurement and the Rp = (Rp/R*) × R* comparison does not apply.",
    EXPLAINED_STELLAR: "Both papers publish Rp/R* values whose intervals overlap, both rows take R* from the same paper as Rp, and rescaling each radius to the other paper's stellar radius lands inside the other's interval. The papers' own numbers show the difference comes from the adopted stellar radius.",
    PLAUSIBLY_STELLAR: "Rescaling to the other row's stellar radius closes the gap, but the papers' published Rp/R* values are missing, disagree, or the stellar radius is from another reference, so the cause is not confirmed.",
    UNEXPLAINED: "Checked and not explained: a change in the adopted stellar radius does not account for the difference.",
    DOCUMENTED: "NASA's literature-discrepancy table already documents an issue with this planet's radius, transit depth or planet naming (see the note on the entry).",
    NOT_CHECKABLE: "Not checked: at least one row has no stellar radius, so the stellar-radius explanation could not be tested.",
}


def _true(value) -> bool:
    return value is not None and not pd.isna(value) and bool(value)


def classify_pair(pair: dict, inconsistent_rows: set, consistent_rows: set | None = None, notes: dict | None = None) -> str:
    if _true(pair.get("intervals_overlap")):
        return AGREES
    transiting = pair.get("both_rows_transiting")
    if transiting is not None and not pd.isna(transiting) and not transiting:
        return NOT_COMPARABLE
    if notes and documented(pair["pl_name"], "pair_radius", notes):
        return DOCUMENTED
    keys = {(pair["pl_name"], pair["reference_a"]), (pair["pl_name"], pair["reference_b"])}
    rows_ok = not (keys & inconsistent_rows) and (consistent_rows is None or keys <= consistent_rows)
    rescaled = pair.get("stellar_rescaling_outcome") == "consistent_after_stellar_rescaling"
    if (rescaled and rows_ok and _true(pair.get("published_rp_rs_intervals_overlap"))
            and _true(pair.get("stellar_refs_match_planet_refs"))):
        return EXPLAINED_STELLAR
    if rescaled:
        return PLAUSIBLY_STELLAR
    if pair.get("stellar_rescaling_outcome") == "stellar_radius_unavailable":
        return NOT_CHECKABLE
    return UNEXPLAINED


def triage_pairs(pairs: pd.DataFrame, row_check: pd.DataFrame, notes: dict | None = None) -> tuple[pd.DataFrame, dict]:
    inconsistent, consistent = set(), set()
    if len(row_check):
        leads = row_check[row_check["is_lead"]]
        inconsistent = set(zip(leads["pl_name"], leads["pl_refname"]))
        within = row_check[~row_check["beyond_rounding_and_units"].astype(bool)]
        consistent = set(zip(within["pl_name"], within["pl_refname"]))
    out = pairs.copy()
    if out.empty:
        return out, {}
    records = out.to_dict("records")
    notes = load_all_notes() if notes is None else notes
    out["triage_tier"] = [classify_pair(r, inconsistent, consistent, notes) for r in records]
    out["triage_reason"] = out["triage_tier"].map(REASONS)
    out["triage_set_aside"] = out["triage_tier"].isin(SET_ASIDE)
    out["involves_self_inconsistent_row"] = [
        bool({(r["pl_name"], r["reference_a"]), (r["pl_name"], r["reference_b"])} & inconsistent) for r in records
    ]
    shown = out[out["triage_tier"] != AGREES]
    stats = {
        "tiers_non_overlapping_pairs": {k: int(v) for k, v in sorted(shown["triage_tier"].value_counts().items())},
        "tiers_non_overlapping_planets": {k: int(v) for k, v in sorted(shown.groupby("triage_tier")["pl_name"].nunique().items())},
        "pairs_involving_self_inconsistent_row": int(shown["involves_self_inconsistent_row"].sum()),
    }
    return out, stats
