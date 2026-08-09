"""Canonical, presentation-free Inputs V2 domain model."""

from __future__ import annotations

from dataclasses import dataclass, replace
from inputs_v2.domain.reinforcement_arrangement import ReinforcementArrangement
from enum import StrEnum
import hashlib
import json


class LayoutMode(StrEnum):
    COUNT = "Count"
    SPACING = "Spacing"


ALLOWED_BAR_DIAMETERS = (10, 12, 16, 20, 24, 28, 32, 36, 40)


@dataclass(frozen=True, slots=True)
class LongitudinalReinforcement:
    mode: LayoutMode = LayoutMode.COUNT
    bars: int = 3
    spacing_mm: float = 150.0
    diameter_mm: int = 10
    cover_mm: float = 40.0

    def validated(self) -> "BottomReinforcement":
        if self.bars < 2 or self.bars > 12:
            raise ValueError("Longitudinal reinforcement bar count must be between 2 and 12.")
        if self.spacing_mm < 50.0 or self.spacing_mm > 500.0:
            raise ValueError("Longitudinal reinforcement spacing must be between 50 and 500 mm.")
        if self.diameter_mm not in ALLOWED_BAR_DIAMETERS:
            raise ValueError("Longitudinal reinforcement diameter is not supported.")
        if self.cover_mm < 10.0 or self.cover_mm > 150.0:
            raise ValueError("Longitudinal cover must be between 10 and 150 mm.")
        return self


BottomReinforcement = LongitudinalReinforcement
TopReinforcement = LongitudinalReinforcement


@dataclass(frozen=True, slots=True)
class ShearReinforcement:
    diameter_mm: int = 0
    legs: int = 0
    spacing_mm: float = 200.0

    def validated(self) -> "ShearReinforcement":
        if self.diameter_mm != 0 and self.diameter_mm not in ALLOWED_BAR_DIAMETERS:
            raise ValueError("Shear link diameter is not supported.")
        if self.legs not in (0, 2, 4, 6, 8):
            raise ValueError("Shear link legs must be 2, 4, 6 or 8.")
        if (self.diameter_mm == 0) != (self.legs == 0):
            raise ValueError("Shear links must be fully off or specify diameter and legs.")
        if self.spacing_mm < 50.0 or self.spacing_mm > 600.0:
            raise ValueError("Shear link spacing must be between 50 and 600 mm.")
        return self


@dataclass(frozen=True, slots=True)
class MaterialInputs:
    concrete_strength_mpa: float = 40.0
    reinforcement_strength_mpa: float = 500.0

    def validated(self) -> "MaterialInputs":
        if self.concrete_strength_mpa not in (20, 25, 32, 40, 50, 65, 80, 100):
            raise ValueError("Concrete strength is not supported.")
        if self.reinforcement_strength_mpa not in (400, 500, 600):
            raise ValueError("Reinforcement strength is not supported.")
        return self


@dataclass(frozen=True, slots=True)
class ActionInputs:
    bending_moment_knm: float = 0.0
    torsion_knm: float = 0.0
    shear_force_kn: float = 0.0
    axial_force_kn: float = 0.0

    def validated(self) -> "ActionInputs":
        if self.bending_moment_knm < 0 or self.bending_moment_knm > 100000:
            raise ValueError("Bending moment must be between 0 and 100000 kNm.")
        if self.torsion_knm < 0 or self.torsion_knm > 100000:
            raise ValueError("Design torsion must be between 0 and 100000 kNm.")
        if self.shear_force_kn < 0 or self.shear_force_kn > 10000:
            raise ValueError("Shear force must be between 0 and 10000 kN.")
        if self.axial_force_kn < -100000 or self.axial_force_kn > 100000:
            raise ValueError("Axial force must be between -100000 and 100000 kN.")
        return self


@dataclass(frozen=True, slots=True)
class SupportInputs:
    left_type: str = "Pinned"
    right_type: str = "Roller"

    def validated(self) -> "SupportInputs":
        allowed = {"Pinned", "Roller", "Fixed"}
        if self.left_type not in allowed or self.right_type not in allowed:
            raise ValueError("Support type is not supported.")
        return self


@dataclass(frozen=True, slots=True)
class TimeDependentInputs:
    shrinkage_time_days: float = 365.0
    creep_time_days: float = 365.0
    age_at_loading_days: float = 28.0

    def validated(self) -> "TimeDependentInputs":
        if min(self.shrinkage_time_days, self.creep_time_days, self.age_at_loading_days) < 0:
            raise ValueError("Time-dependent inputs cannot be negative.")
        return self


@dataclass(frozen=True, slots=True)
class VoidInputs:
    ducts: int = 0
    diameter_mm: float = 0.0

    def validated(self) -> "VoidInputs":
        if self.ducts < 0 or self.ducts > 100:
            raise ValueError("Number of ducts must be between 0 and 100.")
        if self.diameter_mm < 0 or self.diameter_mm > 1000:
            raise ValueError("Duct diameter must be between 0 and 1000 mm.")
        if self.ducts == 0 and self.diameter_mm != 0:
            raise ValueError("Duct diameter must be zero when there are no ducts.")
        return self


@dataclass(frozen=True, slots=True)
class DeflectionInputs:
    support_condition: str = "Simply supported"
    limit_ratio: float = 250.0

    def validated(self) -> "DeflectionInputs":
        if self.support_condition not in {"Simply supported", "Continuous", "Cantilever", "Fixed-ended"}:
            raise ValueError("Support condition is not supported for deflection.")
        if self.limit_ratio not in (200.0, 250.0, 300.0, 400.0):
            raise ValueError("Deflection limit ratio is not supported.")
        return self


@dataclass(frozen=True, slots=True)
class ServiceabilityInputs:
    """Explicit SLS/crack-control inputs carried with the beam snapshot."""

    moment_knm: float = 0.0
    shear_kn: float = 0.0
    permanent_udl_knm_per_m: float = 0.0
    imposed_udl_knm_per_m: float = 0.0
    equivalent_udl_knm_per_m: float = 0.0
    sustained_load_factor: float = 0.4
    crack_width_limit_mm: float = 0.3
    crack_member_type: str = "Primarily flexure"
    crack_k1: float = 0.8
    crack_k2: float = 0.5
    creep_coefficient: float = 2.0
    shrinkage_microstrain: float = 300.0
    use_uls_fallback: bool = True

    def validated(self) -> "ServiceabilityInputs":
        if abs(self.moment_knm) > 100000.0:
            raise ValueError("SLS moment must be between -100000 and 100000 kNm.")
        if abs(self.shear_kn) > 10000.0:
            raise ValueError("SLS shear must be between -10000 and 10000 kN.")
        if min(
            self.permanent_udl_knm_per_m,
            self.imposed_udl_knm_per_m,
            self.equivalent_udl_knm_per_m,
            self.crack_k1,
            self.crack_k2,
            self.creep_coefficient,
            self.shrinkage_microstrain,
        ) < 0.0:
            raise ValueError("SLS loads and serviceability factors cannot be negative.")
        if not 0.0 <= self.sustained_load_factor <= 1.0:
            raise ValueError("Sustained load factor must be between 0 and 1.")
        if self.crack_width_limit_mm not in (0.2, 0.3, 0.4):
            raise ValueError("Crack width limit must be 0.2, 0.3 or 0.4 mm.")
        if self.crack_member_type not in {"Primarily flexure", "Primarily tension"}:
            raise ValueError("Crack member type is not supported.")
        return self


@dataclass(frozen=True, slots=True)
class BeamInputs:
    revision: int = 0
    width_mm: float = 250.0
    depth_mm: float = 300.0
    span_mm: float = 2000.0
    section_shape: str = "RECT"
    width_locked: bool = False
    depth_locked: bool = False
    bottom: LongitudinalReinforcement = LongitudinalReinforcement()
    bottom_arrangement: ReinforcementArrangement | None = None
    top: LongitudinalReinforcement = LongitudinalReinforcement(bars=2, diameter_mm=10)
    shear: ShearReinforcement = ShearReinforcement()
    materials: MaterialInputs = MaterialInputs()
    actions: ActionInputs = ActionInputs()
    supports: SupportInputs = SupportInputs()
    time_dependent: TimeDependentInputs = TimeDependentInputs()
    voids: VoidInputs = VoidInputs()
    deflection: DeflectionInputs = DeflectionInputs()
    serviceability: ServiceabilityInputs = ServiceabilityInputs()

    def validated(self) -> "BeamInputs":
        if self.revision < 0:
            raise ValueError("Input revision cannot be negative.")
        if self.width_mm < 150.0 or self.width_mm > 3000.0:
            raise ValueError("Beam width must be between 150 and 3000 mm.")
        if self.depth_mm < 200.0 or self.depth_mm > 5000.0:
            raise ValueError("Beam depth must be between 200 and 5000 mm.")
        if self.span_mm < 500.0 or self.span_mm > 100000.0:
            raise ValueError("Beam span must be between 500 and 100000 mm.")
        if self.section_shape not in {"RECT", "T", "I"}:
            raise ValueError("Section shape is not supported.")
        self.bottom.validated()
        self.top.validated()
        self.shear.validated()
        self.materials.validated()
        self.actions.validated()
        self.supports.validated()
        self.time_dependent.validated()
        self.voids.validated()
        self.deflection.validated()
        self.serviceability.validated()
        minimum_fit = 2.0 * self.bottom.cover_mm + 2.0 * self.bottom.diameter_mm
        if self.width_mm <= minimum_fit:
            raise ValueError("Beam width is too small for the selected cover and bars.")
        return self

    def next_revision(
        self,
        *,
        width_mm: float,
        depth_mm: float,
        span_mm: float | None = None,
        section_shape: str | None = None,
        width_locked: bool | None = None,
        depth_locked: bool | None = None,
        bottom: LongitudinalReinforcement,
        top: LongitudinalReinforcement | None = None,
        shear: ShearReinforcement | None = None,
        materials: MaterialInputs | None = None,
        actions: ActionInputs | None = None,
        supports: SupportInputs | None = None,
        time_dependent: TimeDependentInputs | None = None,
        voids: VoidInputs | None = None,
        deflection: DeflectionInputs | None = None,
        serviceability: ServiceabilityInputs | None = None,
    ) -> "BeamInputs":
        candidate = replace(
            self,
            revision=self.revision + 1,
            width_mm=float(width_mm),
            depth_mm=float(depth_mm),
            span_mm=self.span_mm if span_mm is None else float(span_mm),
            section_shape=self.section_shape if section_shape is None else str(section_shape),
            width_locked=self.width_locked if width_locked is None else bool(width_locked),
            depth_locked=self.depth_locked if depth_locked is None else bool(depth_locked),
            bottom=bottom,
            # A stored arrangement is valid only for the exact geometry and
            # reinforcement inputs that produced it. Any canonical edit
            # invalidates that snapshot; Apply re-attaches a newly checked
            # arrangement explicitly after the command succeeds.
            bottom_arrangement=None,
            top=self.top if top is None else top,
            shear=self.shear if shear is None else shear,
            materials=self.materials if materials is None else materials,
            actions=self.actions if actions is None else actions,
            supports=self.supports if supports is None else supports,
            time_dependent=self.time_dependent if time_dependent is None else time_dependent,
            voids=self.voids if voids is None else voids,
            deflection=self.deflection if deflection is None else deflection,
            serviceability=self.serviceability if serviceability is None else serviceability,
        )
        return candidate.validated()

    @property
    def canonical_payload(self) -> dict[str, object]:
        return {
            "width_mm": self.width_mm,
            "depth_mm": self.depth_mm,
            "span_mm": self.span_mm,
            "section_shape": self.section_shape,
            "width_locked": self.width_locked,
            "depth_locked": self.depth_locked,
            "bottom": {
                "mode": self.bottom.mode.value,
                "bars": self.bottom.bars,
                "spacing_mm": self.bottom.spacing_mm,
                "diameter_mm": self.bottom.diameter_mm,
                "cover_mm": self.bottom.cover_mm,
                "arrangement": None if self.bottom_arrangement is None else {
                    "total_bar_count": self.bottom_arrangement.total_bar_count,
                    "bar_diameter_mm": self.bottom_arrangement.bar_diameter_mm,
                    "layer_count": self.bottom_arrangement.layer_count,
                    "clear_row_gap_mm": self.bottom_arrangement.clear_row_gap_mm,
                    "reinforcement_centroid_mm": self.bottom_arrangement.reinforcement_centroid_mm,
                    "effective_depth_mm": self.bottom_arrangement.effective_depth_mm,
                    "rows": [
                        {"row_index": row.row_index, "bar_count": row.bar_count,
                         "clear_spacing_mm": row.clear_spacing_mm,
                         "centre_from_tension_face_mm": row.centre_from_tension_face_mm}
                        for row in self.bottom_arrangement.rows
                    ],
                },
            },
            "top": {
                "mode": self.top.mode.value,
                "bars": self.top.bars,
                "spacing_mm": self.top.spacing_mm,
                "diameter_mm": self.top.diameter_mm,
                "cover_mm": self.top.cover_mm,
            },
            "shear": {
                "diameter_mm": self.shear.diameter_mm,
                "legs": self.shear.legs,
                "spacing_mm": self.shear.spacing_mm,
            },
            "materials": {
                "concrete_strength_mpa": self.materials.concrete_strength_mpa,
                "reinforcement_strength_mpa": self.materials.reinforcement_strength_mpa,
            },
            "actions": {
                "bending_moment_knm": self.actions.bending_moment_knm,
                "torsion_knm": self.actions.torsion_knm,
                "shear_force_kn": self.actions.shear_force_kn,
                "axial_force_kn": self.actions.axial_force_kn,
            },
            "supports": {
                "left_type": self.supports.left_type,
                "right_type": self.supports.right_type,
            },
            "time_dependent": {
                "shrinkage_time_days": self.time_dependent.shrinkage_time_days,
                "creep_time_days": self.time_dependent.creep_time_days,
                "age_at_loading_days": self.time_dependent.age_at_loading_days,
            },
            "voids": {"ducts": self.voids.ducts, "diameter_mm": self.voids.diameter_mm},
            "deflection": {
                "support_condition": self.deflection.support_condition,
                "limit_ratio": self.deflection.limit_ratio,
            },
            "serviceability": {
                "moment_knm": self.serviceability.moment_knm,
                "shear_kn": self.serviceability.shear_kn,
                "permanent_udl_knm_per_m": self.serviceability.permanent_udl_knm_per_m,
                "imposed_udl_knm_per_m": self.serviceability.imposed_udl_knm_per_m,
                "equivalent_udl_knm_per_m": self.serviceability.equivalent_udl_knm_per_m,
                "sustained_load_factor": self.serviceability.sustained_load_factor,
                "crack_width_limit_mm": self.serviceability.crack_width_limit_mm,
                "crack_member_type": self.serviceability.crack_member_type,
                "crack_k1": self.serviceability.crack_k1,
                "crack_k2": self.serviceability.crack_k2,
                "creep_coefficient": self.serviceability.creep_coefficient,
                "shrinkage_microstrain": self.serviceability.shrinkage_microstrain,
                "use_uls_fallback": self.serviceability.use_uls_fallback,
            },
        }

    @property
    def content_hash(self) -> str:
        payload = self.canonical_payload
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
