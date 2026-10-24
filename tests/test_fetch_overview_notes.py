import importlib.util
from pathlib import Path

import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_overview_notes.py"


def load(tmp_path):
    spec = importlib.util.spec_from_file_location("fetch_overview_notes", SCRIPT)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    mod.PROCESSED = tmp_path
    return mod


def test_hosts_still_listed_when_optional_checks_did_not_run(tmp_path):
    pd.DataFrame({"pl_name": ["A b"], "label_only": [False]}).to_csv(tmp_path / "check_a.csv", index=False)
    pd.DataFrame({"pl_name": ["B b"]}).to_csv(tmp_path / "check_b.csv", index=False)
    pd.DataFrame({"pl_name": ["A b", "B b", "C b"], "hostname": ["A", "B", "C"]}).to_csv(tmp_path / "nasa_ps_confirmed_latest.csv", index=False)
    assert load(tmp_path).lead_hosts() == ["A", "B"]
    pd.DataFrame({"pl_name": ["C b"], "bucket": ["D-newer-paper"]}).to_csv(tmp_path / "check_d.csv", index=False)
    assert load(tmp_path).lead_hosts() == ["A", "B", "C"]
