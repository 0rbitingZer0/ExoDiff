from __future__ import annotations

import pandas as pd

from .references import parse_reference
from .screening import _text

CATALOGUE_REFERENCES = {
    "TICv8": "TESS Input Catalog, version 8",
    "Q1-Q17 DR25 KOI Table": "Kepler Objects of Interest table, DR25 (mission catalogue)",
    "Hipparcos and Tycho Catalogs": "Hipparcos and Tycho catalogues",
}
REFERENCE_COLUMN_BY_PREFIX = {"pl_": "pl_refname", "st_": "st_refname", "sy_": "sy_refname", "disc_": "disc_refname"}
UNIT_COPIES = {"pl_radj": "pl_rade", "pl_bmassj": "pl_bmasse", "pl_massj": "pl_masse", "pl_msinij": "pl_msinie"}


def reference_column(column: str) -> str | None:
    base = column
    for suffix in ("err1", "err2", "lim", "str", "reflink"):
        if base.endswith(suffix) and base != suffix:
            base = base[: -len(suffix)]
            break
    for prefix, ref in REFERENCE_COLUMN_BY_PREFIX.items():
        if base.startswith(prefix):
            return ref
    return None


def reference_kind(label: str) -> str:
    return "catalogue" if label in CATALOGUE_REFERENCES else "paper"


def value_source(row: pd.Series, column: str) -> dict:
    if column in UNIT_COPIES:
        return {"kind": "converted", "reference": UNIT_COPIES[column]}
    value = row.get(column)
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return {"kind": "none", "reference": ""}
    ref_col = reference_column(column)
    if ref_col is None:
        return {"kind": "paper", "reference": ""}
    label = parse_reference(_text(row.get(ref_col)))["label"]
    return {"kind": reference_kind(label) if label else "none", "reference": label}


def is_paper_sourced(row: pd.Series, column: str) -> bool:
    return value_source(row, column)["kind"] == "paper"


def column_tags(frame: pd.DataFrame) -> dict:
    labels = {ref: frame[ref].map(lambda v: parse_reference(_text(v))["label"]) if ref in frame else None
              for ref in REFERENCE_COLUMN_BY_PREFIX.values()}
    tags = {}
    for column in frame.columns:
        filled = frame[column].notna()
        count = int(filled.sum())
        if column in UNIT_COPIES:
            tags[column] = {"filled": count, "converted": count}
            continue
        ref = reference_column(column)
        if ref is None or labels.get(ref) is None:
            tags[column] = {"filled": count}
            continue
        catalogue = int((filled & labels[ref].isin(CATALOGUE_REFERENCES)).sum())
        tags[column] = {"filled": count, "reference_column": ref, "paper": count - catalogue, "catalogue": catalogue}
    return tags

