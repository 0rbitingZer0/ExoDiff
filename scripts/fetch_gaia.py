from __future__ import annotations
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from exodiff import runlog
from exodiff.gaia import fetch_gaia, saved_gaia, source_ids


def main() -> int:
    nasa = pd.read_csv(ROOT / "data/processed/nasa_ps_confirmed_latest.csv", usecols=["default_flag", "gaia_dr3_id"],
                       low_memory=False)
    try:
        result = fetch_gaia(source_ids(nasa), ROOT)
    except RuntimeError as exc:
        saved = saved_gaia(ROOT)
        runlog.record(ROOT, "Gaia DR3", "copy" if saved else "missing",
                      copy_from=saved[1]["retrieved_at_utc"] if saved else None, error=str(exc)[:200])
        print(f"WARNING: Gaia DR3 distances not updated: {exc}", file=sys.stderr)
        return 0
    runlog.record(ROOT, "Gaia DR3", "unchanged" if result["unchanged"] else "fresh", copy_from=result["retrieved_at_utc"],
                  stars=result["rows"], stars_asked=result["ids_new"])
    print(f"Gaia DR3: {result['rows']:,} stars ({result['ids_new']:,} asked for; {'no new star' if result['unchanged'] else 'saved'}); "
          f"SHA-256 {result['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
