"""Authoritative crack-control summary projection.

The page-local crack calculator was deliberately removed from this boundary.
Detailed pages render the current V2 publication or an explicit unavailable
state; they cannot create a competing engineering result.
"""

from typing import Any, Dict

from calculations.crack_control import pick_governing_check_row
from inputs_application.authoritative_check_packs import (
    authoritative_check_pack_or_unavailable,
)


def build_crack_check_rows_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    return authoritative_check_pack_or_unavailable(st_state, "crack")


__all__ = ["build_crack_check_rows_from_state", "pick_governing_check_row"]
