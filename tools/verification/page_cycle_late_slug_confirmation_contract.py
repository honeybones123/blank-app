from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_helpers import (
    PAGE_CYCLE_LATE_SLUG_CONFIRMATION_CLASS,
    PAGE_CYCLE_NAVIGATION_TIMEOUT_CLASS,
    _page_cycle_deadline_result,
)


def test_exact_target_slug_is_confirmed_at_deadline() -> None:
    result = _page_cycle_deadline_result(
        target_slug="creep",
        current_slug="creep",
        selector="visible_radio_nav_label",
        elapsed_ms=12_001,
        errors=["locator retry exhausted"],
        message="navigation timed out",
    )

    assert result["clicked"] is True
    assert result["already_active"] is False
    assert result["late_slug_confirmation"] is True
    assert result["classification"] == PAGE_CYCLE_LATE_SLUG_CONFIRMATION_CLASS
    assert result["current_slug"] == "creep"


def test_nonmatching_slug_still_fails_closed() -> None:
    result = _page_cycle_deadline_result(
        target_slug="creep",
        current_slug="shear",
        selector="visible_radio_nav_label",
        elapsed_ms=12_001,
        errors=["locator retry exhausted"],
        message="navigation timed out",
    )

    assert result["clicked"] is False
    assert result["already_active"] is False
    assert result["late_slug_confirmation"] is False
    assert result["classification"] == PAGE_CYCLE_NAVIGATION_TIMEOUT_CLASS
    assert result["current_slug"] == "shear"


def main() -> int:
    test_exact_target_slug_is_confirmed_at_deadline()
    test_nonmatching_slug_still_fails_closed()
    print("page_cycle_late_slug_confirmation_contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
