from __future__ import annotations
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from exodiff import runlog
from exodiff.nasa import fetch_radius_solutions, reuse_saved_copy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="TOP-limited smoke test only; not a representative sample")
    parser.add_argument("--timeout", type=int, default=120, help="HTTP read timeout in seconds (default: 120)")
    args = parser.parse_args()
    runlog.start(ROOT)
    try:
        result = fetch_radius_solutions(ROOT, limit=args.limit, timeout_seconds=args.timeout)
    except Exception as exc:
        saved = None if args.limit else reuse_saved_copy(ROOT)
        if saved is None:
            runlog.record(ROOT, "NASA archive", "missing", error=str(exc)[:200])
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        runlog.record(ROOT, "NASA archive", "copy", copy_from=saved["retrieved_at_utc"], error=str(exc)[:200])
        print(f"WARNING: NASA archive unreachable ({exc}); using the saved copy from {saved['retrieved_at_utc']}", file=sys.stderr)
        return 0
    runlog.record(ROOT, "NASA archive", "unchanged" if result["unchanged"] else "fresh", copy_from=result["retrieved_at_utc"],
                  rows=result["rows"])
    print(f"NASA archive: {'unchanged since ' + result['retrieved_at_utc'][:10] + ', saved copy used' if result['unchanged'] else 'downloaded'}; "
          f"rows {result['rows']:,}; planets {result['planets']:,}; SHA-256 {result['sha256']}")
    if result["limited_smoke_test"]:
        print("WARNING: This TOP-limited pull is not random or representative; do not use it for population-level conclusions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
