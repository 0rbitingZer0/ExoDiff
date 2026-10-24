from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from exodiff.raw_store import older_copies


def main() -> int:
    raw, delete = ROOT / "data" / "raw", "--delete" in sys.argv
    old = older_copies([p.name for p in raw.iterdir()]) if raw.is_dir() else []
    for name in old:
        if delete:
            (raw / name).unlink()
    print(f"{'Deleted' if delete else 'Would delete (dry run; pass --delete)'} {len(old)} older copies in data/raw", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
