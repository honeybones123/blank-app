"""V2-owned shear reinforcement detailing checks."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from inputs_v2.domain.beam_inputs import SUPPORTED_SHEAR_LEG_COUNTS


@dataclass(frozen=True)
class ShearDetailingInput:
    reinforcement_area_mm2: float
    spacing_mm: float | None
    concrete_strength_mpa: float
    web_width_mm: float
    reinforcement_strength_mpa: float
    section_depth_mm: float | None
    effective_legs: int = 0
    link_diameter_mm: float = 0.0
    side_cover_mm: float = 40.0
    nominal_aggregate_size_mm: float = 20.0
    longitudinal_bar_coordinates_mm: tuple[tuple[float, float, float], ...] = ()


@dataclass(frozen=True)
class ShearDetailingResult:
    Asv_over_s: float
    Asv_min_over_s: float
    min_shear_ok: bool
    max_spacing: float
    spacing_ok: bool
    transverse_leg_centres_mm: tuple[float, ...]
    transverse_adjacent_spacings_mm: tuple[float, ...]
    transverse_max_leg_spacing_mm: float
    transverse_spacing_limit_mm: float
    transverse_min_clear_spacing_mm: float
    transverse_minimum_clear_spacing_mm: float
    transverse_clear_spacing_ok: bool
    transverse_minimum_even_legs: int | None
    transverse_spacing_ok: bool
    transverse_fit_ok: bool
    cage_topology_id: str
    cage_topology_verified: bool
    longitudinal_bar_collision_ok: bool
    internal_leg_anchorage_ok: bool
    longitudinal_bar_restraint_ok: bool
    cage_rejection_codes: tuple[str, ...]

    def as_family_values(self) -> dict[str, object]:
        return asdict(self)


def calculate_shear_detailing(values: ShearDetailingInput) -> ShearDetailingResult:
    """Check minimum transverse steel and AS 3600 maximum spacing."""
    _validate_finite(values)
    spacing = values.spacing_mm
    provided = values.reinforcement_area_mm2 / spacing if spacing else 0.0
    strength = values.reinforcement_strength_mpa or 1.0
    minimum = (
        0.08
        * math.sqrt(max(values.concrete_strength_mpa, 0.0))
        * values.web_width_mm
        / strength
    )
    maximum_spacing = (
        min(0.75 * values.section_depth_mm, 500.0)
        if values.section_depth_mm
        else 500.0
    )
    (
        leg_centres,
        adjacent_spacings,
        transverse_max_spacing,
        transverse_limit,
        minimum_even_legs,
        transverse_spacing_ok,
        transverse_fit_ok,
        transverse_min_clear_spacing,
        transverse_minimum_clear_spacing,
        transverse_clear_spacing_ok,
    ) = _transverse_leg_spacing(values)
    (
        topology_id,
        topology_verified,
        collision_ok,
        anchorage_ok,
        restraint_ok,
        cage_rejections,
    ) = _verify_cage_topology(values, leg_centres)
    return ShearDetailingResult(
        Asv_over_s=provided,
        Asv_min_over_s=minimum,
        min_shear_ok=provided >= minimum,
        max_spacing=maximum_spacing,
        spacing_ok=spacing <= maximum_spacing if spacing else False,
        transverse_leg_centres_mm=leg_centres,
        transverse_adjacent_spacings_mm=adjacent_spacings,
        transverse_max_leg_spacing_mm=transverse_max_spacing,
        transverse_spacing_limit_mm=transverse_limit,
        transverse_min_clear_spacing_mm=transverse_min_clear_spacing,
        transverse_minimum_clear_spacing_mm=transverse_minimum_clear_spacing,
        transverse_clear_spacing_ok=transverse_clear_spacing_ok,
        transverse_minimum_even_legs=minimum_even_legs,
        transverse_spacing_ok=transverse_spacing_ok,
        transverse_fit_ok=transverse_fit_ok,
        cage_topology_id=topology_id,
        cage_topology_verified=topology_verified,
        longitudinal_bar_collision_ok=collision_ok,
        internal_leg_anchorage_ok=anchorage_ok,
        longitudinal_bar_restraint_ok=restraint_ok,
        cage_rejection_codes=cage_rejections,
    )


def resolve_transverse_leg_centres(
    values: ShearDetailingInput,
) -> tuple[float, ...]:
    """Return the verified across-width link-leg centre lines.

    This is a factual geometry projection shared with section renderers.  It
    does not generate candidates, rank arrangements or make a Design Brain
    decision.
    """

    _validate_finite(values)
    return _transverse_leg_spacing(values)[0]


def _verify_cage_topology(
    values: ShearDetailingInput,
    leg_centres: tuple[float, ...],
) -> tuple[str, bool, bool, bool, bool, tuple[str, ...]]:
    """Return factual cage checks; this function never selects a candidate.

    Coordinates are ``(x, y, diameter)``.  Outer legs form the closed link;
    internal legs are explicit crossties.  The check is deliberately
    conservative: an internal leg may be tangent to a longitudinal bar but
    may not pass through its circle.
    """

    legs = int(values.effective_legs or 0)
    if legs <= 0:
        return "links_off", True, True, True, True, ()
    topology = {
        2: "outer_closed_link",
        3: "outer_closed_link_plus_1_crosstie",
        4: "two_overlapping_closed_links",
        5: "outer_closed_link_plus_3_crossties",
        6: "multi_cell_closed_link_cage_6",
        8: "multi_cell_closed_link_cage_8",
    }.get(legs, "unsupported")
    failures: list[str] = []
    if topology == "unsupported" or len(leg_centres) != legs:
        failures.append("shear_cage_topology_unavailable")

    link_radius = max(float(values.link_diameter_mm), 0.0) / 2.0
    tolerance = 1e-6
    collision_ok = True
    for leg_x in leg_centres[1:-1]:
        for bar_x, _bar_y, bar_diameter in values.longitudinal_bar_coordinates_mm:
            required = link_radius + max(float(bar_diameter), 0.0) / 2.0
            if abs(float(leg_x) - float(bar_x)) + tolerance < required:
                collision_ok = False
                break
        if not collision_ok:
            break
    if not collision_ok:
        failures.append("shear_cage_longitudinal_bar_collision")

    # A standard crosstie needs a hook envelope at both faces.  This is a
    # geometric availability check, not a substitute for project anchorage
    # design.  Six link diameters is the deliberately conservative envelope
    # used by the current detailing contract.
    hook_envelope = 6.0 * max(float(values.link_diameter_mm), 0.0)
    available_depth = max(
        float(values.section_depth_mm or 0.0) - 2.0 * float(values.side_cover_mm),
        0.0,
    )
    anchorage_ok = legs in (2, 4) or available_depth + tolerance >= 2.0 * hook_envelope
    if not anchorage_ok:
        failures.append("internal_leg_anchorage_failed")

    # Every longitudinal bar must lie inside the outer closed link. Internal
    # legs are then checked independently for collision above.
    restraint_ok = bool(leg_centres)
    if values.longitudinal_bar_coordinates_mm and leg_centres:
        left, right = leg_centres[0], leg_centres[-1]
        restraint_ok = all(
            left - tolerance <= float(x) <= right + tolerance
            for x, _y, _diameter in values.longitudinal_bar_coordinates_mm
        )
    if not restraint_ok:
        failures.append("longitudinal_bar_restraint_failed")

    verified = not failures
    return topology, verified, collision_ok, anchorage_ok, restraint_ok, tuple(failures)


def _transverse_leg_spacing(
    values: ShearDetailingInput,
) -> tuple[
    tuple[float, ...],
    tuple[float, ...],
    float,
    float,
    int | None,
    bool,
    bool,
    float,
    float,
    bool,
]:
    """Resolve fitted across-width leg centres and maximum adjacent spacing."""

    legs = int(values.effective_legs or 0)
    depth = max(float(values.section_depth_mm or 0.0), 0.0)
    limit = min(600.0, depth) if depth > 0.0 else 0.0
    minimum_clear = max(
        link_diameter := max(float(values.link_diameter_mm or 0.0), 0.0),
        25.0,
        1.5 * max(float(values.nominal_aggregate_size_mm or 0.0), 0.0),
    )
    if legs <= 0:
        return (), (), 0.0, limit, 0, True, True, 0.0, minimum_clear, True

    centre_offset = float(values.side_cover_mm) + link_diameter / 2.0
    outer_span = float(values.web_width_mm) - 2.0 * centre_offset
    fit_ok = legs >= 2 and link_diameter > 0.0 and outer_span >= 0.0 and limit > 0.0
    if not fit_ok:
        return (), (), 0.0, limit, None, False, False, 0.0, minimum_clear, False

    raw_minimum = math.ceil(outer_span / limit) + 1
    minimum_even = next(
        (candidate for candidate in SUPPORTED_SHEAR_LEG_COUNTS if candidate >= raw_minimum),
        None,
    )
    step = outer_span / (legs - 1)
    targets = tuple(centre_offset + index * step for index in range(legs))
    centres = _fit_internal_leg_centres(values, targets, minimum_clear)
    adjacent = tuple(
        centres[index + 1] - centres[index]
        for index in range(len(centres) - 1)
    )
    maximum = max(adjacent, default=0.0)
    minimum_actual_clear = min(
        (centre_spacing - link_diameter for centre_spacing in adjacent),
        default=0.0,
    )
    clear_spacing_ok = minimum_actual_clear + 1e-9 >= minimum_clear
    spacing_ok = (
        minimum_even is not None
        and legs in SUPPORTED_SHEAR_LEG_COUNTS
        and maximum <= limit + 1e-9
        and clear_spacing_ok
    )
    return (
        centres,
        adjacent,
        maximum,
        limit,
        minimum_even,
        spacing_ok,
        True,
        minimum_actual_clear,
        minimum_clear,
        clear_spacing_ok,
    )


def _fit_internal_leg_centres(
    values: ShearDetailingInput,
    targets: tuple[float, ...],
    minimum_clear: float,
) -> tuple[float, ...]:
    """Move internal legs to the nearest collision-free bar edge.

    The outer legs remain fixed.  An internal leg is allowed to touch the
    outside of a longitudinal bar but cannot intersect it.  This produces
    factual geometry only; the selected family still owns candidate order
    and ranking.
    """

    if len(targets) <= 2 or not values.longitudinal_bar_coordinates_mm:
        return targets
    link_radius = max(float(values.link_diameter_mm), 0.0) / 2.0
    minimum_centre_spacing = minimum_clear + 2.0 * link_radius
    obstacles = tuple(
        (
            float(x) - (max(float(diameter), 0.0) / 2.0 + link_radius),
            float(x) + (max(float(diameter), 0.0) / 2.0 + link_radius),
        )
        for x, _y, diameter in values.longitudinal_bar_coordinates_mm
    )
    resolved = [targets[0]]
    for index, target in enumerate(targets[1:-1], start=1):
        lower = resolved[-1] + minimum_centre_spacing
        remaining = len(targets) - index - 1
        upper = targets[-1] - remaining * minimum_centre_spacing
        candidates = [target, lower, upper]
        for obstacle_lower, obstacle_upper in obstacles:
            candidates.extend((obstacle_lower, obstacle_upper))
        feasible = [
            candidate
            for candidate in candidates
            if lower - 1e-9 <= candidate <= upper + 1e-9
            and all(
                candidate <= obstacle_lower + 1e-9
                or candidate >= obstacle_upper - 1e-9
                for obstacle_lower, obstacle_upper in obstacles
            )
        ]
        resolved.append(
            min(feasible, key=lambda value: (abs(value - target), value))
            if feasible
            else target
        )
    resolved.append(targets[-1])
    return tuple(resolved)


def _validate_finite(values: ShearDetailingInput) -> None:
    for name, value in vars(values).items():
        if name == "longitudinal_bar_coordinates_mm":
            for coordinate in value:
                if len(coordinate) != 3 or any(
                    not math.isfinite(float(component)) for component in coordinate
                ):
                    raise ValueError(
                        "longitudinal_bar_coordinates_mm must contain finite x, y and diameter values"
                    )
            continue
        if value is not None and not math.isfinite(float(value)):
            raise ValueError(f"{name} must be finite")


__all__ = [
    "ShearDetailingInput",
    "ShearDetailingResult",
    "calculate_shear_detailing",
    "resolve_transverse_leg_centres",
]
