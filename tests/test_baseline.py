import pandas as pd

from exodiff.baseline import chance_baseline, separation_counts
from test_screening import row


def test_separation_counts_thresholds():
    pairs = pd.DataFrame([
        {"pl_name": "A b", "intervals_overlap": False, "gap_divided_by_combined_edge_error": 2.5},
        {"pl_name": "A b", "intervals_overlap": False, "gap_divided_by_combined_edge_error": 0.5},
        {"pl_name": "B b", "intervals_overlap": True, "gap_divided_by_combined_edge_error": None},
    ])
    c = separation_counts(pairs)
    assert c["0.0"] == {"pairs": 2, "planets": 1}
    assert c["2.0"] == {"pairs": 1, "planets": 1}
    assert c["5.0"] == {"pairs": 0, "planets": 0}


def test_chance_baseline_is_reproducible_and_matches_theory():
    rows = [row(f"P{i} b", ref, 10.0, 1.0, -1.0, "2020") for i in range(400) for ref in ("Paper A", "Paper B")]
    frame = pd.DataFrame(rows)
    a = chance_baseline(frame, runs=3, seed=1, error_scales=(1.0,))
    b = chance_baseline(frame, runs=3, seed=1, error_scales=(1.0,))
    assert a == b
    rate = a["by_error_scale"]["1.0"]["0.0"]["pairs_mean"] / 400
    assert 0.11 < rate < 0.21
