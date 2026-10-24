from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

USER_AGENT = "ExoDiff (data experiment; https://github.com/0rbitingZer0)"
GIVE_UP_AFTER = 5
MAX_PAGE_BYTES = 3_000_000


def _capped_text(r, cap: int) -> str:
    if not hasattr(r, "iter_content"):
        if len(r.text) > cap:
            raise ValueError(f"page over {cap:,} bytes")
        return r.text
    body, size = [], 0
    for chunk in r.iter_content(65536):
        size += len(chunk)
        if size > cap:
            raise ValueError(f"page over {cap:,} bytes")
        body.append(chunk)
    return b"".join(body).decode(r.encoding or "utf-8", errors="replace")


def fetch_all(items: dict, parse, workers: int = 10, delay_seconds: float = 1.0, session=None,
              sleep=time.sleep, progress: bool = False, give_up_after: int = GIVE_UP_AFTER) -> tuple[dict, dict]:
    getter = session.get if session else requests.get
    keys = sorted(items)
    lanes = [keys[i::max(1, workers)] for i in range(max(1, workers))]
    done, streak, lock, stop = [0], [0], threading.Lock(), threading.Event()

    def lane(batch):
        out = []
        for i, key in enumerate(batch):
            if stop.is_set():
                out.append((key, None, f"not requested: {give_up_after} failures in a row"))
                continue
            if i:
                sleep(delay_seconds)
            try:
                r = getter(items[key], headers={"User-Agent": USER_AGENT}, timeout=(15, 60), stream=True)
                r.raise_for_status()
                out.append((key, parse(_capped_text(r, MAX_PAGE_BYTES)), None))
                with lock:
                    streak[0] = 0
            except Exception as exc:
                out.append((key, None, str(exc)[:200]))
                with lock:
                    streak[0] += 1
                    if streak[0] >= give_up_after:
                        stop.set()
            done[0] += 1
            if progress and done[0] % 250 == 0:
                print(f"  {done[0]:,}/{len(keys):,} pages", file=sys.stderr, flush=True)
        return out

    ok, failed = {}, {}
    with ThreadPoolExecutor(max_workers=len(lanes)) as pool:
        for results in pool.map(lane, lanes):
            for key, parsed, error in results:
                if parsed is not None:
                    ok[key] = parsed
                else:
                    failed[key] = error
    return ok, failed
