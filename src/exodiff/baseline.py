from __future__ import annotations

import numpy as np
import pandas as pd

from .screening import _row_exclusion_reasons, screen_radius_solutions

SEPARATION_THRESHOLDS = (0.0, 1.0, 2.0, 5.0)


def separation_counts(pairs: pd.DataFrame, thresholds=SEPARATION_THRESHOLDS) -> dict:
    out = {}
    if pairs.empty:
        return {str(t): {"pairs": 0, "planets": 0} for t in thresholds}
    apart = pairs[~pairs["intervals_overlap"].astype(bool)]
    for t in thresholds:
        hit = apart[apart["gap_divided_by_combined_edge_error"].fillna(0) >= t] if t > 0 else apart
        out[str(t)] = {"pairs": int(len(hit)), "planets": int(hit["pl_name"].nunique())}
    return out


def _simulate(frame: pd.DataFrame, truth: pd.Series, rng: np.random.Generator, scale: float) -> pd.DataFrame:
    sim = frame.copy()
    up = sim["pl_radeerr1"].abs() * scale
    down = sim["pl_radeerr2"].abs() * scale
    z = rng.standard_normal(len(sim))
    value = truth + np.where(z > 0, z * up, z * down)
    sim["pl_rade"] = value.where(value > 0, 1e-3).where(truth.notna(), sim["pl_rade"])
    return sim


def chance_baseline(frame: pd.DataFrame, runs: int = 10, seed: int = 20261014,
                    error_scales=(1.0, 1.5)) -> dict:
    eligible = pd.Series([not _row_exclusion_reasons(r) for _, r in frame.iterrows()], index=frame.index)
    truth = frame["pl_rade"].where(eligible).groupby(frame["pl_name"]).transform("median")
    rng = np.random.default_rng(seed)
    result = {
        "model": "same radius per planet (median of eligible values); independent 1-sigma errors; "
                 "asymmetric bars as two half-normals; simulated data run through screen_radius_solutions",
        "runs": runs,
        "seed": seed,
        "by_error_scale": {},
    }
    for scale in error_scales:
        samples = [separation_counts(screen_radius_solutions(_simulate(frame, truth, rng, scale))[0])
                   for _ in range(runs)]
        summary = {}
        for t in samples[0]:
            pairs = [s[t]["pairs"] for s in samples]
            planets = [s[t]["planets"] for s in samples]
            summary[t] = {
                "pairs_mean": float(np.mean(pairs)), "pairs_min": int(min(pairs)), "pairs_max": int(max(pairs)),
                "planets_mean": float(np.mean(planets)),
            }
        result["by_error_scale"][str(scale)] = summary
    return result
