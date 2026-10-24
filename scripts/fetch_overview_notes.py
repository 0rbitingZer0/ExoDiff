from __future__ import annotations
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from exodiff import runlog
from exodiff.overview_notes import fetch_overviews, latest_snapshot

PROCESSED = ROOT / "data" / "processed"


def host_updates() -> dict:
    rows = pd.read_csv(PROCESSED / "nasa_ps_confirmed_latest.csv", usecols=["hostname", "rowupdate"], dtype=str)
    return rows.dropna().groupby("hostname")["rowupdate"].max().to_dict()


def lead_hosts() -> list[str]:
    planets = set()
    a = pd.read_csv(PROCESSED / "check_a.csv")
    planets |= set(a.loc[~a["label_only"].astype(bool), "pl_name"])
    planets |= set(pd.read_csv(PROCESSED / "check_b.csv")["pl_name"])
    if (PROCESSED / "check_c.csv").exists():
        c = pd.read_csv(PROCESSED / "check_c.csv", usecols=["pl_name", "bucket"])
        planets |= set(c.loc[c["bucket"] == "C-none", "pl_name"])
    if (PROCESSED / "check_d.csv").exists():
        d = pd.read_csv(PROCESSED / "check_d.csv", usecols=["pl_name", "bucket"])
        planets |= set(d.loc[d["bucket"].isin(["D-disagree", "D-newer-paper", "D-letters"]), "pl_name"])
    hosts = pd.read_csv(PROCESSED / "nasa_ps_confirmed_latest.csv", usecols=["pl_name", "hostname"], low_memory=False)
    return sorted(set(hosts.loc[hosts["pl_name"].isin(planets), "hostname"].dropna()))


def main() -> int:
    hosts = lead_hosts()
    try:
        result = fetch_overviews(hosts, ROOT, updated=host_updates(), progress=True)
    except RuntimeError as exc:
        runlog.record(ROOT, "NASA notes", "copy" if latest_snapshot(ROOT).get("systems") else "missing", error=str(exc)[:200])
        print(f"WARNING: overview notes not updated: {exc}", file=sys.stderr)
        return 0
    status = "partial" if result["failures"] else "unchanged" if result["unchanged"] else "fresh"
    runlog.record(ROOT, "NASA notes", status, copy_from=result["retrieved_at_utc"],
                  requests=result["hosts_requested"], read=result["hosts_read"], failures=result["failures"])
    print(f"overview notes: {result['hosts_read']:,} of {result['hosts_requested']:,} due pages read "
          f"({len(hosts):,} systems with leads), {result['notes']:,} notes, {result['failures']} failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
