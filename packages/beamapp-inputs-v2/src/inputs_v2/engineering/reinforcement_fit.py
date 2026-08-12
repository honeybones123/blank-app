"""Pure physical fit calculation for longitudinal reinforcement."""
import math
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.reinforcement_arrangement import (
    CongestionAssessment, ReinforcementArrangement, ReinforcementFitResult, ReinforcementRow,
)

def practical_row_counts(total_bar_count: int) -> tuple[tuple[int, ...], ...]:
    """Generate symmetric one-row and balanced two-row arrangements only."""
    total = int(total_bar_count)
    if total <= 0:
        return ()
    options: list[tuple[int, ...]] = [(total,)]
    if total >= 4:
        low = total // 2
        high = total - low
        options.append((high, low))
    return tuple(options)

def evaluate_arrangement(
    inputs: BeamInputs,
    row_counts: tuple[int, ...],
    *,
    row_diameters_mm: tuple[float, ...] | None = None,
    min_clear_spacing_mm: float = 20.0,
    min_row_gap_mm: float | None = None,
    aggregate_clearance_mm: float = 0.0,
) -> ReinforcementFitResult:
    """Evaluate one exact bottom-reinforcement arrangement; never selects it."""
    default_diameter = float(inputs.bottom.diameter_mm)
    committed = inputs.bottom_arrangement
    committed_rows = tuple(committed.rows) if committed is not None else ()
    if min_row_gap_mm is None:
        row_gap = float(committed.clear_row_gap_mm) if committed is not None else 25.0
    else:
        row_gap = float(min_row_gap_mm)
    inferred_diameters = (
        tuple(float(row.bar_diameter_mm or default_diameter) for row in committed_rows)
        if committed_rows
        and tuple(int(row.bar_count) for row in committed_rows) == tuple(int(value) for value in row_counts)
        else ()
    )
    diameters = tuple(float(value) for value in (row_diameters_mm or inferred_diameters))
    if not diameters:
        diameters = tuple(default_diameter for _ in row_counts)
    ligature = float(inputs.shear.diameter_mm)
    usable_width = inputs.width_mm - 2.0 * (inputs.bottom.cover_mm + ligature + aggregate_clearance_mm)
    rows: list[ReinforcementRow] = []
    failures: list[str] = []
    row_centres: list[float] = []
    if not row_counts or any(int(count) < 2 for count in row_counts):
        failures.append("each reinforcement row must contain at least two bars")
    if len(diameters) != len(row_counts):
        failures.append("each reinforcement row must provide one bar diameter")
    aggregate_clearance_ok = aggregate_clearance_mm >= 0.0
    cover_ok = usable_width > 0.0
    if not cover_ok:
        failures.append("cover, ligature and aggregate clearance leave no usable width")
    if not aggregate_clearance_ok:
        failures.append("aggregate clearance cannot be negative")
    previous_centre = 0.0
    previous_diameter = 0.0
    for index, count in enumerate(row_counts, start=1):
        count = int(count)
        diameter = diameters[index - 1] if index - 1 < len(diameters) else default_diameter
        clear = (usable_width - count * diameter) / (count - 1) if count > 1 else usable_width
        horizontal_margin = clear - min_clear_spacing_mm
        if horizontal_margin < 0:
            failures.append(f"row {index} clear spacing {clear:.1f} mm is below {min_clear_spacing_mm:.1f} mm")
        # ``centre_from_tension_face`` is measured to the bar centre.  The
        # first row starts at cover + ligature + radius; each later row is one
        # diameter plus the clear row gap above the preceding row.  The old
        # expression added one extra diameter to every row, underestimating
        # effective depth and distorting both capacity and SLS results.
        if index == 1:
            centre = inputs.bottom.cover_mm + ligature + diameter / 2.0
        else:
            centre = previous_centre + previous_diameter / 2.0 + row_gap + diameter / 2.0
        row_centres.append(centre)
        rows.append(ReinforcementRow(index, count, clear, centre, diameter))
        previous_centre = centre
        previous_diameter = diameter
    last_diameter = rows[-1].bar_diameter_mm if rows else default_diameter
    vertical_margin = inputs.depth_mm - inputs.top.cover_mm - (row_centres[-1] + last_diameter / 2.0 if row_centres else 0.0)
    if len(rows) > 1 and row_gap < 0:
        failures.append("row gap is invalid")
    if vertical_margin < 0:
        failures.append("reinforcement rows do not fit within the available depth")
    total = sum(row_counts)
    total_area = sum(
        row.bar_count * math.pi * row.bar_diameter_mm**2 / 4.0
        for row in rows
    )
    centroid = (
        sum(
            row.bar_count
            * math.pi
            * row.bar_diameter_mm**2
            / 4.0
            * row.centre_from_tension_face_mm
            for row in rows
        )
        / total_area
        if total_area
        else 0.0
    )
    effective_depth = inputs.depth_mm - centroid
    horizontal_margin = min((row.clear_spacing_mm - min_clear_spacing_mm for row in rows), default=usable_width)
    congestion_class = "invalid" if failures else ("high" if horizontal_margin < 10 else "moderate" if horizontal_margin < 25 else "low")
    congestion = CongestionAssessment(horizontal_margin, vertical_margin, tuple(row_counts), len(rows), total, inputs.shear.legs, not failures, congestion_class, tuple(failures))
    arrangement = ReinforcementArrangement(total, diameters[0] if diameters else default_diameter, tuple(rows), len(rows), row_gap, centroid, effective_depth)
    return ReinforcementFitResult(arrangement, not failures, vertical_margin >= 0, cover_ok, horizontal_margin >= 0, aggregate_clearance_ok, not failures, congestion, tuple(failures))
