from __future__ import annotations
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from exodiff.public_catalog import PublicCatalogError, latest_public_snapshot
from exodiff.public_join import archive_planet_names, join_public

OUT = ROOT / "data/processed/public_join.json"


def main() -> int:
    try:
        snapshot = latest_public_snapshot(ROOT)
    except PublicCatalogError as exc:
        print(f"WARNING: {exc}; check C will be skipped", file=sys.stderr)
        snapshot = None
    if snapshot is None:
        print("No public catalogue snapshot; check C will be skipped.", file=sys.stderr)
        OUT.unlink(missing_ok=True)
        return 0
    records, manifest = snapshot
    archive = pd.read_csv(ROOT / "data/processed/nasa_ps_confirmed_latest.csv", usecols=["pl_name"], low_memory=False)
    result = join_public(records, archive_planet_names(archive))
    result["public_snapshot"] = {k: manifest[k] for k in ("retrieved_at_utc", "sha256_canonical_json", "record_count")}
    OUT.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result["stats"], indent=1))
    print("archive-only:", result["archive_only"][:20])
    print("public-only:", [p["exo_id"] for p in result["public_only"]][:20])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
