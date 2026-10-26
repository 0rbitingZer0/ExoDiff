import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def test_git_holds_only_what_the_gitignore_allows():
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    forced = subprocess.run(["git", "ls-files", "-ci", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    assert set(forced) <= {"site/data/ledger.json", "site/data/updates.json", "site/data/meta.json"}, forced


def test_tampered_or_unrecorded_saved_copies_are_not_used(tmp_path):
    raw = tmp_path / "raw"; raw.mkdir()
    good, bad = b"a,b\n1,2\n", b"a,b\n1,3\n"
    (raw / "src_20261001T000000Z.csv").write_bytes(good)
    (raw / "src_20261001T000000Z.manifest.json").write_text(json.dumps({"sha256": hashlib.sha256(good).hexdigest()}))
    (raw / "other_20261001T000000Z.csv").write_bytes(bad)
    (raw / "other_20261001T000000Z.manifest.json").write_text(json.dumps({"sha256": hashlib.sha256(good).hexdigest()}))
    (raw / "stray_20261001T000000Z.json").write_text("{}")
    (raw / ".gitkeep").write_text("")
    assert [p.name for p in load("verify_raw").bad_files(raw)] == [
        "other_20261001T000000Z.csv", "other_20261001T000000Z.manifest.json", "stray_20261001T000000Z.json"]


def test_a_restored_copy_must_be_on_the_committed_list(tmp_path):
    good = b"a,b\n1,2\n"
    for name in ("src_20261001T000000Z.csv", "forged_20261002T000000Z.csv"):
        (tmp_path / name).write_bytes(good)
        (tmp_path / name.replace(".csv", ".manifest.json")).write_text(json.dumps({"sha256": hashlib.sha256(good).hexdigest()}))
    committed = {n: hashlib.sha256((tmp_path / n).read_bytes()).hexdigest()
                 for n in ("src_20261001T000000Z.csv", "src_20261001T000000Z.manifest.json")}
    assert [p.name for p in load("verify_raw").bad_files(tmp_path, committed)] == [
        "forged_20261002T000000Z.csv", "forged_20261002T000000Z.manifest.json"]


def test_a_copy_that_comes_from_git_unchanged_is_kept(tmp_path):
    verify = load("verify_raw")
    good = b"a,b\n1,2\n"
    for name in ("seed_20261003T000000Z.csv", "swapped_20261003T000000Z.csv"):
        (tmp_path / name).write_bytes(good)
        (tmp_path / name.replace(".csv", ".manifest.json")).write_text(json.dumps({"sha256": hashlib.sha256(good).hexdigest()}))
    from_git = {n: verify.git_blob((tmp_path / n).read_bytes()) for n in
                ("seed_20261003T000000Z.csv", "seed_20261003T000000Z.manifest.json", "swapped_20261003T000000Z.manifest.json")}
    from_git["swapped_20261003T000000Z.csv"] = verify.git_blob(b"a,b\n9,9\n")
    assert [p.name for p in verify.bad_files(tmp_path, {"other.csv": "0" * 64}, from_git)] == ["swapped_20261003T000000Z.csv"]


def _history(folder, updates=None, leads=None):
    folder.mkdir(exist_ok=True)
    (folder / "ledger.json").write_text(json.dumps({"run": {"date": "2026-10-15", "data": "d", "code": "c", "skipped": []},
                                                    "baseline": "2026-10-15", "planets": {"A b": "2026-10-15"},
                                                    "leads": leads or {"A b|B|radius|P|": {"since": "2026-10-15", "key": "B/B-look"}},
                                                    "notes": {"A b": {"C": 1}}}))
    (folder / "updates.json").write_text(json.dumps(updates or [{"date": "2026-10-15", "cause": "first run", "findings": 1, "planets": 1,
                                                                  "planets_with_findings": 1, "notes": 1, "by_check": {"B": 1}, "data": "d", "code": "c"}]))
    (folder / "meta.json").write_text(json.dumps({"snapshot_sha256": "a" * 64, "run": {}, "query": load("check_history").EXPECTED_QUERY}))
    return folder


def test_history_files_are_checked_before_commit(tmp_path):
    check = load("check_history")
    assert check.problems(_history(tmp_path / "ok")) == []
    first = json.loads((tmp_path / "ok/updates.json").read_text())[0]
    note = {"planet": "A b", "from": 2, "to": 1}
    for good in ([note], [{**note, "checks": {"C": [2, 1]}}]):
        assert check.problems(_history(tmp_path / "notes", [{**first, "notes_changed": good}])) == [], good
    for bad in ({**first, "not_checked": "A"}, {**first, "removed_planets": ["x" * 500]}, {**first, "planets_with_findings": None},
                {**first, "date": "1999-01-01"}, {**first, "cause": "<script>"},
                {**first, "notes_changed": [{**note, "checks": {"Z": [2, 1]}}]}, {**first, "notes_changed": [{**note, "checks": {"C": [2, "<b>"]}}]}):
        assert check.problems(_history(tmp_path / "bad", [bad])), bad
    meta = json.loads((tmp_path / "ok/meta.json").read_text())
    (tmp_path / "ok/meta.json").write_text(json.dumps({**meta, "query": "SELECT * FROM ps"}))
    assert check.problems(tmp_path / "ok") == ["meta.json: the archive query isn't the expected one"]


def test_a_failed_check_cannot_be_published_as_a_successful_one(tmp_path):
    check = load("check_history")
    folder = _history(tmp_path / "h")
    meta = json.loads((folder / "meta.json").read_text())
    t = "2026-10-26T06:17:00+00:00"
    source = lambda **r: {"status": "copy", "checked_utc": t, "copy_from": "2026-10-15T21:36:18.747289+00:00",
                          "last_ok_utc": "2026-10-20T21:41:33+00:00", **r}
    for good in (source(), source(status="unchanged", last_ok_utc=t), source(status="missing", copy_from=None, last_ok_utc=None)):
        (folder / "meta.json").write_text(json.dumps({**meta, "run": {"sources": {"exoplanet.eu": good}}}))
        assert check.problems(folder) == [], good
    for bad in (source(last_ok_utc=t), source(status="partial", last_ok_utc=t), source(last_ok_utc="2026-10-27T00:00:00+00:00"),
                source(status="fine"), source(checked_utc="yesterday"), source(last_ok_utc="2026-10-20"), "copy"):
        (folder / "meta.json").write_text(json.dumps({**meta, "run": {"sources": {"exoplanet.eu": bad}}}))
        assert check.problems(folder), bad


def test_the_committed_past_cannot_be_rewritten(tmp_path):
    check = load("check_history")
    old = _history(tmp_path / "old")
    first = json.loads((old / "updates.json").read_text())[0]
    newer = {**first, "date": "2026-10-16", "cause": "new data", "findings": 2}
    assert check.problems(_history(tmp_path / "new", [newer, first]), old) == []
    assert check.problems(_history(tmp_path / "rewritten", [newer, {**first, "findings": 9}]), old)
    forged = {"A b|B|radius|P|": {"since": "2026-10-01", "key": "B/B-look"}}
    assert check.problems(_history(tmp_path / "forged", [newer, first], forged), old) == [
        "ledger.json: a committed first-seen date of leads changed"]


def test_expected_archive_query_is_the_one_the_code_runs():
    from exodiff.nasa import build_query
    assert load("check_history").EXPECTED_QUERY == build_query()


def test_local_history_files_pass_the_commit_check():
    folder = ROOT / "site/data"
    if (folder / "updates.json").exists():
        assert load("check_history").problems(folder) == []


WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.y*ml"))
PERMISSIONS = {"build": {"contents": "read"}, "save-history": {"contents": "write"},
               "deploy": {"pages": "write", "id-token": "write"}, "alert": {"issues": "write"}}


def _jobs(wf: str) -> dict:
    jobs, job, in_perms = {}, None, False
    for line in wf.split("\njobs:\n", 1)[1].splitlines():
        if m := re.match(r"^  ([a-z][a-z-]*):", line):
            job, in_perms = m.group(1), False
            jobs[job] = None
        elif job and (m := re.match(r"^    permissions:\s*(\{\})?\s*(#.*)?$", line)):
            jobs[job], in_perms = {}, not m.group(1)
        elif in_perms and (m := re.match(r"^      ([a-z-]+):\s*([a-z-]+)", line)):
            jobs[job][m.group(1)] = m.group(2)
        elif in_perms and not line.startswith("      "):
            in_perms = False
    return jobs


def test_workflows_cannot_be_triggered_or_steered_by_outsiders():
    assert [w.name for w in WORKFLOWS] == ["update-site.yml"]
    for path in WORKFLOWS:
        wf = path.read_text()
        triggers = wf.split("\non:\n", 1)[1].split("\npermissions:")[0]
        assert re.findall(r"^  ([a-z_]+):", triggers, re.M) == ["schedule", "workflow_dispatch", "push"]
        assert re.search(r"^permissions: \{\}", wf, re.M)
        assert _jobs(wf) == PERMISSIONS
        for line in re.findall(r"uses:\s*(\S+)", wf):
            assert line.startswith("actions/") and re.search(r"@[0-9a-f]{40}$", line), line
        alert = wf.split("\n  alert:\n", 1)[1]
        assert "actions/checkout" not in alert and 'author:app/github-actions' in alert and "exit 1" not in alert
        run_blocks = re.findall(r"run: \|\n((?:\s{10,}.*\n)+)|run: (.*)", wf)
        for block, single in run_blocks:
            assert "${{" not in block + single, (block + single)[:80]


def test_page_never_turns_data_into_code():
    js, html = (ROOT / "site/app.js").read_text(), (ROOT / "site/index.html").read_text()
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function", "setTimeout(\"", "javascript:"):
        assert sink not in js, sink
    assert ('content="default-src \'none\'; script-src \'self\'; style-src \'self\'; img-src \'self\'; connect-src \'self\'; base-uri \'none\'; form-action \'none\';"' in html)
    assert re.findall(r"<script[^>]*>", html) == ['<script src="app.js">']


def test_a_crashed_check_alerts_but_a_missing_input_does_not(tmp_path, monkeypatch):
    from exodiff import runlog
    mod = load("run_check_e")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "OUT_CSV", tmp_path / "check_e.csv")
    monkeypatch.setattr(mod, "OUT_JSON", tmp_path / "check_e.json")
    runlog.start(tmp_path)
    mod.skip("Gaia snapshot or archive snapshot missing")
    assert runlog.down(tmp_path) == []
    mod.skip("KeyError: 'r_med_geo'", crashed=True)
    assert runlog.down(tmp_path) == ["check E"]


def test_the_alert_names_each_source_and_what_went_wrong(tmp_path, monkeypatch):
    from exodiff import runlog
    mod = load("run_summary")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runlog.start(tmp_path)
    runlog.record(tmp_path, "NASA archive", "unchanged")
    runlog.record(tmp_path, "exoplanet.eu", "copy", copy_from="2026-10-15T21:36:18+00:00", error="timed out | <b>")
    runlog.record(tmp_path, "NASA notes", "partial")
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    mod.main()
    assert out.read_text().splitlines() == ["down=NASA notes, exoplanet.eu",
        "down_detail=NASA notes (partly read: failed pages retried next run), exoplanet.eu (unreachable: saved copy used)"]
