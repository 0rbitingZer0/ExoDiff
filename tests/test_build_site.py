from scripts.build_site import check_inputs


def test_check_inputs_refuses_truncated_or_mismatched_snapshots():
    manifest = {"limited_smoke_test": False, "sha256_raw_response": "abc", "row_count": 16759}
    report = {"input_sha256": "abc", "input_rows": 16759}
    assert check_inputs(manifest, report, {"snapshot_rows": 27834}, 0.95)
    assert check_inputs({**manifest, "query": "q"}, report, {"snapshot_rows": 27834, "query": "q"}, 0.95)
    assert check_inputs({**manifest, "query": "new"}, report, {"snapshot_rows": 27834, "query": "old"}, 0.95) == []
    assert check_inputs(manifest, {**report, "input_sha256": "zzz"}, {}, 0.95)
    assert check_inputs(manifest, {**report, "input_rows": 1}, {}, 0.95)
    assert check_inputs({**manifest, "limited_smoke_test": True}, report, {}, 0.95)
    assert check_inputs(manifest, report, {"snapshot_rows": 16800}, 0.95) == []


def test_newest_manifest_is_chosen_by_recorded_time_not_filename(tmp_path):
    import json
    from exodiff.nasa import newest_manifests
    q = "SELECT * FROM ps WHERE soltype = 'Published Confirmed'"
    (tmp_path / "zzz_old.manifest.json").write_text(json.dumps({"retrieved_at_utc": "2026-10-14T00:00:00+00:00", "query": q}))
    (tmp_path / "aaa_new.manifest.json").write_text(json.dumps({"retrieved_at_utc": "2026-10-15T00:00:00+00:00", "query": q}))
    (tmp_path / "comp.manifest.json").write_text(json.dumps({"retrieved_at_utc": "2026-10-16T00:00:00+00:00",
                                                             "query": "SELECT pl_name FROM pscomppars"}))
    (tmp_path / "public.manifest.json").write_text(json.dumps({"retrieved_at_utc": "2026-10-17T00:00:00+00:00"}))
    assert newest_manifests(tmp_path)[-1].name == "aaa_new.manifest.json"


def test_reconcile_planets_catches_count_drift():
    from scripts.build_site import reconcile_planets
    index = [{"n": "P b", "a": 1, "b": 2, "c": 1}]
    report = {"check_a": {"leads": 1}, "check_b": {"by_bucket": {"B-look": 2}}}
    assert reconcile_planets(index, report, {"by_bucket": {"C-none": 1, "C-other": 5}}) == []
    assert reconcile_planets(index, report, {"by_bucket": {"C-none": 6, "C-other": 0}})
    assert reconcile_planets(index, {**report, "check_a": {"leads": 2}}, {"by_bucket": {"C-none": 1}})
    c = {"by_bucket": {"C-none": 1}}
    assert reconcile_planets([{**index[0], "x": 3}], report, c, {"by_bucket": {"D-disagree": 3}}) == []
    assert reconcile_planets([{**index[0], "x": 3}], report, c, {"by_bucket": {"D-disagree": 4}})
    assert reconcile_planets([{**index[0], "x": 3}], report, c)


def test_reconcile_planets_counts_gaia_leads_per_planet():
    import pandas as pd
    from scripts.build_site import reconcile_planets
    report = {"check_a": {"leads": 0}, "check_b": {"by_bucket": {"B-look": 0}}}
    e = pd.DataFrame({"bucket": ["E-differs", "E-same"], "planets": ["K-1 b; K-1 c", "G-3 b"]})
    index = [{"n": "K-1 b", "a": 0, "b": 0, "c": 0, "e": 1}, {"n": "K-1 c", "a": 0, "b": 0, "c": 0, "e": 1}]
    assert reconcile_planets(index, report, {"by_bucket": {"C-none": 0}}, None, e) == []
    assert reconcile_planets(index[:1], report, {"by_bucket": {"C-none": 0}}, None, e)


def test_check_c_results_from_another_archive_snapshot_are_dropped(tmp_path, monkeypatch):
    import json
    import scripts.build_site as bs
    monkeypatch.setattr(bs, "ROOT", tmp_path)
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports/check_c.json").write_text(json.dumps({"archive_sha256": "old", "by_bucket": {"C-none": 3}}))
    frame, join, stats = bs.check_c_inputs("new")
    assert frame.empty and join is None and stats["skipped"]


def test_an_update_is_dated_by_its_run_not_by_the_archive_download(tmp_path, monkeypatch):
    import scripts.build_site as bs
    from exodiff import runlog
    monkeypatch.setattr(bs, "ROOT", tmp_path)
    runlog.start(tmp_path)
    assert bs.run_date() == runlog.load(tmp_path)["started_utc"][:10]
