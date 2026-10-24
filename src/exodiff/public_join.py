from __future__ import annotations

import pandas as pd


def normalise(name) -> str:
    return " ".join(str(name or "").split()).casefold()


def public_names(acf: dict) -> list[str]:
    candidates = [str(acf.get("exo_id") or "").replace("_", " ")]
    host, letter = acf.get("pl_hostname"), acf.get("pl_letter")
    if host and letter:
        candidates.append(f"{host} {letter}")
    return [normalise(c) for c in candidates if normalise(c)]


PUBLIC_PAGE_PREFIX = "https://science.nasa.gov/"


def _valid(record) -> bool:
    return isinstance(record, dict) and isinstance(record.get("acf"), dict) and isinstance(record.get("id"), int)


def join_public(records: list, archive_names) -> dict:
    by_norm: dict[str, str] = {}
    for name in sorted(set(archive_names)):
        by_norm.setdefault(normalise(name), name)
    matched: dict[str, dict] = {}
    public_only, ambiguous, rejected, via_fallback = [], [], [], 0
    for record in sorted((r for r in records if _valid(r)), key=lambda r: r["id"]):
        acf = record.get("acf") or {}
        names = public_names(acf)
        target = next((by_norm[n] for n in names if n in by_norm), None)
        if target is None:
            public_only.append({"id": record.get("id"), "exo_id": acf.get("exo_id"), "display_name": acf.get("display_name"),
                                "link": record.get("link")})
            continue
        if names and names[0] not in by_norm:
            via_fallback += 1
        link = record.get("link") if isinstance(record.get("link"), str) else None
        if link and not link.startswith(PUBLIC_PAGE_PREFIX):
            rejected.append({"id": record.get("id"), "reason": "link outside science.nasa.gov", "link": link[:200]})
            link = None
        info = {"id": record.get("id"), "link": link, "modified": record.get("modified"), "acf": acf}
        if target in matched:
            ambiguous.append({"pl_name": target, "ids": [matched[target]["id"], record.get("id")]})
            continue
        matched[target] = info
    archive_only = sorted(set(archive_names) - set(matched))
    return {
        "matched": matched,
        "archive_only": archive_only,
        "public_only": public_only,
        "ambiguous": ambiguous,
        "rejected": rejected + [{"reason": "malformed record"} for r in records if not _valid(r)],
        "stats": {"public_records": len(records), "archive_planets": len(set(archive_names)), "matched": len(matched),
                  "matched_via_fallback": via_fallback, "archive_only": len(archive_only),
                  "public_only": len(public_only), "ambiguous": len(ambiguous),
                  "rejected": len(rejected) + sum(1 for r in records if not _valid(r))},
    }


def archive_planet_names(frame: pd.DataFrame) -> list[str]:
    return sorted(frame["pl_name"].dropna().astype(str).unique())
