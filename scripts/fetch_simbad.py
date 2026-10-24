from __future__ import annotations
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from exodiff.eu_catalog import join_eu
from exodiff import runlog
from exodiff.simbad import STEM, fetch_idents, host_gaia


def main() -> int:
    eu_files = sorted((ROOT / "data/raw").glob("exoplanet_eu_*[0-9]Z.csv"))
    if not eu_files:
        runlog.record(ROOT, "SIMBAD", "skipped", error="no exoplanet.eu data to match star names against")
        print("WARNING: SIMBAD skipped: no exoplanet.eu snapshot", file=sys.stderr)
        return 0
    nasa = pd.read_csv(ROOT / "data/processed/nasa_ps_confirmed_latest.csv", low_memory=False,
                       usecols=["pl_name", "default_flag", "gaia_dr3_id"])
    join = join_eu(pd.read_csv(eu_files[-1], low_memory=False), nasa["pl_name"].dropna().unique())
    ids = sorted(set(host_gaia(nasa, join["nasa_only"]).values()))
    try:
        result = fetch_idents(ids, ROOT)
    except RuntimeError as exc:
        saved = sorted((ROOT / "data/raw").glob(f"{STEM}_*Z.json"))
        runlog.record(ROOT, "SIMBAD", "copy" if saved else "missing", error=str(exc)[:200])
        print(f"WARNING: SIMBAD identifiers not updated: {exc}", file=sys.stderr)
        return 0
    runlog.record(ROOT, "SIMBAD", "unchanged" if result["unchanged"] else "fresh", copy_from=result["retrieved_at_utc"],
                  stars=result["objects_found"], stars_asked=result["ids_new"])
    print(f"SIMBAD: {result['objects_found']:,} hosts known ({result['ids_new']:,} asked for); SHA-256 {result['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
