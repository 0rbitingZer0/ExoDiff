from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

PUBLIC_URL = "https://science.nasa.gov/wp-json/wp/v2/exoplanet"
FIELDS = "id,slug,link,modified,acf"
USER_AGENT = "ExoDiff (data experiment on the NASA Exoplanet Archive; https://github.com/0rbitingZer0)"
SNAPSHOT_STEM = "nasa_public_catalog"


class PublicCatalogError(RuntimeError):
    pass


def _get(session, page: int, per_page: int, timeout: int, extra: dict | None = None):
    response = session.get(PUBLIC_URL, params={"per_page": per_page, "page": page, "_fields": FIELDS, **(extra or {})},
                           headers={"User-Agent": USER_AGENT}, timeout=(15, timeout))
    if response.status_code == 429 or response.status_code >= 500:
        raise PublicCatalogError(f"HTTP {response.status_code} on page {page}; stopping and keeping the last snapshot")
    response.raise_for_status()
    return response


def canonical_bytes(records: list) -> bytes:
    return json.dumps(sorted(records, key=lambda r: str(r.get("id", "")) if isinstance(r, dict) else ""), sort_keys=True,
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _read_all(session, per_page: int, delay_seconds: float, timeout: int, extra: dict | None = None) -> tuple[list, int, int]:
    first = _get(session, 1, per_page, timeout, extra)
    total = int(first.headers.get("X-WP-Total", "0"))
    pages = min(int(first.headers.get("X-WP-TotalPages", "0")), -(-total // per_page))
    records = list(first.json())
    for page in range(2, pages + 1):
        time.sleep(delay_seconds)
        records.extend(_get(session, page, per_page, timeout, extra).json())
    return records, total, max(1, pages)


def _write(raw_dir: Path, records: list, total: int, requests_made: int, mode: str) -> dict:
    ids = [r.get("id") for r in records]
    if not total or len(records) != total:
        raise PublicCatalogError(f"got {len(records)} records but the endpoint reports {total}; nothing written")
    if len(set(ids)) != len(ids):
        raise PublicCatalogError("duplicate ids across pages (the list changed during the fetch); nothing written")
    body = canonical_bytes(records)
    digest = hashlib.sha256(body).hexdigest()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    data_path = raw_dir / f"{SNAPSHOT_STEM}_{stamp}.json"
    data_path.write_bytes(body)
    manifest = {
        "source_name": "NASA Science exoplanet catalogue (science.nasa.gov), WordPress REST read endpoint",
        "source_url": PUBLIC_URL,
        "fields": FIELDS,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "reported_total": total,
        "requests": requests_made,
        "mode": mode,
        "modified_max": max((r.get("modified") or "" for r in records), default=""),
        "sha256_canonical_json": digest,
        "note": "Undocumented endpoint; field names follow the archive's pre-2021 naming. Optional input to check C.",
    }
    data_path.with_name(f"{SNAPSHOT_STEM}_{stamp}.manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"unchanged": False, "records": len(records), "path": str(data_path), "sha256": digest,
            "retrieved_at_utc": manifest["retrieved_at_utc"], "requests": requests_made, "mode": mode}


def fetch_public_catalog(project_root: Path, per_page: int = 100, delay_seconds: float = 1.0,
                         timeout_seconds: int = 60, session=None) -> dict:
    session = session or requests.Session()
    raw_dir = Path(project_root).resolve() / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    try:
        saved = latest_public_snapshot(project_root)
    except PublicCatalogError:
        saved = None
    try:
        if saved:
            records, manifest = saved
            since = manifest.get("modified_max") or max((r.get("modified") or "" for r in records), default="")
            since = min(since, manifest["retrieved_at_utc"][:19])
            since = (datetime.fromisoformat(since) - timedelta(days=1)).isoformat(timespec="seconds")
            changed, changed_total, pages = _read_all(session, per_page, delay_seconds, timeout_seconds, {"modified_after": since})
            time.sleep(delay_seconds)
            total = int(_get(session, 1, 1, timeout_seconds).headers.get("X-WP-Total", "0"))
            merged = {r["id"]: r for r in records}
            really_changed = [r for r in changed if merged.get(r["id"]) != r]
            merged.update({r["id"]: r for r in changed})
            if len(merged) == total and len(changed) == changed_total:
                if not really_changed:
                    return {"unchanged": True, "records": len(records), "sha256": manifest["sha256_canonical_json"],
                            "retrieved_at_utc": manifest["retrieved_at_utc"], "requests": pages + 1, "mode": "changes only"}
                return _write(raw_dir, list(merged.values()), total, pages + 1, f"changes only ({len(really_changed)} records)")
            time.sleep(delay_seconds)
        records, total, pages = _read_all(session, per_page, delay_seconds, timeout_seconds)
    except (requests.RequestException, ValueError) as exc:
        raise PublicCatalogError(f"public catalogue fetch failed: {exc}") from exc
    return _write(raw_dir, records, total, pages, "full")


def latest_public_snapshot(project_root: Path) -> tuple[list, dict] | None:
    raw_dir = Path(project_root).resolve() / "data" / "raw"
    manifests = []
    for path in raw_dir.glob(f"{SNAPSHOT_STEM}_*.manifest.json"):
        try:
            manifests.append((json.loads(path.read_text(encoding="utf-8"))["retrieved_at_utc"], path))
        except (OSError, ValueError, KeyError):
            continue
    if not manifests:
        return None
    _, path = max(manifests)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    data = path.with_name(path.name.replace(".manifest.json", ".json")).read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest["sha256_canonical_json"]:
        raise PublicCatalogError(f"{path.name}: data file does not match its recorded SHA-256")
    return json.loads(data), manifest
