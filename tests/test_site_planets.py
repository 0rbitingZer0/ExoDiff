import pandas as pd

from exodiff.site_planets import SHARDS, build_planets, shard_of

REF = "<a refstr=B href=https://ui.adsabs.harvard.edu/abs/2022ApJ...936...55B/abstract target=ref>Beard et al. 2022</a>"


def test_index_and_shards():
    archive = pd.DataFrame([
        {"pl_name": "GJ 3929 b", "hostname": "GJ 3929", "default_flag": 1, "pl_refname": REF, "pl_pubdate": "2022-08",
         "pl_rade": 1.09, "pl_radeerr1": 0.04, "pl_radeerr2": -0.04, "pl_radelim": 0, "pl_bmasse": 1.75,
         "pl_bmassprov": "Mass", "discoverymethod": "Transit", "disc_year": 2022},
        {"pl_name": "GJ 3929 b", "hostname": "GJ 3929", "default_flag": 0, "pl_refname": "Kemmer et al. 2022",
         "pl_pubdate": "2022-01", "pl_rade": 1.15, "discoverymethod": "Transit", "disc_year": 2022},
    ])
    check_b = pd.DataFrame([{"pl_name": "GJ 3929 b", "check": "radius", "reference": "Beard et al. 2022", "listed_value": 1.09,
                             "implied_value": 0.545, "mismatch_pct": 100.0, "mismatch_in_error_bars": 13.6,
                             "bucket": "B-look", "bucket_title": "worth a second look", "bucket_reason": "none apply"}])
    check_c = pd.DataFrame([{"pl_name": "GJ 3929 b", "field": "mass", "public_display": "1.75 Earths", "bucket": "C-default",
                             "matched_reference": "Beard et al. 2022", "labels": "[]"}])
    join = {"matched": {"GJ 3929 b": {"link": "https://science.nasa.gov/exoplanet-catalog/gj-3929-b/"}}}
    index, shards = build_planets(archive, pd.DataFrame(), check_b, check_c, join)
    entry = index[0]
    assert entry["n"] == "GJ 3929 b" and entry["p"] == 2 and entry["b"] == 1 and entry["s"] == shard_of("GJ 3929 b")
    detail = shards[entry["s"]]["GJ 3929 b"]
    assert detail["papers"][0]["default"] and detail["papers"][0]["ref"] == "Beard et al. 2022"
    assert detail["papers"][0]["values"]["radius"] == {"v": 1.09, "e1": 0.04, "e2": -0.04, "lim": 0}
    assert detail["links"]["archive"].endswith("/overview/GJ%203929%20b")
    assert detail["public"]["mass"]["bucket"] == "C-default"
    assert len(shards) == SHARDS


def test_check_d_and_planet_type_reach_the_page():
    archive = pd.DataFrame([{"pl_name": "TOI-262 b", "hostname": "TOI-262", "default_flag": 1, "pl_refname": REF,
                             "pl_orbsmax": 0.163, "pl_orbper": 11.15}])
    check_d = pd.DataFrame([
        {"pl_name": "TOI-262 b", "field": "orbit", "eu_name": "TOI-262 b", "eu_value": 0.163, "nasa_default": 0.163,
         "bucket": "D-same", "matched_reference": "Beard et al. 2022"},
        {"pl_name": "TOI-262 b", "field": "period", "eu_name": "TOI-262 b", "eu_value": 11.5, "nasa_default": 11.15,
         "bucket": "D-disagree", "matched_reference": None},
        {"pl_name": "TOI-262 b", "field": "mass", "eu_name": "TOI-262 b", "eu_value": None, "nasa_default": None,
         "bucket": "D-absent", "matched_reference": None},
    ])
    join = {"matched": {"TOI-262 b": {"link": "https://science.nasa.gov/x/", "acf": {"planet_type": "Super Earth"}}}}
    index, shards = build_planets(archive, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), join, check_d=check_d,
                                  eu_links={"TOI-262 b": "https://exoplanet.eu/catalog/toi_262_b--9999/"})
    detail = shards[index[0]["s"]]["TOI-262 b"]
    assert index[0]["x"] == 1
    assert set(detail["eu"]) == {"orbit", "period"}
    assert detail["eu"]["orbit"]["bucket"] == "D-same"
    assert detail["type"] == "Super Earth"
    assert detail["links"]["eu"] == "https://exoplanet.eu/catalog/toi_262_b--9999/"
