import pandas as pd

from exodiff.evaluation import evaluate_row_check
from exodiff.screening import SOLAR_TO_EARTH_RADII
from test_consistency import ratio_row


def test_row_check_catches_unit_errors_and_ignores_the_control():
    rows = []
    for i in range(60):
        k, star = 0.02 + i * 1e-4, 0.8 + i * 1e-3
        rows.append(ratio_row(f"Ev-{i} b", round(k * star * SOLAR_TO_EARTH_RADII, 4), round(k, 5), round(star, 4),
                              plus=0.02, minus=-0.02))
    result = evaluate_row_check(pd.DataFrame(rows))
    assert result["planet radius in Jupiter units"]["rate"] > 0.9
    assert result["control: star and planet rescaled together"]["rate"] < 0.1
    assert result["planet radius off by 25%"]["rate"] > result["planet radius off by 2%"]["rate"]
