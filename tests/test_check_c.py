import pandas as pd

from exodiff.check_c import check_c, public_value


def acf(**over):
    base = {"pl_rade": 1.09, "planet_mass": "1.75 Earths", "pl_orbper": 2.616235, "pl_orbsmax": 0.0252,
            "eccentricity": "0.0", "pl_orbeccen": 0, "pl_eccenlim": 0, "st_dist": 15.8095}
    base.update(over)
    return base


def archive_row(ref="<a refstr=B href=https://ui.adsabs.harvard.edu/abs/x/abstract target=ref>Beard et al. 2022</a>",
                default=1, **over):
    base = {"pl_name": "GJ 3929 b", "default_flag": default, "pl_refname": ref, "pl_rade": 1.09, "pl_bmasse": 1.75,
            "pl_bmassprov": "Mass", "pl_orbper": 2.616235, "pl_orbsmax": 0.0252, "pl_orbeccen": 0.0,
            "pl_orbeccenlim": 0, "sy_dist": 15.8095}
    base.update(over)
    return base


def run(public, rows, comp=None, archive_only=()):
    join = {"matched": {"GJ 3929 b": {"link": "https://science.nasa.gov/exoplanet-catalog/gj-3929-b/", "acf": public}},
            "archive_only": list(archive_only)}
    comp = comp if comp is not None else pd.DataFrame([{"pl_name": "GJ 3929 b"}])
    result, stats = check_c(join, pd.DataFrame(rows), comp)
    return result.set_index(["pl_name", "field"])["bucket"].to_dict(), result, stats


def test_public_value_parsing():
    j = public_value("mass", acf(planet_mass="1.2 Jupiters"))
    assert abs(j["value"] - 1.2 * 317.83) < 0.01 and abs(j["tolerance"] - (0.05 * 317.83 + 0.0005 * 1.2 * 317.83)) < 0.01
    m = public_value("mass", acf(planet_mass="3 Earths"))
    assert m["value"] == 3 and m["tolerance"] == 0.5
    assert public_value("mass", acf(planet_mass="Unknown")) is None
    e = public_value("eccentricity", acf(eccentricity="< 0.05", pl_eccenlim=0.05))
    assert e["limit"] and e["value"] == 0.05
    assert public_value("eccentricity", acf(eccentricity="", pl_orbeccen=0)) is None
    assert public_value("radius", acf(pl_rade="")) is None


def test_buckets_default_composite_other_none():
    rows = [archive_row(), archive_row(ref="Kemmer et al. 2022", default=0, pl_rade=1.15, pl_orbper=2.6162745)]
    comp = pd.DataFrame([{"pl_name": "GJ 3929 b", "pl_orbsmax": 0.035, "pl_orbsmax_reflink": "Other 2021"}])
    buckets, _, _ = run(acf(pl_rade=1.15, pl_orbsmax=0.035, st_dist=99.0), rows, comp)
    assert buckets[("GJ 3929 b", "radius")] == "C-other"
    assert buckets[("GJ 3929 b", "orbit")] == "C-composite"
    assert buckets[("GJ 3929 b", "distance")] == "C-none"
    assert buckets[("GJ 3929 b", "period")] == "C-default"


def test_rounding_tolerance_and_absent():
    buckets, _, _ = run(acf(pl_rade=1.1), [archive_row(pl_rade=1.09)])
    assert buckets[("GJ 3929 b", "radius")] == "C-default"
    buckets, _, _ = run(acf(), [archive_row()], archive_only=["New-1 b"])
    assert buckets[("New-1 b", "radius")] == "C-absent"


def test_limit_kept_as_limit_and_labelled_when_storage_differs():
    _, result, _ = run(acf(eccentricity="< 0.05", pl_eccenlim=0.05), [archive_row(pl_orbeccen=0.05, pl_orbeccenlim=1)])
    ecc = result[result.field == "eccentricity"].iloc[0]
    assert ecc["bucket"] == "C-default" and ecc["labels"] == []
    _, result, _ = run(acf(eccentricity="< 0.05", pl_eccenlim=0.05), [archive_row(pl_orbeccen=0.05, pl_orbeccenlim=0)])
    assert "limit shown differently" in result[result.field == "eccentricity"].iloc[0]["labels"][0]


def test_hostile_public_values_are_ignored_not_fatal():
    for bad in ["<", "< ", "<abc", "<0.1.2", "nan", "1e999"]:
        assert public_value("eccentricity", acf(eccentricity=bad, pl_eccenlim=None)) is None
    assert public_value("radius", acf(pl_rade=True)) is None
    assert public_value("radius", acf(pl_rade="=cmd|' /C calc'!A0")) is None
    assert public_value("mass", acf(planet_mass="<script>alert(1)</script>")) is None


def test_mass_in_jupiters_matches_the_default_rows_jupiter_copy():
    rows = [archive_row(pl_bmasse=3000.0, pl_bmassj=8.0),
            archive_row(ref="Older 2008", default=0, pl_bmasse=2543.0, pl_bmassj=8.0)]
    buckets, _, _ = run(acf(planet_mass="8 Jupiters"), rows)
    assert buckets[("GJ 3929 b", "mass")] == "C-default"


def test_small_catalog_distance_gap_is_a_survey_note():
    buckets, _, _ = run(acf(st_dist=15.85), [archive_row()])
    assert buckets[("GJ 3929 b", "distance")] == "C-survey"
    buckets, _, _ = run(acf(st_dist=17.5), [archive_row()])
    assert buckets[("GJ 3929 b", "distance")] == "C-none"


def test_estimated_radius_is_a_note_not_compared():
    buckets, _, _ = run(acf(pl_rade=13.6, planet_radius="1.22 x Jupiter (estimate)"), [archive_row()])
    assert buckets[("GJ 3929 b", "radius")] == "C-estimate"
    buckets, _, _ = run(acf(pl_rade=13.6, planet_radius="1.22 x Jupiter"), [archive_row()])
    assert buckets[("GJ 3929 b", "radius")] == "C-none"
