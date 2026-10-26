from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from exodiff import __version__
from exodiff.known_notes import load_all_notes
from exodiff.explanations import confirm_letters
from exodiff.eu_catalog import latest_eu_index
from exodiff.eu_sources import latest_sources
from exodiff.catalog_pages import classify, contradictions, page_from_record
from exodiff.overview_notes import content_sha256, latest_snapshot as latest_overviews
from exodiff.ledger import totals as ledger_totals, update as update_ledger
from exodiff.nasa import newest_manifests
from exodiff.raw_store import STAMPED, fingerprints
from exodiff import runlog
from exodiff import wording
from exodiff.check_b import OPEN as B_OPEN
from exodiff.site_planets import D_OPEN, add_explanations, build_planets
from exodiff.triage import REASONS

PROCESSED = ROOT / "data/processed"
SITE_DATA = ROOT / "site/data"
DETAIL_LIMIT = 90


NOTES = load_all_notes()
_overview = sorted(p for p in (ROOT / "data/raw").glob("nasa_overview_notes_*Z.json"))
NOTES_SHA = content_sha256(latest_overviews(ROOT)) if _overview else ""


def confirm_shared_aliases(shards: dict, d_frame: pd.DataFrame) -> int:
    eu_files = sorted((ROOT / "data/raw").glob("exoplanet_eu_*[0-9]Z.csv"))
    if d_frame is None or d_frame.empty or not eu_files:
        return 0
    eu = pd.read_csv(eu_files[-1], usecols=["name", "alternate_names"], low_memory=False)
    alternates = {n: [a.strip() for a in str(alt).split(",") if a.strip() and str(alt) != "nan"]
                  for n, alt in zip(eu["name"], eu["alternate_names"])}
    eu_names = {k: v for k, v in zip(d_frame["pl_name"], d_frame["eu_name"]) if isinstance(v, str)}
    aliases = {}
    for system in latest_overviews(ROOT).get("systems", {}).values():
        for obj, names in system.get("aliases", {}).items():
            flat = [x for v in names.values() for x in (v if isinstance(v, list) else [v])]
            aliases[obj] = flat
    planets = {name: detail for shard in shards.values() for name, detail in shard.items()}
    return confirm_letters(planets, eu_names, alternates, aliases)


def attach_notes(shards: dict) -> int:
    count = 0
    for shard in shards.values():
        for name, planet in shard.items():
            planet["nasa_notes"] = [{"text": n["notes"], "about": n["parameter"] or None, "ref": n["reference"] or None,
                                     "date": n.get("date"), "on": n.get("on", "planet"),
                                     "source": "overview page" if n.get("source") == "overview" else "discrepancy table"}
                                    for n in NOTES.get(name, [])]
            count += len(planet["nasa_notes"])
    return count


def _git_commit() -> str | None:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "scripts"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return commit + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return None


def _write(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, low_memory=False)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def check_c_inputs(snapshot_sha: str) -> tuple[pd.DataFrame, dict | None, dict]:
    stats = _read_json(ROOT / "reports/check_c.json") or {"skipped": True, "reason": "not run"}
    if stats.get("skipped"):
        return pd.DataFrame(), None, stats
    if stats.get("archive_sha256") != snapshot_sha:
        return pd.DataFrame(), None, {"skipped": True, "reason": "check C ran against a different archive snapshot"}
    return _read_csv(PROCESSED / "check_c.csv"), _read_json(PROCESSED / "public_join.json"), stats


def check_d_inputs(snapshot_sha: str) -> tuple[pd.DataFrame, dict]:
    stats = _read_json(ROOT / "reports/check_d.json") or {"skipped": True, "reason": "not run"}
    if stats.get("skipped"):
        return pd.DataFrame(), stats
    if stats.get("archive_sha256") != snapshot_sha:
        return pd.DataFrame(), {"skipped": True, "reason": "check D ran against a different archive snapshot"}
    return _read_csv(PROCESSED / "check_d.csv"), stats


def check_e_inputs(snapshot_sha: str) -> tuple[pd.DataFrame, dict]:
    stats = _read_json(ROOT / "reports/check_e.json") or {"skipped": True, "reason": "not run"}
    if stats.get("skipped"):
        return pd.DataFrame(), stats
    if stats.get("archive_sha256") != snapshot_sha:
        return pd.DataFrame(), {"skipped": True, "reason": "check E ran against a different archive snapshot"}
    return _read_csv(PROCESSED / "check_e.csv"), stats


def catalog_self_checks() -> tuple[dict, dict]:
    join = _read_json(PROCESSED / "public_join.json") or {}
    pages = {name: page_from_record(record.get("acf") or {}) for name, record in (join.get("matched") or {}).items()}
    archive = pd.read_csv(PROCESSED / "nasa_ps_confirmed_latest.csv", low_memory=False,
                          usecols=["pl_name", "pl_refname", "pl_bmasse", "pl_orbper", "pl_orbsmax", "st_mass"])
    rows = {name: g for name, g in archive.groupby("pl_name")}
    found = {name: [classify(x, page, rows.get(name)) for x in c] for name, page in pages.items() if (c := contradictions(page))}
    compared = {k: sum(1 for p in pages.values() if k in p["s"] and k in p["box"]) for k in ("mass", "period", "orbit")}
    stats = {"pages_read": len(pages), "pairs_compared": compared,
             "pages_with_contradictions": len(found), "by_quantity": {}, "by_cause": {}}
    for c in found.values():
        for x in c:
            stats["by_quantity"][x["quantity"]] = stats["by_quantity"].get(x["quantity"], 0) + 1
            stats["by_cause"][x["cause"]] = stats["by_cause"].get(x["cause"], 0) + 1
    return found, stats


def export_planets(check_c_frame: pd.DataFrame, join: dict | None,
                   check_d_frame: pd.DataFrame | None = None, check_e_frame: pd.DataFrame | None = None,
                   catalog_self: dict | None = None) -> tuple[list, dict]:
    archive = pd.read_csv(PROCESSED / "nasa_ps_confirmed_latest.csv", low_memory=False)
    row_checked = set(_read_csv(PROCESSED / "row_self_consistency.csv").get("pl_name", pd.Series(dtype=str))) | \
        set(_read_csv(PROCESSED / "identity_checks.csv").get("pl_name", pd.Series(dtype=str)))
    return build_planets(archive, _read_csv(PROCESSED / "check_a.csv"), _read_csv(PROCESSED / "check_b.csv"),
                         check_c_frame, join, row_checked, check_d_frame, check_e_frame, latest_eu_index(ROOT),
                         catalog_self)


def reconcile_planets(index: list, report: dict, c_stats: dict, d_stats: dict | None = None,
                      e_frame: pd.DataFrame | None = None) -> list[str]:
    problems = []
    a, b = report.get("check_a") or {}, report.get("check_b") or {}
    if sum(p["a"] for p in index) != a.get("leads", 0):
        problems.append(f"planet index shows {sum(p['a'] for p in index)} check-A leads, report says {a.get('leads')}")
    if sum(p["b"] for p in index) != sum((b.get("by_bucket") or {}).get(k, 0) for k in B_OPEN):
        problems.append("planet index check-B leads differ from the report's open B buckets")
    expected_c = 0 if c_stats.get("skipped") else c_stats["by_bucket"]["C-none"]
    if sum(p["c"] for p in index) != expected_c:
        problems.append(f"planet index shows {sum(p['c'] for p in index)} check-C leads, report says {expected_c}")
    d_stats = d_stats or {"skipped": True}
    expected_d = 0 if d_stats.get("skipped") else sum(d_stats["by_bucket"].get(b, 0) for b in D_OPEN) + d_stats.get("letters_planets", 0)
    if sum(p.get("x", 0) for p in index) != expected_d:
        problems.append(f"planet index shows {sum(p.get('x', 0) for p in index)} check-D leads, report says {expected_d}")
    expected_e = 0 if e_frame is None or e_frame.empty else int(
        e_frame.loc[e_frame["bucket"] == "E-differs", "planets"].str.count(";").add(1).sum())
    if sum(p.get("e", 0) for p in index) != expected_e:
        problems.append(f"planet index shows {sum(p.get('e', 0) for p in index)} check-E leads, report implies {expected_e}")
    if len({p["n"] for p in index}) != len(index):
        problems.append("duplicate planet names in the index")
    return problems


def publish_snapshot(manifest_path: Path) -> None:
    raw = manifest_path.with_name(manifest_path.name.replace(".manifest.json", ".csv"))
    target = SITE_DATA / "snapshot.csv.gz"
    tmp = target.with_suffix(".gz.tmp")
    with open(tmp, "wb") as handle, gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=0) as gz:
        gz.write(raw.read_bytes())
    os.replace(tmp, target)
    shutil.copyfile(manifest_path, SITE_DATA / "snapshot.manifest.json")


def data_fingerprints() -> dict:
    out = {}
    for name in fingerprints(ROOT / "data/raw"):
        if not name.endswith(".manifest.json"):
            continue
        source = STAMPED.match(name)["source"]
        m = _read_json(ROOT / "data/raw" / name) or {}
        out[source] = next((m[k] for k in ("sha256_raw_response", "sha256_canonical_json", "sha256") if m.get(k)), None)
    if (snap := latest_overviews(ROOT)).get("systems"):
        out["nasa_overview_notes"] = content_sha256(snap)
    if pages := latest_sources(ROOT):
        out["exoplanet_eu_sources"] = hashlib.sha256(json.dumps(pages, sort_keys=True).encode()).hexdigest()
    return dict(sorted(out.items()))


def rules_fingerprint() -> str:
    h = hashlib.sha256()
    for p in sorted((ROOT / "src/exodiff").glob("*.py")):
        h.update(p.name.encode() + p.read_bytes())
    return h.hexdigest()[:16]


def run_date() -> str:
    started = runlog.load(ROOT).get("started_utc") or ""
    return started[:10] if started else datetime.now(timezone.utc).strftime("%Y-%m-%d")


def check_inputs(manifest: dict, report: dict, previous_meta: dict, min_row_ratio: float) -> list[str]:
    problems = []
    if manifest.get("limited_smoke_test"):
        problems.append("newest snapshot is a TOP-limited smoke test")
    if report.get("input_sha256") != manifest.get("sha256_raw_response"):
        problems.append("screening report was not produced from the newest raw snapshot (sha256 differs)")
    if report.get("input_rows") != manifest.get("row_count"):
        problems.append(f"screened rows {report.get('input_rows')} != snapshot rows {manifest.get('row_count')}")
    previous_rows = previous_meta.get("snapshot_rows")
    same_query = previous_meta.get("query") == manifest.get("query")
    if same_query and previous_rows and manifest.get("row_count", 0) < min_row_ratio * previous_rows:
        problems.append(f"snapshot has {manifest.get('row_count')} rows, below {min_row_ratio:.0%} of the "
                        f"previous {previous_rows}; possible truncated download")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-row-ratio", type=float, default=0.95,
                        help="refuse to publish if the snapshot has fewer rows than this share of the previous one")
    args = parser.parse_args()

    pairs_path, rows_path = PROCESSED / "radius_pairs_for_review.csv", PROCESSED / "row_self_consistency.csv"
    report_path = ROOT / "reports/screening_report.json"
    manifests = newest_manifests(ROOT / "data/raw")
    missing = [p for p in (pairs_path, rows_path, report_path) if not p.exists()]
    if missing or not manifests:
        print("Missing inputs. Run scripts/fetch_nasa.py then scripts/screen_radius.py first.", file=sys.stderr)
        return 1
    manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    meta_path, ledger_path, updates_path = SITE_DATA / "meta.json", SITE_DATA / "ledger.json", SITE_DATA / "updates.json"
    previous_meta = _read_json(meta_path) or {}

    problems = check_inputs(manifest, report, previous_meta, args.min_row_ratio)
    if problems:
        print("Refusing to publish; site/data left unchanged:\n- " + "\n- ".join(problems), file=sys.stderr)
        return 1

    c_frame, c_join, c_stats = check_c_inputs(manifest["sha256_raw_response"])
    d_frame, d_stats = check_d_inputs(manifest["sha256_raw_response"])
    e_frame, e_stats = check_e_inputs(manifest["sha256_raw_response"])
    f_found, f_stats = catalog_self_checks()
    planet_index, planet_shards = export_planets(c_frame, c_join, d_frame, e_frame, f_found)
    f_shown = sum(1 for s in planet_shards.values() for p in s.values() for l in p["leads"] if l["kind"] == "F")
    if f_shown != sum(f_stats["by_quantity"].values()):
        print(f"Refusing to publish: {f_shown} check-F notes on planet pages, stats say {sum(f_stats['by_quantity'].values())}", file=sys.stderr)
        return 1
    planet_problems = reconcile_planets(planet_index, report, c_stats, d_stats, e_frame)
    notes_shown = attach_notes(planet_shards)
    if planet_problems:
        print("Refusing to publish; site/data left unchanged:\n- " + "\n- ".join(planet_problems), file=sys.stderr)
        return 1
    code_commit = _git_commit()
    explanations = add_explanations(planet_index, planet_shards)
    letters_confirmed = confirm_shared_aliases(planet_shards, d_frame)
    sources = data_fingerprints()
    data_id = hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()[:16]
    skipped = [k for k, stats in (("C", c_stats), ("D", d_stats), ("E", e_stats)) if stats.get("skipped")]
    skipped += ["F"] if not f_stats["pages_read"] else []
    ledger, update_entry = update_ledger(_read_json(ledger_path), planet_index, planet_shards,
                                         {"date": run_date(), "data": data_id, "code": rules_fingerprint(),
                                          "skipped": skipped})
    shown = ledger_totals(planet_index, {n: d for shard in planet_shards.values() for n, d in shard.items()})
    if sum(shown["by_check"].values()) != shown["findings"]:
        print(f"Refusing to publish: findings per check add up to {sum(shown['by_check'].values())}, the total is {shown['findings']}",
              file=sys.stderr)
        return 1
    explained = sum(e["leads"] for e in explanations)
    indexed = sum(p["a"] + p["b"] + p["c"] + p.get("x", 0) + p.get("e", 0) for p in planet_index)
    if explained != indexed:
        print(f"Refusing to publish; site/data left unchanged:\n- {explained} explained leads, {indexed} in the planet index", file=sys.stderr)
        return 1
    updates = _read_json(updates_path) or []
    if update_entry:
        lists = ("new_findings", "resolved_findings", "new_planets", "removed_planets", "notes_changed")
        updates = [update_entry] + [e if i < DETAIL_LIMIT - 1 else {k: v for k, v in e.items() if k not in lists}
                                    for i, e in enumerate(updates)]
    meta = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_version": __version__,
        "code_commit": code_commit,
        "snapshot_retrieved_at_utc": manifest["retrieved_at_utc"],
        "snapshot_sha256": manifest["sha256_raw_response"],
        "snapshot_rows": manifest["row_count"],
        "query": manifest["query"],
        "source_url": manifest["source_url"],
        "optional_columns_missing": report.get("optional_columns_missing"),
        "screening": {k: report.get(k) for k in (
            "input_rows", "valid_comparison_rows", "candidate_pair_count", "planets_considered", "non_overlapping_pair_count",
            "non_overlapping_planet_count", "row_exclusion_reason_counts")},
        "triage": report.get("triage"),
        "row_check": report.get("row_self_consistency"),
        "identity_checks": report.get("identity_checks"),
        "separation_observed": report.get("separation_observed"),
        "chance_baseline": report.get("chance_baseline"),
        "detector_evaluation": report.get("detector_evaluation"),
        "snapshot_download": "data/snapshot.csv.gz",
        "tier_reasons": REASONS,
        "check_a": report.get("check_a"),
        "check_b": report.get("check_b"),
        "check_c": c_stats,
        "check_d": d_stats,
        "check_e": e_stats,
        "check_f": f_stats,
        "nasa_notes": {"shown": notes_shown, "overview_sha256": NOTES_SHA or None},
        "run": runlog.for_site(runlog.load(ROOT), previous_meta.get("run")),
        "letters_confirmed_by_alias": letters_confirmed,
        "planets": len(planet_index),
        "row_checks_run": (report.get("row_self_consistency") or {}).get("checkable_rows", 0)
            + sum((v or {}).get("checkable_rows", 0) for v in (report.get("identity_checks") or {}).values()),
    }

    publish_snapshot(manifests[-1])
    _write(SITE_DATA / "planets.json", planet_index)
    (SITE_DATA / "planets").mkdir(exist_ok=True)
    for shard, planets in planet_shards.items():
        _write(SITE_DATA / "planets" / f"{shard:02d}.json", planets)
    _write(SITE_DATA / "explanations.json", [{k: v for k, v in e.items() if k != "items"} for e in explanations])
    _write(SITE_DATA / "wording.json", wording.export())
    _write(ledger_path, ledger)
    _write(updates_path, updates)
    meta["raw_files"] = fingerprints(ROOT / "data/raw")
    meta["data_fingerprints"] = sources
    meta["published"] = {str(p.relative_to(ROOT / "site")): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted((ROOT / "site").rglob("*")) if p.is_file() and p != meta_path and not p.name.endswith(".tmp")}
    _write(meta_path, meta)
    print(f"Site data written to {SITE_DATA}: {sum(p.get('nf', 0) for p in planet_index)} findings on "
          f"{sum(1 for p in planet_index if p.get('nf'))} planets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
