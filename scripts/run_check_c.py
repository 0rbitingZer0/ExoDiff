from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from exodiff.check_c import check_c
from exodiff import runlog
from exodiff.nasa import newest_manifests

OUT_CSV = ROOT / "data/processed/check_c.csv"
OUT_JSON = ROOT / "reports/check_c.json"
MIN_COMPOSITE_SHARE = 0.95


def newest(pattern: str) -> Path | None:
    paths = sorted((ROOT / "data/raw").glob(pattern))
    return paths[-1] if paths else None


def skip(reason: str, crashed: bool = False) -> int:
    runlog.record(ROOT, "check C", "failed" if crashed else "skipped", error=reason[:200])
    print(f"Check C skipped: {reason}", file=sys.stderr)
    OUT_CSV.unlink(missing_ok=True)
    OUT_JSON.write_text(json.dumps({"skipped": True, "reason": reason}, indent=2), encoding="utf-8")
    return 0


def main() -> int:
    join_path, composite = ROOT / "data/processed/public_join.json", newest("nasa_pscomppars_*[0-9]Z.csv")
    manifests = newest_manifests(ROOT / "data/raw")
    if not join_path.exists() or composite is None or not manifests:
        return skip("public catalogue join, composite table or archive snapshot missing")
    try:
        archive_manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
        join = json.loads(join_path.read_text(encoding="utf-8"))
        archive = pd.read_csv(ROOT / "data/processed/nasa_ps_confirmed_latest.csv", low_memory=False)
        comp = pd.read_csv(composite, low_memory=False)
        planets = archive["pl_name"].nunique()
        if len(comp) < MIN_COMPOSITE_SHARE * planets:
            return skip(f"composite table has {len(comp)} rows for {planets} archive planets; possible truncated download")
        result, stats = check_c(join, archive, comp)
    except Exception as exc:
        return skip(f"{type(exc).__name__}: {exc}", crashed=True)
    result.to_csv(OUT_CSV, index=False)
    stats.update({
        "archive_sha256": archive_manifest["sha256_raw_response"],
        "public_snapshot": join.get("public_snapshot"),
        "composite_snapshot": composite.name,
        "composite_sha256": hashlib.sha256(composite.read_bytes()).hexdigest(),
    })
    OUT_JSON.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps({k: stats[k] for k in ("compared", "by_bucket", "share_default_or_composite", "share_none", "labels")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
