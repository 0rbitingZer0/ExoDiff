import pandas as pd

from exodiff.eu_catalog import check_d, join_eu

REF_B = "<a refstr=B href=https://ui.adsabs.harvard.edu/abs/b/abstract target=ref>Beard et al. 2022</a>"
REF_K = "<a refstr=K href=https://ui.adsabs.harvard.edu/abs/k/abstract target=ref>Kemmer et al. 2022</a>"


def eu_row(**over):
    base = {"name": "GJ 3929 b", "alternate_names": "TOI-2013 b, TOI-2013.01", "radius": 0.1026, "radius_error_min": 0.0036,
            "radius_error_max": 0.0036, "mass": None, "orbital_period": 2.6162745, "orbital_period_error_min": 3e-6,
            "orbital_period_error_max": 3e-6, "semi_major_axis": 0.0252, "semi_major_axis_error_min": 0.0005,
            "semi_major_axis_error_max": 0.0005, "eccentricity": None, "star_distance": 15.83,
            "star_distance_error_min": 0.006, "star_distance_error_max": 0.006}
    base.update(over)
    return base


def nasa_rows():
    return pd.DataFrame([
        {"pl_name": "GJ 3929 b", "default_flag": 1, "pl_refname": REF_B, "pl_rade": 1.09, "pl_radeerr1": 0.04, "pl_radeerr2": -0.04,
         "pl_orbper": 2.616235, "pl_orbpererr1": 5e-6, "pl_orbpererr2": -5e-6, "pl_orbsmax": 0.0252, "sy_dist": 15.8095,
         "sy_disterr1": 0.0096, "sy_disterr2": -0.0095, "pl_masse": 1.75},
        {"pl_name": "GJ 3929 b", "default_flag": 0, "pl_refname": REF_K, "pl_rade": 1.15, "pl_orbper": 2.6162745,
         "pl_orbsmax": 0.02569, "sy_dist": 15.8095, "pl_masse": 1.21},
    ])


def test_join_exact_then_alias_and_unmatched():
    eu = pd.DataFrame([eu_row(), eu_row(name="TOI-2013 b", alternate_names=""), eu_row(name="Nowhere b", alternate_names="")])
    out = join_eu(eu, ["GJ 3929 b", "Only-NASA b"])
    assert out["matched"] == {"GJ 3929 b": "GJ 3929 b"}
    assert out["ambiguous"] == [] and out["eu_only"] == ["Nowhere b", "TOI-2013 b"] and out["nasa_only"] == ["Only-NASA b"]


def test_buckets():
    eu = pd.DataFrame([eu_row(star_distance=16.5)])
    result, stats = check_d(nasa_rows(), eu, join_eu(eu, ["GJ 3929 b"]))
    b = result.set_index("field")["bucket"].to_dict()
    assert b["radius"] == "D-other-paper"
    assert b["period"] == "D-other-paper"
    assert b["orbit"] == "D-same"
    assert b["distance"] == "D-disagree"
    assert b["mass"] == "D-absent" and b["eccentricity"] == "D-absent"


def test_within_errors_and_no_errors():
    eu = pd.DataFrame([eu_row(star_distance=15.83, star_distance_error_min=None, star_distance_error_max=None,
                              semi_major_axis=0.0256, semi_major_axis_error_min=0.0006, semi_major_axis_error_max=0.0006)])
    nasa = nasa_rows(); nasa.loc[0, "pl_orbsmaxerr1"], nasa.loc[0, "pl_orbsmaxerr2"] = 0.0005, -0.0005
    nasa.loc[1, "pl_orbsmax"] = 0.03
    result, _ = check_d(nasa, eu, join_eu(eu, ["GJ 3929 b"]))
    b = result.set_index("field")["bucket"].to_dict()
    assert b["orbit"] == "D-within-errors" and b["distance"] == "D-no-errors"


def test_component_naming_variants():
    from exodiff.eu_catalog import name_variants
    assert "11 Com b" in name_variants("11 Com Ab")
    assert "16 Cyg B b" in name_variants("16 Cyg Bb") and "16 Cyg b" not in name_variants("16 Cyg Bb")
    eu = pd.DataFrame([eu_row(name="11 Com Ab", alternate_names="")])
    assert join_eu(eu, ["11 Com b"])["matched"] == {"11 Com b": "11 Com Ab"}


def test_catalogue_distance_is_a_label():
    eu = pd.DataFrame([eu_row(star_distance=16.5)])
    nasa = nasa_rows()
    nasa["sy_refname"] = "<a refstr=TICV8 href=https://ui.adsabs.harvard.edu/abs/x/abstract target=ref>TICv8</a>"
    result, _ = check_d(nasa, eu, join_eu(eu, ["GJ 3929 b"]))
    assert result.set_index("field").loc["distance", "bucket"] == "D-catalogue-distance"


def test_jupiter_value_matches_nasa_jupiter_copy():
    eu = pd.DataFrame([eu_row(mass=8.0, mass_error_min=1.0, mass_error_max=1.0)])
    nasa = nasa_rows(); nasa.loc[0, "pl_masse"], nasa.loc[0, "pl_massj"] = 3000.0, 8.0
    result, _ = check_d(nasa, eu, join_eu(eu, ["GJ 3929 b"]))
    assert result.set_index("field")["bucket"]["mass"] == "D-same"


def test_planet_index_gives_page_links():
    from exodiff.eu_catalog import parse_eu_index
    html = ('<a href="/catalog/1rxs_1609_b--501/">1RXS 1609 b</a>'
            '<a href="/catalog/1rxs_j103137_1_690205_b--9525/">1RXS J103137.1-690205  b</a>'
            '<a href="/catalog/barnard_s_star_b--1/">Barnard&#x27;s star b</a><a href="/catalog/">all</a>')
    links = parse_eu_index(html)
    assert links["1RXS 1609 b"] == "https://exoplanet.eu/catalog/1rxs_1609_b--501/"
    assert "1RXS J103137.1-690205 b" in links and "Barnard's star b" in links and len(links) == 3


def test_star_pair_naming_variants():
    from exodiff.eu_catalog import name_variants
    assert "Kepler-47 b" in name_variants("Kepler-47 (AB)b")
    assert "DP Leo b" in name_variants("DP Leo (AB) b") and "BEBOP-4 AB b" in name_variants("BEBOP-4 (AB)b")


def test_ambiguous_match_is_not_compared():
    eu = pd.DataFrame([eu_row(name="GJ 3929 Ab", alternate_names=""), eu_row(name="GJ 3929 b", alternate_names="")])
    out = join_eu(eu, ["GJ 3929 b"])
    assert "GJ 3929 b" not in out["matched"] and out["ambiguous"][0]["pl_name"] == "GJ 3929 b"


def test_theoretical_values_are_never_compared_as_measured():
    eu = pd.DataFrame([eu_row(radius=0.5, radius_measurement_type="Theoretical")])
    result, _ = check_d(nasa_rows(), eu, join_eu(eu, ["GJ 3929 b"]))
    assert result.set_index("field")["bucket"]["radius"] == "D-theoretical"


def _buckets(eu_over, nasa=None, sources=None):
    eu = pd.DataFrame([eu_row(**eu_over)])
    result, _ = check_d(nasa if nasa is not None else nasa_rows(), eu, join_eu(eu, ["GJ 3929 b"]), sources)
    return result[result["pl_name"] == "GJ 3929 b"].set_index("field")


def test_nasa_limit_is_not_a_measurement():
    nasa = nasa_rows(); nasa["pl_orbeccen"] = [0.34, None]; nasa["pl_orbeccenlim"] = [-1, None]
    nasa["pl_orbeccenerr1"], nasa["pl_orbeccenerr2"] = [0.12, None], [-0.12, None]
    assert _buckets({"eccentricity": 0.91, "eccentricity_error_min": 0.02, "eccentricity_error_max": 0.02}, nasa).loc["eccentricity", "bucket"] == "D-limit"
    assert _buckets({"eccentricity": 0.10, "eccentricity_error_min": 0.02, "eccentricity_error_max": 0.02}, nasa).loc["eccentricity", "bucket"] == "D-disagree"


def test_ranges_touching_after_unit_conversion_overlap():
    nasa = nasa_rows(); nasa.loc[0, ["pl_rade", "pl_radeerr1", "pl_radeerr2"]] = [11.76945, 0.44836, -0.44836]
    nasa.loc[1, "pl_rade"] = 20.0
    assert _buckets({"radius": 0.98, "radius_error_min": 0.03, "radius_error_max": 0.03}, nasa).loc["radius", "bucket"] == "D-within-errors"


def test_zero_error_bars_count_as_none():
    assert _buckets({"star_distance": 16.5, "star_distance_error_min": 0.0, "star_distance_error_max": 0.0}).loc["distance", "bucket"] == "D-no-errors"


def test_under_two_error_bars_is_close():
    r = _buckets({"star_distance": 15.8302, "star_distance_error_min": 0.006, "star_distance_error_max": 0.006})
    assert r.loc["distance", "bucket"] == "D-close" and r.loc["distance", "bars"] < 2


def test_inside_another_rows_error_bars_is_a_note():
    nasa = nasa_rows(); nasa.loc[1, ["sy_dist", "sy_disterr1", "sy_disterr2"]] = [16.4, 0.2, -0.2]
    r = _buckets({"star_distance": 16.5}, nasa)
    assert r.loc["distance", "bucket"] == "D-other-row" and r.loc["distance", "matched_reference"] == "Kemmer et al. 2022"


def test_cited_paper_decides():
    pub = lambda author, year, vol="1", page="1": {"first_author": author, "year": year, "journal": "AJ", "volume": vol, "page": page}
    nasa = nasa_rows(); nasa["pl_pubdate"] = ["2022-03", "2022-05"]
    held = _buckets({"star_distance": 16.5}, nasa, {"GJ 3929 b": {"distance": [pub("BEARD C.", 2022)]}})
    assert held.loc["distance", "bucket"] == "D-disagree" and held.loc["distance", "matched_reference"] == "Beard et al. 2022"
    newer = _buckets({"star_distance": 16.5}, nasa, {"GJ 3929 b": {"distance": [pub("SMITH A.", 2026)]}})
    assert newer.loc["distance", "bucket"] == "D-newer-paper" and newer.loc["distance", "eu_reference"] == "Smith 2026"
    several = _buckets({"star_distance": 16.5}, nasa, {"GJ 3929 b": {"distance": [pub("SMITH A.", 2026), pub("BEARD C.", 2022)]}})
    assert several.loc["distance", "bucket"] == "D-disagree" and pd.isna(several.loc["distance", "matched_reference"])
    assert several.loc["distance", "eu_reference"] == "Smith 2026; Beard 2022"
    older = _buckets({"star_distance": 16.5}, nasa, {"GJ 3929 b": {"distance": [pub("JONES B.", 2019)]}})
    assert older.loc["distance", "bucket"] == "D-eu-paper"


def test_other_row_overlap_does_not_hide_a_different_cited_paper():
    nasa = nasa_rows(); nasa["pl_pubdate"] = ["2022-03", "2022-05"]
    nasa.loc[1, ["sy_dist", "sy_disterr1", "sy_disterr2"]] = [16.4, 0.2, -0.2]
    r = _buckets({"star_distance": 16.5}, nasa, {"GJ 3929 b": {"distance": [{"first_author": "JONES B.", "year": 2026}]}})
    assert r.loc["distance", "bucket"] == "D-newer-paper"


def test_sibling_value_is_letters():
    nasa = pd.concat([nasa_rows(), pd.DataFrame([{"pl_name": "GJ 3929 c", "default_flag": 1, "pl_refname": REF_B,
                                                   "pl_orbper": 15.04, "pl_orbpererr1": 0.03, "pl_orbpererr2": -0.03}])], ignore_index=True)
    nasa["hostname"] = "GJ 3929"
    assert _buckets({"orbital_period": 15.05, "orbital_period_error_min": 0.01, "orbital_period_error_max": 0.01}, nasa).loc["period", "bucket"] == "D-letters"


def test_same_paper_is_judged_against_that_papers_row():
    nasa = nasa_rows(); nasa["pl_pubdate"] = ["2024-01", "2022-05"]
    nasa.loc[0, ["pl_orbper", "pl_orbpererr1", "pl_orbpererr2"]] = [9.1004157, 4.1e-6, -4.5e-6]
    nasa.loc[1, ["pl_orbper", "pl_orbpererr1", "pl_orbpererr2"]] = [9.1205, 0.0005, -0.0005]
    src = {"GJ 3929 b": {"period": [{"first_author": "KEMMER J.", "year": 2022}]}}
    r = _buckets({"orbital_period": 9.1265, "orbital_period_error_min": 0.0005, "orbital_period_error_max": 0.0005}, nasa, src)
    assert r.loc["period", "bucket"] == "D-disagree" and r.loc["period", "nasa_row_value"] == 9.1205
    near = _buckets({"orbital_period": 9.1219, "orbital_period_error_min": 0.0005, "orbital_period_error_max": 0.0005}, nasa, src)
    assert near.loc["period", "bucket"] == "D-close"


def test_d_rules_for_known_cases():
    nasa = nasa_rows(); nasa["pl_pubdate"] = ["2022-03", "2022-05"]; nasa.loc[1, "sy_dist"] = None
    r = _buckets({"star_distance": 16.5}, nasa, {"GJ 3929 b": {"distance": [{"first_author": "KEMMER J.", "year": 2022}]}})
    assert r.loc["distance", "bucket"] == "D-disagree" and pd.isna(r.loc["distance", "matched_reference"])
    nasa = nasa_rows(); nasa["pl_masselim"] = [1, None]; nasa.loc[0, "pl_masse"] = 2.0
    assert _buckets({"mass": 5.4 / 317.83, "mass_error_min": 1.4 / 317.83, "mass_error_max": 1.4 / 317.83}, nasa).loc["mass", "bucket"] == "D-disagree"
    assert _buckets({"mass": 2.3 / 317.83, "mass_error_min": 0.5 / 317.83, "mass_error_max": 0.5 / 317.83}, nasa).loc["mass", "bucket"] == "D-limit"
    assert _buckets({"mass": 9 / 317.83, "mass_error_min": 9 / 317.83, "mass_error_max": 0}, nasa).loc["mass", "bucket"] == "D-limit"
    assert _buckets({"orbital_period": 2.616265, "orbital_period_error_min": 1e-7, "orbital_period_error_max": 1e-7}).loc["period", "bucket"] == "D-disagree"


def test_letters_at_planet_level():
    nasa = pd.concat([nasa_rows(), pd.DataFrame([{"pl_name": "GJ 3929 c", "default_flag": 1, "pl_refname": REF_B,
                                                   "pl_orbper": 15.04, "pl_rade": 3.0}])], ignore_index=True)
    nasa["hostname"] = "GJ 3929"
    r = _buckets({"orbital_period": 15.05, "orbital_period_error_min": 0.01, "orbital_period_error_max": 0.01, "radius": 0.5}, nasa)
    assert r.loc["period", "bucket"] == "D-letters" and r.loc["radius", "bucket"] == "D-letters"


def test_gap_score_applies_rounding_once():
    from exodiff.eu_catalog import _interval, gap_in_error_bars
    assert abs(gap_in_error_bars(0, _interval(0, 1, 1), 3, _interval(3, 1, 1), tol=1) - 2 / 2 ** 0.5) < 1e-12


def test_nasas_rounding_is_allowed_for():
    nasa = nasa_rows(); nasa.loc[0, ["pl_orbper", "pl_orbpererr1", "pl_orbpererr2"]] = [4.532, 2e-6, -2e-6]
    r = _buckets({"orbital_period": 4.532055, "orbital_period_error_min": 1e-6, "orbital_period_error_max": 1e-6}, nasa)
    assert r.loc["period", "bucket"] == "D-close" and r.loc["period", "bars"] == 0
    nasa.loc[0, "pl_orbper"] = 4.53212
    assert _buckets({"orbital_period": 4.532055, "orbital_period_error_min": 1e-6, "orbital_period_error_max": 1e-6}, nasa).loc["period", "bucket"] == "D-disagree"


def test_limit_boundaries():
    nasa = nasa_rows(); nasa["pl_masselim"] = [1, None]; nasa.loc[0, "pl_masse"] = 2.0
    assert _buckets({"mass": 9 / 317.83, "mass_error_min": 9 / 317.83, "mass_error_max": 0}, nasa).loc["mass", "bucket"] == "D-limit"
    nasa.loc[0, "pl_masselim"], nasa.loc[0, "pl_masse"] = -1, 20.0
    assert _buckets({"mass": 9 / 317.83, "mass_error_min": 9 / 317.83, "mass_error_max": 0}, nasa).loc["mass", "bucket"] == "D-disagree"
    assert _buckets({"mass": 25 / 317.83, "mass_error_min": 3 / 317.83, "mass_error_max": 3 / 317.83}, nasa).loc["mass", "bucket"] == "D-limit"
    assert _buckets({"mass": 10 / 317.83, "mass_error_min": 3 / 317.83, "mass_error_max": 3 / 317.83}, nasa).loc["mass", "bucket"] == "D-disagree"


def test_mass_compared_with_nasas_jupiter_copy():
    nasa = nasa_rows(); nasa["pl_pubdate"] = ["2015-03", "2015-03"]
    nasa.loc[0, ["pl_masse", "pl_masseerr1", "pl_masseerr2", "pl_massj", "pl_massjerr1", "pl_massjerr2"]] = [3000.0, 300.0, -300.0, 8.0, 1.0, -1.0]
    nasa.loc[1, "pl_masse"] = 4000.0
    src = {"GJ 3929 b": {"mass": [{"first_author": "LAZZONI C.", "year": 2026}]}}
    r = _buckets({"mass": 6.6, "mass_error_min": 0.3, "mass_error_max": 0.3}, nasa, src)
    assert r.loc["mass", "bucket"] == "D-close" and 1.2 < r.loc["mass", "bars"] < 1.4
    nasa[["pl_massj", "pl_massjerr1", "pl_massjerr2"]] = None
    assert _buckets({"mass": 6.6, "mass_error_min": 0.3, "mass_error_max": 0.3}, nasa, src).loc["mass", "bucket"] == "D-newer-paper"
