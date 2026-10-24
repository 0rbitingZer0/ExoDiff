import pandas as pd
import pytest

from exodiff.screening import SOLAR_TO_EARTH_RADII, compare_measurements, screen_radius_solutions


def row(name, ref, radius, plus, minus, date, limit=0, soltype="Published Confirmed"):
    return {
        "pl_name": name,
        "hostname": "Test Star",
        "soltype": soltype,
        "default_flag": 0,
        "pl_controv_flag": 0,
        "pl_rade": radius,
        "pl_radeerr1": plus,
        "pl_radeerr2": minus,
        "pl_radelim": limit,
        "pl_refname": ref,
        "pl_pubdate": date,
        "st_rad": 1.0,
        "st_raderr1": 0.1,
        "st_raderr2": -0.1,
        "st_refname": "Stellar paper",
        "discoverymethod": "Transit",
        "disc_year": 2020,
    }


def test_non_overlapping_intervals_flagged_for_review_not_error():
    data = pd.DataFrame([
        row("Demo-1 b", "Paper A", 1.0, 0.1, -0.1, "2020-01"),
        row("Demo-1 b", "Paper B", 2.0, 0.1, -0.1, "2021-01"),
    ])
    pairs, report = screen_radius_solutions(data)
    assert len(pairs) == 1
    assert bool(pairs.iloc[0]["intervals_overlap"]) is False
    assert pairs.iloc[0]["reported_interval_gap_rearth"] > 0
    assert "not a significance test" in pairs.iloc[0]["methodology_warning"]
    assert report["candidate_pair_count"] == 1


def test_overlapping_intervals_are_not_flagged_as_nonoverlap():
    data = pd.DataFrame([
        row("Demo-2 b", "Paper A", 1.0, 0.2, -0.2, "2020-01"),
        row("Demo-2 b", "Paper B", 1.1, 0.2, -0.2, "2021-01"),
    ])
    pairs, _ = screen_radius_solutions(data)
    assert len(pairs) == 1
    assert bool(pairs.iloc[0]["intervals_overlap"]) is True
    assert pairs.iloc[0]["reported_interval_gap_rearth"] == 0


def test_unknown_limit_or_missing_error_is_excluded():
    data = pd.DataFrame([
        row("Demo-3 b", "Paper A", 1.0, 0.1, -0.1, "2020-01", limit=None),
        row("Demo-3 b", "Paper B", 2.0, 0.1, -0.1, "2021-01", limit=0),
        row("Demo-3 b", "Paper C", 3.0, None, -0.2, "2022-01", limit=0),
    ])
    pairs, report = screen_radius_solutions(data)
    assert pairs.empty
    assert report["candidate_pair_count"] == 0


def test_same_reference_is_not_compared_to_itself():
    data = pd.DataFrame([
        row("Demo-4 b", "Same Paper", 1.0, 0.1, -0.1, "2020-01"),
        row("Demo-4 b", "Same Paper", 1.2, 0.1, -0.1, "2020-01"),
        row("Demo-4 b", "Other Paper", 1.1, 0.1, -0.1, "2021-01"),
    ])
    pairs, report = screen_radius_solutions(data)
    assert pairs.empty
    assert report["planets_excluded_for_multiple_distinct_rows_same_reference"] == 1


def test_non_confirmed_rows_are_not_in_primary_pilot():
    data = pd.DataFrame([
        row("Demo-5 b", "Paper A", 1.0, 0.1, -0.1, "2020-01", soltype="Published Candidate"),
        row("Demo-5 b", "Paper B", 2.0, 0.1, -0.1, "2021-01", soltype="Published Candidate"),
    ])
    pairs, _ = screen_radius_solutions(data)
    assert pairs.empty


def test_candidate_id_stable_under_input_order():
    data = pd.DataFrame([
        row("Demo-6 b", "Paper A", 1.0, 0.1, -0.1, "2020-01"),
        row("Demo-6 b", "Paper B", 2.0, 0.1, -0.1, "2021-01"),
    ])
    p1, _ = screen_radius_solutions(data)
    p2, _ = screen_radius_solutions(data.iloc[::-1].reset_index(drop=True))
    assert p1.iloc[0]["candidate_id"] == p2.iloc[0]["candidate_id"]


def test_non_overlapping_pairs_sort_before_overlapping_pairs():
    data = pd.DataFrame([
        row("Demo-7 b", "Paper A", 1.0, 1.0, -1.0, "2020-01"),
        row("Demo-7 b", "Paper B", 2.0, 1.0, -1.0, "2021-01"),
        row("Demo-8 b", "Paper C", 1.0, 0.05, -0.05, "2020-01"),
        row("Demo-8 b", "Paper D", 3.0, 0.05, -0.05, "2021-01"),
    ])
    pairs, _ = screen_radius_solutions(data)
    assert len(pairs) == 2
    assert bool(pairs.iloc[0]["intervals_overlap"]) is False
    assert bool(pairs.iloc[1]["intervals_overlap"]) is True


def star_row(name, ref, radius, star, stellar_ref=None, tran=1, ratio=None):
    r = row(name, ref, radius, 0.05, -0.05, "2020-01" if ref == "Paper A" else "2021-01")
    r.update({"st_rad": star, "st_refname": stellar_ref or ref, "tran_flag": tran})
    if ratio is not None:
        r.update({"pl_ratror": ratio, "pl_ratrorerr1": 0.001, "pl_ratrorerr2": -0.001, "pl_ratrorlim": 0})
    return r


def test_difference_explained_by_stellar_radius_alone():
    data = pd.DataFrame([
        star_row("Demo-9 b", "Paper A", 2.0, 1.0),
        star_row("Demo-9 b", "Paper B", 3.0, 1.5),
    ])
    p = screen_radius_solutions(data)[0].iloc[0]
    assert bool(p["intervals_overlap"]) is False
    assert p["stellar_rescaling_outcome"] == "consistent_after_stellar_rescaling"
    assert p["stellar_share_of_log_radius_change"] == pytest.approx(1.0)
    assert p["implied_rp_rs_relative_difference_pct"] == pytest.approx(0.0)
    assert bool(p["both_rows_transiting"]) is True
    assert bool(p["stellar_refs_match_planet_refs"]) is True


def test_difference_persists_when_star_unchanged_direction_wrong():
    data = pd.DataFrame([
        star_row("Demo-10 b", "Paper A", 2.0, 1.0),
        star_row("Demo-10 b", "Paper B", 3.0, 0.9),
    ])
    p = screen_radius_solutions(data)[0].iloc[0]
    assert p["stellar_rescaling_outcome"] == "persists_after_stellar_rescaling"
    assert p["stellar_share_of_log_radius_change"] < 0


def test_same_star_and_missing_star_outcomes():
    same = pd.DataFrame([star_row("D-11 b", "Paper A", 2.0, 1.0), star_row("D-11 b", "Paper B", 3.0, 1.0)])
    assert screen_radius_solutions(same)[0].iloc[0]["stellar_rescaling_outcome"] == "same_stellar_radius"
    missing = pd.DataFrame([star_row("D-12 b", "Paper A", 2.0, None), star_row("D-12 b", "Paper B", 3.0, 1.0)])
    assert screen_radius_solutions(missing)[0].iloc[0]["stellar_rescaling_outcome"] == "stellar_radius_unavailable"


def test_premise_flags_for_foreign_stellar_reference_and_non_transit():
    data = pd.DataFrame([
        star_row("D-13 b", "Paper A", 2.0, 1.0, stellar_ref="Stellar catalogue", tran=0),
        star_row("D-13 b", "Paper B", 3.0, 1.5),
    ])
    p = screen_radius_solutions(data)[0].iloc[0]
    assert bool(p["stellar_refs_match_planet_refs"]) is False
    assert bool(p["both_rows_transiting"]) is False


def test_transit_flag_unknown_for_old_snapshots():
    data = pd.DataFrame([row("D-14 b", "Paper A", 1.0, 0.1, -0.1, "2020"), row("D-14 b", "Paper B", 2.0, 0.1, -0.1, "2021")])
    p = screen_radius_solutions(data)[0].iloc[0]
    assert pd.isna(p["both_rows_transiting"])
    assert pd.isna(p["published_rp_rs_intervals_overlap"])


def test_published_ratio_and_row_self_consistency():
    k = 0.02
    consistent = k * 1.0 * SOLAR_TO_EARTH_RADII
    data = pd.DataFrame([
        star_row("D-15 b", "Paper A", consistent, 1.0, ratio=k),
        star_row("D-15 b", "Paper B", consistent * 3, 1.0, ratio=k),
    ])
    p = screen_radius_solutions(data)[0].iloc[0]
    assert bool(p["published_rp_rs_intervals_overlap"]) is True
    assert p["rp_vs_rp_rs_times_rs_deviation_pct_a"] == pytest.approx(0.0, abs=1e-9)
    assert p["rp_vs_rp_rs_times_rs_deviation_pct_b"] == pytest.approx(200.0)


def test_reference_columns_parsed_and_pair_count():
    ads = "<a refstr=X_2020 href=https://ui.adsabs.harvard.edu/abs/2020ApJ...900....1X/abstract target=ref>X et al. 2020</a>"
    data = pd.DataFrame([row("D-16 b", ads, 1.0, 0.1, -0.1, "2020"), row("D-16 b", "Paper B", 2.0, 0.1, -0.1, "2021"),
                         row("D-16 b", "Paper C", 3.0, 0.1, -0.1, "2022")])
    pairs = screen_radius_solutions(data)[0]
    first = pairs[pairs["reference_a"] == ads].iloc[0]
    assert first["reference_bibcode_a"] == "2020ApJ...900....1X"
    assert first["reference_label_a"] == "X et al. 2020"
    assert set(pairs["planet_pair_count"]) == {3}


def test_ranks_do_not_depend_on_input_row_order():
    data = pd.DataFrame([row("Tie-1 b", ref, 1.0, 0.1, -0.1, "2020") for ref in ("Paper A", "Paper B", "Paper C")])
    orders = {tuple(screen_radius_solutions(data.iloc[list(perm)].reset_index(drop=True))[0]["candidate_id"])
              for perm in ((0, 1, 2), (2, 1, 0), (1, 0, 2), (2, 0, 1))}
    assert len(orders) == 1


def test_candidate_id_survives_cosmetic_reference_markup_and_value_revision():
    ref = "<a refstr=X_2020 href=https://ui.adsabs.harvard.edu/abs/2020ApJ...900....1X/abstract target=ref>X et al. 2020</a>"
    base = pd.DataFrame([row("Id-1 b", ref, 1.0, 0.1, -0.1, "2020"), row("Id-1 b", "Paper B", 2.0, 0.1, -0.1, "2021")])
    restyled = base.copy()
    restyled.loc[0, "pl_refname"] = ref.replace("target=ref", "target=_blank")
    revised = base.copy()
    revised.loc[0, "pl_radeerr1"] = 0.2
    p0, p1, p2 = (screen_radius_solutions(d)[0].iloc[0] for d in (base, restyled, revised))
    assert p0["candidate_id"] == p1["candidate_id"] == p2["candidate_id"]
    assert p0["content_hash"] == p1["content_hash"] != p2["content_hash"]


def test_intervals_touching_within_float_noise_overlap():
    data = pd.DataFrame([row("Touch-1 b", "Paper A", 0.7, 0.1, -0.1, "2020"),
                         row("Touch-1 b", "Paper B", 0.9, 0.1, -0.1, "2021")])
    p = screen_radius_solutions(data)[0].iloc[0]
    assert bool(p["intervals_overlap"]) is True
    assert p["reported_interval_gap_rearth"] == 0


def test_only_exact_confirmed_soltype_is_eligible():
    data = pd.DataFrame([row("Sol-1 b", "Paper A", 1.0, 0.1, -0.1, "2020", soltype="Unconfirmed Planet Solution"),
                         row("Sol-1 b", "Paper B", 2.0, 0.1, -0.1, "2021", soltype="Unconfirmed Planet Solution")])
    assert screen_radius_solutions(data)[0].empty
