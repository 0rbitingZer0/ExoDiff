from __future__ import annotations

import pandas as pd

from .references import parse_reference
from .screening import SOLAR_TO_EARTH_RADII, _num, _row_exclusion_reasons, _text

EARTH_RADIUS_CONVENTION_ALLOWANCE = 6.3781e6 / 6371008.7714 - 1.0


def _decimals(value: float) -> int:
    text = repr(float(value))
    if "e" in text or "E" in text:
        mantissa, exponent = text.lower().split("e")
        places = len(mantissa.split(".")[1]) if "." in mantissa else 0
        return max(0, places - int(exponent))
    return len(text.split(".")[1]) if "." in text else 0


def rounding_allowance(*values: float) -> float:
    return sum(0.5 * 10 ** (-_decimals(v)) / abs(v) for v in values)


def input_uncertainty(row, inputs: dict) -> tuple[float, list]:
    total, assumed = 0.0, []
    for column, exponent in inputs.items():
        value = _num(row.get(column))
        plus, minus = _num(row.get(column + "err1")), _num(row.get(column + "err2"))
        errors = [abs(e) for e in (plus, minus) if e]
        if not value or not errors:
            assumed.append(column)
            continue
        total += (exponent * (sum(errors) / len(errors)) / abs(value)) ** 2
    return total ** 0.5, assumed


def combined_tolerance(own_error: float, implied: float, relative_input_error: float) -> float:
    return (own_error ** 2 + (implied * relative_input_error) ** 2) ** 0.5


def row_self_consistency(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    records = []
    skipped = {"not_eligible_for_screening": 0, "no_published_rp_rs": 0, "no_stellar_radius": 0}
    for _, row in frame.iterrows():
        if _row_exclusion_reasons(row):
            skipped["not_eligible_for_screening"] += 1
            continue
        ratio = _num(row.get("pl_ratror"))
        if not ratio or ratio <= 0 or _num(row.get("pl_ratrorlim")) != 0.0:
            skipped["no_published_rp_rs"] += 1
            continue
        star = _num(row.get("st_rad"))
        if not star or star <= 0:
            skipped["no_stellar_radius"] += 1
            continue
        radius = _num(row["pl_rade"])
        predicted = ratio * star * SOLAR_TO_EARTH_RADII
        mismatch = radius - predicted
        own_error = abs(_num(row["pl_radeerr2"]) if mismatch > 0 else _num(row["pl_radeerr1"]))
        allowance = rounding_allowance(radius, ratio, star) + EARTH_RADIUS_CONVENTION_ALLOWANCE
        rel_in, assumed = input_uncertainty(row, {"pl_ratror": 1, "st_rad": 1})
        tolerance = combined_tolerance(own_error, predicted, rel_in)
        ref = parse_reference(_text(row.get("pl_refname")))
        stellar_ref = parse_reference(_text(row.get("st_refname")))
        relative = mismatch / predicted
        records.append({
            "pl_name": _text(row.get("pl_name")),
            "hostname": _text(row.get("hostname")),
            "pl_refname": _text(row.get("pl_refname")),
            "reference": ref["label"],
            "reference_bibcode": ref["bibcode"],
            "reference_url": ref["url"],
            "stellar_reference": stellar_ref["label"],
            "stellar_reference_matches_planet_reference": bool(ref["refstr"]) and ref["refstr"] == stellar_ref["refstr"],
            "pl_rade": radius,
            "pl_radeerr1": _num(row["pl_radeerr1"]),
            "pl_radeerr2": _num(row["pl_radeerr2"]),
            "pl_ratror": ratio,
            "st_rad": star,
            "rp_from_ratio_times_star_rearth": predicted,
            "mismatch_pct": 100.0 * relative,
            "allowance_pct": 100.0 * allowance,
            "mismatch_in_own_error_bars": abs(mismatch) / own_error,
            "mismatch_in_error_bars": abs(mismatch) / tolerance,
            "assumed_inputs": ",".join(assumed),
            "beyond_rounding_and_units": abs(relative) > allowance,
            "beyond_own_error_bar": abs(mismatch) > own_error,
            "beyond_all_errors": abs(mismatch) > tolerance and not assumed,
        })
    result = pd.DataFrame(records)
    if len(result):
        per_paper = result.groupby(["pl_name", "pl_refname"])["pl_name"].transform("size")
        result["archive_rows_for_this_paper"] = per_paper
    stats = {"checkable_rows": int(len(result)), "skipped_rows": skipped, "lead_rows": 0}
    if len(result):
        result["is_lead"] = result["beyond_rounding_and_units"] & result["beyond_all_errors"]
        result = result.sort_values(
            ["is_lead", "mismatch_in_error_bars", "pl_name", "pl_refname", "pl_rade"],
            ascending=[False, False, True, True, True], kind="mergesort",
        ).reset_index(drop=True)
        stats["lead_rows"] = int(result["is_lead"].sum())
        stats["median_abs_mismatch_pct"] = float(result["mismatch_pct"].abs().median())
    stats["rule"] = (
        "Lead when |pl_rade − pl_ratror × st_rad × R☉/R⊕| exceeds both the rounding of the published "
        "digits plus the Earth-radius convention allowance (0.111%), and the row's own pl_rade error bar "
        "on the side facing the predicted value."
    )
    return result, stats

