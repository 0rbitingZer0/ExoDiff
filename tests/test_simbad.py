import pandas as pd

from exodiff.explanations import confirm_letters
from exodiff.simbad import host_gaia, join_by_host, norm


def eu():
    return pd.DataFrame([
        {"name": "Barnard's star b", "star_name": "Barnard's star", "star_alternate_names": "GJ 699"},
        {"name": "Barnard's star c", "star_name": "Barnard's star", "star_alternate_names": ""},
        {"name": "Twin b", "star_name": "Twin A", "star_alternate_names": ""},
        {"name": "Twin 2 b", "star_name": "Twin B", "star_alternate_names": ""},
        {"name": "Taken b", "star_name": "Taken", "star_alternate_names": ""},
    ])


def test_norm_collapses_simbad_padding():
    assert norm("HD   1237") == norm("hd 1237")


def test_join_by_host_matches_letter_and_skips_ambiguous_and_taken():
    idents = {"Gaia DR3 1": [norm("NAME Barnard's star"), norm("GJ 699")],
              "Gaia DR3 2": [norm("Twin A"), norm("Twin B")],
              "Gaia DR3 3": [norm("Taken")]}
    gaia_of = {"Barnard b": "Gaia DR3 1", "Barnard c": "Gaia DR3 1", "Barnard d": "Gaia DR3 1",
               "Twin b": "Gaia DR3 2", "Other b": "Gaia DR3 3", "Nogaia b": None}
    out = join_by_host(eu(), list(gaia_of), gaia_of, idents, taken={"Taken b"})
    assert out["matched"] == {"Barnard b": "Barnard's star b", "Barnard c": "Barnard's star c"}
    assert [a["pl_name"] for a in out["ambiguous"]] == ["Twin b"]


def test_host_gaia_prefers_default_row():
    nasa = pd.DataFrame([{"pl_name": "X b", "default_flag": 0, "gaia_dr3_id": "Gaia DR3 9"},
                         {"pl_name": "X b", "default_flag": 1, "gaia_dr3_id": "Gaia  DR3 5"}])
    assert host_gaia(nasa, ["X b"]) == {"X b": "Gaia DR3 5"}


def test_confirm_letters_marks_shared_alias_only_on_sibling():
    planets = {"S b": {"host": "S", "leads": [{"kind": "D", "why": "letters"}]},
               "S c": {"host": "S", "leads": []},
               "T b": {"host": "T", "leads": [{"kind": "D", "why": "letters"}]}}
    n = confirm_letters(planets, {"S b": "S b", "T b": "T b"}, {"S b": ["TOI-1.02"], "T b": ["TOI-9.01"]},
                        {"S c": ["TOI-1.02"], "U b": ["TOI-9.01"]})
    assert n == 1
    assert planets["S b"]["leads"][0]["alias_of"] == "S c"
    assert "shared_alias" not in planets["T b"]["leads"][0]
