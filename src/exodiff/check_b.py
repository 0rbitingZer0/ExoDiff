from __future__ import annotations

import math

import pandas as pd

from . import wording
from .known_notes import documented
from .references import parse_reference
from .screening import _text
from .sources import CATALOGUE_REFERENCES

STAR_INPUTS = {"radius": "st_rad", "density": None, "kepler": "st_mass", "a_over_rstar": "st_rad"}
NOTE_CHECK = {"radius": "radius", "density": "density", "kepler": "kepler", "a_over_rstar": "a_over_rstar"}

OPEN = ("B-cat", "B-src", "B-look")
_TITLES = {"B-doc": "NASA has a note on it", "B-meanR": "Jupiter mean radius", "B-lit": "orbit size from an older paper",
           "B-transit": "orbit size from the transit fit", "B-cat": "star value from a catalogue",
           "B-src": "star value from another paper", "B-dup": "several rows for this paper",
           "B-close": "less than two error bars", "B-look": "worth a second look"}
BUCKETS = {b: (t, wording.means(f"B/{b}")) for b, t in _TITLES.items()}
_R, _M = 11.209, 317.83
FINGERPRINTS = {
    "radius": {"radius in Jupiter vs Earth units": _R},
    "density": {"radius in Jupiter vs Earth units (cubed)": _R ** 3, "mass in Jupiter vs Earth units": _M},
    "kepler": {},
    "a_over_rstar": {},
}


def fingerprint(ratio: float, check: str = "radius") -> str | None:
    if not ratio or ratio <= 0:
        return None
    for name, factor in FINGERPRINTS.get(check, {}).items():
        for f, direction in ((factor, "x"), (1 / factor, "÷")):
            if abs(math.log(ratio / f)) < math.log(1.02):
                return f"{direction} {name}"
    return None


MEAN_RADIUS = {"radius": (1.0215, 1.0226), "density": (1.0215 ** 3, 1.0226 ** 3)}
SUN_IN_AU = 215.032
CLOSE_BARS = 2.0


def mean_radius(ratio: float, check: str) -> bool:
    return bool(ratio) and ratio > 0 and any(abs(abs(math.log(ratio)) - math.log(f)) < math.log(1.005) for f in MEAN_RADIUS.get(check, ()))


def _rel(row, col):
    v = row.get(col)
    errs = [abs(e) for e in (row.get(col + "err1"), row.get(col + "err2")) if e is not None and e == e and e != 0]
    return (sum(errs) / len(errs)) / abs(v) if v and v == v and errs else None


LITERATURE_ORBIT = {
    "2017AJ....153..136S": "Stassun et al. 2017, §2.7: \"For the non-transiting planets, we use the values of a from the literature.\"",
}


def numeric_transit_match(row, listed: float) -> bool:
    ratdor, rstar = row.get("pl_ratdor"), row.get("st_rad")
    return bool(ratdor and rstar and ratdor == ratdor and rstar == rstar and listed
                and abs(ratdor * rstar / SUN_IN_AU / listed - 1) <= 0.01)


def circular_or_unreported(row) -> bool:
    e = row.get("pl_orbeccen")
    return e is None or e != e or e == 0


def transit_fit(row, listed: float) -> bool:
    return numeric_transit_match(row, listed) and circular_or_unreported(row)


def from_transit(row, listed: float, implied: float) -> bool:
    if not implied or not transit_fit(row, listed):
        return False
    rels = [_rel(row, "pl_ratdor"), _rel(row, "st_rad"), _rel(row, "st_mass")]
    if None in rels:
        return False
    rel_p = _rel(row, "pl_orbper")
    if rel_p is None:
        return False
    allowed = CLOSE_BARS * (rels[0] ** 2 + rels[1] ** 2 + (rels[2] / 3) ** 2 + (2 * rel_p / 3) ** 2) ** 0.5
    return abs(listed / implied - 1) <= allowed


def _row_of(candidates: list, lead) -> dict | None:
    from .identities import _kepler_a
    same = [r for r in candidates if r.get("pl_orbsmax") == lead["listed_value"]]
    if len(same) <= 1:
        return same[0] if same else None
    def implied(r):
        try:
            m = r.get("pl_bmasse") if r.get("pl_bmasselim") == 0 else None
            return _kepler_a({"pl_orbper": float(r["pl_orbper"]), "st_mass": float(r["st_mass"]),
                              "pl_bmasse": m if m == m else None})
        except (TypeError, ValueError, KeyError):
            return float("inf")
    return min(same, key=lambda r: abs(implied(r) - (lead["implied_value"] or 0)))


def unify(radius_rows: pd.DataFrame, identities: pd.DataFrame) -> pd.DataFrame:
    parts = []
    if len(radius_rows):
        r = radius_rows[radius_rows["is_lead"].astype(bool)]
        parts.append(pd.DataFrame({
            "check": "radius", "pl_name": r["pl_name"], "pl_refname": r["pl_refname"], "reference": r["reference"],
            "listed_value": r["pl_rade"], "implied_value": r["rp_from_ratio_times_star_rearth"],
            "mismatch_pct": r["mismatch_pct"], "mismatch_in_error_bars": r["mismatch_in_error_bars"],
            "archive_rows_for_this_paper": r["archive_rows_for_this_paper"]}))
    if len(identities):
        i = identities[identities["is_lead"].astype(bool)]
        parts.append(i[["check", "pl_name", "pl_refname", "reference", "listed_value", "implied_value", "mismatch_pct",
                        "mismatch_in_error_bars", "archive_rows_for_this_paper"]])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def bucket_leads(frame: pd.DataFrame, leads: pd.DataFrame, notes: dict) -> tuple[pd.DataFrame, dict]:
    if leads.empty:
        return leads, {"leads": 0, "by_bucket": {}, "by_check": {}}
    star_ref = {(n, p): _text(s) for n, p, s in zip(frame["pl_name"], frame["pl_refname"], frame.get("st_refname", ""))}
    rows = {}
    for r in frame.to_dict("records"):
        rows.setdefault((r["pl_name"], r["pl_refname"]), []).append(r)
    buckets, reasons, prints, fits, numeric = [], [], [], [], []
    for lead in leads.to_dict("records"):
        check = lead["check"]
        key = (lead["pl_name"], lead["pl_refname"])
        star_input = STAR_INPUTS[check]
        star = parse_reference(star_ref.get(key, ""))
        planet = parse_reference(_text(lead["pl_refname"]))
        ratio = lead["listed_value"] / lead["implied_value"] if lead["implied_value"] else None
        row = _row_of(rows.get(key, []), lead) if check == "kepler" else None
        if documented(lead["pl_name"], NOTE_CHECK[check], notes, parse_reference(_text(lead["pl_refname"]))["bibcode"] or None):
            bucket = "B-doc"
        elif row is not None and planet["bibcode"] in LITERATURE_ORBIT and row.get("tran_flag") == 0:
            bucket = "B-lit"
        elif mean_radius(ratio, check):
            bucket = "B-meanR"
        elif row is not None and from_transit(row, lead["listed_value"], lead["implied_value"]):
            bucket = "B-transit"
        elif (lead.get("mismatch_in_error_bars") or 0) < CLOSE_BARS:
            bucket = "B-close"
        elif star_input and star["label"] in CATALOGUE_REFERENCES:
            bucket = "B-cat"
        elif star_input and (star["refstr"] or star["label"]) != (planet["refstr"] or planet["label"]):
            bucket = "B-src"
        elif (lead.get("archive_rows_for_this_paper") or 1) > 1:
            bucket = "B-dup"
        else:
            bucket = "B-look"
        buckets.append(bucket)
        reasons.append(BUCKETS[bucket][1])
        prints.append(fingerprint(ratio, check) if ratio else None)
        fits.append(row is not None and transit_fit(row, lead["listed_value"]))
        numeric.append(row is not None and numeric_transit_match(row, lead["listed_value"]) and not circular_or_unreported(row))
    out = leads.assign(bucket=buckets, bucket_title=[BUCKETS[b][0] for b in buckets], bucket_reason=reasons,
                       unit_fingerprint=prints, transit_fit=fits, transit_numeric_only=numeric)
    by_check = {c: {b: int(n) for b, n in g["bucket"].value_counts().items()} for c, g in out.groupby("check")}
    stats = {"leads": int(len(out)), "by_bucket": {b: int((out["bucket"] == b).sum()) for b in BUCKETS},
             "by_check": by_check, "with_unit_fingerprint": int(out["unit_fingerprint"].notna().sum())}
    return out, stats
