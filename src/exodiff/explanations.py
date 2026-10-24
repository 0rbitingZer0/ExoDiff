from __future__ import annotations

import math
import re
from collections import defaultdict

from . import wording

CLOSE = math.log(1.02)

_PATTERN_TITLES = [("impossible", "Invalid as stored"),
                   ("letters", "Possible planet-letter mismatch"),
                   ("system", "Several planets, same gap"),
                   ("units", "Close to a unit ratio"),
                   ("tenfold", "Close to a power of ten"),
                   ("double", "Close to double or half"),
                   ("timing", "Tiny orbit-time differences"),
                   ("unit-copies", "Earth and Jupiter copies disagree"),
                   ("catalog", "NASA's catalog page shows another number"),
                   ("paper", "Many findings from one paper"),
                   ("other", "No simple pattern")]
EXPLANATIONS = [(k, t, wording.means(f"pattern/{k}")) for k, t in _PATTERN_TITLES]
TITLES = {k: (t, w) for k, t, w in EXPLANATIONS}

UNIT_FACTORS = {"Jupiter vs Earth radius": 11.209, "Jupiter vs Earth mass": 317.83, "Sun vs Earth radius": 109.076,
                "Sun vs Jupiter mass": 1047.57, "Sun vs Earth mass": 332946.0, "au vs Sun radius": 215.032,
                "years vs days": 365.25}


def _near(ratio: float, factor: float) -> bool:
    return abs(abs(math.log(ratio)) - math.log(factor)) < CLOSE


def shape(ratio: float | None) -> str | None:
    if not ratio or ratio <= 0 or not math.isfinite(ratio):
        return None
    if any(_near(ratio, f) for f in UNIT_FACTORS.values()):
        return "units"
    if any(_near(ratio, 10 ** k) for k in (1, 2, 3)):
        return "tenfold"
    if _near(ratio, 2):
        return "double"
    return None


_COPY = re.compile(r"= ([-+0-9.eE]+), \w+ = [-+0-9.eE]+ \(x[0-9.]+ = ([-+0-9.eE]+)\)")
_LEADING_NUMBER = re.compile(r"^\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)")


def pair_of(lead: dict) -> tuple[float | None, float | None]:
    if lead["kind"] == "B":
        return lead.get("listed"), lead.get("implied")
    if lead["kind"] == "D":
        return lead.get("nasa"), lead.get("eu")
    if lead["kind"] == "E":
        return lead.get("nasa"), lead.get("gaia")
    if lead["kind"] == "A" and lead["rule"] in ("A5", "A5m"):
        m = _COPY.search(lead.get("detail") or "")
        return (float(m.group(1)), float(m.group(2))) if m else (None, None)
    if lead["kind"] == "C":
        text = lead.get("display") or ""
        m = _LEADING_NUMBER.match(text)
        if not m:
            return lead.get("archive"), None
        factor = {"mass": 317.83, "radius": 11.209}.get(lead["rule"], 1.0) if "Jupiter" in text else 1.0
        return lead.get("archive"), float(m.group(1)) * factor
    return None, None


def explain(planets: dict) -> dict:
    by_host = defaultdict(dict)
    for name, p in planets.items():
        default = next((x for x in p["papers"] if x["default"]), None)
        if default:
            by_host[p.get("host")][name] = {f: v["v"] for f, v in default["values"].items()}

    groups = defaultdict(list)
    for name, p in planets.items():
        for l in p["leads"]:
            if l["kind"] == "B" and not l["label_only"] and l.get("pct") is not None:
                groups[(p.get("host"), l.get("ref"), l["rule"])].append((name, l))
    system = set()
    for members in groups.values():
        if len({n for n, _ in members}) < 2:
            continue
        pcts = sorted(l["pct"] for _, l in members)
        if pcts[-1] - pcts[0] <= 1.0:
            system.update(id(l) for _, l in members)

    paper_counts = defaultdict(int)
    for p in planets.values():
        for l in p["leads"]:
            if l["kind"] == "B" and not l["label_only"]:
                paper_counts[l.get("ref")] += 1

    items = defaultdict(list)
    for name, p in planets.items():
        for l in p["leads"]:
            if l["label_only"]:
                continue
            if l["kind"] == "C" and l.get("archive") is None:
                default = next((x for x in p["papers"] if x["default"]), {"values": {}})
                l["archive"] = (default["values"].get(l["rule"]) or {}).get("v")
            a, b = pair_of(l)
            l["pair"] = [a, b] if a is not None and b is not None else None
            ratio = a / b if a and b else None
            why = "letters" if l.get("bucket") == "D-letters" else None
            if l["kind"] == "A":
                why = "unit-copies" if l["rule"] in ("A5", "A5m") else "impossible"
            elif l["kind"] == "C":
                why = "catalog"
            elif l["kind"] == "D" and b is not None:
                siblings = by_host.get(p.get("host"), {})
                if any(other != name and (v := vals.get(l["rule"])) and abs(math.log(abs(b) / abs(v))) < math.log(1.01)
                       for other, vals in siblings.items() if b):
                    why = "letters"
            if why is None and id(l) in system:
                why = "system"
            if why is None:
                why = shape(ratio)
            if why is None and l["kind"] == "D" and l["rule"] == "period" and ratio and abs(ratio - 1) < 0.001:
                why = "timing"
            if why is None and l["kind"] == "B" and paper_counts[l.get("ref")] >= 5:
                why = "paper"
            l["why"] = why or "other"
            items[l["why"]].append({"planet": name, "kind": l["kind"], "rule": l["rule"], "ref": l.get("ref"),
                                    "a": a, "b": b, "ratio": ratio, "bars": l.get("bars"),
                                    "display": l.get("display"), "title": l.get("title"), "detail": l.get("detail")})
    return items


def summary(items: dict) -> list[dict]:
    out = []
    for key, title, why in EXPLANATIONS:
        rows = items.get(key, [])
        out.append({"id": key, "title": title, "why": why, "leads": len(rows),
                    "planets": len({r["planet"] for r in rows}), "items": rows})
    return out


def confirm_letters(planets: dict, eu_names: dict, eu_alternates: dict, nasa_aliases: dict) -> int:
    norm = lambda s: " ".join(str(s).split()).casefold()
    owner = defaultdict(set)
    for planet, names in nasa_aliases.items():
        for n in [planet, *names]:
            owner[norm(n)].add(planet)
    confirmed = 0
    for name, p in planets.items():
        eu_name = eu_names.get(name)
        for l in p["leads"]:
            if l.get("why") != "letters" or not eu_name:
                continue
            for alt in [eu_name, *eu_alternates.get(eu_name, [])]:
                others = sorted(o for o in owner.get(norm(alt), ()) if o != name and planets.get(o, {}).get("host") == p.get("host"))
                if others:
                    l["shared_alias"], l["alias_of"] = alt, others[0]
                    confirmed += 1
                    break
    return confirmed
