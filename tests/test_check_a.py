import pandas as pd
import pytest

from exodiff.check_a import JUPITER_IN_EARTH_MASSES, JUPITER_IN_EARTH_RADII, check_a


def row(name="P b", ref="Paper A", **over):
    base = {"pl_name": name, "pl_refname": ref, "soltype": "Published Confirmed",
            "pl_rade": 11.209, "pl_radeerr1": 0.1, "pl_radeerr2": -0.1, "pl_radelim": 0, "pl_radj": 1.0,
            "pl_bmasse": 317.83, "pl_bmassj": 1.0, "pl_orbeccen": 0.1, "pl_orbper": 3.0}
    base.update(over)
    return base


def rules(frame):
    result, _ = check_a(pd.DataFrame(frame))
    return sorted(result["rule"]) if len(result) else []


def test_constants():
    assert JUPITER_IN_EARTH_RADII == pytest.approx(11.209, abs=1e-3)
    assert JUPITER_IN_EARTH_MASSES == pytest.approx(317.83, abs=1e-2)


def test_clean_row_has_no_flags():
    assert rules([row()]) == []


def test_each_rule_fires():
    assert rules([row(pl_orbper=-3.0)]) == ["A1"]
    assert rules([row(pl_orbeccen=1.2)]) == ["A2"]
    assert rules([row(pl_radeerr1=-0.1)]) == ["A3"]
    assert rules([row(pl_radelim=1)]) == ["A4"]
    assert rules([row(pl_radj=1.2)]) == ["A5"]
    assert rules([row(), row(pl_orbper=3.5)]) == ["A7"]


def test_unit_copies_within_rounding_pass():
    assert rules([row(pl_rade=1.09, pl_radj=0.0972, pl_bmasse=None, pl_bmassj=None)]) == []


def test_labels_are_not_leads():
    result, stats = check_a(pd.DataFrame([row(pl_radelim=1), row(pl_orbper=-1.0, name="Q b")]))
    assert stats["labels"] == 1 and stats["leads"] == 1


def test_mean_radius_convention_is_a_label_not_a_lead():
    from exodiff.check_a import MEAN_RADIUS_FACTOR
    jup = 0.6339
    result, stats = check_a(pd.DataFrame([row(pl_rade=round(jup * MEAN_RADIUS_FACTOR, 4), pl_radj=jup,
                                              pl_bmasse=None, pl_bmassj=None)]))
    assert list(result["rule"]) == ["A5m"] and stats["leads"] == 0


def test_coarse_values_matching_both_factors_are_not_labelled():
    assert rules([row(pl_rade=1.1, pl_radj=0.1, pl_bmasse=None, pl_bmassj=None)]) == []


def test_whole_earth_values_are_taken_as_rounded_to_units():
    assert rules([row(pl_bmasse=111.0, pl_bmassj=0.348, pl_rade=None, pl_radj=None)]) == []


def test_rounded_earth_copy_is_a_label_not_a_lead():
    result, stats = check_a(pd.DataFrame([row(pl_bmasse=3000.0, pl_bmassj=8.0, pl_rade=None, pl_radj=None)]))
    assert list(result["rule"]) == ["A5r"] and stats["leads"] == 0
    assert rules([row(pl_rade=3.59, pl_radj=0.369, pl_bmasse=None, pl_bmassj=None)]) == ["A5"]


def test_a7_names_differing_assumptions():
    result, _ = check_a(pd.DataFrame([row(pl_bmasse=2543.0, pl_bmassj=8.0, st_age=0.005),
                                      row(pl_bmasse=3814.0, pl_bmassj=12.0, st_age=0.01)]))
    assert "the rows also differ in st_age" in result.loc[result["rule"] == "A7", "detail"].iloc[0]


def test_a5_counts_best_mass_copy_once_and_uses_printed_digits():
    from exodiff.check_a import check_a
    row = {"pl_name": "HIP 78530 b", "pl_refname": "x", "soltype": "Published Confirmed",
           "pl_masse": 7700.0, "pl_massj": 24.0, "pl_bmasse": 7700.0, "pl_bmassj": 24.0,
           "pl_massestr": "7700&plusmn;700", "pl_massjstr": "24&plusmn;2"}
    out, _ = check_a(pd.DataFrame([row]))
    assert out.empty
    row.update(pl_massjstr=None, pl_massestr=None, pl_massj=23.0, pl_bmassj=23.0)
    out, _ = check_a(pd.DataFrame([row]))
    assert list(out["rule"]) == ["A5"] and list(out["column"]) == ["pl_masse"]


TIC = "<a refstr=STASSUN_ET_AL__2019 href=https://ui.adsabs.harvard.edu/abs/2019AJ....158..138S/abstract target=ref>TICv8</a>"


def star(**over):
    base = {"default_flag": 1, "sy_refname": TIC, "sy_dist": 5.675773, "sy_disterr1": 0.0059099, "sy_disterr2": -0.0059099,
            "sy_plx": 392.4, "sy_plxerr1": 0.91}
    base.update(over)
    return row(**base)


def test_distance_that_does_not_match_the_parallax():
    out, _ = check_a(pd.DataFrame([star()]))
    hit = out[out["rule"] == "A8"].iloc[0]
    assert hit["reference"] == "TICv8" and hit["column"] == "sy_dist" and not hit["label_only"]
    assert rules([star(sy_dist=2.548)]) == []
    assert rules([star(sy_dist=1919.19, sy_disterr1=150.0, sy_disterr2=-120.0, sy_plx=0.4945, sy_plxerr1=0.04)]) == []
    for over in ({"sy_plxerr1": 50.0}, {"sy_plx": None}, {"sy_plx": 0.0}, {"sy_plx": -1.0}, {"sy_plxerr1": None},
                 {"sy_dist": None}, {"sy_disterr1": None}, {"default_flag": 0}):
        assert rules([star(**over)]) == [], over


def test_a_nasa_note_on_the_distance_makes_it_a_note():
    note = {"source": "overview", "categories": {"distance"}, "bibcode": "2019AJ....158..138S",
            "notes": "The distance in the TESS Input Catalog for this object may be missing or incorrect."}
    out, _ = check_a(pd.DataFrame([star()]), {"P b": [note]})
    assert list(out["rule"]) == ["A8n"] and bool(out["label_only"].iloc[0])
    out, _ = check_a(pd.DataFrame([star()]), {"P b": [{**note, "bibcode": "2020A&A...643A.112S"}]})
    assert list(out["rule"]) == ["A8"]
