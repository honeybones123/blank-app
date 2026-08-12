"""Authoritative deflection summary projection.

There is intentionally no page-local fallback calculation here.
"""

from typing import Any, Dict

from inputs_application.authoritative_check_packs import (
    authoritative_check_pack_or_unavailable,
)


def build_deflection_check_rows_from_state(
    st_state: Dict[str, Any],
) -> Dict[str, Any]:
    return authoritative_check_pack_or_unavailable(st_state, "deflection")


__all__ = ["build_deflection_check_rows_from_state"]
