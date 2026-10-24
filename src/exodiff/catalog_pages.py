from __future__ import annotations

import re

from .check_a import JUPITER_IN_EARTH_MASSES

DAYS_PER_YEAR = 365.25
CONVERSION_ALLOWANCE = 0.0005
_NUM = r"([0-9]+(?:\.[0-9]+)?)"


def _plural(unit: str) -> str:
    return unit if unit.endswith("s") or unit == "AU" else unit + "s"


def _q(number: str, unit: str) -> dict:
    decimals = len(number.split(".")[1]) if "." in number else 0
    return {"v": float(number), "unit": unit, "half": 0.5 * 10 ** -decimals, "shown": f"{number} {unit}"}


def _box(raw, pattern: str) -> dict | None:
    raw = "" if raw is None else str(raw).strip()
    if raw in ("", "Unknown"):
        return {"unknown": True, "shown": "Unknown"}
    m = re.match(pattern, raw)
    return _q(m.group(1), _plural(m.group(2))) if m else None


def page_from_record(acf: dict) -> dict:
    sentence = (acf.get("short_description") or "").strip() or (acf.get("derived_description") or "").strip()
    if not re.search(r"Its mass is|to complete one orbit", sentence):
        sentence = None
    s = {}
    if sentence:
        if m := re.search(r"Its mass is " + _NUM + r" (Earths?|Jupiters?)\b", sentence):
            s["mass"] = _q(m.group(1), _plural(m.group(2)))
        if m := re.search(r"takes " + _NUM + r" (days?|years?) to complete one orbit", sentence):
            s["period"] = _q(m.group(1), _plural(m.group(2)))
        if m := re.search(r"is " + _NUM + r" AU from its star", sentence):
            s["orbit"] = _q(m.group(1), "AU")
    orbit = acf.get("pl_orbsmax")
    box = {k: v for k, v in (("mass", _box(acf.get("planet_mass"), _NUM + r" (Earths?|Jupiters?)$")),
                              ("period", _box(acf.get("period_display"), _NUM + r" (days?|years?)$")),
                              ("orbit", _box(None if orbit in (None, "") else f"{orbit} AU", _NUM + r" (AU)$")))
           if v is not None}
    return {"sentence": sentence, "s": s, "box": box}


def _to(q: dict, unit: str) -> tuple[float, float]:
    factor = 1.0
    if q["unit"] != unit:
        factor = {("Jupiters", "Earths"): JUPITER_IN_EARTH_MASSES, ("Earths", "Jupiters"): 1 / JUPITER_IN_EARTH_MASSES,
                  ("years", "days"): DAYS_PER_YEAR, ("days", "years"): 1 / DAYS_PER_YEAR}[(q["unit"], unit)]
    return q["v"] * factor, q["half"] * factor


def contradictions(page: dict) -> list[dict]:
    out = []
    for key in ("mass", "period", "orbit"):
        s, b = page["s"].get(key), page["box"].get(key)
        if s is None or b is None:
            continue
        if b.get("unknown"):
            out.append({"quantity": key, "sentence": s["shown"], "box": "Unknown"})
            continue
        sv, sh = _to(s, b["unit"])
        allowance = sh + b["half"] + (CONVERSION_ALLOWANCE * abs(b["v"]) if key == "mass" and s["unit"] != b["unit"] else 0.0)
        if abs(sv - b["v"]) > allowance * (1 + 1e-9):
            out.append({"quantity": key, "sentence": s["shown"], "box": b["shown"]})
    return out


ARCHIVE_COLUMN = {"mass": "pl_bmasse", "period": "pl_orbper", "orbit": "pl_orbsmax"}
BOX_UNIT_FOR_ARCHIVE = {"mass": "Earths", "period": "days", "orbit": "AU"}


def classify(contradiction: dict, page: dict, rows) -> dict:
    from .identities import _kepler_a
    k = contradiction["quantity"]
    out = dict(contradiction)
    if contradiction["box"] == "Unknown":
        out["cause"] = "box-unknown"
        return out
    value, half = _to(page["s"][k], BOX_UNIT_FOR_ARCHIVE[k])
    num = lambda x: None if x is None or x != x else float(x)
    published = [] if rows is None else [v for v in map(num, rows[ARCHIVE_COLUMN[k]]) if v is not None]
    older = [r for r in ([] if rows is None else rows.itertuples())
             if (v := num(getattr(r, ARCHIVE_COLUMN[k], None))) is not None and abs(v - value) <= half + abs(v) * CONVERSION_ALLOWANCE]
    if older:
        from .references import parse_reference
        out["cause"], out["paper"] = "older-paper", parse_reference(str(getattr(older[0], "pl_refname", "")))["label"] or None
    elif k == "orbit" and not published:
        out["cause"] = "calculated"
    elif k == "orbit" and rows is not None and any(
            abs(_kepler_a({"pl_orbper": float(r.pl_orbper), "st_mass": float(r.st_mass)}) - value) / value < 0.002
            for r in rows.itertuples() if num(r.pl_orbper) is not None and num(r.st_mass) is not None):
        out["cause"] = "calculated"
    else:
        out["cause"] = "other"
    return out
