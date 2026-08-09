"""Pure physical fit calculation for longitudinal reinforcement."""
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
    min_clear_spacing_mm: float = 20.0,
    min_row_gap_mm: float = 25.0,
    aggregate_clearance_mm: float = 0.0,
) -> ReinforcementFitResult:
    """Evaluate one exact bottom-reinforcement arrangement; never selects it."""
    diameter = float(inputs.bottom.diameter_mm)
    ligature = float(inputs.shear.diameter_mm)
    usable_width = inputs.width_mm - 2.0 * (inputs.bottom.cover_mm + ligature + aggregate_clearance_mm)
    rows: list[ReinforcementRow] = []
    failures: list[str] = []
    row_centres: list[float] = []
    if not row_counts or any(int(count) < 2 for count in row_counts):
        failures.append("each reinforcement row must contain at least two bars")
    aggregate_clearance_ok = aggregate_clearance_mm >= 0.0
    cover_ok = usable_width > 0.0
    if not cover_ok:
        failures.append("cover, ligature and aggregate clearance leave no usable width")
    if not aggregate_clearance_ok:
        failures.append("aggregate clearance cannot be negative")
    for index, count in enumerate(row_counts, start=1):
        count = int(count)
        clear = (usable_width - count * diameter) / (count - 1) if count > 1 else usable_width
        horizontal_margin = clear - min_clear_spacing_mm
        if horizontal_margin < 0:
            failures.append(f"row {index} clear spacing {clear:.1f} mm is below {min_clear_spacing_mm:.1f} mm")
        # ``centre_from_tension_face`` is measured to the bar centre.  The
        # first row starts at cover + ligature + radius; each later row is one
        # diameter plus the clear row gap above the preceding row.  The old
        # expression added one extra diameter to every row, underestimating
        # effective depth and distorting both capacity and SLS results.
        first_row_centre = inputs.bottom.cover_mm + ligature + diameter / 2.0
        centre = first_row_centre + (index - 1) * (diameter + min_row_gap_mm)
        row_centres.append(centre)
        rows.append(ReinforcementRow(index, count, clear, centre))
    vertical_margin = inputs.depth_mm - inputs.top.cover_mm - (row_centres[-1] + diameter / 2.0 if row_centres else 0.0)
    if len(rows) > 1 and min_row_gap_mm < 0:
        failures.append("row gap is invalid")
    if vertical_margin < 0:
        failures.append("reinforcement rows do not fit within the available depth")
    total = sum(row_counts)
    centroid = sum(row.bar_count * row.centre_from_tension_face_mm for row in rows) / total if total else 0.0
    effective_depth = inputs.depth_mm - centroid
    horizontal_margin = min((row.clear_spacing_mm - min_clear_spacing_mm for row in rows), default=usable_width)
    congestion_class = "invalid" if failures else ("high" if horizontal_margin < 10 else "moderate" if horizontal_margin < 25 else "low")
    congestion = CongestionAssessment(horizontal_margin, vertical_margin, tuple(row_counts), len(rows), total, inputs.shear.legs, not failures, congestion_class, tuple(failures))
    arrangement = ReinforcementArrangement(total, diameter, tuple(rows), len(rows), min_row_gap_mm, centroid, effective_depth)
    return ReinforcementFitResult(arrangement, not failures, vertical_margin >= 0, cover_ok, horizontal_margin >= 0, aggregate_clearance_ok, not failures, congestion, tuple(failures))
