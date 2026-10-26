from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

RUN_FILE = Path("reports") / "run.json"
OK = ("fresh", "unchanged")
DOWN = ("copy", "missing")
ALERT = (*DOWN, "partial", "failed")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _when(text):
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def for_site(run: dict, previous: dict | None = None) -> dict:
    before = (previous or {}).get("sources") or {}
    sources = {}
    for name, r in run["sources"].items():
        r = {k: v for k, v in r.items() if k != "error"}
        saved = r.get("copy_from") if r["status"] == "copy" else None
        known = [t for t in ((before.get(name) or {}).get("last_ok_utc"), saved) if _when(t)]
        r["last_ok_utc"] = r["checked_utc"] if r["status"] in OK else max(known, key=_when, default=None)
        sources[name] = r
    return {**run, "sources": sources}


def start(project_root: Path) -> None:
    path = Path(project_root) / RUN_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"started_utc": now_utc(), "sources": {}}, indent=2), encoding="utf-8")


def load(project_root: Path) -> dict:
    try:
        return json.loads((Path(project_root) / RUN_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"started_utc": None, "sources": {}}


def record(project_root: Path, source: str, status: str, copy_from: str | None = None, **details) -> None:
    run = load(project_root)
    run["sources"][source] = {"status": status, "checked_utc": now_utc(), "copy_from": copy_from, **details}
    path = Path(project_root) / RUN_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, indent=2), encoding="utf-8")


def down(project_root: Path) -> list[str]:
    return sorted(s for s, r in load(project_root)["sources"].items() if r["status"] in ALERT)
