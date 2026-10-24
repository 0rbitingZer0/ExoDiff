from __future__ import annotations


def lead_key(planet: str, lead: dict) -> str:
    return "|".join([planet, lead["kind"], str(lead["rule"]), lead.get("ref") or "", lead.get("column") or "" if lead["kind"] == "A" else ""])


def open_leads(planet: str, leads: list) -> list[tuple[str, dict]]:
    out = {}
    for l in leads:
        if not l["label_only"]:
            out.setdefault(lead_key(planet, l), l)
    return list(out.items())


def notes_by_check(planets: dict) -> dict:
    out = {}
    for name, p in planets.items():
        groups = {}
        for l in p["leads"]:
            if l["label_only"]:
                groups.setdefault(l["kind"], set()).add(l.get("group") or id(l))
        if groups:
            out[name] = {k: len(v) for k, v in sorted(groups.items())}
    return out


def cause(run: dict, previous: dict) -> str:
    data, rules = run.get("data") != previous.get("data"), run.get("code") != previous.get("code")
    return {(True, True): "new data and a rule change", (True, False): "new data",
            (False, True): "rule change", (False, False): "same data re-checked"}[(data, rules)]


def totals(index: list, planets: dict) -> dict:
    by_check = dict.fromkeys("ABCDE", 0)
    for p in planets.values():
        for kind, _ in {(l["kind"], l.get("group") or id(l)) for l in p["leads"] if not l["label_only"]}:
            if kind in by_check:
                by_check[kind] += 1
    return {"planets": len(index), "planets_with_findings": sum(1 for p in index if p.get("nf")),
            "findings": sum(p.get("nf", 0) for p in index), "notes": sum(p.get("nn", 0) for p in index), "by_check": by_check}


def update(previous: dict | None, index: list, shards: dict, run: dict) -> tuple[dict, dict | None]:
    planets = {name: detail for shard in shards.values() for name, detail in shard.items()}
    leads = {k: (n, l) for n, p in planets.items() for k, l in open_leads(n, p["leads"])}
    notes = notes_by_check(planets)
    prev = previous or {}
    prev_leads, prev_planets, prev_notes = prev.get("leads", {}), prev.get("planets", {}), prev.get("notes", {})
    skipped = set(run.get("skipped") or ())
    unsure = skipped | set((prev.get("run") or {}).get("skipped") or ())
    kind = lambda k: k.split("|")[1]
    carried = {k: v for k, v in prev_leads.items() if kind(k) in skipped}
    date = run["date"]
    ledger = {"run": run, "baseline": prev.get("baseline", date),
              "planets": {n: prev_planets.get(n, date) for n in sorted(planets)},
              "leads": dict(sorted({**carried, **{k: {"since": prev_leads[k]["since"] if k in prev_leads else date,
                                                      "key": leads[k][1].get("key")} for k in leads}}.items())),
              "notes": notes}
    week = {"date": date, "data": run["data"], "code": run["code"], **totals(index, planets)}
    if skipped:
        week["not_checked"] = sorted(skipped)
    if back := set((prev.get("run") or {}).get("skipped") or ()) - skipped:
        week["checked_again"] = sorted(back)

    if previous is None:
        return ledger, {**week, "cause": "first run"}
    if ledger["leads"].keys() == prev_leads.keys() and planets.keys() == prev_planets.keys() and notes == prev_notes:
        same = run["data"] == previous["run"]["data"] and run["code"] == previous["run"]["code"]
        ledger["run"] = previous["run"] if same else run
        return ledger, None

    label = lambda l: {"kind": l["kind"], "rule": l["rule"], "ref": l.get("ref"), "key": l.get("key")}
    resolved = [{"planet": k.split("|")[0], "kind": kind(k), "rule": k.split("|")[2], "ref": k.split("|")[3] or None,
                 "key": prev_leads[k].get("key")} for k in sorted(prev_leads.keys() - ledger["leads"].keys())]
    shown = lambda counts: sum(v for c, v in (counts or {}).items() if c not in unsure)
    def by_check(n: str) -> dict:
        old, new = prev_notes.get(n) or {}, notes.get(n) or {}
        return {c: [old.get(c, 0), new.get(c, 0)] for c in sorted(set(old) | set(new)) if c not in unsure and old.get(c, 0) != new.get(c, 0)}
    return ledger, {
        **week, "cause": cause(run, previous["run"]),
        "new_planets": sorted(planets.keys() - prev_planets.keys()),
        "removed_planets": sorted(prev_planets.keys() - planets.keys()),
        "new_findings": [{**label(leads[k][1]), "planet": leads[k][0]} for k in sorted(leads.keys() - prev_leads.keys())],
        "resolved_findings": resolved,
        "notes_changed": [{"planet": n, "from": shown(prev_notes.get(n)), "to": shown(notes.get(n)), "checks": by_check(n)}
                          for n in sorted(notes.keys() | prev_notes.keys()) if shown(prev_notes.get(n)) != shown(notes.get(n))],
    }
