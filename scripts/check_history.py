from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import re
import sys

LIMITS = {"ledger.json": 10_000_000, "updates.json": 10_000_000, "meta.json": 2_000_000}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CHECKS = set("ABCDEF")
CAUSES = {"first run", "new data", "rule change", "new data and a rule change", "same data re-checked"}
OK = {"fresh", "unchanged"}
STATUSES = {*OK, "copy", "missing", "skipped", "partial", "failed"}
EXPECTED_QUERY = "SELECT * FROM ps WHERE soltype = 'Published Confirmed'"
LISTS = ("new_findings", "resolved_findings", "new_planets", "removed_planets", "notes_changed")
ENTRY_KEYS = {"date", "data", "code", "planets", "planets_with_findings", "findings", "notes", "by_check", "cause",
              "not_checked", "checked_again", *LISTS}


def _date_ok(d) -> bool:
    if not (isinstance(d, str) and DATE.match(d)):
        return False
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    return "2026-10-01" <= d <= tomorrow


def _str(x, n: int, none_ok: bool = False) -> bool:
    return (none_ok and x is None) or (isinstance(x, str) and len(x) <= n)


def _count(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool) and x >= 0


def _ledger(led) -> list[str]:
    if not isinstance(led, dict) or set(led) != {"run", "baseline", "planets", "leads", "notes"}:
        return ["ledger.json: not the expected keys"]
    out, run = [], led["run"]
    if not (isinstance(run, dict) and set(run) <= {"date", "data", "code", "skipped"} and _date_ok(run.get("date"))
            and _str(run.get("data"), 64) and _str(run.get("code"), 64) and set(run.get("skipped") or []) <= CHECKS):
        out.append("ledger.json: run record not the expected shape")
    if not _date_ok(led["baseline"]):
        out.append("ledger.json: baseline date")
    if not (isinstance(led["planets"], dict) and all(_str(k, 120) and _date_ok(v) for k, v in led["planets"].items())):
        out.append("ledger.json: planets not name -> date")
    if not (isinstance(led["leads"], dict) and all(_str(k, 300) and isinstance(v, dict) and set(v) == {"since", "key"}
                                                   and _date_ok(v["since"]) and _str(v["key"], 40, True)
                                                   for k, v in led["leads"].items())):
        out.append("ledger.json: a finding without a valid first-seen date or key")
    if not (isinstance(led["notes"], dict) and all(_str(k, 120) and isinstance(v, dict) and set(v) <= CHECKS
                                                   and all(_count(n) for n in v.values()) for k, v in led["notes"].items())):
        out.append("ledger.json: notes not counted per check")
    return out


def _finding(f) -> bool:
    return (isinstance(f, dict) and set(f) <= {"kind", "rule", "ref", "key", "planet"} and f.get("kind") in CHECKS
            and _str(f.get("rule"), 40) and _str(f.get("ref"), 200, True) and _str(f.get("key"), 40, True) and _str(f.get("planet"), 120))


def _entry(e) -> bool:
    if not (isinstance(e, dict) and set(e) <= ENTRY_KEYS and _date_ok(e.get("date")) and e.get("cause") in CAUSES):
        return False
    if not all(_count(e.get(k)) for k in ("planets", "planets_with_findings", "findings", "notes")):
        return False
    if not (isinstance(e.get("by_check"), dict) and set(e["by_check"]) <= CHECKS and all(_count(v) for v in e["by_check"].values())):
        return False
    if not (_str(e.get("data"), 64) and _str(e.get("code"), 64)):
        return False
    for k in ("not_checked", "checked_again"):
        if k in e and not (isinstance(e[k], list) and set(e[k]) <= CHECKS):
            return False
    for k in ("new_planets", "removed_planets"):
        if k in e and not (isinstance(e[k], list) and all(_str(x, 120) for x in e[k])):
            return False
    for k in ("new_findings", "resolved_findings"):
        if k in e and not (isinstance(e[k], list) and all(_finding(x) for x in e[k])):
            return False
    if "notes_changed" in e and not (isinstance(e["notes_changed"], list) and all(
            isinstance(x, dict) and {"planet", "from", "to"} <= set(x) <= {"planet", "from", "to", "checks"} and _str(x["planet"], 120)
            and _count(x["from"]) and _count(x["to"]) and isinstance(x.get("checks", {}), dict) and set(x.get("checks", {})) <= CHECKS
            and all(isinstance(v, list) and len(v) == 2 and all(_count(n) for n in v) for v in x.get("checks", {}).values())
            for x in e["notes_changed"])):
        return False
    return True


def _time(x):
    try:
        t = datetime.fromisoformat(x) if isinstance(x, str) and len(x) <= 40 else None
    except ValueError:
        return None
    return t if t is not None and t.utcoffset() == timedelta(0) else None


def _sources(run) -> list[str]:
    sources = run.get("sources", {})
    if not (isinstance(sources, dict) and all(_str(n, 80) and isinstance(r, dict) for n, r in sources.items())):
        return ["meta.json: run sources not the expected shape"]
    for name, r in sources.items():
        checked, last_ok = _time(r.get("checked_utc")), _time(r.get("last_ok_utc"))
        if not (r.get("status") in STATUSES and checked and all(r.get(k) is None or _time(r[k]) for k in ("copy_from", "last_ok_utc"))):
            return [f"meta.json: run record of {name} not the expected shape"]
        if last_ok and (last_ok > checked or (r["status"] not in OK and last_ok == checked)):
            return [f"meta.json: {name} has a last successful check that this run doesn't support"]
    return []


def _meta(meta) -> list[str]:
    out = []
    if not (isinstance(meta, dict) and HEX64.match(str(meta.get("snapshot_sha256", ""))) and isinstance(meta.get("run"), dict)):
        return ["meta.json: not the expected shape"]
    if meta.get("query") != EXPECTED_QUERY:
        out.append("meta.json: the archive query isn't the expected one")
    out += _sources(meta["run"])
    for k in ("raw_files", "published"):
        if k in meta and not (isinstance(meta[k], dict) and all(_str(n, 200) and HEX64.match(str(h)) for n, h in meta[k].items())):
            out.append(f"meta.json: {k} not file -> SHA-256")
    strings = []
    def walk(x):
        if isinstance(x, str):
            strings.append(x)
        elif isinstance(x, dict):
            for k, v in x.items():
                walk(k); walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(meta)
    if any(len(s) > 2000 for s in strings):
        out.append("meta.json: a text over 2,000 characters")
    return out


def _continuity(new: dict, old: dict) -> list[str]:
    out = []
    old_u, new_u = old.get("updates.json"), new.get("updates.json")
    if isinstance(old_u, list) and isinstance(new_u, list) and old_u:
        tail = new_u[1:] if len(new_u) == len(old_u) + 1 else new_u
        strip = lambda e: {k: v for k, v in e.items() if k not in LISTS} if isinstance(e, dict) else e
        if len(tail) != len(old_u) or any(strip(a) != strip(b) for a, b in zip(tail, old_u)):
            out.append("updates.json: earlier updates differ from the committed ones")
        elif len(new_u) == len(old_u) + 1 and isinstance(new_u[0], dict) and new_u[0].get("date", "") < old_u[0].get("date", ""):
            out.append("updates.json: the new update is dated before the last committed one")
    old_l, new_l = old.get("ledger.json"), new.get("ledger.json")
    if isinstance(old_l, dict) and isinstance(new_l, dict):
        for part in ("leads", "planets"):
            o, n = old_l.get(part) or {}, new_l.get(part) or {}
            since = (lambda v: v.get("since")) if part == "leads" else (lambda v: v)
            if any(k in n and since(n[k]) != since(v) for k, v in o.items() if isinstance(v, (dict, str))):
                out.append(f"ledger.json: a committed first-seen date of {part} changed")
    return out


def _load(folder: Path) -> tuple[dict, list[str]]:
    data, out = {}, []
    for name, limit in LIMITS.items():
        path = folder / name
        if not path.is_file():
            out.append(f"{name}: missing")
            continue
        if path.stat().st_size > limit:
            out.append(f"{name}: {path.stat().st_size:,} bytes, over the {limit:,} limit")
            continue
        try:
            data[name] = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            out.append(f"{name}: not valid JSON ({exc})")
    return data, out


def problems(folder: Path, committed: Path | None = None) -> list[str]:
    data, out = _load(Path(folder))
    if "ledger.json" in data:
        out += _ledger(data["ledger.json"])
    if "updates.json" in data:
        u = data["updates.json"]
        if not (isinstance(u, list) and u and all(_entry(e) for e in u)):
            out.append("updates.json: an entry with unexpected fields, types or values")
    if "meta.json" in data:
        out += _meta(data["meta.json"])
    if committed is not None and not out:
        old = {k: v for k, v in _load(Path(committed))[0].items()}
        out += _continuity(data, old)
    return out


def main() -> int:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("site/data")
    committed = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    found = problems(folder, committed)
    for p in found:
        print(f"REFUSED: {p}", file=sys.stderr)
    if not found:
        print("history files: valid")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
