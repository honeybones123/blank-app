"""Prove Runtime consumes the installed Inputs V2 distribution coherently."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path

from application.contracts.design_brain import EngineeringInputSnapshot
from application.v2_source_manifest import (
    EXPECTED_INPUTS_V2_VERSION,
    installed_inputs_v2_root,
)
from inputs_application.v2_engineering_calculation_adapter import (
    calculate_v2_authoritative_result,
)


def main() -> int:
    runtime_root = Path(__file__).resolve().parents[2]
    adapter_source = (
        runtime_root
        / "inputs_application"
        / "v2_engineering_calculation_adapter.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "DEFAULT_V2_SOURCE_ROOT",
        "INPUTS_V2_SOURCE_ROOT",
        "sys.path",
        "inputs-v2-lab",
    )
    present = [token for token in forbidden if token in adapter_source]
    if present:
        raise AssertionError(f"Runtime adapter retains path coupling: {present}")

    version = metadata.version("beamapp-inputs-v2")
    if version != EXPECTED_INPUTS_V2_VERSION:
        raise AssertionError(
            f"expected V2 {EXPECTED_INPUTS_V2_VERSION}, found {version}"
        )
    package_root = installed_inputs_v2_root()
    if not package_root.is_dir():
        raise AssertionError("installed inputs_v2 package root is unavailable")

    snapshot = EngineeringInputSnapshot()
    result = calculate_v2_authoritative_result(
        engineering_snapshot=snapshot,
        resolved_inputs={},
        input_revision=1,
    )
    calculations = dict(result.current_calculations)
    if result.engineering_hash != snapshot.engineering_hash:
        raise AssertionError("Runtime/V2 engineering hash mismatch")
    if calculations.get("source") != "inputs_v2":
        raise AssertionError("Runtime result did not originate from V2")
    if calculations.get("v2_source_revision") != 1:
        raise AssertionError("Runtime/V2 input revision mismatch")
    if not calculations.get("v2_source_manifest_hash"):
        raise AssertionError("installed V2 source manifest identity is missing")

    print(
        "inputs_v2_installed_package_contract PASS "
        f"version={version} package={package_root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
