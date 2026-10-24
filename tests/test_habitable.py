from exodiff.habitable import MAXIMUM_GREENHOUSE, RUNAWAY_GREENHOUSE, in_habitable_zone, s_eff


def test_sun_limits_match_the_paper_table():
    assert s_eff(5780, RUNAWAY_GREENHOUSE) == 1.107 and s_eff(5780, MAXIMUM_GREENHOUSE) == 0.356


def test_earth_in_venus_out_mars_in():
    assert in_habitable_zone(1.0, 5780) is True
    assert in_habitable_zone(1.91, 5780) is False
    assert in_habitable_zone(0.43, 5780) is True


def test_unknown_when_inputs_missing_or_star_out_of_range():
    assert in_habitable_zone(None, 5780) is None
    assert in_habitable_zone(1.0, None) is None
    assert in_habitable_zone(1.0, 9000) is None


def test_insolation_prefers_listed_then_computes():
    from exodiff.habitable import insolation
    assert insolation(2.0, 0.0, 1.0) == (2.0, "listed")
    assert insolation(None, 0.0, 2.0) == (0.25, "computed")
    assert insolation(None, None, 1.0) == (None, None)
