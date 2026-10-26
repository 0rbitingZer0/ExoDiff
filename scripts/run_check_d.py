from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from exodiff.eu_catalog import check_d, join_eu, latest_eu_index
from exodiff import runlog
from exodiff.eu_sources import fetch_sources, latest_sources, saved_retrieved_at
from exodiff.simbad import host_gaia, join_by_host, latest_idents
from exodiff.nasa import newest_manifests

OUT_CSV, OUT_JSON = ROOT / "data/processed/check_d.csv", ROOT / "reports/check_d.json"


def skip(reason: str, crashed: bool = False) -> int:
    runlog.record(ROOT, "check D", "failed" if crashed else "skipped", error=reason[:200])
    print(f"Check D skipped: {reason}", file=sys.stderr)
    OUT_CSV.unlink(missing_ok=True)
    OUT_JSON.write_text(json.dumps({"skipped": True, "reason": reason}, indent=2), encoding="utf-8")
    return 0


def read_sources(first_pass: pd.DataFrame, join: dict, eu: pd.DataFrame) -> dict:
    saved, saved_at = latest_sources(ROOT), saved_retrieved_at(ROOT)
    if runlog.load(ROOT)["sources"].get("exoplanet.eu", {}).get("status") in runlog.DOWN:
        runlog.record(ROOT, "exoplanet.eu pages", "copy" if saved else "missing", copy_from=saved_at, error="exoplanet.eu unreachable")
        return {}
    index = latest_eu_index(ROOT)
    todo = sorted(set(first_pass.loc[first_pass["bucket"].isin(["D-disagree", "D-other-row"]), "pl_name"]))
    links = {p: index[" ".join(join["matched"][p].split())] for p in todo if " ".join(join["matched"].get(p, "").split()) in index}
    eu_updated = dict(zip(eu["name"].astype(str), eu["updated"].fillna("").astype(str)))
    updated = {p: eu_updated.get(join["matched"][p], "") for p in links}
    try:
        result = fetch_sources(links, ROOT, updated=updated)
    except RuntimeError as exc:
        runlog.record(ROOT, "exoplanet.eu pages", "copy" if saved else "missing", copy_from=saved_at, error=str(exc)[:200])
        print(f"WARNING: exoplanet.eu sources not updated: {exc}", file=sys.stderr)
        return {}
    runlog.record(ROOT, "exoplanet.eu pages", "partial" if result["failures"] else "unchanged" if result["unchanged"] else "fresh",
                  copy_from=result["manifest"]["retrieved_at_utc"] if "manifest" in result else saved_at,
                  requests=result["requested"], read=result["read"], failures=len(result["failures"]))
    print(f"exoplanet.eu pages: {result['read']:,} of {result['requested']:,} needed pages read "
          f"({len(links):,} planets to settle, {len(todo) - len(links)} without a page link)", file=sys.stderr)
    return result["pages"]


def main() -> int:
    eu_files = sorted((ROOT / "data/raw").glob("exoplanet_eu_*[0-9]Z.csv"))
    manifests = newest_manifests(ROOT / "data/raw")
    if not eu_files or not manifests:
        return skip("exoplanet.eu snapshot or archive snapshot missing")
    try:
        archive_manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
        eu_manifest = json.loads(eu_files[-1].with_name(eu_files[-1].name.replace(".csv", ".manifest.json")).read_text(encoding="utf-8"))
        eu = pd.read_csv(eu_files[-1], low_memory=False)
        nasa = pd.read_csv(ROOT / "data/processed/nasa_ps_confirmed_latest.csv", low_memory=False)
        comp_files = sorted((ROOT / "data/raw").glob("nasa_pscomppars_*[0-9]Z.csv"))
        composite = pd.read_csv(comp_files[-1], low_memory=False) if comp_files else None
        join = join_eu(eu, nasa["pl_name"].dropna().unique())
        idents = latest_idents(ROOT)
        if idents:
            j2 = join_by_host(eu, join["nasa_only"], host_gaia(nasa, join["nasa_only"]), idents, set(join["matched"].values()))
            join["matched"].update(j2["matched"])
            join["nasa_only"] = sorted(set(join["nasa_only"]) - set(j2["matched"]))
            join["ambiguous_simbad"] = j2["ambiguous"]
            join["stats"].update(matched=len(join["matched"]), matched_via_simbad=len(j2["matched"]),
                                 ambiguous_simbad=len(j2["ambiguous"]))
        result, stats = check_d(nasa, eu, join, composite=composite)
        sources = latest_sources(ROOT)
        if "--fetch-sources" in sys.argv:
            sources = read_sources(result, join, eu) or sources
        if sources:
            result, stats = check_d(nasa, eu, join, sources, composite)
            stats["eu_sources_pages"] = len(sources)
    except Exception as exc:
        return skip(f"{type(exc).__name__}: {exc}", crashed=True)
    result.to_csv(OUT_CSV, index=False)
    stats.update({"archive_sha256": archive_manifest["sha256_raw_response"], "eu_snapshot": eu_files[-1].name,
                  "eu_sha256": hashlib.sha256(eu_files[-1].read_bytes()).hexdigest(),
                  "eu_retrieved_at_utc": eu_manifest.get("retrieved_at_utc"),
                  "composite_snapshot": comp_files[-1].name if comp_files else None})
    OUT_JSON.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps({k: stats[k] for k in ("compared", "by_bucket", "share_same_or_other_paper", "share_disagree", "join")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
