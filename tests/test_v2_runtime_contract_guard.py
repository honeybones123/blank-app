from __future__ import annotations

import pytest

from inputs_application.new_design_brain_adapter import (
    _require_compatible_v2_design_brain_contract,
)


def test_runtime_accepts_current_installed_design_brain_contract() -> None:
    _require_compatible_v2_design_brain_contract(2)


@pytest.mark.parametrize("version", [None, 1, 3, "2"])
def test_runtime_rejects_stale_or_unknown_design_brain_contract(version: object) -> None:
    with pytest.raises(RuntimeError, match="Reinstall"):
        _require_compatible_v2_design_brain_contract(version)
