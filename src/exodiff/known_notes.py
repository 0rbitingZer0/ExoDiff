from __future__ import annotations

import csv
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTES_PATH = ROOT / "reference" / "nasa_lit_discrepancies.csv"

_CATEGORY_PATTERNS = {
    "identity": r"planet letter|planet name|entire candidate|stellar alias",
    "radius": r"planet radius|transit depth|^δ$|rp/r",
    "mass": r"planet mass|mp sin|density",
    "orbit": r"orbital period|semi-major axis|a/r|stellar mass",
}
_TEXT_PATTERNS = {
    "identity": r"planet letter|planet name|\balias",
    "radius": r"radius|radii|transit depth|rp\s*/\s*r",
    "mass": r"\bmass\b|density|m\s*sin\s*i|msini",
    "orbit": r"orbital period|semi-major axis|a\s*/\s*r|stellar mass",
}
CHECK_CATEGORIES = {
    "pair_radius": {"identity", "radius"},
    "radius": {"identity", "radius"},
    "density": {"identity", "radius", "mass"},
    "kepler": {"identity", "orbit"},
    "a_over_rstar": {"identity", "orbit"},
}


def category(parameter: str) -> str:
    text = parameter.strip().lower()
    for name, pattern in _CATEGORY_PATTERNS.items():
        if re.search(pattern, text):
            return name
    return "other" if text else "unknown"


def _letters(text: str) -> list[str]:
    return re.findall(r"\b([a-z])\b", text)


def load_notes(path: Path = NOTES_PATH) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as handle:
        lines = [line for line in handle if not line.startswith("#")]
    notes: dict[str, list[dict]] = {}
    for row in csv.DictReader(lines):
        letters = _letters(row["letters"]) or [""]
        for letter in letters:
            planet = f"{row['host']} {letter}".strip()
            notes.setdefault(planet, []).append({
                "parameter": row["parameter"], "category": category(row["parameter"]),
                "notes": row["notes"], "reference": row["reference"],
            })
    return notes


def text_categories(text: str) -> set[str]:
    low = text.lower()
    return {name for name, pattern in _TEXT_PATTERNS.items() if re.search(pattern, low)} or {"other"}


def add_overview_notes(notes: dict, snapshot: dict) -> dict:
    for system in (snapshot.get("systems") or {}).values():
        for n in system["notes"]:
            n = {**n, "note": html.unescape(n["note"]), "reference": html.unescape(n.get("reference") or "")}
            targets = [n["object"]] if n["kind"] == "planet" else system["planets"]
            for planet in targets:
                known = notes.setdefault(planet, [])
                if any(k.get("source") != "overview" and k["notes"] and n["note"].startswith(k["notes"].rstrip(".")) for k in known):
                    continue
                known.append({"parameter": "", "categories": text_categories(n["note"]), "category": None,
                              "notes": n["note"], "reference": n.get("reference") or "", "bibcode": n.get("bibcode"),
                              "date": n.get("date"), "on": n["kind"], "source": "overview"})
    return notes


def documented(planet: str, check: str, notes: dict, bibcode: str | None = None) -> list[dict]:
    wanted = CHECK_CATEGORIES[check]
    out = []
    for n in notes.get(planet, []):
        if n.get("source") != "overview":
            if n["category"] in wanted:
                out.append(n)
            continue
        hit = n["categories"] & wanted
        if "identity" in hit or (hit and bibcode and n.get("bibcode") == bibcode):
            out.append(n)
    return out


def load_all_notes(project_root: Path = ROOT) -> dict[str, list[dict]]:
    from .overview_notes import latest_snapshot
    return add_overview_notes(load_notes(), latest_snapshot(project_root))
