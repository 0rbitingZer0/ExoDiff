from exodiff.ledger import update


def build(leads_by_planet):
    shards = {0: {n: {"leads": [{"kind": "B", "rule": r, "ref": "P", "key": "B/B-look", "label_only": False} for r in rules]}
                  for n, rules in leads_by_planet.items()}}
    index = [{"n": n} for n in leads_by_planet]
    return index, shards


def run(date, data="d1", code="c1"):
    return {"date": date, "data": data, "code": code}


def test_first_run_then_new_resolved_and_unchanged():
    index, shards = build({"A b": ["radius"], "B b": ["kepler"]})
    ledger, entry = update(None, index, shards, run("2026-10-15"))
    assert entry["cause"] == "first run" and ledger["leads"]["A b|B|radius|P|"] == {"since": "2026-10-15", "key": "B/B-look"}

    index, shards = build({"A b": ["radius", "density"], "C b": []})
    ledger2, entry = update(ledger, index, shards, run("2026-10-22", data="d2"))
    assert entry["cause"] == "new data" and entry["new_planets"] == ["C b"] and entry["removed_planets"] == ["B b"]
    assert [l["rule"] for l in entry["new_findings"]] == ["density"] and [l["rule"] for l in entry["resolved_findings"]] == ["kepler"]
    assert ledger2["leads"]["A b|B|radius|P|"]["since"] == "2026-10-15"
    assert entry["resolved_findings"][0]["key"] == "B/B-look"

    _, entry = update(ledger2, index, shards, run("2026-10-22", data="d2"))
    assert entry is None


def test_same_data_new_rules_is_a_rule_change():
    index, shards = build({"A b": ["radius"]})
    ledger, _ = update(None, index, shards, run("2026-10-15"))
    index, shards = build({"A b": []})
    _, entry = update(ledger, index, shards, run("2026-10-15", code="c2"))
    assert entry["cause"] == "rule change" and len(entry["resolved_findings"]) == 1


def test_rows_from_one_paper_are_one_finding_per_column():
    from exodiff.ledger import open_leads
    lead = {"kind": "A", "rule": "A3", "ref": "R", "column": "sy_dist", "detail": "+120.0 / 60.0", "label_only": False}
    keys = [k for k, _ in open_leads("P b", [lead, {**lead, "detail": "+600.0 / 390.0"}, {**lead, "column": "pl_masse"}])]
    assert keys == ["P b|A|A3|R|sy_dist", "P b|A|A3|R|pl_masse"]


def test_notes_changes_and_totals():
    index, shards = build({"A b": ["radius"]})
    note = lambda g: {"kind": "C", "rule": "orbit", "ref": None, "label_only": True, "group": g}
    shards[0]["A b"]["leads"] += [note("g1"), note("g2"), note("g2")]
    index[0].update(nf=1, a=0, b=1, nn=2)
    ledger, first = update(None, index, shards, run("2026-10-15"))
    assert first["findings"] == 1 and first["notes"] == 2 and first["by_check"]["B"] == 1
    assert ledger["notes"] == {"A b": {"C": 2}}
    shards[0]["A b"]["leads"].append(note("g3")); index[0]["nn"] = 3
    _, entry = update(ledger, index, shards, run("2026-10-22", data="d2"))
    assert entry["notes_changed"] == [{"planet": "A b", "from": 2, "to": 3, "checks": {"C": [2, 3]}}] and entry["notes"] == 3


def test_a_check_that_did_not_run_resolves_nothing():
    shards = {0: {"A b": {"leads": [{"kind": "B", "rule": "radius", "ref": "P", "key": "B/B-look", "label_only": False},
                                    {"kind": "D", "rule": "mass", "ref": None, "key": "D/D-disagree", "label_only": False},
                                    {"kind": "D", "rule": "period", "ref": None, "key": "D/D-close", "label_only": True, "group": "g1"}]}}}
    index = [{"n": "A b", "nf": 2, "b": 1, "x": 1, "nn": 1}]
    ledger, _ = update(None, index, shards, run("2026-10-15"))
    shards_no_d = {0: {"A b": {"leads": shards[0]["A b"]["leads"][:1]}}}
    ledger2, entry = update(ledger, [{"n": "A b", "nf": 1, "b": 1}], shards_no_d, {**run("2026-10-16", data="d2"), "skipped": ["D"]})
    assert entry["resolved_findings"] == [] and entry["notes_changed"] == [] and entry["not_checked"] == ["D"]
    assert "A b|D|mass||" in ledger2["leads"]
    _, back = update(ledger2, index, shards, run("2026-10-17", data="d3"))
    assert back["new_findings"] == [] and back["resolved_findings"] == [] and back["notes_changed"] == []
    assert back["checked_again"] == ["D"] and "not_checked" not in back


def test_new_source_data_without_any_planet_change_records_no_update():
    index, shards = build({"A b": ["radius"]})
    ledger, _ = update(None, index, shards, run("2026-10-15"))
    ledger2, entry = update(ledger, index, shards, run("2026-10-16", data="d2"))
    assert entry is None and ledger2["run"]["data"] == "d2"
    index, shards = build({"A b": ["radius"]})
    _, entry = update(ledger2, index, shards, run("2026-10-17", data="d2", code="c2"))
    assert entry is None


def test_cause_says_what_changed():
    from exodiff.ledger import cause
    assert cause(run("d", data="d2"), run("d")) == "new data"
    assert cause(run("d", code="c2"), run("d")) == "rule change"
    assert cause(run("d", data="d2", code="c2"), run("d")) == "new data and a rule change"
    assert cause(run("d"), run("d")) == "same data re-checked"
