"""Executable contract for the Design page's pure summary policy."""

from __future__ import annotations

import sys
from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parents[2]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from engineering_page_sections.design_check_summary_policy import (
    format_strength,
    resolve_header_check_state,
    serviceability_values,
)


def main() -> int:
    assert format_strength(123.456, "kNm") == "123.46 kNm"
    assert format_strength(None, "kN") == "\u2014"
    assert format_strength(float("nan"), "kN") == "\u2014"

    assert resolve_header_check_state(90.0, 100.0, "0.1", []) == (
        "0.90",
        "NEAR LIMIT",
    )
    assert resolve_header_check_state(101.0, 100.0, "", []) == ("1.01", "FAIL")
    assert resolve_header_check_state(0.0, None, "util 0.72", []) == (
        "0.72",
        "PASS",
    )
    assert resolve_header_check_state(
        0.0,
        None,
        "",
        [{"util": "0.81"}, {"util": "0.94"}],
    ) == ("0.94", "NEAR LIMIT")
    assert resolve_header_check_state(0.0, None, "", []) == ("\u2014", "NOT CHECKED")

    rows = [
        {"title": "Other", "capacity": "A", "is_primary": True},
        {
            "title": "Direct crack width check",
            "limit": "0.30 mm",
            "value": "0.20 mm",
            "util": "0.67",
            "status": "PASS",
        },
    ]
    assert serviceability_values(rows, preferred_title="crack width") == (
        "0.30 mm",
        "0.20 mm",
        "0.67",
        "PASS",
    )
    assert serviceability_values([]) == ("\u2014", "\u2014", "\u2014", "INFO")
    print("Design check summary policy contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
