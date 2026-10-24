import json

import pytest

from exodiff.public_catalog import PublicCatalogError, fetch_public_catalog, latest_public_snapshot


class FakeResponse:
    def __init__(self, records, total, pages, status=200):
        self._records, self.status_code = records, status
        self.headers = {"X-WP-Total": str(total), "X-WP-TotalPages": str(pages)}

    def json(self):
        return self._records

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self, pages, total, fail_on=None, status=429):
        self.pages, self.total, self.fail_on, self.status = pages, total, fail_on, status

    def get(self, url, params, headers, timeout):
        assert "ExoDiff" in headers["User-Agent"]
        page = params["page"]
        if page == self.fail_on:
            return FakeResponse([], self.total, len(self.pages), status=self.status)
        return FakeResponse(self.pages[page - 1], self.total, len(self.pages))


def rec(i):
    return {"id": i, "slug": f"p-{i}", "link": f"https://science.nasa.gov/exoplanet-catalog/p-{i}/",
            "modified": "2026-10-09T15:58:30", "acf": {"exo_id": f"P-{i}_b"}}


def test_snapshot_written_and_reloaded_with_hash_check(tmp_path):
    session = FakeSession([[rec(1), rec(2)], [rec(3)]], total=3)
    result = fetch_public_catalog(tmp_path, per_page=2, delay_seconds=0, session=session)
    assert result["records"] == 3
    records, manifest = latest_public_snapshot(tmp_path)
    assert [r["id"] for r in records] == [1, 2, 3] and manifest["reported_total"] == 3


def test_rate_limit_stops_without_writing(tmp_path):
    session = FakeSession([[rec(1)], [rec(2)]], total=2, fail_on=2, status=429)
    with pytest.raises(PublicCatalogError, match="429"):
        fetch_public_catalog(tmp_path, per_page=1, delay_seconds=0, session=session)
    assert latest_public_snapshot(tmp_path) is None


def test_count_mismatch_is_rejected(tmp_path):
    session = FakeSession([[rec(1)], [rec(2)]], total=5)
    with pytest.raises(PublicCatalogError, match="reports 5"):
        fetch_public_catalog(tmp_path, per_page=1, delay_seconds=0, session=session)


def test_tampered_snapshot_is_refused(tmp_path):
    fetch_public_catalog(tmp_path, per_page=5, delay_seconds=0, session=FakeSession([[rec(1)]], total=1))
    data = next((tmp_path / "data/raw").glob("nasa_public_catalog_*[0-9]Z.json"))
    data.write_text(json.dumps([rec(99)]))
    with pytest.raises(PublicCatalogError, match="SHA-256"):
        latest_public_snapshot(tmp_path)


class ChangesSession:
    def __init__(self, everything, changed):
        self.everything, self.changed, self.calls = everything, changed, []

    def get(self, url, params, headers, timeout):
        self.calls.append(dict(params))
        if "modified_after" in params:
            return FakeResponse(self.changed, len(self.changed), 1)
        return FakeResponse(self.everything[:params["per_page"]], len(self.everything), 1)


def test_only_changed_planets_are_downloaded_and_merged(tmp_path):
    fetch_public_catalog(tmp_path, delay_seconds=0, session=FakeSession([[rec(1), rec(2)]], total=2))
    edited = {**rec(2), "modified": "2026-10-20T10:00:00", "acf": {"exo_id": "P-2_b", "planet_mass": "3 Earths"}}
    session = ChangesSession([rec(1), edited], [edited])
    result = fetch_public_catalog(tmp_path, delay_seconds=0, session=session)
    assert result["mode"].startswith("changes only") and session.calls[0]["modified_after"] == "2026-10-08T15:58:30"
    records, manifest = latest_public_snapshot(tmp_path)
    assert {r["id"]: r for r in records}[2]["acf"]["planet_mass"] == "3 Earths" and manifest["modified_max"] == "2026-10-20T10:00:00"


def test_no_change_writes_nothing(tmp_path):
    fetch_public_catalog(tmp_path, delay_seconds=0, session=FakeSession([[rec(1), rec(2)]], total=2))
    result = fetch_public_catalog(tmp_path, delay_seconds=0, session=ChangesSession([rec(1), rec(2)], [rec(2)]))
    assert result["unchanged"] and len(list(tmp_path.glob("data/raw/*.manifest.json"))) == 1


def test_a_removed_planet_triggers_a_full_read(tmp_path):
    fetch_public_catalog(tmp_path, delay_seconds=0, session=FakeSession([[rec(1), rec(2)]], total=2))
    result = fetch_public_catalog(tmp_path, delay_seconds=0, session=ChangesSession([rec(1)], []))
    assert result["mode"] == "full" and [r["id"] for r in latest_public_snapshot(tmp_path)[0]] == [1]
