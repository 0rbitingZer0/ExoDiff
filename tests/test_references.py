from exodiff.references import parse_reference

ADS = "<a refstr=MANN_ET_AL__2013 href=https://ui.adsabs.harvard.edu/abs/2013ApJ...779..188M/abstract target=ref>Mann et al. 2013</a>"
ENTITY = "<a refstr=FULTON__AMP__PETIGURA_2018 href=https://ui.adsabs.harvard.edu/abs/2018AJ....156..264F/abstract target=ref>Fulton &amp; Petigura 2018</a>"
AMPERSAND_BIBCODE = "<a refstr=MANTOVAN_ET_AL_2024 href=https://ui.adsabs.harvard.edu/abs/2024A&A...691A..67M/abstract target=ref>Mantovan et al. 2024</a>"
NON_ADS = "<a refstr=Q1_Q16_KOI_TABLE href=https://exoplanetarchive.ipac.caltech.edu/docs/Kepler_KOI_docs.html target=ref>Q1-Q16 KOI Table</a>"
PADDED = "<a refstr=SWIFT_ET_AL__2013 href=https://ui.adsabs.harvard.edu/abs/2013ApJ...764..105S/abstract target=ref> Swift et al. 2013 </a>"


def test_ads_anchor_parsed():
    ref = parse_reference(ADS)
    assert ref == {
        "label": "Mann et al. 2013",
        "refstr": "MANN_ET_AL__2013",
        "url": "https://ui.adsabs.harvard.edu/abs/2013ApJ...779..188M/abstract",
        "bibcode": "2013ApJ...779..188M",
    }


def test_html_entities_and_ampersand_bibcodes():
    assert parse_reference(ENTITY)["label"] == "Fulton & Petigura 2018"
    assert parse_reference(AMPERSAND_BIBCODE)["bibcode"] == "2024A&A...691A..67M"


def test_non_ads_link_has_no_bibcode():
    ref = parse_reference(NON_ADS)
    assert ref["bibcode"] == ""
    assert ref["url"].startswith("https://exoplanetarchive.ipac.caltech.edu/")
    assert ref["label"] == "Q1-Q16 KOI Table"


def test_whitespace_and_plain_text_and_missing():
    assert parse_reference(PADDED)["label"] == "Swift et al. 2013"
    assert parse_reference("Paper A") == {"label": "Paper A", "refstr": "", "url": "", "bibcode": ""}
    assert parse_reference(None)["label"] == ""
    assert parse_reference(float("nan"))["label"] == ""


def test_non_web_urls_are_dropped_at_parse_time():
    evil = '<a refstr=X href=javascript:alert(1) target=ref>"><script>alert(1)</script></a>'
    assert parse_reference(evil)["url"] == ""
    assert parse_reference(evil.replace("javascript:alert(1)", "data:text/html,x"))["url"] == ""
