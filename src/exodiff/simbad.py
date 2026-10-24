from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from .screening import _text

SIMBAD_TAP = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"
STEM = "simbad_idents"
CHUNK = 300


def norm(name: str) -> str:
    return " ".join(str(name).split()).casefold()


def strip_name_prefix(ident: str) -> str:
    return ident[5:] if ident.startswith("name ") else ident


def letter(planet: str) -> str:
    return planet.rsplit(" ", 1)[-1] if " " in planet else ""


def fetch_idents(gaia_ids: list[str], project_root: Path, session=None) -> dict:
    post = session.post if session else requests.post
    raw_dir = Path(project_root).resolve() / "data" / "raw"
    saved_files = sorted(raw_dir.glob(f"{STEM}_*Z.json"))
    saved = json.loads(saved_files[-1].read_text()) if saved_files else {}
    frames = []
    ids = sorted(set(gaia_ids) - set(saved))
    for i in range(0, len(ids), CHUNK):
        names = ",".join("'" + g.replace("'", "''") + "'" for g in ids[i:i + CHUNK])
        query = ("SELECT g.id AS gaia, a.id AS ident FROM ident AS g JOIN ident AS a ON g.oidref = a.oidref "
                 f"WHERE g.id IN ({names})")
        try:
            r = post(SIMBAD_TAP, data={"request": "doQuery", "lang": "adql", "format": "csv", "query": query}, timeout=(15, 300))
            r.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"SIMBAD query failed: {exc}. Nothing written.") from exc
        if not r.text.endswith("\n"):
            raise RuntimeError("SIMBAD reply does not end with a newline; possible truncated download. Nothing written.")
        frame = pd.read_csv(StringIO(r.text), dtype=str)
        if not {"gaia", "ident"} <= set(frame.columns):
            raise RuntimeError("SIMBAD returned an unexpected table. Nothing written.")
        frames.append(frame)
    table = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["gaia", "ident"])
    found = {g: sorted({norm(x) for x in grp["ident"]}) for g, grp in table.groupby("gaia")}
    if saved_files and not found:
        manifest = json.loads(saved_files[-1].with_name(saved_files[-1].stem + ".manifest.json").read_text())
        return {**manifest, "unchanged": True, "ids_new": len(ids)}
    idents = saved | found
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = raw_dir / f"{STEM}_{stamp}.json"
    body = json.dumps(idents, indent=0, sort_keys=True).encode()
    path.write_bytes(body)
    manifest = {"source_name": "SIMBAD (CDS, Strasbourg), table ident", "source_url": SIMBAD_TAP,
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "ids_requested": len(ids),
                "objects_found": len(idents), "sha256": hashlib.sha256(body).hexdigest(), "file": path.name}
    path.with_name(path.stem + ".manifest.json").write_text(json.dumps(manifest, indent=2))
    return {**manifest, "unchanged": False, "ids_new": len(ids)}


def latest_idents(project_root: Path) -> dict:
    raw_dir = Path(project_root).resolve() / "data" / "raw"
    files = sorted(p for p in raw_dir.glob(f"{STEM}_*Z.json"))
    return json.loads(files[-1].read_text()) if files else {}


def host_gaia(nasa: pd.DataFrame, planets) -> dict:
    rows = nasa[nasa["pl_name"].isin(set(planets))].sort_values("default_flag", ascending=False)
    out = {}
    for name, gid in zip(rows["pl_name"], rows["gaia_dr3_id"]):
        if name not in out and _text(gid):
            out[name] = " ".join(_text(gid).split())
    return out


def join_by_host(eu: pd.DataFrame, unmatched: list[str], gaia_of: dict, idents: dict, taken: set) -> dict:
    star_index: dict[str, list[str]] = {}
    for _, row in eu.iterrows():
        name = _text(row["name"])
        if name in taken:
            continue
        stars = [_text(row.get("star_name"))] + [s for s in str(row.get("star_alternate_names") or "").split(",")]
        for s in {norm(s) for s in stars if s and s.strip() and s != "nan"}:
            star_index.setdefault(s, []).append(name)
    matched, ambiguous = {}, []
    for planet in sorted(unmatched):
        gid = gaia_of.get(planet)
        if not gid or gid not in idents:
            continue
        names = {strip_name_prefix(i) for i in idents[gid]} | set(idents[gid])
        candidates = sorted({eu_name for ident in names for eu_name in star_index.get(ident, [])
                             if letter(eu_name) == letter(planet)})
        if len(candidates) == 1:
            matched[planet] = candidates[0]
        elif candidates:
            ambiguous.append({"pl_name": planet, "eu_names": candidates})
    used = {}
    for planet, eu_name in list(matched.items()):
        if eu_name in used:
            ambiguous.append({"pl_name": planet, "eu_names": [eu_name], "also": used[eu_name]})
            matched.pop(planet)
            matched.pop(used[eu_name], None)
        else:
            used[eu_name] = planet
    return {"matched": matched, "ambiguous": ambiguous}
