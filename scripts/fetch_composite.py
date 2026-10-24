from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from exodiff import runlog
from exodiff.nasa import COMPOSITE_STEM, fetch_composite, newest_manifests


def saved() -> dict | None:
    files = sorted((ROOT / "data/raw").glob(f"{COMPOSITE_STEM}_*[0-9]Z.manifest.json"))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def main() -> int:
    copy = saved()
    archive = runlog.load(ROOT)["sources"].get("NASA archive", {}).get("status")
    archive_at = json.loads(newest_manifests(ROOT / "data/raw")[-1].read_text())["retrieved_at_utc"] if newest_manifests(ROOT / "data/raw") else ""
    if copy and archive == "unchanged" and copy["retrieved_at_utc"] >= archive_at:
        runlog.record(ROOT, "NASA composite table", "unchanged", copy_from=copy["retrieved_at_utc"])
        print(f"Composite table: archive unchanged; saved copy from {copy['retrieved_at_utc'][:10]} used")
        return 0
    try:
        result = fetch_composite(ROOT)
    except RuntimeError as exc:
        runlog.record(ROOT, "NASA composite table", "copy" if copy else "missing",
                      copy_from=copy["retrieved_at_utc"] if copy else None, error=str(exc)[:200])
        print(f"WARNING: composite table not updated: {exc}", file=sys.stderr)
        return 0
    runlog.record(ROOT, "NASA composite table", "fresh", copy_from=result["retrieved_at_utc"], rows=result["rows"])
    print(f"Composite table: {result['rows']:,} planets; SHA-256 {result['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
