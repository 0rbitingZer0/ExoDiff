from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from exodiff import runlog
from exodiff.public_catalog import PublicCatalogError, fetch_public_catalog, latest_public_snapshot


def main() -> int:
    try:
        result = fetch_public_catalog(ROOT)
    except PublicCatalogError as exc:
        try:
            saved = latest_public_snapshot(ROOT)
        except PublicCatalogError:
            saved = None
        runlog.record(ROOT, "NASA catalog", "copy" if saved else "missing",
                      copy_from=saved[1]["retrieved_at_utc"] if saved else None, error=str(exc)[:200])
        print(f"WARNING: public catalogue not updated: {exc}", file=sys.stderr)
        return 0
    runlog.record(ROOT, "NASA catalog", "unchanged" if result["unchanged"] else "fresh", copy_from=result["retrieved_at_utc"],
                  records=result["records"], requests=result["requests"], mode=result["mode"])
    print(f"Public catalogue: {result['records']:,} records ({'no change' if result['unchanged'] else result['mode']}, "
          f"{result['requests']} requests); SHA-256 {result['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
