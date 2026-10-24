from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from . import wording
from .references import parse_reference
from .screening import _num, _text

GAIA_TAP = "https://gea.esac.esa.int/tap-server/tap/sync"
STEM = "gaia_dr3_distances"
SMALL = 0.05
CHUNK = 500
CATALOGUE_LABELS = {"TICv8"}
FINE_WHEN = {b: wording.means(f"E/{b}") for b in ("E-same", "E-small", "E-differs", "E-no-errors", "E-quality")}
SCREENS = (("phot_g_mean_mag", "Gaia's brightness differs from NASA's by more than 1 magnitude: possibly a different star"),
           ("ruwe", "Gaia's fit for this star is poor (RUWE above 1.4), often a sign of a companion"),
           ("parallax_over_error", "Gaia's parallax is less than 5 times its uncertainty"),
           ("astrometric_excess_noise_sig", "Gaia sees significant extra motion (excess noise), often a sign of a companion"))


def quality_reason(row, nasa_gmag) -> str | None:
    g, ruwe, poe, noise = (_num(row.get(c)) for c, _ in SCREENS)
    tests = (g is not None and nasa_gmag is not None and abs(g - nasa_gmag) > 1.0, ruwe is not None and ruwe > 1.4,
             poe is not None and poe < 5, noise is not None and noise > 20)
    return next((why for (_, why), failed in zip(SCREENS, tests) if failed), None)


def source_ids(nasa: pd.DataFrame) -> list[int]:
    ids = nasa.loc[nasa["default_flag"] == 1, "gaia_dr3_id"].dropna().astype(str).str.extract(r"(\d+)\s*$")[0]
    return sorted({int(i) for i in ids.dropna()})


def saved_gaia(project_root: Path) -> tuple[pd.DataFrame, dict] | None:
    files = sorted((Path(project_root).resolve() / "data" / "raw").glob(f"{STEM}_*[0-9]Z.csv"))
    if not files:
        return None
    manifest = json.loads(files[-1].with_name(files[-1].stem + ".manifest.json").read_text())
    return pd.read_csv(files[-1]), manifest


def fetch_gaia(ids: list[int], project_root: Path, session=None) -> dict:
    post = session.post if session else requests.post
    saved = saved_gaia(project_root)
    have = set(saved[0]["source_id"].astype("int64")) if saved else set()
    todo = sorted(set(ids) - have)
    parts = []
    for i in range(0, len(todo), CHUNK):
        chunk = ",".join(str(x) for x in todo[i:i + CHUNK])
        query = ("SELECT d.source_id, d.r_med_geo, d.r_lo_geo, d.r_hi_geo, g.phot_g_mean_mag, g.ruwe, "
                 "g.parallax_over_error, g.astrometric_excess_noise_sig FROM external.gaiaedr3_distance AS d "
                 f"JOIN gaiadr3.gaia_source AS g ON g.source_id = d.source_id WHERE d.source_id IN ({chunk})")
        try:
            response = post(GAIA_TAP, data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": query},
                            timeout=(15, 300))
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Gaia archive query failed: {exc}. Nothing written.") from exc
        if not response.text.endswith("\n"):
            raise RuntimeError("Gaia archive reply does not end with a newline; possible truncated download. Nothing written.")
        frame = pd.read_csv(StringIO(response.text))
        if "r_med_geo" not in frame.columns:
            raise RuntimeError("Gaia archive returned an unexpected table. Nothing written.")
        parts.append(frame)
    found = sum(len(f) for f in parts)
    if saved and not found:
        return {**saved[1], "unchanged": True, "ids_new": len(todo)}
    table = pd.concat(([saved[0]] if saved else []) + parts, ignore_index=True) if (saved or parts) else \
        pd.DataFrame(columns=["source_id", "r_med_geo", "r_lo_geo", "r_hi_geo"])
    raw_dir = Path(project_root).resolve() / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = raw_dir / f"{STEM}_{stamp}.csv"
    body = table.drop_duplicates("source_id").sort_values("source_id").to_csv(index=False).encode()
    path.write_bytes(body)
    manifest = {"source_name": "Gaia archive, external.gaiaedr3_distance (Bailer-Jones et al. 2021, AJ 161, 147) joined with gaiadr3.gaia_source quality columns",
                "source_url": GAIA_TAP, "licence": "CC BY-NC 3.0 IGO", "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "ids_requested": len(todo), "rows": int(table["source_id"].nunique()), "sha256": hashlib.sha256(body).hexdigest(),
                "file": path.name}
    path.with_name(path.stem + ".manifest.json").write_text(json.dumps(manifest, indent=2))
    return {**manifest, "unchanged": False, "ids_new": len(todo)}


def _bucket(d, e1, e2, g, lo, hi) -> str:
    if e1 is None or e2 is None or (e1 == 0 and e2 == 0):
        return "E-no-errors"
    if d - abs(e2) <= hi and lo <= d + abs(e1):
        return "E-same"
    return "E-small" if apart(d, g) < SMALL else "E-differs"


def apart(a: float, b: float) -> float:
    hi, lo = max(a, b), min(a, b)
    return hi / lo - 1


def check_e(nasa: pd.DataFrame, gaia: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    gaia = gaia.assign(source_id=gaia["source_id"].astype("int64")).set_index("source_id")
    rows = []
    default = nasa[nasa["default_flag"] == 1]
    for host, group in default.groupby("hostname", sort=True):
        r = group.iloc[0]
        d = _num(r.get("sy_dist"))
        sid = _text(r.get("gaia_dr3_id")).rsplit(" ", 1)[-1]
        if d is None or not sid.isdigit():
            continue
        sid = int(sid)
        dist_ref = parse_reference(_text(r.get("sy_refname")))["label"]
        star_ref = parse_reference(_text(r.get("st_refname")))["label"]
        base = {"hostname": host, "planets": "; ".join(sorted(group["pl_name"])), "gaia_dr3_id": sid,
                "nasa_dist": d, "nasa_err1": _num(r.get("sy_disterr1")), "nasa_err2": _num(r.get("sy_disterr2")),
                "dist_ref": dist_ref, "dist_from_catalogue": dist_ref in CATALOGUE_LABELS,
                "star_radius_from_catalogue": star_ref in CATALOGUE_LABELS}
        if sid not in gaia.index or pd.isna(gaia.at[sid, "r_med_geo"]):
            rows.append({**base, "bucket": "E-no-gaia"})
            continue
        g, lo, hi = (float(gaia.at[sid, c]) for c in ("r_med_geo", "r_lo_geo", "r_hi_geo"))
        bucket = _bucket(d, base["nasa_err1"], base["nasa_err2"], g, lo, hi)
        why = quality_reason(gaia.loc[sid], _num(r.get("sy_gaiamag"))) if bucket == "E-differs" else None
        rows.append({**base, "gaia_dist": g, "gaia_lo": lo, "gaia_hi": hi, "ratio": d / g,
                     "bucket": "E-quality" if why else bucket, "quality": why})
    out = pd.DataFrame(rows)
    hosts_with_distance = default.loc[default["sy_dist"].notna(), "hostname"].nunique()
    compared = out[out["bucket"] != "E-no-gaia"] if len(out) else out
    differs = compared[compared["bucket"] == "E-differs"] if len(compared) else compared
    stats = {"hosts_with_distance": int(hosts_with_distance), "hosts_with_dr3_id": int(len(out)),
             "compared": int(len(compared)), "by_bucket": {b: int((out["bucket"] == b).sum()) for b in [*FINE_WHEN, "E-no-gaia"]},
             "differs_distance_from_catalogue": int(differs["dist_from_catalogue"].sum()) if len(differs) else 0,
             "differs_star_radius_from_catalogue": int(differs["star_radius_from_catalogue"].sum()) if len(differs) else 0}
    return out, stats
