"""Page-neutral design-action handover contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Preserve the established engineering identity while the contract receives a
# clearer application-owned name. Changing this value would invalidate every
# committed Beam Setup engineering hash without changing an engineering input.
DESIGN_ACTIONS_SNAPSHOT_SCHEMA_VERSION = "resolved_design_actions.v1"


@dataclass(frozen=True)
class DesignActionsSnapshot:
    """Immutable actions supplied to the shared Design Brain.

    Moments use separate non-negative sagging (``*_pos``) and hogging
    (``*_neg``) magnitudes. ``*_signed`` is positive for sagging and negative
    for hogging. Forces are expressed in kN and moments in kNm.
    """

    mu: float
    mu_signed: float
    mu_pos: float
    mu_neg: float
    has_sagging_case: bool
    has_hogging_case: bool
    vu: float
    nu: float
    sls_m: float
    sls_m_signed: float
    sls_m_pos: float
    sls_m_neg: float
    sls_v: float
    sls_n: float
    tu: float
    pu: float
    source: str
    actions_source: str
    actions_mode: str
    design_actions_source: str
    sls_line_load: float
    sls_point_load: float
    design_section_x_m: float | None = None
    input_revision: int | None = None

    @property
    def signature(self) -> tuple[Any, ...]:
        return (
            self.mu,
            self.vu,
            self.nu,
            self.sls_m,
            self.sls_v,
            self.source,
            self.actions_source,
            self.actions_mode,
        )

    def to_legacy_mapping(self) -> dict[str, Any]:
        return {
            "Mu": self.mu,
            "Mu_signed": self.mu_signed,
            "Mu_pos": self.mu_pos,
            "Mu_neg": self.mu_neg,
            "has_sagging_case": self.has_sagging_case,
            "has_hogging_case": self.has_hogging_case,
            "Vu": self.vu,
            "Nu": self.nu,
            "SLS_M": self.sls_m,
            "SLS_M_signed": self.sls_m_signed,
            "SLS_M_pos": self.sls_m_pos,
            "SLS_M_neg": self.sls_m_neg,
            "SLS_V": self.sls_v,
            "Tu": self.tu,
            "Pu": self.pu,
            "source": self.source,
            "actions_source": self.actions_source,
            "actions_mode": self.actions_mode,
            "signature": self.signature,
        }

    def to_snapshot_mapping(self) -> dict[str, Any]:
        resolved = self.to_legacy_mapping()
        resolved.pop("signature", None)
        resolved["SLS_N"] = self.sls_n
        resolved["design_actions_source"] = self.design_actions_source
        if self.design_section_x_m is not None:
            resolved["design_section_x_m"] = self.design_section_x_m
        return {
            "schema_version": DESIGN_ACTIONS_SNAPSHOT_SCHEMA_VERSION,
            "resolved": resolved,
            "serviceability_loads": {
                "w_sls_kNm_per_m": self.sls_line_load,
                "P_sls_kN": self.sls_point_load,
            },
        }


# Compatibility name retained while existing consumers migrate.
ResolvedDesignActions = DesignActionsSnapshot


__all__ = [
    "DESIGN_ACTIONS_SNAPSHOT_SCHEMA_VERSION",
    "DesignActionsSnapshot",
    "ResolvedDesignActions",
]
