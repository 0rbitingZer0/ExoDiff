import pandas as pd

from exodiff.gaia import _bucket, check_e, source_ids

TIC = "<a refstr=STASSUN_ET_AL__2019 href=https://ui.adsabs.harvard.edu/abs/2019AJ....158..138S/abstract target=ref>TICv8</a>"


def test_buckets():
    assert _bucket(15.8095, 0.0096, -0.0095, 15.8224, 15.8167, 15.8281) == "E-same"
    assert _bucket(100.0, 0.1, -0.1, 103.0, 102.9, 103.1) == "E-small"
    assert _bucket(100.0, 0.1, -0.1, 110.0, 109.9, 110.1) == "E-differs"
    assert _bucket(100.0, None, None, 110.0, 109.9, 110.1) == "E-no-errors"


def nasa():
    return pd.DataFrame([
        {"pl_name": "K-1 b", "hostname": "K-1", "default_flag": 1, "sy_dist": 3460.5, "sy_disterr1": 100.0, "sy_disterr2": -90.0,
         "gaia_dr3_id": "Gaia DR3 11", "sy_refname": TIC, "st_refname": TIC},
        {"pl_name": "K-1 c", "hostname": "K-1", "default_flag": 1, "sy_dist": 3460.5, "sy_disterr1": 100.0, "sy_disterr2": -90.0,
         "gaia_dr3_id": "Gaia DR3 11", "sy_refname": TIC, "st_refname": "Paper 2020"},
        {"pl_name": "K-1 b", "hostname": "K-1", "default_flag": 0, "sy_dist": 1.0, "gaia_dr3_id": "Gaia DR3 99"},
        {"pl_name": "N-2 b", "hostname": "N-2", "default_flag": 1, "sy_dist": 50.0, "sy_disterr1": 1.0, "sy_disterr2": -1.0,
         "gaia_dr3_id": None, "sy_refname": TIC},
        {"pl_name": "G-3 b", "hostname": "G-3", "default_flag": 1, "sy_dist": 20.0, "sy_disterr1": 0.1, "sy_disterr2": -0.1,
         "gaia_dr3_id": "Gaia DR3 33", "sy_refname": "Paper 2019"},
    ])


def test_source_ids_from_default_rows_only():
    assert source_ids(nasa()) == [11, 33]


def test_check_e_one_row_per_host():
    gaia = pd.DataFrame({"source_id": [11], "r_med_geo": [1717.0], "r_lo_geo": [1650.0], "r_hi_geo": [1790.0]})
    out, stats = check_e(nasa(), gaia)
    by = out.set_index("hostname")
    assert by.at["K-1", "bucket"] == "E-differs" and by.at["K-1", "planets"] == "K-1 b; K-1 c"
    assert bool(by.at["K-1", "dist_from_catalogue"])
    assert by.at["G-3", "bucket"] == "E-no-gaia"
    assert "N-2" not in by.index
    assert stats["compared"] == 1 and stats["by_bucket"]["E-differs"] == 1 and stats["hosts_with_distance"] == 3


def test_five_percent_is_symmetric():
    from exodiff.gaia import apart
    assert abs(apart(105, 100) - apart(100, 105)) < 1e-12
    assert _bucket(105.0, 0.1, -0.1, 100.0, 99.9, 100.1) == _bucket(100.0, 0.1, -0.1, 105.0, 104.9, 105.1) == "E-differs"


def test_zero_uncertainty_counts_as_none():
    from exodiff.gaia import _bucket
    assert _bucket(100.0, 0.0, 0.0, 120.0, 118.0, 122.0) == "E-no-errors"
    assert _bucket(100.0, 1.0, -1.0, 120.0, 118.0, 122.0) == "E-differs"
