from __future__ import annotations
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
HASH_KEYS = ("sha256_raw_response", "sha256_canonical_json", "sha256")


def bad_files(raw: Path, committed: dict | None = None) -> list[Path]:
    bad = []
    data = {p for p in raw.iterdir() if p.is_file() and p.name != ".gitkeep" and not p.name.endswith(".manifest.json")}
    for manifest in sorted(raw.glob("*.manifest.json")):
        stem = manifest.name[: -len(".manifest.json")]
        files = [p for p in data if p.name.startswith(stem + ".")]
        try:
            expected = next(v for k in HASH_KEYS if (v := json.loads(manifest.read_text(encoding="utf-8")).get(k)))
        except (OSError, ValueError, StopIteration):
            expected = None
        if len(files) != 1 or expected is None or hashlib.sha256(files[0].read_bytes()).hexdigest() != expected:
            bad += [manifest, *files]
        data -= set(files)
    bad += list(data)
    if committed:
        bad += [p for p in raw.iterdir() if p.is_file() and p.name != ".gitkeep" and p not in bad
                and committed.get(p.name) != hashlib.sha256(p.read_bytes()).hexdigest()]
    return sorted(set(bad))


def main() -> int:
    raw, delete = ROOT / "data" / "raw", "--delete" in sys.argv
    try:
        committed = json.loads((ROOT / "site/data/meta.json").read_text(encoding="utf-8")).get("raw_files")
    except (OSError, ValueError):
        committed = None
    bad = bad_files(raw, committed) if raw.is_dir() else []
    for path in bad:
        print(f"{'removed' if delete else 'would remove'}: {path.name} (fingerprint doesn't match its manifest or the committed list)", file=sys.stderr)
        if delete:
            path.unlink()
    print(f"saved copies checked: {len(bad)} not usable", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
