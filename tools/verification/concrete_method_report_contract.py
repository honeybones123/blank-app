"""Contract checks for method-specific report projection."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import reporting.report_content as report_content  # noqa: E402


def _sections(results: dict, values: dict) -> list[dict]:
    report_content._ss = lambda key, default="": results if key == "results" else default
    report_content.get_param = lambda key, default=None: values.get(key, default)
    report_content.resolve_design_actions = lambda: {"Mu": 0.0, "Vu": 0.0, "Nu": 0.0}
    return report_content.extract_check_sections()


def main() -> None:
    legacy_values = {"w_calc": 0.2, "wmax_char": 0.3}
    legacy = _sections({}, legacy_values)
    assert [section["title"] for section in legacy] == ["Crack Control"]

    as5100 = _sections(
        {
            "crack_method": {
                "method": "as5100_wall",
                "reference": "AS 5100.5:2017 Clause 11.7.2",
                "required_area_per_face_mm2_per_m": 2750.0,
                "maximum_spacing_mm": 150.0,
                "passes": True,
                "warnings": [],
            }
        },
        legacy_values,
    )
    assert [section["title"] for section in as5100] == ["Wall Crack Control - AS 5100.5"]

    c766 = _sections(
        {
            "crack_method": {
                "method": "ciria_c766_ec2",
                "reference": "CIRIA C766 Equations 3.1 and 3.21-3.23",
                "restrained_strain": 400e-6,
                "crack_initiates": True,
                "characteristic_crack_width_mm": 0.25,
                "warnings": ["No spreadsheet-parity claim."],
            },
            "shrinkage_method": {
                "method": "ec2_c766",
                "reference": "CIRIA C766 Appendices A3-A4",
                "warnings": ["Equation path."],
            },
        },
        {
            **legacy_values,
            "eps_cse": 75e-6,
            "eps_csd_t": 312e-6,
            "eps_cs_total": 387e-6,
        },
    )
    assert [section["title"] for section in c766] == [
        "Shrinkage - EC2 / CIRIA C766",
        "Restrained-Deformation Crack Control - CIRIA C766 / EC2",
    ]

    print("PASS: concrete method report projection contract")


if __name__ == "__main__":
    main()
