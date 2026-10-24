from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from exodiff import runlog
from exodiff.baseline import chance_baseline, separation_counts
from exodiff.consistency import row_self_consistency
from exodiff.evaluation import evaluate
from exodiff.identities import identity_checks
from exodiff.check_a import check_a
from exodiff.check_b import bucket_leads, unify
from exodiff.known_notes import load_all_notes
from exodiff.sources import CATALOGUE_REFERENCES, column_tags
from exodiff.screening import OPTIONAL_COLUMNS, screen_radius_solutions
from exodiff.triage import triage_pairs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "data/processed/nasa_ps_confirmed_latest.csv"))
    parser.add_argument("--baseline-runs", type=int, default=10, help="simulations per error scale for the chance baseline")
    parser.add_argument("--if-notes-changed", action="store_true",
                        help="second pass of a run: skip unless NASA's notes changed since the first (check B reads them)")
    args = parser.parse_args()
    if args.if_notes_changed and runlog.load(ROOT)["sources"].get("NASA notes", {}).get("status") != "fresh":
        print("Notes unchanged: the first pass already used them; skipped.")
        return 0
    source = Path(args.input)
    if not source.exists():
        print(f"Input not found: {source}\nFirst run: python scripts/fetch_nasa.py", file=sys.stderr)
        return 1
    try:
        frame = pd.read_csv(source, low_memory=False)
        pairs, report = screen_radius_solutions(frame)
        rows, row_report = row_self_consistency(frame)
        identities, identity_report = identity_checks(frame)
        notes = load_all_notes()
        values_a, check_a_report = check_a(frame, notes)
        leads_b, check_b_report = bucket_leads(frame, unify(rows, identities), notes)
        pairs, triage_report = triage_pairs(pairs, rows)
        baseline = chance_baseline(frame, runs=args.baseline_runs)
        detector_evaluation = evaluate(frame)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    out_dir = ROOT / "data/processed"
    report_dir = ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    out_pairs = out_dir / "radius_pairs_for_review.csv"
    pairs.to_csv(out_pairs, index=False)
    out_rows = out_dir / "row_self_consistency.csv"
    rows.to_csv(out_rows, index=False)
    values_a.to_csv(out_dir / "check_a.csv", index=False)
    leads_b.to_csv(out_dir / "check_b.csv", index=False)
    out_identities = out_dir / "identity_checks.csv"
    identities.to_csv(out_identities, index=False)
    report.update({
        "row_self_consistency": row_report,
        "identity_checks": identity_report,
        "check_a": check_a_report,
        "check_b": check_b_report,
        "column_sources": {"catalogue_references": CATALOGUE_REFERENCES, "columns": column_tags(frame)},
        "separation_observed": separation_counts(pairs),
        "chance_baseline": baseline,
        "detector_evaluation": detector_evaluation,
        "triage": triage_report,
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source),
        "output_pairs_path": str(out_pairs.relative_to(ROOT)),
        "output_row_check_path": str(out_rows.relative_to(ROOT)),
        "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "input_columns": list(frame.columns),
        "optional_columns_missing": sorted(OPTIONAL_COLUMNS - set(frame.columns)),
        "rank_order": [
            "non-overlapping reported intervals first",
            "then larger interval gap divided by combined one-sided error values",
            "then larger central-value relative difference"
        ],
        "scientific_warning": "Screening uses published columns as supplied. It does not harmonise confidence levels or model covariance/shared data. It cannot identify errors or discoveries on its own.",
    })
    if report["optional_columns_missing"]:
        print("WARNING: optional columns missing, related checks are skipped: "
              + ", ".join(report["optional_columns_missing"]), file=sys.stderr)
    out_report = report_dir / "screening_report.json"
    out_report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nPairs saved to: {out_pairs}")
    print(f"Report saved to: {out_report}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
