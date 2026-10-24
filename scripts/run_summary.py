from __future__ import annotations
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from exodiff import runlog

WORDS = {"fresh": "new data", "unchanged": "no change", "copy": "UNREACHABLE: saved copy used", "missing": "UNREACHABLE: not checked",
         "skipped": "skipped: its input isn't available (see note)", "partial": "PARTLY READ: failed pages retried next run", "failed": "CHECK FAILED: findings carried"}


def main() -> int:
    run = runlog.load(ROOT)
    clean = lambda text: " ".join(str(text).replace("|", "/").replace("`", "'").split())[:120]
    rows = [(name, WORDS.get(r["status"], r["status"]), (r.get("copy_from") or "")[:10], clean(r.get("error") or ""))
            for name, r in run["sources"].items()]
    table = "| source | this run | data from | note |\n|---|---|---|---|\n" + "".join(f"| {' | '.join(r)} |\n" for r in rows)
    print(table)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"## Sources (run started {run.get('started_utc')})\n\n{table}\n")
    down = runlog.down(ROOT)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"down={', '.join(down)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
