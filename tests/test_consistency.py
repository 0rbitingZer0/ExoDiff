import pandas as pd
import pytest

from exodiff.consistency import EARTH_RADIUS_CONVENTION_ALLOWANCE, rounding_allowance, row_self_consistency
from exodiff.screening import SOLAR_TO_EARTH_RADII
from test_screening import row


def ratio_row(name, radius, ratio, star, plus=0.1, minus=-0.1):
    r = row(name, f"Paper {name}", radius, plus, minus, "2020")
    r.update({"st_rad": star, "pl_ratror": ratio, "pl_ratrorerr1": 0.001, "pl_ratrorerr2": -0.001,
              "pl_ratrorlim": 0, "tran_flag": 1})
    return r


def test_rounding_allowance_uses_published_digits():
    assert rounding_allowance(2.0) == pytest.approx(0.5 * 0.1 / 2.0)
    assert rounding_allowance(0.0574) == pytest.approx(0.5e-4 / 0.0574)
    assert rounding_allowance(1.5e-05) == pytest.approx(0.5e-6 / 1.5e-05)


def test_convention_allowance_is_about_a_tenth_of_a_percent():
    assert EARTH_RADIUS_CONVENTION_ALLOWANCE == pytest.approx(0.00110, abs=2e-5)


def test_consistent_row_is_not_a_lead():
    k, star = 0.02, 1.0
    data = pd.DataFrame([ratio_row("Ok-1 b", round(k * star * SOLAR_TO_EARTH_RADII, 3), k, star)])
    result, stats = row_self_consistency(data)
    assert stats["checkable_rows"] == 1 and stats["lead_rows"] == 0
    assert not result.iloc[0]["is_lead"]


def test_self_inconsistent_row_is_a_lead():
    data = pd.DataFrame([ratio_row("Bad-1 b", 90.81, 0.00784, 0.798764, plus=17.73, minus=-8.99)])
    result, stats = row_self_consistency(data)
    lead = result.iloc[0]
    assert stats["lead_rows"] == 1 and lead["is_lead"]
    assert lead["mismatch_in_own_error_bars"] > 9
    assert lead["mismatch_pct"] > 10000


def test_mismatch_within_own_error_bar_is_not_a_lead():
    k, star = 0.02013, 1.013
    true = k * star * SOLAR_TO_EARTH_RADII
    data = pd.DataFrame([ratio_row("Wide-1 b", round(true * 1.10, 3), k, star, plus=0.5, minus=-0.5)])
    lead = row_self_consistency(data)[0].iloc[0]
    assert lead["beyond_rounding_and_units"] and not lead["beyond_own_error_bar"]
    assert not lead["is_lead"]


def test_coarse_published_digits_widen_the_allowance():
    k, star = 0.02, 1.0
    data = pd.DataFrame([ratio_row("Coarse-1 b", round(k * star * SOLAR_TO_EARTH_RADII * 1.10, 3), k, star, plus=0.01, minus=-0.01)])
    lead = row_self_consistency(data)[0].iloc[0]
    assert lead["beyond_own_error_bar"] and not lead["beyond_rounding_and_units"]
    assert not lead["is_lead"]


def test_rows_without_ratio_or_star_are_counted_not_checked():
    data = pd.DataFrame([ratio_row("No-1 b", 2.0, None, 1.0), ratio_row("No-2 b", 2.0, 0.02, None)])
    result, stats = row_self_consistency(data)
    assert result.empty
    assert stats["skipped_rows"]["no_published_rp_rs"] == 1
    assert stats["skipped_rows"]["no_stellar_radius"] == 1


def test_multiple_archive_rows_for_one_paper_are_flagged():
    data = pd.DataFrame([ratio_row("Dup-1 b", 2.0, 0.02, 1.0), ratio_row("Dup-1 b", 2.6, 0.02, 1.0)])
    result, _ = row_self_consistency(data)
    assert set(result["archive_rows_for_this_paper"]) == {2}
