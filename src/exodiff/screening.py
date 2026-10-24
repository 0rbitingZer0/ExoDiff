from __future__ import annotations

import hashlib
import itertools
import math
from typing import Any

import pandas as pd

from .references import parse_reference

NOMINAL_SOLAR_RADIUS_M = 6.957e8
NOMINAL_EARTH_EQUATORIAL_RADIUS_M = 6.3781e6
SOLAR_TO_EARTH_RADII = NOMINAL_SOLAR_RADIUS_M / NOMINAL_EARTH_EQUATORIAL_RADIUS_M

CONFIRMED_SOLTYPES = {"Published Confirmed"}

OPTIONAL_COLUMNS = {"tran_flag", "pl_ratror", "pl_ratrorerr1", "pl_ratrorerr2", "pl_ratrorlim",
                    "pl_bmasse", "pl_dens", "pl_orbsmax", "pl_orbper", "pl_ratdor", "st_mass", "pl_orbeccen",
                    "sy_dist", "sy_plx", "sy_plxerr1"}

REQUIRED_COLUMNS = {
    "pl_name", "hostname", "soltype", "pl_rade", "pl_radeerr1", "pl_radeerr2",
    "pl_radelim", "pl_refname", "pl_pubdate", "default_flag", "pl_controv_flag",
    "st_rad", "st_raderr1", "st_raderr2", "st_refname", "discoverymethod", "disc_year"
}


def _num(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        result = float(value)
        if not math.isfinite(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _row_exclusion_reasons(row: pd.Series) -> list[str]:
    reasons = []
    planet = _text(row.get("pl_name"))
    ref = _text(row.get("pl_refname"))
    value = _num(row.get("pl_rade"))
    plus_raw = _num(row.get("pl_radeerr1"))
    minus_raw = _num(row.get("pl_radeerr2"))
    if not planet:
        reasons.append("missing_planet_name")
    if not ref:
        reasons.append("missing_parameter_reference")
    if value is None:
        reasons.append("missing_or_nonfinite_radius")
    elif value <= 0:
        reasons.append("nonpositive_radius")
    limit_flag = _num(row.get("pl_radelim"))
    if limit_flag is None:
        reasons.append("unknown_radius_limit_flag")
    elif limit_flag != 0.0:
        reasons.append("radius_marked_as_limit")
    if plus_raw is None or minus_raw is None:
        reasons.append("missing_or_nonfinite_uncertainty")
    else:
        if abs(plus_raw) <= 0 or abs(minus_raw) <= 0:
            reasons.append("zero_uncertainty")
    soltype = _text(row.get("soltype"))
    if soltype not in CONFIRMED_SOLTYPES:
        reasons.append("not_explicitly_marked_confirmed")
    return reasons


def _row_to_measurement(row: pd.Series) -> dict | None:
    if _row_exclusion_reasons(row):
        return None
    planet = _text(row.get("pl_name"))
    ref = _text(row.get("pl_refname"))
    value = _num(row.get("pl_rade"))
    plus_raw = _num(row.get("pl_radeerr1"))
    minus_raw = _num(row.get("pl_radeerr2"))
    assert value is not None and plus_raw is not None and minus_raw is not None
    plus, minus = abs(plus_raw), abs(minus_raw)
    soltype = _text(row.get("soltype"))
    planet_ref = parse_reference(ref)
    stellar_ref_text = _text(row.get("st_refname"))
    stellar_ref = parse_reference(stellar_ref_text)
    if planet_ref["refstr"] and stellar_ref["refstr"]:
        stellar_ref_matches = planet_ref["refstr"] == stellar_ref["refstr"]
    else:
        stellar_ref_matches = bool(stellar_ref_text) and stellar_ref_text == ref
    ratio = _num(row.get("pl_ratror"))
    ratio_plus = _num(row.get("pl_ratrorerr1"))
    ratio_minus = _num(row.get("pl_ratrorerr2"))
    if not (ratio and ratio > 0 and _num(row.get("pl_ratrorlim")) == 0.0
            and ratio_plus and ratio_minus):
        ratio = ratio_plus = ratio_minus = None
    return {
        "planet": planet,
        "host": _text(row.get("hostname")),
        "soltype": soltype,
        "default_flag": _text(row.get("default_flag")),
        "controversial_flag": _text(row.get("pl_controv_flag")),
        "value": value,
        "err_plus": plus,
        "err_minus": minus,
        "limit_flag": _num(row.get("pl_radelim")),
        "reference": ref,
        "reference_label": planet_ref["label"],
        "reference_bibcode": planet_ref["bibcode"],
        "reference_url": planet_ref["url"],
        "reference_key": planet_ref["bibcode"] or planet_ref["refstr"] or planet_ref["label"] or ref,
        "publication_date": _text(row.get("pl_pubdate")),
        "stellar_radius_solar": _num(row.get("st_rad")),
        "stellar_radius_err_plus": _num(row.get("st_raderr1")),
        "stellar_radius_err_minus": _num(row.get("st_raderr2")),
        "stellar_reference": stellar_ref_text,
        "stellar_reference_label": stellar_ref["label"],
        "stellar_reference_matches_planet_reference": stellar_ref_matches,
        "transit_flag": _num(row.get("tran_flag")),
        "ratio": ratio,
        "ratio_err_plus": abs(ratio_plus) if ratio_plus else None,
        "ratio_err_minus": abs(ratio_minus) if ratio_minus else None,
        "discovery_method": _text(row.get("discoverymethod")),
        "discovery_year": _text(row.get("disc_year")),
    }


def _interval(m: dict) -> tuple[float, float]:
    return (m["value"] - m["err_minus"], m["value"] + m["err_plus"])


def _ratio_consistency_pct(m: dict) -> float | None:
    star, ratio = _num(m["stellar_radius_solar"]), _num(m["ratio"])
    if not ratio or not star or star <= 0:
        return None
    return 100.0 * (m["value"] / (ratio * star * SOLAR_TO_EARTH_RADII) - 1.0)


def stellar_rescaling(a: dict, b: dict) -> dict:
    rs_a, rs_b = _num(a["stellar_radius_solar"]), _num(b["stellar_radius_solar"])
    flags = (_num(a["transit_flag"]), _num(b["transit_flag"]))
    result = {
        "stellar_rescaling_outcome": "stellar_radius_unavailable",
        "stellar_radius_ratio_b_over_a": None,
        "planet_radius_ratio_b_over_a": b["value"] / a["value"],
        "stellar_share_of_log_radius_change": None,
        "implied_rp_rs_relative_difference_pct": None,
        "radius_a_rescaled_to_star_b_rearth": None,
        "radius_b_rescaled_to_star_a_rearth": None,
        "both_rows_transiting": None if None in flags else (flags == (1.0, 1.0)),
        "stellar_refs_match_planet_refs": bool(
            a["stellar_reference_matches_planet_reference"]
            and b["stellar_reference_matches_planet_reference"]
        ),
    }
    if not rs_a or not rs_b or rs_a <= 0 or rs_b <= 0:
        return result
    star_ratio = rs_b / rs_a
    result["stellar_radius_ratio_b_over_a"] = star_ratio
    k_a, k_b = a["value"] / rs_a, b["value"] / rs_b
    result["implied_rp_rs_relative_difference_pct"] = 100.0 * abs(k_a - k_b) / ((k_a + k_b) / 2.0)
    log_planet = math.log(b["value"] / a["value"])
    if log_planet != 0:
        result["stellar_share_of_log_radius_change"] = math.log(star_ratio) / log_planet
    if rs_a == rs_b:
        result["stellar_rescaling_outcome"] = "same_stellar_radius"
        return result
    a_scaled, b_scaled = a["value"] * star_ratio, b["value"] / star_ratio
    result["radius_a_rescaled_to_star_b_rearth"] = a_scaled
    result["radius_b_rescaled_to_star_a_rearth"] = b_scaled
    lo_a, hi_a = _interval(a)
    lo_b, hi_b = _interval(b)
    hits = (lo_b <= a_scaled <= hi_b) + (lo_a <= b_scaled <= hi_a)
    result["stellar_rescaling_outcome"] = (
        "persists_after_stellar_rescaling",
        "partly_consistent_after_stellar_rescaling",
        "consistent_after_stellar_rescaling",
    )[hits]
    return result


def published_ratio_comparison(a: dict, b: dict) -> dict:
    k_a, k_b = _num(a["ratio"]), _num(b["ratio"])
    if not k_a or not k_b:
        return {"published_rp_rs_intervals_overlap": None, "published_rp_rs_relative_difference_pct": None}
    lo_a, hi_a = k_a - a["ratio_err_minus"], k_a + a["ratio_err_plus"]
    lo_b, hi_b = k_b - b["ratio_err_minus"], k_b + b["ratio_err_plus"]
    return {
        "published_rp_rs_intervals_overlap": max(lo_a, lo_b) <= min(hi_a, hi_b),
        "published_rp_rs_relative_difference_pct": 100.0 * abs(k_a - k_b) / ((k_a + k_b) / 2.0),
    }


def compare_measurements(a: dict, b: dict) -> dict:
    lo_a, hi_a = _interval(a)
    lo_b, hi_b = _interval(b)
    edge_gap = max(lo_a, lo_b) - min(hi_a, hi_b)
    overlap = edge_gap <= 1e-9 * max(abs(hi_a), abs(hi_b), 1.0)
    interval_gap = 0.0 if overlap else edge_gap
    mean_scale = (abs(a["value"]) + abs(b["value"])) / 2.0
    relative_difference_pct = 100.0 * abs(a["value"] - b["value"]) / mean_scale if mean_scale else None

    if a["value"] >= b["value"]:
        edge_unc_a, edge_unc_b = a["err_minus"], b["err_plus"]
    else:
        edge_unc_a, edge_unc_b = a["err_plus"], b["err_minus"]
    denominator = math.sqrt(edge_unc_a ** 2 + edge_unc_b ** 2)
    gap_over_combined_edge_error = interval_gap / denominator if denominator > 0 else None

    def _digest(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]

    candidate_id = _digest(a["planet"] + "|" + "|".join(sorted([a["reference_key"], b["reference_key"]])))
    content_hash = _digest(a["planet"] + "|" + "|".join(sorted(
        f'{m["reference_key"]}: {m["value"]:.12g}: {m["err_minus"]:.12g}: {m["err_plus"]:.12g}' for m in (a, b)
    )))

    return {
        "candidate_id": candidate_id,
        "content_hash": content_hash,
        "pl_name": a["planet"],
        "hostname": a["host"] or b["host"],
        "discovery_method": a["discovery_method"] or b["discovery_method"],
        "discovery_year": a["discovery_year"] or b["discovery_year"],
        "reference_a": a["reference"],
        "reference_label_a": a["reference_label"],
        "reference_bibcode_a": a["reference_bibcode"],
        "reference_url_a": a["reference_url"],
        "publication_date_a": a["publication_date"],
        "radius_a_rearth": a["value"],
        "error_minus_a_rearth": a["err_minus"],
        "error_plus_a_rearth": a["err_plus"],
        "stellar_radius_a_rsun": a["stellar_radius_solar"],
        "stellar_reference_a": a["stellar_reference_label"] or a["stellar_reference"],
        "rp_vs_rp_rs_times_rs_deviation_pct_a": _ratio_consistency_pct(a),
        "default_flag_a": a["default_flag"],
        "reference_b": b["reference"],
        "reference_label_b": b["reference_label"],
        "reference_bibcode_b": b["reference_bibcode"],
        "reference_url_b": b["reference_url"],
        "publication_date_b": b["publication_date"],
        "radius_b_rearth": b["value"],
        "error_minus_b_rearth": b["err_minus"],
        "error_plus_b_rearth": b["err_plus"],
        "stellar_radius_b_rsun": b["stellar_radius_solar"],
        "stellar_reference_b": b["stellar_reference_label"] or b["stellar_reference"],
        "rp_vs_rp_rs_times_rs_deviation_pct_b": _ratio_consistency_pct(b),
        "default_flag_b": b["default_flag"],
        "intervals_overlap": bool(overlap),
        "reported_interval_gap_rearth": interval_gap,
        "gap_divided_by_combined_edge_error": gap_over_combined_edge_error,
        "relative_difference_pct": relative_difference_pct,
        **stellar_rescaling(a, b),
        **published_ratio_comparison(a, b),
        "screening_reason": (
            "reported intervals do not overlap; check methods, uncertainty conventions, "
            "shared data and source papers"
            if not overlap else
            "central values differ but reported intervals overlap; review only if other context warrants it"
        ),
        "methodology_warning": (
            "Triage only. Published intervals may not use comparable confidence levels; "
            "measurements may share data/assumptions; not a significance test and not evidence of an error."
        ),
    }


def screen_radius_solutions(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError("Input is missing expected NASA columns: " + ", ".join(missing))

    stats = {
        "input_rows": int(len(frame)),
        "rows_with_radius": int(frame["pl_rade"].notna().sum()),
        "comparison_scope": "confirmed solutions with positive radius, explicitly non-limit radius flag, positive two-sided errors, and non-empty parameter reference",
        "excluded_reasons_are_conservative": True,
        "candidate_pair_count": 0,
        "planets_considered": 0,
        "planets_with_multiple_references": 0,
        "planets_excluded_for_multiple_distinct_rows_same_reference": 0,
        "row_exclusion_reason_counts": {},
        "note": "Exclusion reason counts overlap: a single row can have more than one reason. All output pairs are candidates for human review, not errors, discoveries, or statistically significant disagreements.",
    }

    exclusion_counts: dict[str, int] = {}
    measurements: list[dict] = []
    for _, row in frame.iterrows():
        reasons = _row_exclusion_reasons(row)
        if reasons:
            for reason in reasons:
                exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1
            continue
        candidate = _row_to_measurement(row)
        if candidate is not None:
            measurements.append(candidate)
    stats["row_exclusion_reason_counts"] = dict(sorted(exclusion_counts.items()))

    if not measurements:
        stats["valid_comparison_rows"] = 0
        return pd.DataFrame(), stats

    mframe = pd.DataFrame(measurements)
    stats["valid_comparison_rows"] = int(len(mframe))
    pairs = []
    ambiguous_planets = 0

    for planet, group in mframe.groupby("planet", sort=True):
        distinct = group.drop_duplicates(subset=[
            "reference", "value", "err_plus", "err_minus", "limit_flag",
            "stellar_radius_solar", "stellar_radius_err_plus", "stellar_radius_err_minus",
            "stellar_reference"
        ])
        rows_per_reference = distinct.groupby("reference").size()
        if (rows_per_reference > 1).any():
            ambiguous_planets += 1
            continue
        distinct = distinct.drop_duplicates(subset=["reference"], keep="first")
        if len(distinct) < 2:
            continue
        stats["planets_considered"] += 1
        stats["planets_with_multiple_references"] += 1
        records = distinct.to_dict("records")
        for a, b in itertools.combinations(records, 2):
            if a["reference"] == b["reference"]:
                continue
            if (b["publication_date"], b["reference"]) < (a["publication_date"], a["reference"]):
                a, b = b, a
            pairs.append(compare_measurements(a, b))

    stats["planets_excluded_for_multiple_distinct_rows_same_reference"] = ambiguous_planets
    result = pd.DataFrame(pairs)
    stats["candidate_pair_count"] = int(len(result))
    if len(result):
        result["planet_pair_count"] = result.groupby("pl_name")["pl_name"].transform("size")
        result = result.sort_values(
            by=["intervals_overlap", "gap_divided_by_combined_edge_error", "relative_difference_pct", "candidate_id"],
            ascending=[True, False, False, True],
            na_position="last",
            kind="mergesort",
        ).reset_index(drop=True)
        result.insert(1, "review_rank", range(1, len(result) + 1))
        nonoverlap = result[~result["intervals_overlap"]]
        stats["non_overlapping_pair_count"] = int(len(nonoverlap))
        stats["non_overlapping_planet_count"] = int(nonoverlap["pl_name"].nunique())
        stats["stellar_rescaling_outcomes_non_overlapping_pairs"] = {
            str(k): int(v) for k, v in sorted(nonoverlap["stellar_rescaling_outcome"].value_counts().items())
        }
    return result, stats
