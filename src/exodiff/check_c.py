from __future__ import annotations

import re

import pandas as pd

from .check_a import JUPITER_IN_EARTH_MASSES, MASS_CONVENTION_ALLOWANCE
from .consistency import _decimals
from .gaia import apart
from . import wording
from .references import parse_reference
from .screening import _num, _text

FIELDS = {
    "radius": ("pl_rade", "pl_rade", "radius", "Earths"),
    "mass": ("planet_mass", "pl_bmasse", "mass", "Earths"),
    "period": ("pl_orbper", "pl_orbper", "orbital period", "days"),
    "orbit": ("pl_orbsmax", "pl_orbsmax", "orbit size", "au"),
    "eccentricity": ("eccentricity", "pl_orbeccen", "eccentricity", ""),
    "distance": ("st_dist", "sy_dist", "distance", "parsecs"),
}
FINE_WHEN = {b: wording.means(f"C/{b}") for b in ("C-default", "C-composite", "C-other", "C-none", "C-survey", "C-absent", "C-estimate")}
SURVEY_GAP = 0.05
_MASS = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*(Earths?|Jupiters?)\s*$", re.IGNORECASE)


def _tolerance(text_or_number) -> float | None:
    number = _num(text_or_number)
    return None if number is None else 0.5 * 10 ** (-_decimals(number))


def public_value(field: str, acf: dict) -> dict | None:
    key = FIELDS[field][0]
    raw = acf.get(key)
    if field == "mass":
        m = _MASS.match(str(raw or ""))
        if not m:
            return None
        number, unit = float(m.group(1)), m.group(2).lower()
        factor = JUPITER_IN_EARTH_MASSES if unit.startswith("jupiter") else 1.0
        decimals = len(m.group(1).split(".")[1]) if "." in m.group(1) else 0
        tolerance = 0.5 * 10 ** -decimals * factor
        if factor != 1.0:
            tolerance += MASS_CONVENTION_ALLOWANCE * number * factor
        jupiter = {"value": number, "tolerance": 0.5 * 10 ** -decimals} if factor != 1.0 else None
        return {"value": number * factor, "tolerance": tolerance, "display": str(raw), "limit": False, "jupiter": jupiter}
    if field == "eccentricity":
        display = str(acf.get("eccentricity") or "").strip()
        if not display:
            return None
        if display.startswith("<"):
            limit = _num(acf.get("pl_eccenlim"))
            if limit is None:
                return None
            tolerance = _tolerance(display.lstrip("< ").strip() or None)
            if tolerance is None:
                return None
            return {"value": limit, "tolerance": tolerance, "display": display, "limit": True}
        number = _num(display)
        if number is None:
            return None
        return {"value": number, "tolerance": _tolerance(display), "display": display, "limit": False}
    number = _num(raw) if not isinstance(raw, str) else _num(raw.strip() or None)
    if number is None or isinstance(raw, bool):
        return None
    return {"value": number, "tolerance": _tolerance(number), "display": str(raw), "limit": False}


def _matches(public: dict, archive_value) -> bool:
    a = _num(archive_value)
    return a is not None and abs(a - public["value"]) <= public["tolerance"] * (1 + 1e-9) + 1e-12


def _row_matches(public: dict, row, column: str) -> bool:
    if row is None:
        return False
    if _matches(public, row.get(column)):
        return True
    jupiter = public.get("jupiter")
    return bool(jupiter) and column == "pl_bmasse" and _matches(jupiter, row.get("pl_bmassj"))


def check_c(join: dict, archive: pd.DataFrame, composite: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows_by_planet = {name: group for name, group in archive.groupby("pl_name")}
    comp = composite.set_index("pl_name")
    out = []
    for planet in sorted(set(join["matched"]) | set(join["archive_only"])):
        page = join["matched"].get(planet)
        group = rows_by_planet.get(planet)
        default = group[group["default_flag"] == 1].iloc[0] if group is not None and (group["default_flag"] == 1).any() else None
        comp_row = comp.loc[planet] if planet in comp.index else None
        for field, (_, column, name, unit) in FIELDS.items():
            record = {"pl_name": planet, "field": field, "field_name": name, "unit": unit,
                      "page": page["link"] if page else None, "public_display": None, "public_value": None,
                      "default_value": _num(default.get(column)) if default is not None else None,
                      "default_reference": parse_reference(_text(default.get("pl_refname")))["label"] if default is not None else None,
                      "composite_value": _num(comp_row.get(column)) if comp_row is not None else None,
                      "matched_reference": None, "labels": []}
            if page is None:
                record.update(bucket="C-absent", reason="no public page yet")
                out.append(record)
                continue
            public = public_value(field, page["acf"])
            archive_values = [v for v in [record["default_value"], record["composite_value"]] +
                              ([_num(v) for v in group[column]] if group is not None else []) if v is not None]
            if public is None or not archive_values:
                record.update(bucket="C-absent", reason="the page shows no value" if public is None else "the archive has no value",
                              public_display=public["display"] if public else None, public_value=public["value"] if public else None)
                out.append(record)
                continue
            record.update(public_display=public["display"], public_value=public["value"])
            if field == "eccentricity":
                archive_limit = default is not None and _num(default.get("pl_orbeccenlim")) not in (None, 0.0)
                if public["limit"] != archive_limit:
                    record["labels"].append("limit shown differently: " + ("page shows '<', archive stores a value"
                                                                          if public["limit"] else "archive stores a limit, page shows a value"))
            if field == "mass":
                comp_kind = _text(comp_row.get("pl_bmassprov")) if comp_row is not None else ""
                default_kind = _text(default.get("pl_bmassprov")) if default is not None else ""
                if default_kind != "Mass" and comp_kind == "M-R relationship" and _matches(public, record["composite_value"]):
                    record["labels"].append("kind of mass: estimated from the planet's size with a model, not measured")
                elif default_kind == "Msini":
                    record["labels"].append("kind of mass: a minimum mass (from the star's wobble; the true mass is at least as large)")
            if default is not None and _row_matches(public, default, column):
                bucket, ref = "C-default", record["default_reference"]
            elif comp_row is not None and _row_matches(public, comp_row, column):
                bucket = "C-composite"
                ref = parse_reference(_text(comp_row.get(f"{column}_reflink")))["label"] or "composite table"
            else:
                other = group[[_row_matches(public, r, column) for _, r in group.iterrows()]] if group is not None else pd.DataFrame()
                if len(other):
                    bucket, ref = "C-other", parse_reference(_text(other.iloc[0]["pl_refname"]))["label"]
                elif field == "distance" and record["default_value"] and apart(public["value"], record["default_value"]) < SURVEY_GAP:
                    bucket, ref = "C-survey", None
                elif field == "radius" and "estimate" in str(page["acf"].get("planet_radius") or "").lower():
                    bucket, ref = "C-estimate", None
                else:
                    bucket, ref = "C-none", None
            record.update(bucket=bucket, reason=FINE_WHEN[bucket], matched_reference=ref)
            out.append(record)
    result = pd.DataFrame(out)
    present = result[result["bucket"] != "C-absent"]
    stats = {
        "planet_fields": int(len(result)),
        "compared": int(len(present)),
        "by_bucket": {b: int((result["bucket"] == b).sum()) for b in FINE_WHEN},
        "by_field": {f: {b: int(n) for b, n in g["bucket"].value_counts().items()} for f, g in result.groupby("field")},
        "share_default_or_composite": round(float(present["bucket"].isin(["C-default", "C-composite"]).mean()), 4) if len(present) else None,
        "share_none": round(float((present["bucket"] == "C-none").mean()), 4) if len(present) else None,
        "labels": int(result["labels"].map(len).gt(0).sum()),
    }
    return result, stats
