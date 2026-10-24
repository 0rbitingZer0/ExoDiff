import pandas as pd

from exodiff.sources import column_tags, is_paper_sourced, reference_column, value_source

PAPER = "<a refstr=BEARD_ET_AL__2022 href=https://ui.adsabs.harvard.edu/abs/2022ApJ...936...55B/abstract target=ref>Beard et al. 2022</a>"
TIC = "<a refstr=TICV8 href=https://ui.adsabs.harvard.edu/abs/2019AJ....158..138S/abstract target=ref>TICv8</a>"


def row(**over):
    base = {"pl_name": "GJ 3929 b", "pl_refname": PAPER, "st_refname": TIC, "sy_refname": TIC,
            "pl_rade": 1.09, "pl_radj": 0.097, "st_rad": 0.32, "st_raderr1": 0.01, "sy_dist": 15.8, "pl_bmasse": None}
    base.update(over)
    return pd.Series(base)


def test_reference_column_by_prefix_and_suffix():
    assert reference_column("pl_orbper") == "pl_refname"
    assert reference_column("st_raderr1") == "st_refname"
    assert reference_column("sy_distlim") == "sy_refname"
    assert reference_column("hostname") is None


def test_value_sources():
    r = row()
    assert value_source(r, "pl_rade") == {"kind": "paper", "reference": "Beard et al. 2022"}
    assert value_source(r, "st_rad") == {"kind": "catalogue", "reference": "TICv8"}
    assert value_source(r, "sy_dist")["kind"] == "catalogue"
    assert value_source(r, "pl_radj")["kind"] == "converted"
    assert value_source(r, "pl_bmasse")["kind"] == "none"
    assert is_paper_sourced(r, "pl_rade") and not is_paper_sourced(r, "st_rad")
    assert is_paper_sourced(row(st_refname=PAPER), "st_rad")


def test_column_tags_counts():
    frame = pd.DataFrame([row(), row(st_refname=PAPER)])
    tags = column_tags(frame)
    assert tags["st_rad"] == {"filled": 2, "reference_column": "st_refname", "paper": 1, "catalogue": 1}
    assert tags["pl_radj"] == {"filled": 2, "converted": 2}
