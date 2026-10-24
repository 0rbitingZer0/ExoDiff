from __future__ import annotations

import hashlib
import json
import re
from html import unescape
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests

from . import wording
from .check_a import JUPITER_IN_EARTH_MASSES, JUPITER_IN_EARTH_RADII
from .consistency import _decimals
from .public_join import normalise
from .references import parse_reference
from .screening import _num, _text

EU_CSV_URL = "https://exoplanet.eu/catalog/csv/"
EU_STEM = "exoplanet_eu"
EU_REQUIRED = ["name", "planet_status", "mass", "mass_error_min", "mass_error_max", "radius", "radius_error_min",
               "radius_error_max", "orbital_period", "orbital_period_error_min", "orbital_period_error_max",
               "semi_major_axis", "semi_major_axis_error_min", "semi_major_axis_error_max", "eccentricity",
               "eccentricity_error_min", "eccentricity_error_max", "star_distance", "star_distance_error_min",
               "star_distance_error_max", "alternate_names", "updated"]
EU_MIN_ROWS = 5_000
CONVERSION_ALLOWANCE = 0.003
JUPITER_COPY = {"pl_rade": "pl_radj", "pl_masse": "pl_massj"}
OPEN_BUCKETS = ("D-disagree", "D-newer-paper")

FIELDS = {
    "radius": ("radius", JUPITER_IN_EARTH_RADII, "pl_rade"),
    "mass": ("mass", JUPITER_IN_EARTH_MASSES, "pl_masse"),
    "period": ("orbital_period", 1.0, "pl_orbper"),
    "orbit": ("semi_major_axis", 1.0, "pl_orbsmax"),
    "eccentricity": ("eccentricity", 1.0, "pl_orbeccen"),
    "distance": ("star_distance", 1.0, "sy_dist"),
}
FINE_WHEN = {b: wording.means(f"D/{b}") for b in ("D-same", "D-other-paper", "D-within-errors", "D-disagree", "D-newer-paper", "D-eu-paper", "D-other-row", "D-close", "D-letters", "D-limit", "D-catalogue-distance", "D-no-errors", "D-theoretical", "D-absent")}


def fetch_eu(project_root: Path, timeout_seconds: int = 400, session=None) -> dict:
    raw_dir = Path(project_root).resolve() / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    getter = session.get if session else requests.get
    try:
        response = getter(EU_CSV_URL, headers={"User-Agent": "ExoDiff (data experiment; https://github.com/0rbitingZer0)"},
                          timeout=(15, timeout_seconds))
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"exoplanet.eu download failed: {exc}. Nothing written.") from exc
    body = response.content
    if not body.endswith(b"\n"):
        raise RuntimeError("exoplanet.eu response does not end with a newline; possible truncated download.")
    frame = pd.read_csv(BytesIO(body), low_memory=False)
    missing = sorted(set(EU_REQUIRED) - set(frame.columns))
    if missing:
        raise RuntimeError("exoplanet.eu CSV schema changed; missing: " + ", ".join(missing))
    if len(frame) < EU_MIN_ROWS:
        raise RuntimeError(f"exoplanet.eu returned only {len(frame)} rows; possible partial response.")
    digest = hashlib.sha256(body).hexdigest()
    saved = latest_eu_manifest(project_root)
    if saved and len(frame) < 0.95 * (saved.get("row_count") or 0):
        raise RuntimeError(f"exoplanet.eu returned {len(frame):,} rows, under 95% of the saved copy's "
                           f"{saved['row_count']:,}; possible partial response. Nothing written.")
    if saved and saved.get("sha256") == digest:
        return {"unchanged": True, "rows": int(len(frame)), "sha256": digest, "retrieved_at_utc": saved["retrieved_at_utc"]}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = raw_dir / f"{EU_STEM}_{stamp}.csv"
    path.write_bytes(body)
    manifest = {"source_name": "The Extrasolar Planets Encyclopaedia (exoplanet.eu), confirmed planets CSV",
                "source_url": EU_CSV_URL, "licence": "CC BY 4.0", "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "row_count": int(len(frame)), "sha256": digest}
    path.with_name(path.name.replace(".csv", ".manifest.json")).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"unchanged": False, "rows": int(len(frame)), "path": str(path), "sha256": digest,
            "retrieved_at_utc": manifest["retrieved_at_utc"]}


def latest_eu_manifest(project_root: Path) -> dict | None:
    files = sorted((Path(project_root).resolve() / "data" / "raw").glob(f"{EU_STEM}_*[0-9]Z.csv"))
    if not files:
        return None
    try:
        return json.loads(files[-1].with_name(files[-1].name.replace(".csv", ".manifest.json")).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


EU_INDEX_URL = "https://exoplanet.eu/catalog_new/planet_index/"
EU_INDEX_STEM = "exoplanet_eu_index"
_INDEX_LINK = re.compile(r'href="(/catalog/[a-z0-9_]+--[0-9]+/)">([^<]+)<')


def parse_eu_index(html: str) -> dict:
    return {" ".join(unescape(name).split()): "https://exoplanet.eu" + href for href, name in _INDEX_LINK.findall(html)}


def fetch_eu_index(project_root: Path, session=None) -> dict:
    getter = session.get if session else requests.get
    try:
        r = getter(EU_INDEX_URL, headers={"User-Agent": "ExoDiff (data experiment; https://github.com/0rbitingZer0)"}, timeout=(15, 120))
        r.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"exoplanet.eu index download failed: {exc}") from exc
    links = parse_eu_index(r.text)
    if len(links) < EU_MIN_ROWS:
        raise RuntimeError(f"exoplanet.eu index lists only {len(links)} planets; possible partial page.")
    raw_dir = Path(project_root).resolve() / "data" / "raw"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = raw_dir / f"{EU_INDEX_STEM}_{stamp}.json"
    body = json.dumps(links, indent=0, sort_keys=True).encode("utf-8")
    path.write_bytes(body)
    manifest = {"source_name": "exoplanet.eu planet index (name -> page link)", "source_url": EU_INDEX_URL,
                "licence": "CC BY 4.0", "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "planets": len(links),
                "sha256": hashlib.sha256(body).hexdigest(), "file": path.name}
    path.with_name(path.stem + ".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"planets": len(links), "path": str(path)}


def latest_eu_index(project_root: Path) -> dict:
    files = sorted((Path(project_root).resolve() / "data" / "raw").glob(f"{EU_INDEX_STEM}_*Z.json"))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else {}


_COMPONENT = re.compile(r"^(.*\S) ([A-C])([a-z])$")
_PAIR = re.compile(r"^(.*\S) \(AB\) ?([a-z])$")


def name_variants(name: str) -> list[str]:
    out = [name]
    ab = _PAIR.match(name.strip())
    if ab:
        stem, letter = ab.groups()
        out += [f"{stem} {letter}", f"{stem} AB {letter}"]
    m = _COMPONENT.match(name.strip())
    if m:
        stem, component, letter = m.groups()
        out.append(f"{stem} {component} {letter}")
        if component == "A":
            out.append(f"{stem} {letter}")
    return out


def join_eu(eu: pd.DataFrame, nasa_names) -> dict:
    by_norm = {}
    for name in sorted(set(nasa_names)):
        by_norm.setdefault(normalise(name), name)
    matched, ambiguous, eu_only, via_alias = {}, [], [], 0
    for _, row in eu.iterrows():
        names = [_text(row["name"])] + [a.strip() for a in str(row.get("alternate_names") or "").split(",") if a.strip()]
        candidates = [normalise(v) for n in names for v in name_variants(n)]
        target = next((by_norm[c] for c in candidates if c in by_norm), None)
        if target is None:
            eu_only.append(_text(row["name"]))
            continue
        via_alias += candidates[0] not in by_norm
        if target in matched:
            ambiguous.append({"pl_name": target, "eu_names": [matched[target], _text(row["name"])]})
            continue
        matched[target] = _text(row["name"])
    for a in ambiguous:
        matched.pop(a["pl_name"], None)
    return {"matched": matched, "ambiguous": ambiguous, "eu_only": sorted(eu_only),
            "nasa_only": sorted(set(nasa_names) - set(matched)),
            "stats": {"eu_rows": int(len(eu)), "nasa_planets": len(set(nasa_names)), "matched": len(matched),
                      "matched_via_alias": int(via_alias), "ambiguous": len(ambiguous), "eu_only": len(eu_only)}}


def _catalogue_distance(default) -> bool:
    from .sources import CATALOGUE_REFERENCES
    return parse_reference(_text(default.get("sy_refname")))["label"] in CATALOGUE_REFERENCES


def _interval(value, minus, plus, widen: float = 0.0):
    if value is None or minus is None or plus is None or (minus == 0 and plus == 0):
        return None
    return value - abs(minus) - widen, value + abs(plus) + widen


def _overlap(a, b) -> bool:
    return a is not None and b is not None and max(a[0], b[0]) <= min(a[1], b[1])


def gap_in_error_bars(a: float, a_iv, b: float, b_iv, tol: float = 0.0) -> float:
    ea, eb = (a_iv[1] - a, b - b_iv[0]) if a <= b else (a - a_iv[0], b_iv[1] - b)
    spread = (ea ** 2 + eb ** 2) ** 0.5
    gap = max(0.0, abs(a - b) - tol)
    return gap / spread if spread > 0 else float("inf")


def _papers(group: pd.DataFrame) -> list[dict]:
    out = []
    for _, r in group.iterrows():
        ref = parse_reference(_text(r.get("pl_refname")))
        year = re.match(r"(\d{4})", _text(r.get("pl_pubdate")) or "") or re.search(r"(\d{4})", ref["label"])
        out.append({"label": ref["label"], "bibcode": ref["bibcode"], "year": int(year.group(1)) if year else None})
    return out


def _siblings(nasa: pd.DataFrame) -> dict:
    defaults = nasa[nasa["default_flag"] == 1]
    out = {}
    for _, g in defaults.groupby("hostname"):
        for name in g["pl_name"]:
            others = g[g["pl_name"] != name]
            out[name] = {f: [v for v in (_num(x) for x in others[col]) if v] for f, (_, _, col) in FIELDS.items() if col in others}
    return out


LETTERS_MATCH = 0.01
CLOSE_BARS = 2.0


def check_d(nasa: pd.DataFrame, eu: pd.DataFrame, join: dict, sources: dict | None = None) -> tuple[pd.DataFrame, dict]:
    from .eu_sources import describe, held_by_nasa
    sources = sources or {}
    eu_by_name = eu.set_index("name")
    rows_by_planet = {name: g for name, g in nasa.groupby("pl_name")}
    siblings = _siblings(nasa) if "hostname" in nasa else {}
    out = []
    for planet, group in sorted(rows_by_planet.items()):
        eu_name = join["matched"].get(planet)
        e = eu_by_name.loc[eu_name] if eu_name is not None and eu_name in eu_by_name.index else None
        if isinstance(e, pd.DataFrame):
            e = e.iloc[0]
        default = group[group["default_flag"] == 1].iloc[0] if (group["default_flag"] == 1).any() else None
        papers = _papers(group)
        newest_nasa = max((p["year"] for p in papers if p["year"]), default=None)
        ep_, dp_ = (_num(e.get("orbital_period")) if e is not None else None), (_num(default.get("pl_orbper")) if default is not None else None)
        planet_letters = bool(ep_ and dp_ and abs(ep_ / dp_ - 1) > 0.05
                              and any(abs(ep_ / v - 1) <= LETTERS_MATCH for v in siblings.get(planet, {}).get("period", [])))
        for field, (eu_col, factor, col) in FIELDS.items():
            rec = {"pl_name": planet, "field": field, "eu_name": eu_name, "eu_value": None, "nasa_default": None,
                   "matched_reference": None}
            ev = _num(e.get(eu_col)) if e is not None else None
            dv = _num(default.get(col)) if default is not None and col in default else None
            if ev is None or dv is None:
                rec.update(bucket="D-absent", eu_value=ev * factor if ev is not None else None, nasa_default=dv)
                out.append(rec)
                continue
            value = ev * factor
            if field in ("mass", "radius") and _text(e.get(f"{eu_col}_measurement_type")) == "Theoretical":
                rec.update(bucket="D-theoretical", eu_value=value, nasa_default=dv)
                out.append(rec)
                continue
            tol = 0.5 * 10 ** (-_decimals(ev)) * factor + (CONVERSION_ALLOWANCE * abs(value) if factor != 1.0 else 0.0)
            em, ep = _num(e.get(eu_col + "_error_min")), _num(e.get(eu_col + "_error_max"))
            em, ep = (em * factor if em is not None else None), (ep * factor if ep is not None else None)
            pubs = sources.get(planet, {}).get(field) or []
            held_all = [h for h in (held_by_nasa(x, papers) for x in pubs) if h]
            cited = max(pubs, key=lambda x: x.get("year") or 0, default=None)
            held = held_all[0] if len(pubs) == 1 and held_all else None
            rec.update(eu_value=value, nasa_default=dv, eu_err_minus=em, eu_err_plus=ep, eu_updated=_text(e.get("updated")) or None,
                       eu_reference="; ".join(describe(x) for x in pubs) if pubs else None)
            same = lambda nasa_value: nasa_value is not None and abs(nasa_value - value) <= tol * (1 + 1e-9)
            jtol = 0.5 * 10 ** (-_decimals(ev)) * (1 + 1e-9)
            same_row = lambda r: same(_num(r.get(col))) or (
                col in JUPITER_COPY and _num(r.get(JUPITER_COPY[col])) is not None and abs(_num(r.get(JUPITER_COPY[col])) - ev) <= jtol)
            ref_of = lambda r: parse_reference(_text(r.get("pl_refname")))["label"]
            eu_iv = _interval(value, em, ep, tol)

            def nasa_of(r):
                jc = JUPITER_COPY.get(col)
                if jc:
                    jv, j1, j2 = _num(r.get(jc)), _num(r.get(jc + "err1")), _num(r.get(jc + "err2"))
                    if jv is not None and j1 is not None and j2 is not None:
                        return jv * factor, j1 * factor, j2 * factor
                return _num(r.get(col)), _num(r.get(col + "err1")), _num(r.get(col + "err2"))

            row_iv = lambda r: (lambda v, e1, e2: _interval(v, e2, e1))(*nasa_of(r))
            na_iv = row_iv(default)
            dv_cmp = nasa_of(default)[0] if nasa_of(default)[0] is not None else dv
            limit = _num(default.get(col + "lim")) if col + "lim" in default else None
            eu_upper = em is not None and value > 0 and abs(abs(em) - value) <= 0.001 * value and not ep
            z = None
            if planet_letters and field != "distance":
                bucket, ref = "D-letters", None
            elif same_row(default):
                bucket, ref = "D-same", ref_of(default)
            elif other := [r for _, r in group.iterrows() if same_row(r)]:
                pick = next((r for r in other if held and ref_of(r) == held["label"]), other[0])
                bucket, ref = "D-other-paper", ref_of(pick)
            elif limit in (1.0, -1.0):
                allowed = (value - abs(em or 0) - tol <= dv_cmp or eu_upper) if limit == 1.0 else value + abs(ep or 0) + tol >= dv_cmp
                bucket, ref = ("D-limit" if allowed else "D-disagree"), None
            elif eu_upper and dv_cmp <= value + tol:
                bucket, ref = "D-limit", None
            elif eu_iv is None or na_iv is None:
                bucket, ref = "D-no-errors", None
            elif _overlap(eu_iv, na_iv):
                bucket, ref = "D-within-errors", None
            elif field != "distance" and any(abs(value / v - 1) <= LETTERS_MATCH for v in siblings.get(planet, {}).get(field, [])):
                bucket, ref = "D-letters", None
            elif field == "distance" and _catalogue_distance(default):
                bucket, ref = "D-catalogue-distance", None
            else:
                z = gap_in_error_bars(dv_cmp, na_iv, value, _interval(value, em, ep), tol)
                overlapping = [r for _, r in group.iterrows() if _num(r.get("default_flag")) != 1
                               and _overlap(eu_iv, row_iv(r))]
                row = next((r for r in overlapping if not pubs or (held is not None and ref_of(r) == held["label"])), None)
                if row is not None:
                    bucket, ref = "D-other-row", ref_of(row)
                elif z < CLOSE_BARS:
                    bucket, ref = "D-close", None
                elif cited is not None and held is not None:
                    same_paper = [r for _, r in group.iterrows() if ref_of(r) == held["label"] and nasa_of(r)[0] is not None]
                    if not same_paper:
                        bucket, ref = "D-disagree", None
                    else:
                        hrow = min(same_paper, key=lambda r: abs(nasa_of(r)[0] - value))
                        h_iv = row_iv(hrow)
                        if h_iv is not None and eu_iv is not None and _overlap(eu_iv, h_iv):
                            bucket, ref = "D-other-row", held["label"]
                        else:
                            z = gap_in_error_bars(nasa_of(hrow)[0], h_iv, value, _interval(value, em, ep), tol) if h_iv and _interval(value, em, ep) else None
                            bucket, ref = ("D-close" if z is not None and z < CLOSE_BARS else "D-disagree"), held["label"]
                        rec["nasa_row_value"] = _num(hrow.get(col))
                elif held_all:
                    bucket, ref = "D-disagree", None
                elif cited is not None and newest_nasa and cited.get("year") and cited["year"] > newest_nasa:
                    bucket, ref = "D-newer-paper", None
                elif cited is not None:
                    bucket, ref = "D-eu-paper", None
                else:
                    bucket, ref = "D-disagree", None
            rec.update(bucket=bucket, matched_reference=ref, bars=z)
            out.append(rec)
    result = pd.DataFrame(out)
    compared = result[result["bucket"] != "D-absent"]
    stats = {"planet_fields": int(len(result)), "compared": int(len(compared)),
             "by_bucket": {b: int((result["bucket"] == b).sum()) for b in FINE_WHEN},
             "by_field": {f: {b: int(n) for b, n in g["bucket"].value_counts().items()} for f, g in result.groupby("field")},
             "join": join["stats"], "letters_planets": int(result.loc[result["bucket"] == "D-letters", "pl_name"].nunique())}
    if len(compared):
        stats["share_same_or_other_paper"] = round(float(compared["bucket"].isin(["D-same", "D-other-paper"]).mean()), 4)
        stats["share_disagree"] = round(float(compared["bucket"].isin(OPEN_BUCKETS).mean()), 4)
    return result, stats
