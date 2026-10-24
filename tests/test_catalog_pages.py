from exodiff.catalog_pages import contradictions, page_from_record as parse_page


def page(sentence: str, mass="11.41 Earths", period="29.8 days", orbit="0.1794 AU") -> dict:
    return {"short_description": sentence, "derived_description": "", "planet_mass": mass, "period_display": period,
            "pl_orbsmax": None if orbit == "Unknown" else float(orbit.split()[0])}


def test_sentence_and_box_disagree():
    p = parse_page(page("HD 3167 c is a Neptune-like exoplanet. Its mass is 11.13 Earths, it takes 29.8 days to complete "
                        "one orbit of its star, and is 0.1776 AU from its star."))
    got = {c["quantity"] for c in contradictions(p)}
    assert got == {"mass", "orbit"}


def test_rounding_and_units_are_not_contradictions():
    p = parse_page(page("X b. Its mass is 1 Jupiters, it takes 1.2 years to complete one orbit of its star, and is 0.0453 AU "
                        "from its star.", mass="318 Earths", period="438.3 days", orbit="0.0452 AU"))
    assert contradictions(p) == []


def test_unknown_box_with_number_in_sentence():
    p = parse_page(page("X b. Its mass is 9.78 Earths, it takes 6.9 days to complete one orbit of its star, and is "
                        "0.0618 AU from its star.", mass="9.78 Earths", period="6.9 days", orbit="Unknown"))
    assert contradictions(p) == [{"quantity": "orbit", "sentence": "0.0618 AU", "box": "Unknown"}]


def test_missing_from_sentence_is_not_a_contradiction():
    p = parse_page(page("X b. Its mass is 4.61 Earths and it takes 15.3 days to complete one orbit of its star.",
                        mass="4.61 Earths", period="15.3 days", orbit="Unknown"))
    assert contradictions(p) == []


def test_conversion_factors_are_actually_tested():
    ok = parse_page(page("X b. Its mass is 2.000 Jupiters, it takes 1.2000 years to complete one orbit of its star, "
                         "and is 0.1 AU from its star.", mass="635.66 Earths", period="438.30 days", orbit="0.1 AU"))
    assert contradictions(ok) == []
    bad = parse_page(page("X b. Its mass is 2.000 Jupiters, it takes 1.2000 years to complete one orbit of its star, "
                          "and is 0.1 AU from its star.", mass="600.00 Earths", period="438.00 days", orbit="0.1 AU"))
    assert {c["quantity"] for c in contradictions(bad)} == {"mass", "period"}


def test_singular_units_are_read():
    p = parse_page(page("X b. Its mass is 1 Jupiter, it takes 5.7 years to complete one orbit of its star, and is 0.1 AU "
                        "from its star.", mass="1 Jupiters", period="5.7 years", orbit="0.1 AU"))
    assert p["s"]["mass"]["unit"] == "Jupiters" and contradictions(p) == []


def test_classify_names_the_likely_cause():
    import pandas as pd
    from exodiff.catalog_pages import classify
    p = parse_page(page("X b. Its mass is 11.13 Earths, it takes 29.8 days to complete one orbit of its star, and is "
                        "0.1776 AU from its star."))
    rows = pd.DataFrame([{"pl_refname": "Old 2017", "pl_bmasse": 11.13, "pl_orbper": 29.8, "pl_orbsmax": None, "st_mass": None},
                         {"pl_refname": "New 2024", "pl_bmasse": 11.41, "pl_orbper": 29.8, "pl_orbsmax": None, "st_mass": None}])
    by = {c["quantity"]: classify(c, p, rows) for c in contradictions(p)}
    assert by["mass"]["cause"] == "older-paper" and by["mass"]["paper"] == "Old 2017"
    assert by["orbit"]["cause"] == "calculated"


def test_feed_text_choice_matches_the_page():
    rec = page("", mass="2 Jupiters") | {"derived_description": "X b. Its mass is 3 Jupiters."}
    assert parse_page(rec)["s"]["mass"]["v"] == 3.0
    blurb = page("This super hot world is covered in a global ocean of lava.")
    assert parse_page(blurb)["sentence"] is None and contradictions(parse_page(blurb)) == []
