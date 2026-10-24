from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from .polite import fetch_all

OVERVIEW_URL = "https://exoplanetarchive.ipac.caltech.edu/overview/{}"
STEM = "nasa_overview_notes"
_MARKER = "var json = "
WORKERS = 10
REREAD_RUNS = 7


def _text_or_none(value, limit: int):
    return value[:limit] if isinstance(value, str) else None


def parse_overview(html: str) -> dict:
    start = html.find(_MARKER)
    if start < 0:
        raise ValueError("no embedded data on page")
    data, _ = json.JSONDecoder().raw_decode(html[start + len(_MARKER):])
    system = data["system"]
    refs = data.get("reference_dictionary") or {}
    objects = [("system", system["system_info"].get("id"), system["system_info"])]
    for kind, group, key in (("star", "stellar_set", "stars"), ("planet", "planet_set", "planets")):
        for name, obj in ((system["objects"].get(group) or {}).get(key) or {}).items():
            objects.append((kind, name, obj))
    notes, aliases = [], {}
    for kind, name, obj in objects:
        alias = (obj.get("alias_set") or {}).get("aliases")
        if alias and kind != "system":
            aliases[name] = alias
        for note in (obj.get("note_set") or {}).get("notes") or []:
            if not isinstance(note, dict) or note.get("private_flag") or not isinstance(note.get("note"), str):
                continue
            ref = refs.get(note.get("refid")) if isinstance(note.get("refid"), str) else None
            ref = ref if isinstance(ref, dict) else {}
            notes.append({"object": str(name)[:120], "kind": kind, "note": note["note"].strip()[:4000],
                          "reference": _text_or_none(ref.get("authors"), 300), "bibcode": _text_or_none(ref.get("bibcode"), 40),
                          "date": _text_or_none(note.get("creationdate"), 30)})
    return {"system": system["system_info"].get("id"), "compiled": data.get("manifest", {}).get("compilation_date"),
            "planets": [n for k, n, _ in objects if k == "planet"], "notes": notes, "aliases": aliases}


def pages_to_read(hosts: list[str], saved: dict, updated: dict | None = None) -> list[str]:
    systems, read_at = saved.get("systems", {}), saved.get("read_at", {})
    hosts = sorted(set(hosts))

    def stale(h: str) -> bool:
        if h not in systems or not read_at.get(h):
            return True
        when = (updated or {}).get(h) or ""
        return bool(when) and when >= read_at[h]
    must = [h for h in hosts if stale(h)]
    rest = sorted((h for h in hosts if h not in set(must)), key=lambda h: (read_at.get(h, ""), h))
    return must + rest[:-(-len(hosts) // REREAD_RUNS)]


def fetch_overviews(hosts: list[str], project_root: Path, updated: dict | None = None, delay_seconds: float = 1.0,
                    session=None, sleep=time.sleep, workers: int = WORKERS, progress: bool = False) -> dict:
    saved = latest_snapshot(project_root)
    todo = pages_to_read(hosts, saved, updated)
    fetched, failures = fetch_all({h: OVERVIEW_URL.format(quote(h)) for h in todo}, parse_overview,
                                  workers, delay_seconds, session, sleep, progress) if todo else ({}, {})
    if todo and not fetched:
        raise RuntimeError(f"no overview page could be read ({len(failures)} failures). Nothing written.")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    old, read_at = saved.get("systems", {}), saved.get("read_at", {})
    systems = {h: old[h] for h in set(hosts) if h in old} | fetched
    read = {h: read_at.get(h, "") for h in systems} | {h: today for h in fetched}
    raw_dir = Path(project_root).resolve() / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = raw_dir / f"{STEM}_{stamp}.json"
    body = json.dumps({"systems": systems, "read_at": read, "failures": failures}, indent=1, sort_keys=True).encode()
    path.write_bytes(body)
    manifest = {"source_name": "NASA Exoplanet Archive System Overview pages (notes and aliases)",
                "source_url": OVERVIEW_URL.format("<host>"), "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "hosts_requested": len(todo), "hosts_read": len(fetched), "hosts_kept": len(systems), "failures": len(failures),
                "notes": sum(len(s["notes"]) for s in systems.values()), "sha256": hashlib.sha256(body).hexdigest(),
                "content_sha256": content_sha256({"systems": systems}), "file": path.name}
    path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest | {"unchanged": systems == {h: old[h] for h in set(hosts) if h in old}}


def content_sha256(snapshot: dict) -> str:
    return hashlib.sha256(json.dumps(snapshot.get("systems", {}), sort_keys=True).encode()).hexdigest()


def latest_snapshot(project_root: Path) -> dict:
    raw_dir = Path(project_root).resolve() / "data" / "raw"
    files = sorted(p for p in raw_dir.glob(f"{STEM}_*.json") if not p.name.endswith(".manifest.json"))
    return json.loads(files[-1].read_text()) if files else {"systems": {}, "failures": {}}
