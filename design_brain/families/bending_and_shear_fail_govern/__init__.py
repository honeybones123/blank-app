from __future__ import annotations

from design_brain.families.bending_and_shear_fail_govern.runtime import (
    CombinedBendingShearFailResult,
    run_combined_bending_shear_fail_runtime,
)


FAMILY_ID = "COMBINED_BENDING_SHEAR_FAIL_GOVERNS"
RUNTIME_FAMILY_ID = "COMBINED_BENDING_SHEAR_FAIL"


__all__ = [
    "CombinedBendingShearFailResult",
    "FAMILY_ID",
    "RUNTIME_FAMILY_ID",
    "run_combined_bending_shear_fail_runtime",
]
