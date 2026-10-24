from __future__ import annotations

import html
import math
import re

import pandas as pd

from . import wording
from .check_b import CLOSE_BARS
from .consistency import EARTH_RADIUS_CONVENTION_ALLOWANCE, rounding_allowance
from .gaia import SMALL, apart
from .known_notes import documented
from .references import parse_reference, reference_key
from .screening import CONFIRMED_SOLTYPES, _num, _text

JUPITER_IN_EARTH_RADII = 7.1492e7 / 6.3781e6
JUPITER_IN_EARTH_MASSES = 1.2668653e17 / 3.986004e14

MEAN_RADIUS_FACTOR = 69911.0 / 6371.0

POSITIVE_COLUMNS = ("pl_rade", "pl_radj", "pl_bmasse", "pl_bmassj", "pl_masse", "pl_massj", "pl_msinie",
                    "pl_msinij", "pl_orbper", "pl_orbsmax", "pl_dens", "pl_ratror", "pl_ratdor",
                    "st_rad", "st_mass", "sy_dist")
MASS_CONVENTION_ALLOWANCE = 0.0005
A5_MASS_ALLOWANCE = 0.001
UNIT_PAIRS = (("pl_rade", "pl_radj", JUPITER_IN_EARTH_RADII, EARTH_RADIUS_CONVENTION_ALLOWANCE),
              ("pl_bmasse", "pl_bmassj", JUPITER_IN_EARTH_MASSES, A5_MASS_ALLOWANCE),
              ("pl_masse", "pl_massj", JUPITER_IN_EARTH_MASSES, A5_MASS_ALLOWANCE),
              ("pl_msinie", "pl_msinij", JUPITER_IN_EARTH_MASSES, A5_MASS_ALLOWANCE))
DUPLICATE_FIELDS = ("pl_rade", "pl_bmasse", "pl_orbper", "pl_orbsmax", "pl_orbeccen")
PARALLAX_ZERO_POINT = 0.029

FINE_WHEN = {r: wording.means(f"A/{r}") for r in ("A1", "A2", "A3", "A4", "A5", "A7", "A5m", "A5r", "A8", "A8n")}
ASSUMPTION_COLUMNS = ("st_age", "st_mass", "st_rad", "st_teff", "st_met", "st_lum", "sy_dist", "pl_orbincl")
TITLES = {
    "A1": "a value that must be positive is zero or negative",
    "A2": "eccentricity outside 0 to 1",
    "A3": "error bar stored with the wrong sign",
    "A4": "a limit stored together with a two-sided error bar",
    "A5": "the Earth-unit and Jupiter-unit copies of the same number disagree",
    "A7": "the same paper appears in several rows with different values",
    "A5m": "Earth and Jupiter copies converted with mean instead of equatorial radii",
    "A5r": "the Earth-unit copy is the Jupiter value rounded to fewer digits",
    "A8": "the star's distance doesn't match its parallax",
    "A8n": "the star's distance doesn't match its parallax (NASA has a note)",
}


def distance_vs_parallax(row) -> tuple[float, float] | None:
    d, p, pe = _num(row.get("sy_dist")), _num(row.get("sy_plx")), _num(row.get("sy_plxerr1"))
    up, down = _num(row.get("sy_disterr1")), _num(row.get("sy_disterr2"))
    if None in (d, p, pe, up, down) or d <= 0 or p <= 0 or pe <= 0 or pe / p >= 0.1:
        return None
    zero_point = PARALLAX_ZERO_POINT if "TICv8" in (_text(row.get("sy_refname")) or "") else 0.0
    implied = 1000 / (p + zero_point)
    spread = math.hypot(abs(down) if d > implied else abs(up), 1000 * pe / (p + zero_point) ** 2)
    bars = abs(d - implied) / spread if spread else math.inf
    return (implied, bars) if apart(d, implied) >= SMALL and bars > CLOSE_BARS else None


def _sig_figs(x: float) -> int:
    x = abs(float(x))
    if x.is_integer():
        return max(1, len(str(int(x)).rstrip("0")))
    return len(repr(x).replace(".", "").lstrip("0").rstrip("0")) or 1


def _rounded_copy(earth: float, converted: float) -> bool:
    sf = _sig_figs(earth)
    return float(f"{converted:.{sf}g}") == float(earth)


_PRINTED = re.compile(r"^\s*[<>~≈]?\s*[-+]?\d+(?:\.(\d+))?")


def _printed_decimals(text) -> int | None:
    if not isinstance(text, str) or not text.strip():
        return None
    m = _PRINTED.match(html.unescape(re.sub(r"<[^>]+>", " ", text)))
    return len(m.group(1) or "") if m else None


def _copy_allowance(row, earth_col: str, jup_col: str, earth: float, jup: float) -> float:
    total = 0.0
    for col, v in ((earth_col, earth), (jup_col, jup)):
        d = _printed_decimals(row.get(col + "str"))
        total += rounding_allowance(v) if d is None else 0.5 * 10 ** (-d) / abs(v)
    return total


def _value_columns(frame: pd.DataFrame) -> list[str]:
    return sorted(c[:-4] for c in frame.columns if c.endswith("err1") and c[:-4] in frame.columns)


def check_a(frame: pd.DataFrame, notes: dict | None = None) -> tuple[pd.DataFrame, dict]:
    rows = frame[frame["soltype"].isin(CONFIRMED_SOLTYPES)] if "soltype" in frame else frame
    values = _value_columns(rows)
    out = []

    def flag(rule, row, column, value, detail, label_only=False):
        ref = parse_reference(_text(row.get("pl_refname")))
        out.append({"rule": rule, "title": TITLES[rule], "pl_name": _text(row.get("pl_name")),
                    "reference": ref["label"], "reference_url": ref["url"], "ref_key": reference_key(row.get("pl_refname")),
                    "column": column, "value": value, "detail": detail, "fine_when": FINE_WHEN[rule],
                    "label_only": label_only})

    for _, row in rows.iterrows():
        for column in POSITIVE_COLUMNS:
            v = _num(row.get(column))
            if v is not None and v <= 0:
                flag("A1", row, column, v, f"{column} = {v}")
        e = _num(row.get("pl_orbeccen"))
        if e is not None and not 0 <= e < 1:
            flag("A2", row, "pl_orbeccen", e, f"eccentricity = {e}")
        for column in values:
            plus, minus = _num(row.get(column + "err1")), _num(row.get(column + "err2"))
            if (plus is not None and plus < 0) or (minus is not None and minus > 0):
                flag("A3", row, column, _num(row.get(column)), f"+{plus} / {minus}")
            limit = _num(row.get(column + "lim"))
            if limit not in (None, 0.0) and plus and minus:
                flag("A4", row, column, _num(row.get(column)), f"limit flag {limit:+g} with +{plus} / {minus}", label_only=True)
        for earth_col, jup_col, factor, convention in UNIT_PAIRS:
            earth, jup = _num(row.get(earth_col)), _num(row.get(jup_col))
            if not earth or not jup or earth <= 0 or jup <= 0:
                continue
            if earth_col == "pl_bmasse" and any((_num(row.get(e)), _num(row.get(j))) == (earth, jup)
                                                for e, j in (("pl_masse", "pl_massj"), ("pl_msinie", "pl_msinij"))):
                continue
            ratio = earth / (jup * factor)
            allowance = _copy_allowance(row, earth_col, jup_col, earth, jup) + convention
            if float(earth).is_integer():
                allowance += 0.5 / abs(earth)
            if abs(ratio - 1) <= allowance:
                continue
            if earth_col == "pl_rade" and abs(earth / (jup * MEAN_RADIUS_FACTOR) - 1) <= allowance:
                flag("A5m", row, earth_col, earth, f"{earth_col} = {earth}, {jup_col} = {jup}: converted with mean radii "
                                                    f"(x{MEAN_RADIUS_FACTOR:.3f}) instead of equatorial (x{factor:.3f})", label_only=True)
            elif _rounded_copy(earth, jup * factor):
                flag("A5r", row, earth_col, earth, f"{earth_col} = {earth}, {jup_col} = {jup} (x{factor:.3f} = {jup * factor:.4g}, "
                                                   f"rounded to {_sig_figs(earth)} significant figure{'s' if _sig_figs(earth) > 1 else ''})",
                     label_only=True)
            else:
                flag("A5", row, earth_col, earth, f"{earth_col} = {earth}, {jup_col} = {jup} (x{factor:.3f} = {jup * factor:.4g}); "
                                                  f"{100 * (ratio - 1):+.2f}% vs allowed {100 * allowance:.2f}%")

        if _num(row.get("default_flag")) == 1 and (hit := distance_vs_parallax(row)):
            implied, bars = hit
            source = _text(row.get("sy_refname"))
            noted = documented(_text(row.get("pl_name")), "distance", notes or {}, parse_reference(source)["bibcode"])
            flag("A8n" if noted else "A8", {**row, "pl_refname": source}, "sy_dist", _num(row.get("sy_dist")),
                 f"sy_dist = {_num(row.get('sy_dist'))} pc; sy_plx = {_num(row.get('sy_plx'))} mas implies {implied:.4g} pc; "
                 f"{bars:.0f} error bars apart" + (f"; NASA note: {str(noted[0].get('notes') or '').rstrip('.')}" if noted else ""), label_only=bool(noted))

    keyed = rows.assign(_key=rows["pl_name"].astype(str) + "|" + rows["pl_refname"].map(reference_key))
    fields = [c for c in DUPLICATE_FIELDS if c in keyed]
    for key, group in keyed[keyed.duplicated("_key", keep=False)].groupby("_key", sort=True):
        if len(group[fields].drop_duplicates()) > 1:
            first = group.iloc[0]
            differing = [c for c in fields if group[c].nunique(dropna=True) > 1]
            assumed = [c for c in ASSUMPTION_COLUMNS if c in group and group[c].nunique(dropna=True) > 1]
            flag("A7", first, ",".join(differing), None, f"{len(group)} rows; differing: {', '.join(differing) or 'none of the v1 fields'}"
                 + (f"; the rows also differ in {', '.join(assumed)}" if assumed else ""), label_only=True)

    result = pd.DataFrame(out)
    counts = result["rule"].value_counts().to_dict() if len(result) else {}
    stats = {"rows_checked": int(len(rows)), "value_columns_checked": len(values),
             "by_rule": {r: int(counts.get(r, 0)) for r in TITLES},
             "leads": int((~result["label_only"]).sum()) if len(result) else 0,
             "labels": int(result["label_only"].sum()) if len(result) else 0}
    return result, stats
