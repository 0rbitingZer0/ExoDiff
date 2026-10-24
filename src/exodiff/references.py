from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import unquote

import pandas as pd

_REFSTR = re.compile(r"refstr=([^\s>]+)", re.IGNORECASE)
_HREF = re.compile(r"href=([^\s>]+)", re.IGNORECASE)
_LABEL = re.compile(r">([^<]*)</a>", re.IGNORECASE)
_ADS_ABS = re.compile(r"ui\.adsabs\.harvard\.edu/abs/([^/]+)/?", re.IGNORECASE)


def parse_reference(value: Any) -> dict:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        text = ""
    else:
        text = str(value).strip()
    refstr = _REFSTR.search(text)
    href = _HREF.search(text)
    label = _LABEL.search(text)
    url = html.unescape(href.group(1)) if href else ""
    if not url.lower().startswith(("https://", "http://")):
        url = ""
    ads = _ADS_ABS.search(url)
    plain = label.group(1) if label else (text if "<" not in text else "")
    return {
        "label": " ".join(html.unescape(plain).split()),
        "refstr": refstr.group(1) if refstr else "",
        "url": url,
        "bibcode": unquote(ads.group(1)) if ads else "",
    }


def reference_key(refname: Any) -> str:
    ref = parse_reference(refname)
    text = "" if refname is None or (not isinstance(refname, str) and pd.isna(refname)) else str(refname).strip()
    return ref["bibcode"] or ref["refstr"] or ref["label"] or text
