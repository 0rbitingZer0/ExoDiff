from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from .consistency import EARTH_RADIUS_CONVENTION_ALLOWANCE, _decimals, combined_tolerance, input_uncertainty
from .references import parse_reference
from .screening import CONFIRMED_SOLTYPES, _num, _text

GM_SUN = 1.3271244e20
GM_EARTH = 3.986004e14
G = 6.67430e-11
R_SUN = 6.957e8
R_EARTH = 6.3781e6
AU = 149_597_870_700.0
DAY = 86_400.0
EARTH_MASS_KG = GM_EARTH / G
EARTH_DENSITY_UNIT_G_CM3 = EARTH_MASS_KG / (4.0 / 3.0 * math.pi * R_EARTH ** 3) / 1000.0
EARTH_TO_SUN_MASS = GM_EARTH / GM_SUN
AU_IN_SUN_RADII = AU / R_SUN

PROJECTED_SEPARATION_METHODS = {"Microlensing", "Imaging"}


@dataclass(frozen=True)
class Identity:
    key: str
    label: str
    formula: str
    unit: str
    listed: str
    inputs: dict
    predict: Callable[[dict], float]
    convention_allowance: float
    convention_note: str
    citation: str
    extra_limits: tuple = ()
    applies: Callable[[pd.Series], str | None] = field(default=lambda row: None)


def _skip_projected(row: pd.Series) -> str | None:
    if _text(row.get("discoverymethod")) in PROJECTED_SEPARATION_METHODS:
        return "projected_separation"
    return "circumbinary" if _num(row.get("cb_flag")) == 1.0 else None


def _skip_not_true_mass(row: pd.Series) -> str | None:
    return None if _text(row.get("pl_bmassprov")) == "Mass" else "mass_is_minimum_or_unknown"


def _skip_eccentric(row: pd.Series) -> str | None:
    reason = _skip_projected(row)
    if reason:
        return reason
    e = _num(row.get("pl_orbeccen"))
    return None if e == 0.0 else "eccentric_or_unreported"


def _kepler_a(v: dict) -> float:
    planet_mass_sun = (v.get("pl_bmasse") or 0.0) * EARTH_TO_SUN_MASS
    gm = GM_SUN * (v["st_mass"] + planet_mass_sun)
    return (gm * (v["pl_orbper"] * DAY) ** 2 / (4 * math.pi ** 2)) ** (1 / 3) / AU


IDENTITIES = (
    Identity(
        key="density",
        label="density vs mass and radius",
        formula="density = mass ÷ (4/3 π radius³)",
        unit="g/cm³",
        listed="pl_dens",
        inputs={"pl_bmasse": 1, "pl_rade": 3},
        predict=lambda v: EARTH_DENSITY_UNIT_G_CM3 * v["pl_bmasse"] / v["pl_rade"] ** 3,
        convention_allowance=3 * EARTH_RADIUS_CONVENTION_ALLOWANCE,
        convention_note="Earth equatorial vs mean radius, cubed (about 0.33%)",
        citation="definition of mean density; constants IAU 2015 B3, CODATA 2022",
        extra_limits=("pl_bmasselim", "pl_radelim"),
        applies=_skip_not_true_mass,
    ),
    Identity(
        key="kepler",
        label="orbit size vs period and star mass",
        formula="orbit size³ = G × (star mass + planet mass) × period² ÷ 4π²  (Kepler's third law)",
        unit="au",
        listed="pl_orbsmax",
        inputs={"st_mass": 1 / 3, "pl_orbper": 2 / 3},
        predict=_kepler_a,
        convention_allowance=0.001,
        convention_note="planet mass ignored when the row gives none (under 0.1% up to ~3 Jupiter masses per solar mass)",
        citation="Kepler's third law with Newton's correction; GM_sun IAU 2015 B3; au IAU 2012 B2",
        extra_limits=("st_masslim", "pl_orbperlim"),
        applies=_skip_projected,
    ),
    Identity(
        key="a_over_rstar",
        label="orbit size ÷ star size vs the published ratio",
        formula="a/R* = orbit size ÷ star radius  (circular orbits only)",
        unit="(ratio)",
        listed="pl_ratdor",
        inputs={"pl_orbsmax": 1, "st_rad": 1},
        predict=lambda v: v["pl_orbsmax"] * AU_IN_SUN_RADII / v["st_rad"],
        convention_allowance=0.0005,
        convention_note="older solar-radius values (695,508–696,000 km vs 695,700 km nominal)",
        citation="archive definition of pl_ratdor (distance at mid-transit ÷ R*); IAU 2015 B3, IAU 2012 B2",
        extra_limits=("pl_orbsmaxlim", "st_radlim"),
        applies=_skip_eccentric,
    ),
)


def _rounding(values: dict, exponents: dict) -> float:
    return sum(abs(exponents.get(c, 1)) * 0.5 * 10 ** (-_decimals(v)) / abs(v) for c, v in values.items())


def check_identity(frame: pd.DataFrame, identity: Identity) -> tuple[pd.DataFrame, dict]:
    listed, err1, err2 = identity.listed, identity.listed + "err1", identity.listed + "err2"
    needed = {listed, err1, err2, identity.listed + "lim", *identity.inputs, *identity.extra_limits}
    missing = sorted(needed - set(frame.columns))
    if missing:
        return pd.DataFrame(), {"checkable_rows": 0, "lead_rows": 0, "missing_columns": missing}
    skipped: dict[str, int] = {}
    records = []
    for _, row in frame.iterrows():
        def skip(reason):
            skipped[reason] = skipped.get(reason, 0) + 1
        if _text(row.get("soltype")) not in CONFIRMED_SOLTYPES or not _text(row.get("pl_refname")):
            skip("not_confirmed_or_no_reference"); continue
        if any(_num(row.get(c)) != 0.0 for c in (identity.listed + "lim", *identity.extra_limits)):
            skip("limit_or_unknown_flag"); continue
        value, plus, minus = _num(row.get(listed)), _num(row.get(err1)), _num(row.get(err2))
        if not value or value <= 0 or not plus or not minus:
            skip("listed_value_or_error_missing"); continue
        inputs = {c: _num(row.get(c)) for c in identity.inputs}
        if any(v is None or v <= 0 for v in inputs.values()):
            skip("input_missing"); continue
        reason = identity.applies(row)
        if reason:
            skip(reason); continue
        values = dict(inputs)
        if identity.key == "kepler":
            mass = _num(row.get("pl_bmasse"))
            values["pl_bmasse"] = mass if mass and mass > 0 and _num(row.get("pl_bmasselim")) == 0.0 else None
        predicted = identity.predict(values)
        mismatch = value - predicted
        own = abs(minus if mismatch > 0 else plus)
        rel_in, assumed = input_uncertainty(row, identity.inputs)
        tolerance = combined_tolerance(own, predicted, rel_in)
        allowance = _rounding({listed: value, **inputs}, identity.inputs) + identity.convention_allowance
        ref = parse_reference(_text(row.get("pl_refname")))
        records.append({
            "check": identity.key,
            "pl_name": _text(row.get("pl_name")),
            "pl_refname": _text(row.get("pl_refname")),
            "reference": ref["label"],
            "reference_bibcode": ref["bibcode"],
            "reference_url": ref["url"],
            "listed_value": value,
            "listed_err1": plus,
            "listed_err2": -abs(minus),
            "implied_value": predicted,
            "inputs": {c: v for c, v in inputs.items()},
            "mismatch_pct": 100.0 * mismatch / predicted,
            "allowance_pct": 100.0 * allowance,
            "mismatch_in_own_error_bars": abs(mismatch) / own,
            "mismatch_in_error_bars": abs(mismatch) / tolerance,
            "assumed_inputs": ",".join(assumed),
            "beyond_all_errors": abs(mismatch) > tolerance and not assumed,
            "beyond_rounding_and_units": abs(mismatch / predicted) > allowance,
            "beyond_own_error_bar": abs(mismatch) > own,
        })
    result = pd.DataFrame(records)
    stats = {"checkable_rows": int(len(result)), "lead_rows": 0, "skipped_rows": dict(sorted(skipped.items()))}
    if len(result):
        result["is_lead"] = result["beyond_rounding_and_units"] & result["beyond_all_errors"]
        result["archive_rows_for_this_paper"] = result.groupby(["pl_name", "pl_refname"])["pl_name"].transform("size")
        result = result.sort_values(["is_lead", "mismatch_in_error_bars", "pl_name", "pl_refname"],
                                    ascending=[False, False, True, True], kind="mergesort").reset_index(drop=True)
        stats["lead_rows"] = int(result["is_lead"].sum())
        stats["median_abs_mismatch_pct"] = float(result["mismatch_pct"].abs().median())
    return result, stats


def identity_checks(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    parts, stats = [], {}
    for identity in IDENTITIES:
        result, s = check_identity(frame, identity)
        stats[identity.key] = {**s, "label": identity.label, "formula": identity.formula, "unit": identity.unit,
                               "convention_note": identity.convention_note, "citation": identity.citation}
        if len(result):
            parts.append(result)
    return (pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()), stats
