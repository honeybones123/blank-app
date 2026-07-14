from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bending_checks_helpers import build_bending_check_rows_from_state
from crack_checks_helpers import build_crack_check_rows_from_state, pick_governing_check_row
from deflection_checks_helpers import build_deflection_check_rows_from_state
from shear_checks_helpers import build_shear_check_rows_from_state


REQUIRED_ROW_KEYS = {
    "uid",
    "title",
    "capacity",
    "action",
    "value",
    "limit",
    "util",
    "status",
    "route_page",
}


def _assert_row_shape(row: dict, *, route_page: str) -> None:
    missing = REQUIRED_ROW_KEYS - set(row)
    assert not missing, f"{row.get('uid')}: missing {sorted(missing)}"
    assert str(row["uid"]).strip()
    assert str(row["title"]).strip()
    assert row["route_page"] == route_page
    assert str(row["status"]).strip()


def test_bending_check_rows_contract() -> None:
    payload = build_bending_check_rows_from_state({})
    assert "rows" in payload
    assert isinstance(payload["rows"], list)
    assert payload["rows"]
    for row in payload["rows"]:
        _assert_row_shape(row, route_page="bending")
    assert "actions_used" in payload


def test_shear_check_rows_contract() -> None:
    payload = build_shear_check_rows_from_state({})
    assert isinstance(payload["rows"], list)
    assert isinstance(payload["summary_rows"], list)
    assert len(payload["rows"]) >= 1
    for row in payload["rows"]:
        _assert_row_shape(row, route_page="shear")
    assert "summary_status" in payload
    assert "summary_governing_check_name" in payload


def test_crack_check_rows_contract() -> None:
    payload = build_crack_check_rows_from_state({})
    assert isinstance(payload["rows"], list)
    assert len(payload["rows"]) >= 1
    for row in payload["rows"]:
        _assert_row_shape(row, route_page="crack")
    governing = pick_governing_check_row(payload["rows"])
    assert governing is None or governing in payload["rows"]


def test_deflection_check_rows_contract() -> None:
    payload = build_deflection_check_rows_from_state({})
    assert isinstance(payload["rows"], list)
    assert len(payload["rows"]) >= 1
    for row in payload["rows"]:
        _assert_row_shape(row, route_page="deflection")
        assert "calculated" in row
        assert "requirement" in row
    assert any(row.get("is_primary") for row in payload["rows"])


def main() -> int:
    test_bending_check_rows_contract()
    test_shear_check_rows_contract()
    test_crack_check_rows_contract()
    test_deflection_check_rows_contract()
    print("engineering_check_rows_contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
