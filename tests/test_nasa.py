import pandas as pd
import pytest

from exodiff import nasa


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content
        self.text = content.decode("utf-8")
        self.status_code = 200
        self.headers = {"Content-Type": "text/csv", "ETag": '"demo"', "Last-Modified": "Wed, 14 Oct 2026 00:00:00 GMT"}

    def raise_for_status(self):
        return None


def sample_csv() -> bytes:
    cols = nasa.BASE_COLUMNS
    record = {
        "pl_name": "Demo-1 b", "hostname": "Demo-1", "soltype": "Published Confirmed",
        "default_flag": "1", "pl_controv_flag": "0", "pl_rade": "1.2",
        "pl_radeerr1": "0.1", "pl_radeerr2": "-0.1", "pl_radelim": "0",
        "pl_refname": "Demo paper 2025", "pl_pubdate": "2025-01",
        "st_rad": "1.0", "st_raderr1": "0.1", "st_raderr2": "-0.1",
        "st_refname": "Stellar paper 2024", "discoverymethod": "Transit", "disc_year": "2024",
        "tran_flag": "1", "pl_ratror": "0.011", "pl_ratrorerr1": "0.001", "pl_ratrorerr2": "-0.001",
        "pl_ratrorlim": "0",
    }
    return (",".join(cols) + "\n" + ",".join('"' + str(record.get(c, "")).replace('"', '""') + '"' for c in cols) + "\n").encode()


def test_build_query_limit_is_explicit_smoke_test():
    assert "SELECT TOP 2500" in nasa.build_query(2500)
    assert "SELECT * FROM ps WHERE soltype = 'Published Confirmed'" in nasa.build_query()
    assert "LIKE" not in nasa.build_query().upper()
    with pytest.raises(ValueError):
        nasa.build_query(0)


def test_fetch_saves_raw_manifest_and_latest_copy(tmp_path, monkeypatch):
    payload = sample_csv()
    calls = []

    def fake_get(url, params, headers, timeout):
        calls.append((url, params, headers, timeout))
        return FakeResponse(payload)

    monkeypatch.setattr(nasa.requests, "get", fake_get)
    result = nasa.fetch_radius_solutions(tmp_path, limit=10, max_retries=0)
    assert result["rows"] == 1
    assert result["limited_smoke_test"] is True
    assert len(calls) == 1
    raw = open(result["raw_path"], "rb").read()
    assert raw == payload
    assert open(result["latest_path"], "rb").read() == payload
    import json
    manifest = json.loads(open(result["manifest_path"], encoding="utf-8").read())
    assert manifest["sha256_raw_response"] == result["sha256"]
    assert manifest["limited_smoke_test"] is True
    assert "SELECT TOP 10" in manifest["query"]


def test_truncated_body_is_rejected(tmp_path, monkeypatch):
    body = sample_csv()[:-1]
    monkeypatch.setattr(nasa.requests, "get", lambda *a, **k: FakeResponse(body))
    with pytest.raises(RuntimeError, match="truncated"):
        nasa.fetch_radius_solutions(tmp_path, limit=10, max_retries=0)
    assert not list((tmp_path / "data" / "raw").glob("*.csv"))


def test_short_full_pull_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(nasa.requests, "get", lambda *a, **k: FakeResponse(sample_csv()))
    with pytest.raises(RuntimeError, match="partial response"):
        nasa.fetch_radius_solutions(tmp_path, limit=None, max_retries=0)


def test_short_composite_table_is_rejected(tmp_path, monkeypatch):
    body = ("pl_name," + ",".join(c for c in nasa.COMPOSITE_COLUMNS if c != "pl_name") + "\nP b" + "," * (len(nasa.COMPOSITE_COLUMNS) - 1) + "\n").encode()
    monkeypatch.setattr(nasa.requests, "get", lambda *a, **k: FakeResponse(body))
    with pytest.raises(RuntimeError, match="partial response"):
        nasa.fetch_composite(tmp_path)
