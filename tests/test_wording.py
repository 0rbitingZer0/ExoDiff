import re

from exodiff import check_a, check_b, check_c, eu_catalog, explanations, gaia, wording
from exodiff.site_planets import D_NOTES, D_OPEN

BANNED = re.compile(r"\b(?:pl|st|sy)_[a-z]|RUWE|σ|√|Msini|M ?sin ?i|osculat|a/R\*|bibcode|covariance", re.IGNORECASE)


def every_outcome_key():
    keys = {f"A/{r}" for r in check_a.TITLES} | {f"B/{b}" for b in check_b.BUCKETS} | {"B/B-transit-open"}
    keys |= {f"C/{b}" for b in check_c.FINE_WHEN} | {f"D/{b}" for b in eu_catalog.FINE_WHEN} | {f"E/{b}" for b in gaia.FINE_WHEN}
    keys |= {f"pattern/{k}" for k, _, _ in explanations.EXPLANATIONS} | {"F"}
    keys |= {f"card/{c}" for c in ("radius", "density", "kepler", "a_over_rstar", "public", "eu", "gaia", "massKind", "values", "rows")}
    keys |= {f"general/{g}" for g in ("finding", "note", "uncertainty", "no-uncertainty", "precision")} | {"about/intro", "about/lead"}
    return keys


def test_every_outcome_has_a_text():
    missing = sorted(k for k in every_outcome_key() if k not in wording.NEW)
    assert not missing, missing


def test_every_outcome_shown_on_a_page_has_a_filter_label():
    shown = {f"A/{r}" for r in check_a.TITLES} | {f"B/{b}" for b in check_b.BUCKETS} | {"B/B-transit-open"}
    shown |= {"C/C-none", "C/C-other", "C/C-survey", "C/C-estimate"} | {f"D/{b}" for b in (*D_OPEN, *D_NOTES, "D-letters", "D-no-errors")}
    shown |= {"E/E-differs", "E/E-quality", "F", "card/massKind"}
    assert not sorted(shown - set(wording.LABELS))


def test_plain_layers_have_no_jargon():
    offending = {k: m.group(0) for k, (compare, means, _) in wording.NEW.items()
                 for m in [BANNED.search(compare + " " + means)] if m}
    assert not offending, offending


def test_pipeline_texts_are_the_site_texts():
    assert check_a.FINE_WHEN["A5"] == wording.means("A/A5")
    assert check_b.BUCKETS["B-close"][1] == wording.means("B/B-close")
    assert check_c.FINE_WHEN["C-none"] == wording.means("C/C-none")
    assert eu_catalog.FINE_WHEN["D-letters"] == wording.means("D/D-letters")
    assert gaia.FINE_WHEN["E-quality"] == wording.means("E/E-quality")
    assert dict((k, w) for k, _, w in explanations.EXPLANATIONS)["units"] == wording.means("pattern/units")


def test_lead_keys():
    assert wording.lead_key({"kind": "B", "rule": "kepler", "bucket": "B-look", "transit_fit": True}) == "B/B-transit-open"
    assert wording.lead_key({"kind": "B", "rule": "kepler", "bucket": "B-look"}) == "B/B-look"
    assert wording.lead_key({"kind": "C", "rule": "label"}) == "card/massKind"
    assert wording.lead_key({"kind": "D", "rule": "letters", "bucket": "D-letters"}) == "D/D-letters"
    assert wording.lead_key({"kind": "F", "rule": "mass"}) == "F"
    assert set(wording.export()) == {"texts", "labels", "statistic"}


def test_jargon_pattern_catches_what_it_should():
    for bad in ("pl_rade", "st_mass", "RUWE > 1.4", "σ_P", "√2", "Msini", "M sin i", "osculating period", "a/R* = 6", "covariance"):
        assert BANNED.search(bad), bad
    assert not BANNED.search("the star's size and the planet's distance in star sizes")


def test_highlight_marks_are_paired_and_never_reach_the_pipeline():
    for key, layers in wording.NEW.items():
        for layer in layers:
            assert layer.count("**") % 2 == 0, key
        assert "**" not in wording.means(key)
