from exodiff.explanations import explain, shape, summary


def planet(host, leads, values=None):
    return {"host": host, "papers": [{"default": True, "values": {f: {"v": v} for f, v in (values or {}).items()}}], "leads": leads}


def b(rule, ref, listed, implied, pct):
    return {"kind": "B", "rule": rule, "ref": ref, "listed": listed, "implied": implied, "pct": pct, "label_only": False}


def d(rule, nasa, eu):
    return {"kind": "D", "rule": rule, "nasa": nasa, "eu": eu, "label_only": False}


def test_shapes():
    assert shape(2.0) == "double" and shape(0.5) == "double"
    assert shape(10.1) == "tenfold" and shape(1 / 1000) == "tenfold"
    assert shape(317.83) == "units" and shape(1 / 11.2) == "units"
    assert shape(1.3) is None and shape(None) is None and shape(-2) is None


def test_letters_swapped_beats_shape():
    planets = {"X b": planet("X", [d("period", 448.3, 9.64)], {"period": 448.3}),
               "X c": planet("X", [], {"period": 9.64})}
    explain(planets)
    assert planets["X b"]["leads"][0]["why"] == "letters"


def test_whole_system_shift_needs_two_planets_and_same_percentage():
    planets = {"Y b": planet("Y", [b("kepler", "P 2022", 0.07, 0.09, -21.8)]),
               "Y c": planet("Y", [b("kepler", "P 2022", 0.11, 0.14, -21.7)]),
               "Z b": planet("Z", [b("kepler", "Q 2020", 0.07, 0.09, -21.8)])}
    explain(planets)
    assert [planets[n]["leads"][0]["why"] for n in ("Y b", "Y c", "Z b")] == ["system", "system", "other"]


def test_timing_paper_and_other():
    leads = [b("radius", "Big 2017", 1.1, 1.0, 10.0) for _ in range(5)]
    planets = {"T b": planet("T", [d("period", 3.3088770, 3.3088790)]), "U b": planet("U", leads),
               "V b": planet("V", [d("radius", 2.0, 3.0)])}
    items = explain(planets)
    assert planets["T b"]["leads"][0]["why"] == "timing"
    assert {l["why"] for l in planets["U b"]["leads"]} == {"paper"}
    assert planets["V b"]["leads"][0]["why"] == "other"
    assert sum(e["leads"] for e in summary(items)) == 7


def test_label_only_leads_are_not_explained():
    planets = {"W b": planet("W", [{**b("radius", "R", 2.0, 1.0, 100), "label_only": True}])}
    assert explain(planets) == {} and "why" not in planets["W b"]["leads"][0]


def test_no_cause_guessed_from_discovery_method_and_numbers_for_copies_and_catalog():
    p = planet("M", [d("orbit", 0.74, 1.5)])
    p["discovery"] = {"method": "Microlensing"}
    a5 = {"kind": "A", "rule": "A5", "label_only": False, "detail": "pl_rade = 14.359, pl_radj = 1.271 (x11.209 = 14.25); +0.79%"}
    c = {"kind": "C", "rule": "mass", "display": "1.80 Earths", "label_only": False}
    q = planet("Q", [a5, c], {"mass": 1.75})
    items = explain({"M b": p, "Q b": q})
    assert p["leads"][0]["why"] == "double"
    assert (items["unit-copies"][0]["a"], items["unit-copies"][0]["b"]) == (14.359, 14.25)
    assert (items["catalog"][0]["a"], items["catalog"][0]["b"]) == (1.75, 1.8)


def test_catalog_jupiter_display_is_converted_to_earths():
    c = {"kind": "C", "rule": "mass", "display": "6.43 Jupiters", "label_only": False}
    items = explain({"H b": planet("H", [c], {"mass": 2040.0})})
    assert abs(items["catalog"][0]["b"] - 6.43 * 317.83) < 1e-6
