import pandas as pd

from exodiff.check_b import bucket_leads, fingerprint

PAPER = "<a refstr=P_2020 href=https://ui.adsabs.harvard.edu/abs/2020X/abstract target=ref>P et al. 2020</a>"
OTHER = "<a refstr=Q_2019 href=https://ui.adsabs.harvard.edu/abs/2019X/abstract target=ref>Q et al. 2019</a>"
TIC = "<a refstr=TICV8 href=https://ui.adsabs.harvard.edu/abs/2019AJ/abstract target=ref>TICv8</a>"


def lead(name, check="kepler", rows=1, listed=1.2, implied=1.0):
    return {"check": check, "pl_name": name, "pl_refname": PAPER, "reference": "P et al. 2020", "listed_value": listed,
            "implied_value": implied, "mismatch_pct": 20.0, "mismatch_in_error_bars": 5.0,
            "archive_rows_for_this_paper": rows}


def test_buckets_in_preregistered_order():
    frame = pd.DataFrame([
        {"pl_name": "Doc b", "pl_refname": PAPER, "st_refname": TIC},
        {"pl_name": "Cat b", "pl_refname": PAPER, "st_refname": TIC},
        {"pl_name": "Src b", "pl_refname": PAPER, "st_refname": OTHER},
        {"pl_name": "Dup b", "pl_refname": PAPER, "st_refname": PAPER},
        {"pl_name": "Look b", "pl_refname": PAPER, "st_refname": PAPER},
        {"pl_name": "Dens b", "pl_refname": PAPER, "st_refname": TIC},
    ])
    notes = {"Doc b": [{"parameter": "Orbital Period", "category": "orbit", "notes": "x", "reference": "y"}]}
    leads = pd.DataFrame([lead("Doc b"), lead("Cat b"), lead("Src b"), lead("Dup b", rows=2), lead("Look b"),
                          lead("Dens b", check="density")])
    out, stats = bucket_leads(frame, leads, notes)
    assert list(out["bucket"]) == ["B-doc", "B-cat", "B-src", "B-dup", "B-look", "B-look"]
    assert stats["by_bucket"]["B-look"] == 2


def test_unit_fingerprint():
    assert fingerprint(11.3, "radius") == "x radius in Jupiter vs Earth units"
    assert fingerprint(1 / 1408.0, "density") == "÷ radius in Jupiter vs Earth units (cubed)"
    assert fingerprint(317.0, "density") == "x mass in Jupiter vs Earth units"
    assert fingerprint(11.3, "density") is None
    assert fingerprint(2.0, "radius") is None


def test_close_mean_radius_and_transit_buckets():
    base = {"pl_refname": PAPER, "st_refname": PAPER}
    frame = pd.DataFrame([
        {**base, "pl_name": "Close b"}, {**base, "pl_name": "MeanR b"}, {**base, "pl_name": "Big b"},
        {**base, "pl_name": "Fit b", "pl_orbsmax": 0.05, "pl_ratdor": 10.7516, "pl_ratdorerr1": 0.2, "pl_ratdorerr2": -0.2,
         "st_rad": 1.0, "st_raderr1": 0.01, "st_raderr2": -0.01, "st_mass": 1.0, "st_masserr1": 0.05, "st_masserr2": -0.05,
         "pl_orbper": 4.0, "pl_orbpererr1": 1e-5, "pl_orbpererr2": -1e-5},
        {**base, "pl_name": "Far b", "pl_orbsmax": 0.05, "pl_ratdor": 10.7516, "pl_ratdorerr1": 0.02, "pl_ratdorerr2": -0.02,
         "st_rad": 1.0, "st_raderr1": 0.001, "st_raderr2": -0.001, "st_mass": 1.0, "st_masserr1": 0.003, "st_masserr2": -0.003},
    ])
    close = lead("Close b"); close["mismatch_in_error_bars"] = 1.4
    leads = pd.DataFrame([close, lead("MeanR b", check="radius", listed=11.24, implied=11.0),
                          lead("Big b", check="radius", listed=11.5, implied=11.0),
                          lead("Fit b", listed=0.05, implied=0.0515), lead("Far b", listed=0.05, implied=0.0515)])
    out, _ = bucket_leads(frame, leads, {})
    assert list(out["bucket"]) == ["B-close", "B-meanR", "B-look", "B-transit", "B-look"]


def test_literature_orbit_paper_is_a_note_and_transit_fit_flagged():
    stassun = "<a refstr=STASSUN_ET_AL__2017 href=https://ui.adsabs.harvard.edu/abs/2017AJ....153..136S/abstract target=ref>Stassun et al. 2017</a>"
    frame = pd.DataFrame([
        {"pl_name": "Rv b", "pl_refname": stassun, "st_refname": stassun, "pl_orbsmax": 1.3, "tran_flag": 0},
        {"pl_name": "Tr b", "pl_refname": stassun, "st_refname": stassun, "pl_orbsmax": 0.05, "tran_flag": 1,
         "pl_ratdor": 10.7516, "st_rad": 1.0},
    ])
    leads = pd.DataFrame([{**lead("Rv b", listed=1.3, implied=0.9), "pl_refname": stassun},
                          {**lead("Tr b", listed=0.05, implied=0.06), "pl_refname": stassun}])
    out, _ = bucket_leads(frame, leads, {})
    assert list(out["bucket"]) == ["B-lit", "B-look"] and list(out["transit_fit"]) == [False, True]


def test_close_gap_stays_a_note_whatever_the_star_source():
    from exodiff.check_b import OPEN
    frame = pd.DataFrame([{"pl_name": "Cat b", "pl_refname": PAPER, "st_refname": TIC}])
    small = lead("Cat b"); small["mismatch_in_error_bars"] = 1.5
    out, _ = bucket_leads(frame, pd.DataFrame([small, lead("Cat b")]), {})
    assert list(out["bucket"]) == ["B-close", "B-cat"] and "B-cat" in OPEN and "B-close" not in OPEN


def test_transit_note_only_for_circular_or_unreported_orbits():
    base = {"pl_refname": PAPER, "st_refname": PAPER, "pl_orbsmax": 0.05, "pl_ratdor": 10.7516, "pl_ratdorerr1": 0.2,
            "pl_ratdorerr2": -0.2, "st_rad": 1.0, "st_raderr1": 0.01, "st_raderr2": -0.01, "st_mass": 1.0,
            "st_masserr1": 0.05, "st_masserr2": -0.05, "pl_orbper": 4.0, "pl_orbpererr1": 1e-5, "pl_orbpererr2": -1e-5}
    frame = pd.DataFrame([{**base, "pl_name": "Circ b", "pl_orbeccen": 0.0}, {**base, "pl_name": "Ecc b", "pl_orbeccen": 0.3}])
    out, _ = bucket_leads(frame, pd.DataFrame([lead("Circ b", listed=0.05, implied=0.0515), lead("Ecc b", listed=0.05, implied=0.0515)]), {})
    assert list(out["bucket"]) == ["B-transit", "B-look"]
    assert list(out["transit_fit"]) == [True, False] and list(out["transit_numeric_only"]) == [False, True]


def test_transit_note_needs_an_orbit_time_uncertainty_and_the_right_row():
    base = {"pl_refname": PAPER, "st_refname": PAPER, "pl_orbsmax": 0.05, "pl_ratdor": 10.7516, "pl_ratdorerr1": 0.2,
            "pl_ratdorerr2": -0.2, "st_rad": 1.0, "st_raderr1": 0.01, "st_raderr2": -0.01, "st_mass": 1.0,
            "st_masserr1": 0.05, "st_masserr2": -0.05, "pl_orbper": 4.0, "pl_orbpererr1": 1e-5, "pl_orbpererr2": -1e-5}
    no_p = {**base, "pl_name": "NoP b", "pl_orbpererr1": None, "pl_orbpererr2": None}
    first = {**base, "pl_name": "Two b", "st_mass": 2.0}
    second = {**base, "pl_name": "Two b", "st_masserr1": None, "st_masserr2": None}
    frame = pd.DataFrame([no_p, first, second])
    from exodiff.identities import _kepler_a
    implied = _kepler_a({"pl_orbper": 4.0, "st_mass": 1.0, "pl_bmasse": None})
    out, _ = bucket_leads(frame, pd.DataFrame([lead("NoP b", listed=0.05, implied=0.0515),
                                               lead("Two b", listed=0.05, implied=implied)]), {})
    assert list(out["bucket"]) == ["B-look", "B-look"]
