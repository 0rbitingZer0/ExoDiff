from __future__ import annotations

import hashlib
import html as htmllib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from .polite import fetch_all

STEM = "exoplanet_eu_sources"
REREAD_RUNS = 7
PAGE_FIELDS = {"mass": "planet_field_publications_mass", "radius": "planet_field_publications_radius",
               "period": "planet_field_publications_period", "orbit": "planet_field_publications_axis",
               "eccentricity": "planet_field_publications_eccentricity", "distance": "star_field_publications_star_distance"}
_PUB_START = '<li class="list-group-item publication" id="publication_'
_REF = re.compile(r'href="#publication_(\d+)"')


def _plain(fragment: str) -> str:
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def _publication(block: str) -> dict:
    year = re.search(r'<time datetime="(\d{4})', block)
    text = block.split("</h5>", 1)[-1]
    lines = [_plain(x) for x in re.split(r"<br\s*/?>", text)]
    authors = re.sub(r"^\d{4}\s*", "", lines[0]) if lines else ""
    journal = [x.strip() for x in lines[1].split(",")] if len(lines) > 2 else []
    arxiv = re.search(r'arxiv\.org/abs/([^"\s]+)', block)
    return {"title": _plain(block.split("</h5>", 1)[0]), "year": int(year.group(1)) if year else None,
            "first_author": authors.split(",")[0].strip(), "journal": journal[0] if journal else None,
            "volume": journal[1] if len(journal) > 1 else None, "page": journal[2] if len(journal) > 2 else None,
            "arxiv": arxiv.group(1) if arxiv else None}


def _publication_blocks(html: str):
    pos = 0
    while (start := html.find(_PUB_START, pos)) >= 0:
        id_end = html.find('">', start + len(_PUB_START))
        close = html.find("</li>", id_end) if id_end >= 0 else -1
        if close < 0:
            return
        pid = html[start + len(_PUB_START):id_end]
        if pid.isdigit():
            yield pid, html[id_end + 2:close]
        pos = close + 5


def parse_eu_page(html: str) -> dict:
    pubs = {pid: _publication(block) for pid, block in _publication_blocks(html)}
    if not pubs and "publication_" not in html:
        raise ValueError("no publication list on page; layout changed or not a planet page")
    out = {}
    for field, anchor in PAGE_FIELDS.items():
        start = html.find(f'id="{anchor}"')
        if start < 0:
            continue
        ids = _REF.findall(html[start:html.find("</ul>", start)])
        found = [pubs[i] for i in dict.fromkeys(ids) if i in pubs]
        if found:
            out[field] = found
    return out


def saved_retrieved_at(project_root: Path) -> str | None:
    files = sorted((Path(project_root).resolve() / "data" / "raw").glob(f"{STEM}_*Z.manifest.json"))
    return json.loads(files[-1].read_text()).get("retrieved_at_utc") if files else None


def _saved(project_root: Path) -> dict:
    files = sorted(p for p in (Path(project_root).resolve() / "data" / "raw").glob(f"{STEM}_*Z.json"))
    return json.loads(files[-1].read_text()) if files else {}


def fetch_sources(links: dict, project_root: Path, updated: dict | None = None, workers: int = 10, session=None, sleep=None) -> dict:
    saved = _saved(project_root)
    pages, read_at = saved.get("pages", {}), saved.get("read_at", {})
    def stale(planet: str) -> bool:
        if planet not in pages or not read_at.get(planet):
            return True
        when = (updated or {}).get(planet) or ""
        return bool(when) and when >= read_at[planet]
    due = [p for p in links if stale(p)]
    rest = sorted((p for p in links if p not in set(due)), key=lambda p: (read_at.get(p, ""), p))
    due += rest[:-(-len(links) // REREAD_RUNS)]
    todo = {p: links[p] for p in due}
    kwargs = {"workers": workers, "session": session}
    if sleep is not None:
        kwargs["sleep"] = sleep
    fetched, failures = fetch_all(todo, parse_eu_page, **kwargs) if todo else ({}, {})
    if todo and not fetched:
        raise RuntimeError(f"none of {len(todo)} exoplanet.eu pages could be read")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    merged = {p: pages[p] for p in links if p in pages} | fetched
    merged_read = {p: read_at.get(p, "") for p in merged} | {p: today for p in fetched}
    result = {"pages": merged, "requested": len(todo), "read": len(fetched), "failures": failures, "unchanged": not fetched}
    if not fetched:
        return result
    raw_dir = Path(project_root).resolve() / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = raw_dir / f"{STEM}_{stamp}.json"
    body = json.dumps({"pages": merged, "read_at": merged_read, "failures": failures}, indent=0, sort_keys=True).encode()
    path.write_bytes(body)
    manifest = {"source_name": "exoplanet.eu planet pages (publication per value)", "licence": "CC BY 4.0",
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "pages_requested": len(todo),
                "pages_read": len(fetched), "pages_kept": len(merged), "failures": len(failures),
                "sha256": hashlib.sha256(body).hexdigest(), "file": path.name}
    path.with_name(path.stem + ".manifest.json").write_text(json.dumps(manifest, indent=2))
    return result | {"manifest": manifest}


def _surname(name: str) -> str:
    name = re.sub(r"\bet al\.?.*$|&.*$|\b\d{4}\b.*$", "", name)
    name = " ".join(t for t in name.split() if not re.fullmatch(r"(?:[A-Za-z]\.)+-?(?:[A-Za-z]\.)*", t))
    ascii_ = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", ascii_.lower())


def _bibcode_parts(bibcode: str) -> tuple[str, str]:
    if not bibcode or len(bibcode) < 18:
        return "", ""
    return bibcode[9:13].strip("."), re.sub(r"\D", "", bibcode[14:18])


def held_by_nasa(pub: dict, papers: list[dict]) -> dict | None:
    vol, page = (pub.get("volume") or "").strip(), re.sub(r"\D", "", pub.get("page") or "")
    for p in papers:
        v, pg = _bibcode_parts(p.get("bibcode") or "")
        if vol and page and v == vol and pg == page:
            return p
    who = _surname(pub.get("first_author") or "")
    for p in papers:
        if who and who == _surname(p.get("label") or "") and pub.get("year") and p.get("year") \
                and abs(pub["year"] - p["year"]) <= 1:
            return p
    return None


def describe(pub: dict) -> str:
    who = (pub.get("first_author") or "").split()
    surname = " ".join(t for t in who if not re.fullmatch(r"(?:[A-Za-z]\.)+-?(?:[A-Za-z]\.)*", t)).title()
    return " ".join(x for x in (surname, str(pub.get("year") or "")) if x).strip() or (pub.get("title") or "")[:60]


def latest_sources(project_root: Path) -> dict:
    files = sorted(p for p in (Path(project_root).resolve() / "data" / "raw").glob(f"{STEM}_*Z.json"))
    return json.loads(files[-1].read_text()).get("pages", {}) if files else {}
