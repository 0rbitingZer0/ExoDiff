from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from exodiff import runlog
from exodiff.eu_catalog import fetch_eu, fetch_eu_index, latest_eu_index, latest_eu_manifest


def main() -> int:
    saved = latest_eu_manifest(ROOT)
    try:
        result = fetch_eu(ROOT)
    except RuntimeError as exc:
        runlog.record(ROOT, "exoplanet.eu", "copy" if saved else "missing",
                      copy_from=saved["retrieved_at_utc"] if saved else None, error=str(exc)[:200])
        print(f"WARNING: exoplanet.eu not updated: {exc}", file=sys.stderr)
        return 0
    runlog.record(ROOT, "exoplanet.eu", "unchanged" if result["unchanged"] else "fresh",
                  copy_from=result["retrieved_at_utc"], rows=result["rows"])
    print(f"exoplanet.eu: {result['rows']:,} planets ({'no change' if result['unchanged'] else 'new data'}); SHA-256 {result['sha256']}")
    if result["unchanged"] and latest_eu_index(ROOT):
        runlog.record(ROOT, "exoplanet.eu index", "unchanged")
        return 0
    try:
        index = fetch_eu_index(ROOT)
    except RuntimeError as exc:
        runlog.record(ROOT, "exoplanet.eu index", "copy" if latest_eu_index(ROOT) else "missing", error=str(exc)[:200])
        print(f"WARNING: exoplanet.eu index not updated: {exc}", file=sys.stderr)
        return 0
    runlog.record(ROOT, "exoplanet.eu index", "fresh", planets=index["planets"])
    print(f"exoplanet.eu index: {index['planets']:,} planet pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
