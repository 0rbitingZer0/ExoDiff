from __future__ import annotations

RUNAWAY_GREENHOUSE = (1.107, 1.332e-4, 1.58e-8, -8.308e-12, -1.931e-15)
MAXIMUM_GREENHOUSE = (0.356, 6.171e-5, 1.698e-9, -3.198e-12, -5.575e-16)
TEFF_RANGE = (2600.0, 7200.0)


def s_eff(teff: float, coefficients: tuple) -> float:
    t = teff - 5780.0
    s, a, b, c, d = coefficients
    return s + a * t + b * t ** 2 + c * t ** 3 + d * t ** 4


def insolation(listed: float | None, log_luminosity: float | None, orbit_au: float | None) -> tuple[float | None, str | None]:
    if listed is not None:
        return listed, "listed"
    if log_luminosity is not None and orbit_au:
        return 10 ** log_luminosity / orbit_au ** 2, "computed"
    return None, None


def in_habitable_zone(insolation: float | None, teff: float | None) -> bool | None:
    if insolation is None or teff is None or not TEFF_RANGE[0] <= teff <= TEFF_RANGE[1]:
        return None
    return s_eff(teff, MAXIMUM_GREENHOUSE) <= insolation <= s_eff(teff, RUNAWAY_GREENHOUSE)
