from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

STAMPED = re.compile(r"^(?P<source>.+?)_(?P<stamp>\d{8}T\d{6}Z)")


def older_copies(names: list[str]) -> list[str]:
    newest = {}
    for name in names:
        if m := STAMPED.match(name):
            newest[m["source"]] = max(newest.get(m["source"], ""), m["stamp"])
    return sorted(n for n in names if (m := STAMPED.match(n)) and m["stamp"] != newest[m["source"]])


def fingerprints(raw_dir: Path) -> dict:
    raw_dir = Path(raw_dir)
    names = [p.name for p in raw_dir.iterdir() if p.is_file()] if raw_dir.is_dir() else []
    old = set(older_copies(names))
    return {n: hashlib.sha256((raw_dir / n).read_bytes()).hexdigest() for n in sorted(names) if STAMPED.match(n) and n not in old}


def saved_at(raw_dir: Path, stem: str) -> str | None:
    files = sorted(p for p in Path(raw_dir).glob(f"{stem}_*Z.manifest.json") if (m := STAMPED.match(p.name)) and m["source"] == stem)
    try:
        return json.loads(files[-1].read_text(encoding="utf-8")).get("retrieved_at_utc") if files else None
    except (OSError, ValueError):
        return None
