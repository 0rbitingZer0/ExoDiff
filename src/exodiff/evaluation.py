from __future__ import annotations

import numpy as np
import pandas as pd

from .baseline import separation_counts
from .check_b import CLOSE_BARS
from .consistency import _decimals, row_self_consistency
from .screening import screen_radius_solutions

SEED = 2026
ROW_SAMPLE = 400
PLANET_SAMPLE = 300
JUPITER_TO_EARTH_RADII = 7.1492e7 / 6.3781e6


def _round_like(value: float, like: float) -> float:
    return round(value, _decimals(like))


def _keys(frame: pd.DataFrame) -> list:
    return list(zip(frame["pl_name"], frame["pl_refname"], frame["pl_rade"]))


def _row_mutations(rng: np.random.Generator) -> dict:
    def scale_radius(f):
        def mutate(sim, i):
            sign = 1 if rng.random() < 0.5 else -1
            sim.at[i, "pl_rade"] = _round_like(sim.at[i, "pl_rade"] * (1 + sign * f), sim.at[i, "pl_rade"])
        return mutate

    def jupiter_units(sim, i):
        sim.at[i, "pl_rade"] = float(f"{sim.at[i, 'pl_rade'] / JUPITER_TO_EARTH_RADII:.4g}")

    def scale_ratio(sim, i):
        sim.at[i, "pl_ratror"] = _round_like(sim.at[i, "pl_ratror"] * 1.1, sim.at[i, "pl_ratror"])

    def consistent_star_change(sim, i):
        sim.at[i, "st_rad"] = _round_like(sim.at[i, "st_rad"] * 1.1, sim.at[i, "st_rad"])
        sim.at[i, "pl_rade"] = _round_like(sim.at[i, "pl_rade"] * 1.1, sim.at[i, "pl_rade"])

    mutations = {f"planet radius off by {int(f * 100)}%": scale_radius(f) for f in (0.02, 0.05, 0.10, 0.25)}
    mutations["planet radius in Jupiter units"] = jupiter_units
    mutations["size ratio off by 10%"] = scale_ratio
    mutations["control: star and planet rescaled together"] = consistent_star_change
    return mutations


def evaluate_row_check(frame: pd.DataFrame) -> dict:
    base, _ = row_self_consistency(frame)
    clean = set(_keys(base[~base["is_lead"]]))
    candidates = [i for i, k in zip(frame.index, _keys(frame)) if k in clean]
    rng = np.random.default_rng(SEED)
    pick = rng.choice(candidates, min(ROW_SAMPLE, len(candidates)), replace=False)
    results = {}
    for name, mutate in _row_mutations(rng).items():
        sim = frame.copy()
        for i in pick:
            mutate(sim, i)
        planted = set(_keys(sim.loc[pick]))
        flagged, _ = row_self_consistency(sim)
        leads = flagged[flagged["is_lead"]]
        caught = sum(k in planted for k in _keys(leads))
        found = sum(k in planted for k in _keys(leads[leads["mismatch_in_error_bars"] >= CLOSE_BARS]))
        results[name] = {"planted": int(len(pick)), "caught": int(caught), "rate": round(caught / len(pick), 3),
                         "as_finding": int(found), "finding_rate": round(found / len(pick), 3)}
    return results


def evaluate_pair_screen(frame: pd.DataFrame) -> dict:
    pairs, _ = screen_radius_solutions(frame)
    by_planet = pairs.groupby("pl_name")["intervals_overlap"].all()
    quiet = sorted(by_planet[by_planet].index)
    rng = np.random.default_rng(SEED)
    planets = list(rng.choice(quiet, min(PLANET_SAMPLE, len(quiet)), replace=False))
    measured = pd.concat([pairs[["pl_name", "reference_a"]].rename(columns={"reference_a": "ref"}),
                          pairs[["pl_name", "reference_b"]].rename(columns={"reference_b": "ref"})]).drop_duplicates()
    targets = []
    for planet in planets:
        refs = sorted(measured.loc[measured["pl_name"] == planet, "ref"])
        ref = refs[int(rng.integers(len(refs)))]
        rows = frame.index[(frame["pl_name"] == planet) & (frame["pl_refname"] == ref)]
        targets.append(rows[0])
    results = {}
    for factor in (1.1, 1.2, 1.5):
        sim = frame.copy()
        for i in targets:
            sim.at[i, "pl_rade"] = _round_like(sim.at[i, "pl_rade"] * factor, sim.at[i, "pl_rade"])
        sp, _ = screen_radius_solutions(sim)
        sp = sp[sp["pl_name"].isin(planets)]
        counts = separation_counts(sp)
        results[f"one paper's radius {int(round((factor - 1) * 100))}% larger"] = {
            "planets": len(planets),
            "now_disagree": counts["0.0"]["planets"],
            "at_least_2_error_bars": counts["2.0"]["planets"],
            "at_least_5_error_bars": counts["5.0"]["planets"],
        }
    return results


def evaluate(frame: pd.DataFrame) -> dict:
    return {
        "seed": SEED,
        "method": "plant known errors into real rows (values rounded to published digits) and count how many each check flags "
                  "(rate: beyond the row's error bars at all; finding_rate: at least 2 error bars, the finding threshold, rule D5)",
        "row_check": evaluate_row_check(frame),
        "pair_screen": evaluate_pair_screen(frame),
        "v1_seed": V1_SEED,
        "identities": evaluate_identities(frame),
        "unit_copies": evaluate_unit_copies(frame),
    }


V1_SEED = 20261015


def _identity_keys(result: pd.DataFrame) -> set:
    return set(zip(result["pl_name"], result["pl_refname"])) if len(result) else set()


def evaluate_identities(frame: pd.DataFrame, sample: int = 300) -> dict:
    from .identities import IDENTITIES, check_identity
    rng = np.random.default_rng(V1_SEED)
    out = {}
    for identity in IDENTITIES:
        base, _ = check_identity(frame, identity)
        if base.empty:
            continue
        clean = base[~base["is_lead"]]
        keys = set(zip(clean["pl_name"], clean["pl_refname"]))
        idx = [i for i, k in zip(frame.index, zip(frame["pl_name"], frame["pl_refname"])) if k in keys]
        pick = rng.choice(idx, min(sample, len(idx)), replace=False)
        results = {}
        for label, factor in (("listed value off by 5%", 0.05), ("off by 10%", 0.10), ("off by 25%", 0.25)):
            sim = frame.copy()
            for i in pick:
                sign = 1 if rng.random() < 0.5 else -1
                sim.at[i, identity.listed] = _round_like(sim.at[i, identity.listed] * (1 + sign * factor), sim.at[i, identity.listed])
            flagged, _ = check_identity(sim, identity)
            planted = set(zip(sim.loc[pick, "pl_name"], sim.loc[pick, "pl_refname"]))
            leads = flagged[flagged["is_lead"]]
            caught = len(planted & _identity_keys(leads))
            found = len(planted & _identity_keys(leads[leads["mismatch_in_error_bars"] >= CLOSE_BARS]))
            results[label] = {"planted": len(pick), "caught": caught, "rate": round(caught / len(pick), 3),
                              "as_finding": found, "finding_rate": round(found / len(pick), 3)}
        out[identity.key] = results
    return out


def evaluate_unit_copies(frame: pd.DataFrame, sample: int = 300) -> dict:
    from .check_a import check_a
    rng = np.random.default_rng(V1_SEED)
    out = {}
    for earth, jup in (("pl_rade", "pl_radj"), ("pl_bmasse", "pl_bmassj")):
        ok = frame[frame[earth].notna() & frame[jup].notna() & (frame[earth] > 0) & (frame[jup] > 0)].index
        base, _ = check_a(frame.loc[ok])
        already = set(base.loc[base["column"] == earth, "pl_name"]) if len(base) else set()
        clean = [i for i in ok if frame.at[i, "pl_name"] not in already]
        pick = rng.choice(clean, min(sample, len(clean)), replace=False)
        results = {}
        for label, factor in (("copy off by 2%", 0.02), ("copy off by 5%", 0.05)):
            sim = frame.loc[pick].copy()
            for i in pick:
                sign = 1 if rng.random() < 0.5 else -1
                sim.at[i, jup] = _round_like(sim.at[i, jup] * (1 + sign * factor), sim.at[i, jup])
            flagged, _ = check_a(sim)
            leads = flagged[(flagged["rule"] == "A5") & (flagged["column"] == earth)] if len(flagged) else flagged
            masked = flagged[(flagged["rule"] == "A5m") & (flagged["column"] == earth)] if len(flagged) else flagged
            results[label] = {"planted": len(pick), "caught": int(len(leads)), "labelled_innocent": int(len(masked)),
                              "rate": round(len(leads) / len(pick), 3)}
        out[earth] = results
    return out
