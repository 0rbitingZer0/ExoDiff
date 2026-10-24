from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from . import __version__

NASA_TAP_SYNC_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
NASA_TAP_DOCS_URL = "https://exoplanetarchive.ipac.caltech.edu/docs/TAP/usingTAP.html"
NASA_COLUMNS_URL = "https://exoplanetarchive.ipac.caltech.edu/docs/API_PS_columns.html"
NASA_DATA_DOI_URL = "https://exoplanetarchive.ipac.caltech.edu/docs/doi.html"

BASE_COLUMNS = [
    "pl_name",
    "hostname",
    "soltype",
    "default_flag",
    "pl_controv_flag",
    "pl_rade",
    "pl_radeerr1",
    "pl_radeerr2",
    "pl_radelim",
    "pl_refname",
    "pl_pubdate",
    "st_rad",
    "st_raderr1",
    "st_raderr2",
    "st_refname",
    "discoverymethod",
    "disc_year",
    "tran_flag",
    "pl_ratror",
    "pl_ratrorerr1",
    "pl_ratrorerr2",
    "pl_ratrorlim",
    "pl_bmasse", "pl_bmasseerr1", "pl_bmasseerr2", "pl_bmasselim", "pl_bmassprov",
    "pl_dens", "pl_denserr1", "pl_denserr2", "pl_denslim",
    "pl_orbper", "pl_orbpererr1", "pl_orbpererr2", "pl_orbperlim",
    "pl_orbsmax", "pl_orbsmaxerr1", "pl_orbsmaxerr2", "pl_orbsmaxlim",
    "pl_ratdor", "pl_ratdorerr1", "pl_ratdorerr2", "pl_ratdorlim",
    "pl_orbeccen", "pl_orbeccenlim",
    "st_mass", "st_masserr1", "st_masserr2", "st_masslim", "st_radlim",
    "cb_flag",
]


MIN_FULL_PULL_ROWS = 10_000


CONFIRMED_SOLTYPE = "Published Confirmed"
SNAPSHOT_STEM = "nasa_ps_confirmed"


def build_query(limit: Optional[int] = None) -> str:
    top = f"TOP {int(limit)} " if limit is not None else ""
    if limit is not None and int(limit) < 1:
        raise ValueError("limit must be a positive integer")
    return f"SELECT {top}* FROM ps WHERE soltype = '{CONFIRMED_SOLTYPE}'"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


FINGERPRINT_QUERY = ("SELECT max(rowupdate) AS last_update, max(releasedate) AS last_release, count(*) AS row_count, "
                     "count(pl_rade) AS with_radius, count(pl_bmasse) AS with_mass, count(pl_orbsmax) AS with_orbit, "
                     f"count(st_mass) AS with_star_mass FROM ps WHERE soltype = '{CONFIRMED_SOLTYPE}'")


def archive_fingerprint(session=None, timeout_seconds: int = 60) -> dict:
    getter = session.get if session else requests.get
    try:
        r = getter(NASA_TAP_SYNC_URL, params={"query": FINGERPRINT_QUERY, "format": "csv"},
                   headers={"User-Agent": f"ExoDiff/{__version__} (data experiment)"}, timeout=(15, timeout_seconds))
        r.raise_for_status()
        from io import StringIO
        row = pd.read_csv(StringIO(r.text), dtype=str).iloc[0]
    except Exception as exc:
        raise RuntimeError(f"archive fingerprint query failed: {exc}") from exc
    return {k: str(row[k]) for k in row.index}


def newest_manifests(raw_dir: Path) -> list[Path]:
    found = []
    for path in Path(raw_dir).glob("*.manifest.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if re.search(r"\bFROM\s+ps\b", data.get("query", ""), re.IGNORECASE) and not data.get("limited_smoke_test"):
            found.append((data.get("retrieved_at_utc", ""), path))
    return [path for _, path in sorted(found)]


def reuse_saved_copy(project_root: Path) -> dict | None:
    project_root = Path(project_root).resolve()
    manifests = newest_manifests(project_root / "data" / "raw")
    if not manifests:
        return None
    manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
    raw_path = manifests[-1].with_name(manifests[-1].name.replace(".manifest.json", ".csv"))
    if not raw_path.exists() or sha256_bytes(raw_path.read_bytes()) != manifest["sha256_raw_response"]:
        return None
    latest_path = project_root / "data" / "processed" / f"{SNAPSHOT_STEM}_latest.csv"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(raw_path, latest_path)
    return manifest


def fetch_radius_solutions(
    project_root: Path,
    limit: Optional[int] = None,
    timeout_seconds: int = 300,
    max_retries: int = 4,
    if_changed: bool = True,
) -> dict:
    project_root = Path(project_root).resolve()
    raw_dir = project_root / "data" / "raw"
    processed_dir = project_root / "data" / "processed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    fingerprint = None
    if if_changed and limit is None:
        try:
            fingerprint = archive_fingerprint()
        except RuntimeError:
            fingerprint = None
        saved = newest_manifests(raw_dir)
        if fingerprint and saved and json.loads(saved[-1].read_text(encoding="utf-8")).get("fingerprint") == fingerprint:
            manifest = reuse_saved_copy(project_root)
            if manifest:
                return {"unchanged": True, "rows": manifest["row_count"], "planets": manifest["planet_count"],
                        "columns": manifest["column_count"], "raw_path": None, "manifest_path": str(saved[-1]),
                        "latest_path": str(processed_dir / f"{SNAPSHOT_STEM}_latest.csv"),
                        "sha256": manifest["sha256_raw_response"], "retrieved_at_utc": manifest["retrieved_at_utc"],
                        "limited_smoke_test": False}

    query = build_query(limit=limit)
    params = {"query": query, "format": "csv"}
    headers = {"User-Agent": f"ExoDiff/{__version__} (educational research case study)"}
    last_error: Optional[Exception] = None
    response = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(
                NASA_TAP_SYNC_URL,
                params=params,
                headers=headers,
                timeout=(15, timeout_seconds),
            )
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < max_retries:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = min(60.0, max(1.0, float(retry_after))) if retry_after else min(30.0, 2 ** attempt)
                    except ValueError:
                        delay = min(30.0, 2 ** attempt)
                    time.sleep(delay)
                    continue
            response.raise_for_status()
            break
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= max_retries:
                raise RuntimeError(
                    "Could not reach NASA TAP after retries. Check your internet connection, "
                    "then try again. No output data were written."
                ) from exc
            time.sleep(min(30.0, 2 ** attempt))

    if response is None:
        raise RuntimeError(f"NASA TAP request failed: {last_error}")

    raw_bytes = response.content
    text_sample = response.text[:1000].lstrip().lower()
    if not raw_bytes.strip() or "error" in text_sample[:200] and "pl_name" not in text_sample:
        raise RuntimeError(
            "NASA TAP returned an empty response or an apparent error payload. "
            "No output data were written. Response preview: " + response.text[:500]
        )

    declared = response.headers.get("Content-Length")
    if declared and declared.isdigit() and int(declared) != len(raw_bytes) and \
            not response.headers.get("Content-Encoding"):
        raise RuntimeError(
            f"NASA TAP response is {len(raw_bytes)} bytes but declared {declared}; possible truncated "
            "download. No output data were written."
        )
    if not raw_bytes.endswith(b"\n"):
        raise RuntimeError("NASA TAP response does not end with a newline; possible truncated download. "
                           "No output data were written.")

    try:
        from io import BytesIO
        frame = pd.read_csv(BytesIO(raw_bytes))
    except Exception as exc:
        raise RuntimeError(
            "NASA TAP returned a response that could not be parsed as CSV. "
            "No output data were written. Preview: " + response.text[:500]
        ) from exc

    if limit is None and len(frame) < MIN_FULL_PULL_ROWS:
        raise RuntimeError(
            f"Full pull returned only {len(frame)} rows (expected at least {MIN_FULL_PULL_ROWS}); possible "
            "partial response. No output data were written."
        )

    if fingerprint and str(len(frame)) != str(fingerprint.get("row_count")):
        raise RuntimeError(f"NASA TAP returned {len(frame):,} rows but the archive reports {fingerprint.get('row_count')}; "
                           "possible partial download. No output data were written.")
    missing = sorted(set(BASE_COLUMNS) - set(frame.columns))
    if missing:
        raise RuntimeError(
            "NASA TAP response schema differs from the columns expected by this version: "
            + ", ".join(missing)
            + ". Check the current NASA column definitions before changing the query."
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"{SNAPSHOT_STEM}_{stamp}"
    raw_path = raw_dir / f"{stem}.csv"
    manifest_path = raw_dir / f"{stem}.manifest.json"
    digest = sha256_bytes(raw_bytes)

    raw_path.write_bytes(raw_bytes)
    manifest = {
        "project_version": __version__,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_name": "NASA Exoplanet Archive — Planetary Systems (PS) table",
        "source_url": NASA_TAP_SYNC_URL,
        "source_docs": [NASA_TAP_DOCS_URL, NASA_COLUMNS_URL, NASA_DATA_DOI_URL],
        "query": query,
        "limited_smoke_test": limit is not None,
        "requested_limit": limit,
        "row_count": int(len(frame)),
        "planet_count": int(frame["pl_name"].nunique()),
        "column_count": int(len(frame.columns)),
        "columns": list(frame.columns),
        "sha256_raw_response": digest,
        "fingerprint": fingerprint,
        "response_content_type": response.headers.get("Content-Type"),
        "response_etag": response.headers.get("ETag"),
        "response_last_modified": response.headers.get("Last-Modified"),
        "important_note": (
            "A TOP-limited response is not a random/representative sample and must not "
            "be used to infer population rates. Published uncertainties may not share "
            "the same statistical interpretation across papers."
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    latest_path = processed_dir / f"{SNAPSHOT_STEM}_latest.csv"
    shutil.copyfile(raw_path, latest_path)

    return {
        "unchanged": False,
        "retrieved_at_utc": manifest["retrieved_at_utc"],
        "rows": len(frame),
        "planets": int(frame["pl_name"].nunique()),
        "columns": len(frame.columns),
        "raw_path": str(raw_path),
        "manifest_path": str(manifest_path),
        "latest_path": str(latest_path),
        "sha256": digest,
        "limited_smoke_test": limit is not None,
    }


COMPOSITE_STEM = "nasa_pscomppars"
MIN_COMPOSITE_ROWS = 5_000
COMPOSITE_COLUMNS = [
    "pl_name", "pl_rade", "pl_rade_reflink", "pl_bmasse", "pl_bmasse_reflink", "pl_bmassprov",
    "pl_orbper", "pl_orbper_reflink", "pl_orbsmax", "pl_orbsmax_reflink",
    "pl_orbeccen", "pl_orbeccenlim", "pl_orbeccen_reflink", "sy_dist", "sy_dist_reflink",
]


def fetch_composite(project_root: Path, timeout_seconds: int = 300, session=None) -> dict:
    project_root = Path(project_root).resolve()
    raw_dir = project_root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    query = f"SELECT {', '.join(COMPOSITE_COLUMNS)} FROM pscomppars"
    getter = session.get if session else requests.get
    try:
        response = getter(NASA_TAP_SYNC_URL, params={"query": query, "format": "csv"},
                          headers={"User-Agent": f"ExoDiff/{__version__} (data experiment)"}, timeout=(15, timeout_seconds))
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not download the composite table: {exc}. No output data were written.") from exc
    raw_bytes = response.content
    declared = response.headers.get("Content-Length") if hasattr(response, "headers") else None
    if declared and declared.isdigit() and int(declared) != len(raw_bytes) and not response.headers.get("Content-Encoding"):
        raise RuntimeError(f"Composite table is {len(raw_bytes)} bytes but declared {declared}; possible truncated download.")
    if not raw_bytes.endswith(b"\n"):
        raise RuntimeError("Composite table response does not end with a newline; possible truncated download.")
    from io import BytesIO
    frame = pd.read_csv(BytesIO(raw_bytes))
    missing = sorted(set(COMPOSITE_COLUMNS) - set(frame.columns))
    if missing:
        raise RuntimeError("Composite table schema differs from what this version expects: " + ", ".join(missing))
    if frame["pl_name"].duplicated().any():
        raise RuntimeError("Composite table has more than one row for a planet; refusing to use it.")
    if len(frame) < MIN_COMPOSITE_ROWS:
        raise RuntimeError(f"Composite table has only {len(frame)} rows (expected at least {MIN_COMPOSITE_ROWS}); possible partial response.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = raw_dir / f"{COMPOSITE_STEM}_{stamp}.csv"
    raw_path.write_bytes(raw_bytes)
    manifest = {"project_version": __version__, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "source_name": "NASA Exoplanet Archive — Planetary Systems Composite Parameters (pscomppars)",
                "source_url": NASA_TAP_SYNC_URL, "query": query, "row_count": int(len(frame)),
                "sha256_raw_response": sha256_bytes(raw_bytes)}
    raw_path.with_name(raw_path.name.replace(".csv", ".manifest.json")).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"rows": int(len(frame)), "raw_path": str(raw_path), "sha256": manifest["sha256_raw_response"],
            "retrieved_at_utc": manifest["retrieved_at_utc"]}
