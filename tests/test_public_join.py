from exodiff.public_join import join_public


def rec(i, exo_id, host=None, letter=None):
    return {"id": i, "link": f"https://science.nasa.gov/exoplanet-catalog/{i}/", "modified": "2026-10-09",
            "acf": {"exo_id": exo_id, "pl_hostname": host, "pl_letter": letter, "display_name": exo_id}}


def test_exact_fallback_unmatched_and_ambiguous():
    archive = ["GJ 3929 b", "TOI-789 c", "HD 1 b", "New-1 b"]
    records = [
        rec(1, "GJ_3929_b"),
        rec(2, "toi-789  C"),
        rec(3, "HD_000001_b", "HD 1", "b"),
        rec(4, "Nowhere_9_b", "Nowhere 9", "b"),
        rec(5, "GJ 3929 b"),
    ]
    out = join_public(records, archive)
    assert set(out["matched"]) == {"GJ 3929 b", "TOI-789 c", "HD 1 b"}
    assert out["matched"]["GJ 3929 b"]["link"].endswith("/1/")
    assert out["archive_only"] == ["New-1 b"]
    assert [p["id"] for p in out["public_only"]] == [4]
    assert out["ambiguous"] == [{"pl_name": "GJ 3929 b", "ids": [1, 5]}]
    assert out["stats"]["matched_via_fallback"] == 1


def test_no_fuzzy_matching():
    out = join_public([rec(1, "GJ_3929b")], ["GJ 3929 b"])
    assert out["matched"] == {} and out["archive_only"] == ["GJ 3929 b"]


def test_off_site_links_and_malformed_records_are_rejected():
    records = [rec(1, "GJ_3929_b"), {"id": "x", "acf": {}}, "not a dict", {"id": 3, "acf": None}]
    records[0]["link"] = "https://evil.example/x"
    out = join_public(records, ["GJ 3929 b"])
    assert out["matched"]["GJ 3929 b"]["link"] is None
    assert out["stats"]["rejected"] == 4
