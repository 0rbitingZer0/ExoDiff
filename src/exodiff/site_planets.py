from __future__ import annotations

import ast
import hashlib
from urllib.parse import quote

import pandas as pd

from .check_b import OPEN as B_OPEN
from .explanations import explain, summary
from .habitable import in_habitable_zone, insolation
from .wording import lead_key
from .references import parse_reference
from .screening import _num, _text

FIELDS = {
    "radius": ("pl_rade", "Earths", "size (radius)"),
    "mass": ("pl_bmasse", "Earths", "mass"),
    "period": ("pl_orbper", "days", "time for one orbit"),
    "orbit": ("pl_orbsmax", "au", "orbit size"),
    "eccentricity": ("pl_orbeccen", "", "how stretched the orbit is"),
    "distance": ("sy_dist", "parsecs", "distance from us"),
}
EXTRA = {"ratio": "pl_ratror", "star_radius": "st_rad", "star_mass": "st_mass", "a_rstar": "pl_ratdor", "density": "pl_dens"}
SHARDS = 32
ARCHIVE_OVERVIEW = "https://exoplanetarchive.ipac.caltech.edu/overview/"


def shard_of(name: str) -> int:
    return int(hashlib.sha256(name.encode("utf-8")).hexdigest(), 16) % SHARDS


def _clean(v):
    n = _num(v)
    return None if n is None else float(f"{n:.10g}")


def _labels(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.startswith("["):
        return ast.literal_eval(value)
    return []


def _hz(row) -> dict | None:
    if _num(row.get("default_flag")) != 1:
        return None
    flux, how = insolation(_num(row.get("pl_insol")), _num(row.get("st_lum")), _num(row.get("pl_orbsmax")))
    verdict = in_habitable_zone(flux, _num(row.get("st_teff")))
    return None if verdict is None else {"in": verdict, "insolation": how}


D_OPEN = ("D-disagree", "D-newer-paper")
D_NOTES = ("D-theoretical", "D-same-paper", "D-eu-paper", "D-other-row", "D-close", "D-limit")
NOTE_GAP = 0.10
NOTE_GAP_ECC = 0.10


def _far_apart(field: str, eu, nasa) -> bool:
    if eu is None or nasa is None:
        return False
    if field == "eccentricity":
        return abs(eu - nasa) > NOTE_GAP_ECC
    return nasa != 0 and abs(eu / nasa - 1) > NOTE_GAP


def build_planets(archive: pd.DataFrame, check_a: pd.DataFrame, check_b: pd.DataFrame,
                  check_c: pd.DataFrame, join: dict | None,
                  row_checked: set | None = None, check_d: pd.DataFrame | None = None,
                  check_e: pd.DataFrame | None = None, eu_links: dict | None = None,
                  catalog_self: dict | None = None) -> tuple[list, dict]:
    row_checked = row_checked if row_checked is not None else set()
    matched = (join or {}).get("matched", {})
    a_by = {k: g for k, g in check_a.groupby("pl_name")} if len(check_a) else {}
    b_by = {k: g for k, g in check_b.groupby("pl_name")} if len(check_b) else {}
    c_by = {k: g for k, g in check_c.groupby("pl_name")} if len(check_c) else {}
    d_by = {k: g for k, g in check_d.groupby("pl_name")} if check_d is not None and len(check_d) else {}
    e_by = {r["hostname"]: r for r in check_e.to_dict("records")} if check_e is not None and len(check_e) else {}
    index, shards = [], {i: {} for i in range(SHARDS)}

    for name, rows in archive.groupby("pl_name", sort=True):
        keys = [k for k in ("default_flag", "pl_pubdate", "_ref", "pl_rade", "pl_orbper") if k in rows or k == "_ref"]
        rows = rows.assign(_ref=rows["pl_refname"].astype(str)).sort_values(
            keys, ascending=[k in ("_ref", "pl_rade", "pl_orbper") for k in keys], kind="mergesort", na_position="last")
        first = rows.iloc[0]
        page = matched.get(name)
        papers = []
        for _, r in rows.iterrows():
            ref = parse_reference(_text(r.get("pl_refname")))
            entry = {"ref": ref["label"], "url": ref["url"] or None, "default": int(_num(r.get("default_flag")) or 0) == 1,
                     "date": _text(r.get("pl_pubdate")) or None, "values": {}}
            for field, (col, _, _) in FIELDS.items():
                v = _clean(r.get(col))
                if v is None:
                    continue
                entry["values"][field] = {"v": v, "e1": _clean(r.get(col + "err1")), "e2": _clean(r.get(col + "err2")),
                                          "lim": int(_num(r.get(col + "lim")) or 0)}
                if field == "mass":
                    entry["values"][field]["kind"] = _text(r.get("pl_bmassprov")) or None
                    if _clean(r.get("pl_bmassj")) is not None:
                        entry["values"][field]["j"] = {"v": _clean(r.get("pl_bmassj")), "e1": _clean(r.get("pl_bmassjerr1")),
                                                       "e2": _clean(r.get("pl_bmassjerr2"))}
            for field, col in EXTRA.items():
                v = _clean(r.get(col))
                if v is not None:
                    entry["values"][field] = {"v": v, "e1": _clean(r.get(col + "err1")), "e2": _clean(r.get(col + "err2")),
                                              "lim": int(_num(r.get(col + "lim")) or 0)}
            twin = next((p for p in papers if p["ref"] == entry["ref"] and p["values"] == entry["values"]), None)
            if twin is not None:
                twin["copies"] = twin.get("copies", 1) + 1
                twin["default"] = twin["default"] or entry["default"]
                continue
            papers.append(entry)

        public = {}
        if name in c_by:
            for c in c_by[name].to_dict("records"):
                public[c["field"]] = {"display": c.get("public_display") if isinstance(c.get("public_display"), str) else None,
                                      "bucket": c["bucket"], "matched": c.get("matched_reference") if isinstance(c.get("matched_reference"), str) else None,
                                      "labels": _labels(c.get("labels"))}

        eu, eu_name = {}, None
        for d in (d_by[name].to_dict("records") if name in d_by else []):
            eu_name = d.get("eu_name") if isinstance(d.get("eu_name"), str) else eu_name
            if _clean(d.get("eu_value")) is not None:
                eu[d["field"]] = {"v": _clean(d["eu_value"]), "nasa": _clean(d.get("nasa_default")), "bucket": d["bucket"],
                                  "em": _clean(d.get("eu_err_minus")), "ep": _clean(d.get("eu_err_plus")),
                                  "updated": d.get("eu_updated") if isinstance(d.get("eu_updated"), str) else None,
                                  "matched": d.get("matched_reference") if isinstance(d.get("matched_reference"), str) else None,
                                  "source": d.get("eu_reference") if isinstance(d.get("eu_reference"), str) else None,
                                  "bars": _clean(d.get("bars")), "row": _clean(d.get("nasa_row_value"))}

        leads = []
        for a in (a_by[name].to_dict("records") if name in a_by else []):
            leads.append({"kind": "A", "rule": a["rule"], "title": a["title"], "ref": a.get("reference"), "detail": a.get("detail"),
                          "column": a.get("column") if isinstance(a.get("column"), str) else None,
                          "fine_when": a["fine_when"], "label_only": bool(a["label_only"])})
        for b in (b_by[name].to_dict("records") if name in b_by else []):
            leads.append({"kind": "B", "rule": b["check"], "ref": b.get("reference"), "listed": _clean(b["listed_value"]),
                          "implied": _clean(b["implied_value"]), "pct": _clean(b["mismatch_pct"]),
                          "bars": _clean(b["mismatch_in_error_bars"]), "bucket": b["bucket"], "bucket_title": b["bucket_title"],
                          "fine_when": b["bucket_reason"], "transit_fit": bool(b.get("transit_fit")) or None,
                          "transit_numeric_only": bool(b.get("transit_numeric_only")) or None,
                          "label_only": b["bucket"] not in B_OPEN})
        for field, p in public.items():
            if p["bucket"] in ("C-none", "C-other", "C-survey", "C-estimate"):
                leads.append({"kind": "C", "rule": field, "bucket": p["bucket"], "display": p["display"], "matched": p["matched"],
                              "label_only": p["bucket"] in ("C-other", "C-survey", "C-estimate")})
            for label in p["labels"]:
                leads.append({"kind": "C", "rule": "label", "field": field, "title": label, "label_only": True})

        letters = [f for f, e in eu.items() if e["bucket"] == "D-letters"]
        if letters:
            leads.append({"kind": "D", "rule": "letters", "bucket": "D-letters", "fields": letters, "why": "letters", "label_only": False})
        for field, e in eu.items():
            if e["bucket"] in D_OPEN or e["bucket"] in D_NOTES:
                leads.append({"kind": "D", "rule": field, "bucket": e["bucket"], "eu": e["v"], "nasa": e["nasa"],
                              "source": e["source"], "matched": e["matched"], "bars": e["bars"], "row": e["row"],
                              "label_only": e["bucket"] not in D_OPEN})
            elif e["bucket"] == "D-no-errors" and _far_apart(field, e["v"], e["nasa"]):
                leads.append({"kind": "D", "rule": field, "bucket": e["bucket"], "eu": e["v"], "nasa": e["nasa"], "label_only": True})

        e = e_by.get(_text(first.get("hostname")))
        gaia = None
        if e is not None and name not in str(e["planets"]).split("; "):
            e = None
        if e is not None and e["bucket"] != "E-no-gaia":
            gaia = {"v": _clean(e["gaia_dist"]), "lo": _clean(e["gaia_lo"]), "hi": _clean(e["gaia_hi"]),
                    "nasa": _clean(e["nasa_dist"]), "ref": e["dist_ref"], "bucket": e["bucket"]}
            if e["bucket"] in ("E-differs", "E-quality"):
                siblings = [x for x in str(e["planets"]).split("; ") if x != name]
                leads.append({"kind": "E", "rule": "distance", "bucket": e["bucket"], "ref": e["dist_ref"],
                              "nasa": gaia["nasa"], "gaia": gaia["v"], "star_from_catalogue": bool(e["star_radius_from_catalogue"]),
                              "quality": e.get("quality") if isinstance(e.get("quality"), str) else None,
                              "same_star": siblings, "label_only": e["bucket"] == "E-quality"})

        for c in (catalog_self or {}).get(name, []):
            leads.append({"kind": "F", "rule": c["quantity"], "sentence": c["sentence"], "box": c["box"], "cause": c.get("cause"),
                          "paper": c.get("paper"), "label_only": True})

        for l in leads:
            l["key"] = lead_key(l)
        open_leads = [l for l in leads if not l["label_only"]]
        never = any(l["kind"] == "A" and l["rule"] in ("A1", "A2", "A3") for l in open_leads)
        bars = max((l["bars"] or 0 for l in open_leads if l["kind"] == "B"), default=0)
        estimated_mass = any("estimated from the planet's size" in l.get("title", "") for l in leads)
        index.append({
            "n": name, "h": _text(first.get("hostname")), "s": shard_of(name), "p": len({p["ref"] for p in papers}),
            "a": sum(1 for l in open_leads if l["kind"] == "A"), "b": sum(1 for l in open_leads if l["kind"] == "B"),
            "c": sum(1 for l in open_leads if l["kind"] == "C"), "x": sum(1 for l in open_leads if l["kind"] == "D"),
            "e": sum(1 for l in open_leads if l["kind"] == "E"), "l": len(leads) - len(open_leads),
            "em": estimated_mass, "d": _text(first.get("discoverymethod")) or None,
            "sv": 1e9 if never else round(float(bars), 3), "rc": name in row_checked, "pc": bool(page),
            "y": int(_num(first.get("disc_year"))) if _num(first.get("disc_year")) else None,
            "refs": sorted({p["ref"] for p in papers if p["ref"]}),
            **{k: v for k, v in (("fk", sorted({l["key"] for l in open_leads})),
                                 ("nk", sorted({l["key"] for l in leads if l["label_only"]}))) if v},
        })
        shards[shard_of(name)][name] = {
            "name": name, "host": _text(first.get("hostname")),
            "links": {"archive": ARCHIVE_OVERVIEW + quote(name), "public": page["link"] if page else None,
                      "eu": (eu_links or {}).get(" ".join(eu_name.split())) if eu_name else None},
            "discovery": {"method": _text(first.get("discoverymethod")) or None, "year": index[-1]["y"],
                          "facility": _text(first.get("disc_facility")) or None,
                          "ref": parse_reference(_text(first.get("disc_refname")))["label"] or None,
                          "url": parse_reference(_text(first.get("disc_refname")))["url"] or None},
            "type": _text((page or {}).get("acf", {}).get("planet_type")) or None,
            "hz": _hz(first),
            "papers": papers, "public": public, "eu": eu, "gaia": gaia, "leads": leads,
        }
    return index, shards


def _group(lead: dict) -> str:
    if lead["label_only"]:
        return f'{lead["kind"]}|{lead["rule"]}|{lead.get("bucket") or ""}|{lead.get("title") or ""}'
    nums = "/".join(repr(float(f"{x:.4g}")) for x in (lead.get("pair") or []))
    return f'{lead["kind"]}|{lead["rule"]}|{lead.get("ref") or ""}|{nums}'


def add_explanations(index: list, shards: dict) -> list:
    planets = {name: detail for shard in shards.values() for name, detail in shard.items()}
    result = summary(explain(planets))
    for entry in index:
        leads = planets[entry["n"]]["leads"]
        for l in leads:
            l["group"] = _group(l)
        nf = len({l["group"] for l in leads if not l["label_only"]})
        nn = len({l["group"] for l in leads if l["label_only"]})
        entry.update({k: v for k, v in (("nf", nf), ("nn", nn)) if v})
    return result

