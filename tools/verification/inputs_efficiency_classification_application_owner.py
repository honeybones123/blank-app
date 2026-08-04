"""Prove application-owned efficiency classification matches compatibility."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_application.efficiency_classification import (
            identify_materially_overprovided_non_governing_families,
            is_unnecessarily_overdesigned,
        )

    cases = (
        (
            {
                "all_key_pass": True,
                "any_fail": False,
                "worst_util": 0.55,
                "utils": {"bending": 0.90, "shear": 0.40},
            },
            {"classification": "inefficient"},
        ),
        (
            {
                "all_key_pass": True,
                "any_fail": False,
                "worst_util": 0.91,
                "utils": {"bending": 0.91, "shear": 0.65},
            },
            {"classification": "optimal"},
        ),
        (
            {
                "all_key_pass": False,
                "any_fail": True,
                "worst_util": 1.2,
                "utils": {"bending": 1.2, "shear": 0.3},
            },
            {"classification": "inefficient"},
        ),
        (
            {
                "all_key_pass": True,
                "any_fail": False,
                "worst_util": 0.7,
                "governing_check": "shear capacity",
                "packs": {
                    "bending": {"summary_util": 0.45},
                    "serviceability": {"summary_util": 0.0},
                },
                "utils": {"shear": 0.95},
            },
            {"is_efficiency_reduction_mode": True},
        ),
        (
            {
                "all_key_pass": True,
                "any_fail": False,
                "worst_util": 0.86,
                "governing_family": "bending",
                "utils": {"bending": 0.86, "shear": 0.62, "crack": 0.4},
            },
            {"strongly_underutilised": True},
        ),
    )
    for overview, efficiency in cases:
        assert identify_materially_overprovided_non_governing_families(
            overview
        ) == bridge.identify_materially_overprovided_non_governing_families(
            overview
        )
        assert is_unnecessarily_overdesigned(
            overview,
            efficiency,
        ) == bridge.is_unnecessarily_overdesigned(overview, efficiency)
    print("PASS: application efficiency classification has exact 5/5 parity")


if __name__ == "__main__":
    main()
