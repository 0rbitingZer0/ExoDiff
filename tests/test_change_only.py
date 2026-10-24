import json

import pandas as pd
import pytest

from exodiff import runlog
from exodiff.polite import fetch_all


class Response:
    def __init__(self, text="", status=200, headers=None):
        self.text, self.status_code, self.headers = text, status, headers or {}
        self.content = text.encode()

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))


def test_a_crawl_stops_after_five_failures_in_a_row():
    calls = []

    class Down:
        def get(self, url, **kwargs):
            calls.append(url)
            raise ConnectionError("timed out")
    ok, failed = fetch_all({f"p{i}": f"https://x/{i}" for i in range(50)}, str, workers=1, session=Down(), sleep=lambda s: None)
    assert ok == {} and len(failed) == 50 and len(calls) == 5


def test_notes_pages_due_today():
    from exodiff.overview_notes import pages_to_read
    hosts = [f"H{i:02d}" for i in range(14)]
    saved = {"systems": {h: {} for h in hosts[1:]}, "read_at": {h: f"2026-10-{10 + i % 7:02d}" for i, h in enumerate(hosts)}}
    due = pages_to_read(hosts, saved, updated={"H05": "2026-10-20"})
    assert due[:2] == ["H00", "H05"]
    assert len(due) == 2 + 2
    assert due[2:] == ["H07", "H01"]


def test_eu_pages_read_only_when_missing_or_updated(tmp_path):
    from exodiff.eu_sources import fetch_sources
    page = '<li class="list-group-item publication" id="publication_1"><h5>T</h5><time datetime="2020"></time>A B</li>'
    seen = []

    class Site:
        def get(self, url, **kwargs):
            seen.append(url)
            return Response(page)
    links = {"A b": "https://e/a", "C d": "https://e/c"}
    first = fetch_sources(links, tmp_path, updated={"A b": "2026-01-01", "C d": "2026-01-01"}, session=Site(), sleep=lambda s: None)
    assert first["read"] == 2 and len(seen) == 2
    again = fetch_sources(links, tmp_path, updated={"A b": "2026-01-01", "C d": "2026-01-01"}, session=Site(), sleep=lambda s: None)
    assert again["requested"] == 1 and set(again["pages"]) == {"A b", "C d"}
    future = "9999-01-01"
    later = fetch_sources(links, tmp_path, updated={"A b": "2026-01-01", "C d": future}, session=Site(), sleep=lambda s: None)
    assert "https://e/c" in seen[-2:] and later["requested"] == 2


def test_gaia_and_simbad_ask_only_for_new_stars(tmp_path):
    from exodiff.gaia import fetch_gaia
    from exodiff.simbad import fetch_idents
    asked = []

    class Archive:
        def post(self, url, data, timeout):
            asked.append(data.get("QUERY") or data.get("query"))
            if "gaiaedr3_distance" in asked[-1]:
                ids = [int(x) for x in asked[-1].rsplit("(", 1)[1].rstrip(")").split(",")]
                return Response("source_id,r_med_geo,r_lo_geo,r_hi_geo\n" + "".join(f"{i},10,9,11\n" for i in ids))
            names = asked[-1].rsplit("(", 1)[1].rstrip(")").replace("'", "").split(",")
            return Response("gaia,ident\n" + "".join(f"{n},{n}\n{n},HD {n[-1]}\n" for n in names))
    fetch_gaia([1, 2], tmp_path, session=Archive())
    result = fetch_gaia([1, 2, 3], tmp_path, session=Archive())
    assert "IN (3)" in asked[-1] and result["rows"] == 3 and not result["unchanged"]
    assert fetch_gaia([1, 2, 3], tmp_path, session=Archive())["unchanged"] and len(asked) == 2
    fetch_idents(["Gaia DR3 1"], tmp_path, session=Archive())
    fetch_idents(["Gaia DR3 1", "Gaia DR3 2"], tmp_path, session=Archive())
    assert "'Gaia DR3 2'" in asked[-1] and "'Gaia DR3 1'" not in asked[-1]


def test_nasa_archive_reused_when_its_fingerprint_matches(tmp_path, monkeypatch):
    import exodiff.nasa as nasa
    csv = "pl_name,hostname,soltype,default_flag," + ",".join(c for c in nasa.BASE_COLUMNS if c not in
                                                                ("pl_name", "hostname", "soltype", "default_flag")) + "\n"
    csv += "".join(f"P{i} b,P{i},Published Confirmed,1" + "," * (len(nasa.BASE_COLUMNS) - 4) + "\n" for i in range(nasa.MIN_FULL_PULL_ROWS))
    fingerprint = "last_update,last_release,row_count\n2026-10-15,2026-10-15,10000\n"
    calls = []

    def get(url, params, headers, timeout):
        calls.append(params["query"])
        return Response(fingerprint if params["query"] == nasa.FINGERPRINT_QUERY else csv)
    monkeypatch.setattr(nasa.requests, "get", get)
    first = nasa.fetch_radius_solutions(tmp_path)
    assert not first["unchanged"] and len(calls) == 2
    second = nasa.fetch_radius_solutions(tmp_path)
    assert second["unchanged"] and len(calls) == 3
    assert (tmp_path / "data/processed/nasa_ps_confirmed_latest.csv").read_text() == csv
    fingerprint = fingerprint.replace("2026-10-15,10000", "2026-10-22,10000")
    assert not nasa.fetch_radius_solutions(tmp_path)["unchanged"]
    fingerprint = fingerprint.replace("10000", "10001")
    with pytest.raises(RuntimeError, match="partial download"):
        nasa.fetch_radius_solutions(tmp_path)


def test_run_record_lists_sources_that_were_down(tmp_path):
    runlog.start(tmp_path)
    runlog.record(tmp_path, "NASA archive", "unchanged", copy_from="2026-10-15T18:00:00+00:00")
    runlog.record(tmp_path, "exoplanet.eu", "copy", copy_from="2026-10-15T21:00:00+00:00", error="timed out")
    assert runlog.down(tmp_path) == ["exoplanet.eu"]
    assert json.loads((tmp_path / "reports/run.json").read_text())["sources"]["exoplanet.eu"]["error"] == "timed out"


def test_hostile_or_huge_pages_are_refused_not_parsed():
    import time
    from exodiff.eu_sources import parse_eu_page
    from exodiff.overview_notes import parse_overview
    from exodiff.polite import MAX_PAGE_BYTES, _capped_text
    start = '<li class="list-group-item publication" id="publication_1">'
    t = time.time(); parse_eu_page(start * 20_000 + "publication_")
    assert time.time() - t < 0.5
    page = ('var json = {"system": {"system_info": {"id": "X"}, "objects": {"planet_set": {"planets": {"X b": {"note_set": '
            '{"notes": [{"note": "n", "refid": "r", "creationdate": 2026}]}}}}}}, "reference_dictionary": {"r": {"authors": 12345}}};')
    note = parse_overview(page)["notes"][0]
    assert note["reference"] is None and note["date"] is None

    class Big:
        encoding = "utf-8"
        def iter_content(self, n):
            while True:
                yield b"x" * n
    with pytest.raises(ValueError, match="over"):
        _capped_text(Big(), MAX_PAGE_BYTES)
