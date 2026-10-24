import json

from exodiff.known_notes import add_overview_notes, documented, text_categories
from exodiff.overview_notes import fetch_overviews, parse_overview


def page(planet_notes=(), star_notes=(), private=False):
    data = {
        "manifest": {"compilation_date": "2026-10-14"},
        "system": {"system_info": {"id": "TOI-1", "note_set": {}},
                   "objects": {"stellar_set": {"stars": {"TOI-1": {"alias_set": {"aliases": {"Gaia Catalog (DR3)": "Gaia DR3 7"}},
                                                                    "note_set": {"notes": list(star_notes)}}}},
                               "planet_set": {"planets": {"TOI-1 b": {"note_set": {"notes": list(planet_notes)}},
                                                          "TOI-1 c": {"note_set": {}}}}}},
        "reference_dictionary": {"Ref1": {"authors": "Smith et al. 2025", "bibcode": "2025AJ....1....1S"}},
    }
    note = lambda text: {"note": text, "refid": "Ref1", "private_flag": int(private), "creationdate": "2026-07-01"}
    data["system"]["objects"]["planet_set"]["planets"]["TOI-1 b"]["note_set"] = {"notes": [note(t) for t in planet_notes]}
    data["system"]["objects"]["stellar_set"]["stars"]["TOI-1"]["note_set"] = {"notes": [note(t) for t in star_notes]}
    return "<html><script>var json = " + json.dumps(data) + ";\nvar other = 1;</script></html>"


def test_parse_reads_planet_and_star_notes_with_paper():
    parsed = parse_overview(page(["Typo in planet radius units."], ["Stellar radius from TICv8."]))
    assert parsed["planets"] == ["TOI-1 b", "TOI-1 c"]
    assert {(n["object"], n["kind"], n["bibcode"]) for n in parsed["notes"]} == {
        ("TOI-1 b", "planet", "2025AJ....1....1S"), ("TOI-1", "star", "2025AJ....1....1S")}
    assert parsed["aliases"]["TOI-1"]["Gaia Catalog (DR3)"] == "Gaia DR3 7"


def test_private_notes_are_skipped():
    assert parse_overview(page(["secret"], private=True))["notes"] == []


def test_page_without_data_is_an_error():
    try:
        parse_overview("<html></html>")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_text_categories():
    assert text_categories("Typo in transit depth units in Table 2.") == {"radius"}
    assert text_categories("Transit midpoint time (T0) corrected by authors.") == {"other"}
    assert "mass" in text_categories("Planet mass from M sin i")
    assert text_categories("Rotation period typo") == {"other"}


def test_documented_needs_same_paper_unless_identity():
    snap = {"systems": {"TOI-1": parse_overview(page(["Planet radius typo in Table 3."], ["Planet letters b and c swapped; see alias."]))}}
    notes = add_overview_notes({}, snap)
    assert len(notes["TOI-1 b"]) == 2 and len(notes["TOI-1 c"]) == 1
    assert documented("TOI-1 b", "radius", notes, "2025AJ....1....1S")
    assert not [n for n in documented("TOI-1 b", "radius", notes, "2020AJ....9....9X") if "identity" not in n["categories"]]
    assert documented("TOI-1 c", "kepler", notes)


def test_frozen_table_entry_not_repeated():
    frozen = {"TOI-1 b": [{"parameter": "Transit Depth", "category": "radius", "notes": "Typo in transit depth units in Table 2.",
                           "reference": "Smith et al. 2025"}]}
    snap = {"systems": {"TOI-1": parse_overview(page(["Typo in transit depth units in Table 2. Literature Value: 1 ppt."]))}}
    assert len(add_overview_notes(frozen, snap)["TOI-1 b"]) == 1


def test_html_entities_decoded_so_references_match_paper_rows():
    snap = {"systems": {"TOI-1": parse_overview(page(["Radius 1.2 &plusmn; 0.1 in ref."]))}}
    snap["systems"]["TOI-1"]["notes"][0]["reference"] = "Ba&scaron;t&uuml;rk &amp; Smith 2025"
    note = add_overview_notes({}, snap)["TOI-1 b"][0]
    assert note["notes"] == "Radius 1.2 ± 0.1 in ref." and note["reference"] == "Baštürk & Smith 2025"


class FakeResponse:
    def __init__(self, text, status=200):
        self.text, self.status = text, status

    def raise_for_status(self):
        if self.status >= 400:
            import requests
            raise requests.HTTPError(str(self.status))


class FakeSession:
    def __init__(self, pages):
        self.pages, self.urls = pages, []

    def get(self, url, **kwargs):
        self.urls.append(url)
        return self.pages.get(url.rsplit("/", 1)[-1], FakeResponse("", 404))


def test_fetch_writes_snapshot_and_lists_failures(tmp_path):
    session = FakeSession({"TOI-1": FakeResponse(page(["Planet radius typo."]))})
    manifest = fetch_overviews(["TOI-1", "Kepler 9"], tmp_path, session=session, sleep=lambda s: None)
    assert manifest["hosts_read"] == 1 and manifest["failures"] == 1 and manifest["notes"] == 1
    assert session.urls[0].endswith("Kepler%209")
    snap = json.loads((tmp_path / "data/raw" / manifest["file"]).read_text())
    assert "Kepler 9" in snap["failures"]
