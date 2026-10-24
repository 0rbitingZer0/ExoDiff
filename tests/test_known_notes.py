from exodiff.known_notes import category, documented, load_notes


def test_categories():
    assert category("Planet Radius") == "radius"
    assert category("δ") == "radius"
    assert category("Mp sin i") == "mass"
    assert category("Semi-Major Axis (AU)") == "orbit"
    assert category("Planet Letter") == "identity"
    assert category("Transit Midpoint (days)") == "other"
    assert category("") == "unknown"


def test_reference_file_loads_and_matches_known_entry():
    notes = load_notes()
    assert notes, "reference/nasa_lit_discrepancies.csv should be present"
    assert documented("TOI-2048 b", "radius", notes)
    assert not documented("WASP-121 b", "radius", notes)
