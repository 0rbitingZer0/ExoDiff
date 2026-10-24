import math

import pandas as pd
import pytest

from exodiff.identities import (AU_IN_SUN_RADII, EARTH_DENSITY_UNIT_G_CM3, IDENTITIES, _kepler_a, check_identity,
                                  identity_checks)

BY_KEY = {i.key: i for i in IDENTITIES}


def base_row(**over):
    row = {"pl_name": "Id b", "soltype": "Published Confirmed", "pl_refname": "Paper A", "discoverymethod": "Transit",
           "pl_bmassprov": "Mass", "pl_orbeccen": 0.0}
    for col in ("pl_dens", "pl_bmasse", "pl_rade", "pl_orbsmax", "pl_orbper", "st_mass", "pl_ratdor", "st_rad"):
        row[col + "lim"] = 0
    for col in ("pl_bmasse", "pl_rade", "pl_orbper", "st_mass", "pl_orbsmax", "st_rad"):
        value = over.get(col)
        if isinstance(value, (int, float)) and value:
            row[col + "err1"], row[col + "err2"] = 0.001 * value, -0.001 * value
    row.update(over)
    return row


def with_errors(row, col, value, err):
    row[col], row[col + "err1"], row[col + "err2"] = value, err, -err
    return row


def test_constants_match_known_values():
    assert EARTH_DENSITY_UNIT_G_CM3 == pytest.approx(5.51, abs=0.02)
    assert AU_IN_SUN_RADII == pytest.approx(215.03, abs=0.01)
    assert _kepler_a({"st_mass": 1.0, "pl_orbper": 365.25636, "pl_bmasse": 1.0}) == pytest.approx(1.0, abs=2e-4)


def test_density_consistent_and_inconsistent():
    good = with_errors(base_row(pl_bmasse=1.0, pl_rade=1.0), "pl_dens", round(EARTH_DENSITY_UNIT_G_CM3, 3), 0.01)
    bad = with_errors(base_row(pl_name="Bad b", pl_bmasse=1.0, pl_rade=1.0), "pl_dens", 11.0, 0.5)
    result, stats = check_identity(pd.DataFrame([good, bad]), BY_KEY["density"])
    assert stats["checkable_rows"] == 2 and stats["lead_rows"] == 1
    assert result.iloc[0]["pl_name"] == "Bad b" and result.iloc[0]["is_lead"]


def test_density_skips_minimum_masses():
    row = with_errors(base_row(pl_bmasse=1.0, pl_rade=1.0, pl_bmassprov="Msini"), "pl_dens", 11.0, 0.5)
    result, stats = check_identity(pd.DataFrame([row]), BY_KEY["density"])
    assert result.empty and stats["skipped_rows"] == {"mass_is_minimum_or_unknown": 1}


def test_kepler_skips_projected_separations_and_flags_mismatch():
    a = round(_kepler_a({"st_mass": 1.0, "pl_orbper": 10.0}), 5)
    ok = with_errors(base_row(st_mass=1.0, pl_orbper=10.0), "pl_orbsmax", a, 0.001)
    off = with_errors(base_row(pl_name="Off b", st_mass=1.0, pl_orbper=10.0), "pl_orbsmax", round(a * 1.2, 5), 0.001)
    lens = with_errors(base_row(pl_name="Lens b", st_mass=1.0, pl_orbper=10.0, discoverymethod="Microlensing"),
                       "pl_orbsmax", 3.0, 0.1)
    result, stats = check_identity(pd.DataFrame([ok, off, lens]), BY_KEY["kepler"])
    assert stats["skipped_rows"] == {"projected_separation": 1}
    assert set(result[result["is_lead"]]["pl_name"]) == {"Off b"}


def test_a_over_rstar_only_for_circular_orbits():
    circ = with_errors(base_row(pl_orbsmax=0.05, st_rad=1.0), "pl_ratdor", round(0.05 * AU_IN_SUN_RADII, 3), 0.1)
    ecc = with_errors(base_row(pl_name="Ecc b", pl_orbsmax=0.05, st_rad=1.0, pl_orbeccen=0.3), "pl_ratdor", 8.0, 0.1)
    result, stats = check_identity(pd.DataFrame([circ, ecc]), BY_KEY["a_over_rstar"])
    assert stats["checkable_rows"] == 1 and stats["skipped_rows"] == {"eccentric_or_unreported": 1}
    assert not result.iloc[0]["is_lead"]


def test_missing_columns_are_reported_not_crashed():
    result, stats = identity_checks(pd.DataFrame([{"pl_name": "x"}]))
    assert result.empty
    assert all(s["checkable_rows"] == 0 and s["missing_columns"] for s in stats.values())


def test_kepler_skips_circumbinary_planets():
    row = with_errors(base_row(st_mass=1.0, pl_orbper=10.0, cb_flag=1), "pl_orbsmax", 0.2, 0.001)
    result, stats = check_identity(pd.DataFrame([row]), BY_KEY["kepler"])
    assert result.empty and stats["skipped_rows"] == {"circumbinary": 1}


def test_gap_inside_the_inputs_uncertainty_is_not_a_lead():
    row = with_errors(base_row(st_mass=0.942, pl_orbper=123.01), "pl_orbsmax", 0.476, 0.001)
    row["st_masserr1"], row["st_masserr2"] = 0.034, -0.034
    result, _ = check_identity(pd.DataFrame([row]), BY_KEY["kepler"])
    assert not result.iloc[0]["is_lead"] and result.iloc[0]["beyond_own_error_bar"]


def test_assumed_input_without_error_is_never_a_lead():
    row = with_errors(base_row(st_mass=1.44, pl_orbper=10140.0), "pl_orbsmax", 10.26, 0.07)
    row["st_masserr1"] = row["st_masserr2"] = None
    result, _ = check_identity(pd.DataFrame([row]), BY_KEY["kepler"])
    assert not result.iloc[0]["is_lead"] and result.iloc[0]["assumed_inputs"] == "st_mass"
