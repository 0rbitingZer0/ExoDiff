from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from exodiff.gaia import STEM, check_e
from exodiff import runlog
from exodiff.nasa import newest_manifests

OUT_CSV, OUT_JSON = ROOT / "data/processed/check_e.csv", ROOT / "reports/check_e.json"


def skip(reason: str, crashed: bool = False) -> int:
    runlog.record(ROOT, "check E", "failed" if crashed else "skipped", error=reason[:200])
    print(f"Check E skipped: {reason}", file=sys.stderr)
    OUT_CSV.unlink(missing_ok=True)
    OUT_JSON.write_text(json.dumps({"skipped": True, "reason": reason}, indent=2), encoding="utf-8")
    return 0


def main() -> int:
    gaia_files = sorted((ROOT / "data/raw").glob(f"{STEM}_*[0-9]Z.csv"))
    manifests = newest_manifests(ROOT / "data/raw")
    if not gaia_files or not manifests:
        return skip("Gaia snapshot or archive snapshot missing")
    try:
        archive_manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
        gaia_manifest = json.loads(gaia_files[-1].with_name(gaia_files[-1].stem + ".manifest.json").read_text(encoding="utf-8"))
        nasa = pd.read_csv(ROOT / "data/processed/nasa_ps_confirmed_latest.csv", low_memory=False)
        result, stats = check_e(nasa, pd.read_csv(gaia_files[-1]))
    except Exception as exc:
        return skip(f"{type(exc).__name__}: {exc}", crashed=True)
    result.to_csv(OUT_CSV, index=False)
    stats.update({"archive_sha256": archive_manifest["sha256_raw_response"], "gaia_snapshot": gaia_files[-1].name,
                  "gaia_sha256": hashlib.sha256(gaia_files[-1].read_bytes()).hexdigest(),
                  "gaia_retrieved_at_utc": gaia_manifest.get("retrieved_at_utc")})
    OUT_JSON.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
