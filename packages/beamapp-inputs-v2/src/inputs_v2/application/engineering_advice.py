"""Structured, presentation-neutral Design Guide advice."""
from dataclasses import dataclass, asdict
from typing import Any, Literal

CheckStatus = Literal["pass", "fail", "overdesigned", "not_checked", "info", "provisional"]

@dataclass(frozen=True, slots=True)
class ClauseReference:
    standard: str
    edition: str
    clause: str
    title: str
    check_id: str

def clause_reference(check_id: str, metadata: dict[str, Any] | None) -> ClauseReference | None:
    """Build a reference only from calculation-owned metadata."""
    if not metadata:
        return None
    required = ("standard", "edition", "clause", "title")
    if any(not metadata.get(key) for key in required):
        return None
    return ClauseReference(*(str(metadata[key]) for key in required), check_id)

@dataclass(frozen=True, slots=True)
class EngineeringCheck:
    check_id: str
    display_name: str
    standard: str = "AS 3600"
    clause_reference: ClauseReference | None = None
    status: CheckStatus = "not_checked"
    utilisation: float | None = None
    limit: float = 1.0

    @property
    def clause(self) -> str:
        return (f"{self.clause_reference.standard} {self.clause_reference.edition} Clause "
                f"{self.clause_reference.clause}: {self.clause_reference.title}"
                if self.clause_reference else "Clause reference unavailable — review required")

@dataclass(frozen=True, slots=True)
class DesignChange:
    change_type: str
    before: str
    after: str
    reason_code: str


def _ratio(numerator: Any, denominator: Any) -> float | None:
    try:
        denominator_value = float(denominator)
        return abs(float(numerator)) / denominator_value if denominator_value > 0 else None
    except (TypeError, ValueError):
        return None


def authoritative_checks(inputs, result, required_groups: tuple[str, ...]) -> tuple[EngineeringCheck, ...]:
    """Build family-required checks from authoritative calculation payloads."""
    families = result.families
    checks: list[EngineeringCheck] = []

    def add(group: str, check_id: str, display: str, status: CheckStatus, util: float | None = None) -> None:
        payload = families.get(group, {})
        metadata = payload.get("check_metadata", {}).get(check_id)
        checks.append(EngineeringCheck(
            check_id, display,
            standard=str(metadata.get("standard", "AS 3600")) if metadata else "AS 3600",
            clause_reference=clause_reference(check_id, metadata),
            status=status, utilisation=util,
        ))

    requested = set(required_groups)
    bending = families.get("bending", {})
    if "bending" in requested:
        util = float(bending.get("util", 0.0) or 0.0)
        add("bending", "bending_capacity", "Flexural capacity", "fail" if util > 1 else "pass", util)
    if "minimum_tensile" in requested:
        add("bending", "minimum_flexural_strength", "Minimum tensile reinforcement",
            "fail" if str(bending.get("minimum_tensile_status", "")).upper() == "FAIL" else "pass",
            _ratio(bending.get("Ast_min_mm2"), bending.get("Ast_tension_mm2")))
    if "ductility" in requested:
        ductility = families.get("ductility", {})
        util = ductility.get("util")
        add("ductility", "bending_ductility", "Ductility and neutral-axis limit",
            "fail" if str(ductility.get("status", "")).upper() == "FAIL" else "pass",
            float(util) if util is not None else None)
    if "shear" in requested:
        shear = families.get("shear", {})
        demand = abs(float(inputs.actions.shear_force_kn))
        overall = _ratio(demand, shear.get("phi_Vu"))
        web = _ratio(demand, shear.get("Vu_max"))
        add("shear", "shear_strength", "Overall design shear strength", "fail" if overall is not None and overall > 1 else "pass", overall)
        add("shear", "shear_web_crushing", "Maximum shear strength and web crushing", "fail" if web is not None and web > 1 else "pass", web)
        add("shear", "concrete_shear_capacity", "Concrete shear contribution", "info")
        links_required = bool(shear.get("transverse_reinforcement_required"))
        links_provided = float(shear.get("Asv", 0.0) or 0.0) > 0.0
        add("shear", "transverse_reinforcement_required", "Transverse reinforcement requirement",
            "fail" if links_required and not links_provided else "pass")
        minimum_util = _ratio(shear.get("Asv_min_over_s"), shear.get("Asv_over_s"))
        minimum_status: CheckStatus = (
            "info" if not links_required and not links_provided
            else ("pass" if bool(shear.get("min_shear_ok")) else "fail")
        )
        add("shear", "minimum_shear_reinforcement", "Minimum shear reinforcement", minimum_status, minimum_util)
        transverse_util = _ratio(
            shear.get("transverse_max_leg_spacing_mm"),
            shear.get("transverse_spacing_limit_mm"),
        )
        transverse_status: CheckStatus = (
            "info"
            if not links_provided
            else "pass" if bool(shear.get("transverse_spacing_ok")) else "fail"
        )
        add(
            "shear",
            "transverse_shear_leg_spacing",
            "Transverse spacing between effective shear-link legs",
            transverse_status,
            transverse_util,
        )
        reinforcement_util = _ratio(demand, shear.get("Vus_kN")) if links_provided else None
        add("shear", "shear_reinforcement_capacity", "Shear reinforcement contribution", "info", reinforcement_util)
    if "serviceability" in requested:
        service = families.get("serviceability", {})
        present = bool(service.get("serviceability_loads_present"))
        util = service.get("deflection_util")
        state: CheckStatus = "not_checked" if not present else ("fail" if util is not None and float(util) > 1 else "pass")
        for check_id, display in (("short_term_deflection", "Short-term deflection"), ("long_term_deflection", "Additional long-term deflection"), ("span_depth_check", "Span-to-depth check")):
            add("serviceability", check_id, display, state, float(util) if util is not None else None)
    if "crack_control" in requested:
        crack = families.get("crack_control", {})
        present = bool(crack.get("serviceability_loads_present"))
        util = crack.get("util")
        state: CheckStatus = "provisional" if not present else ("fail" if util is not None and float(util) > 1 else "pass")
        add("crack_control", "general_crack_control", "General crack-control detailing", state, float(util) if util is not None else None)
        add("crack_control", "crack_table_method", "Crack-control table method", state, crack.get("table_util"))
        add("crack_control", "direct_crack_width", "Direct crack-width calculation", state, crack.get("width_util"))
    if "reinforcement_fit" in requested:
        fit = families.get("reinforcement_fit", {})
        checks.append(EngineeringCheck("reinforcement_fit", "Reinforcement fit and clear spacing", standard="", status="pass" if fit.get("accepted") else "fail"))
        metadata = fit.get("check_metadata", {}).get("durability_cover")
        checks.append(EngineeringCheck(
            "durability_cover", "Specified concrete cover",
            standard=str(metadata.get("standard", "")) if metadata else "",
            clause_reference=clause_reference("durability_cover", metadata),
            status="info",
        ))
    if "geometry" in requested:
        geometry = families.get("geometry", {})
        checks.append(EngineeringCheck(
            "geometry_proportion", "Section geometry and proportion", standard="",
            status="fail" if str(geometry.get("status", "")).upper() == "FAIL" else "pass",
            utilisation=_ratio(geometry.get("depth_width_ratio"), geometry.get("maximum_depth_width_ratio")),
        ))
    unique = tuple(dict((check.check_id, check) for check in checks).values())
    check_groups = {
        "bending_capacity": "bending",
        "minimum_flexural_strength": "minimum_tensile",
        "bending_ductility": "ductility",
        "shear_strength": "shear", "shear_web_crushing": "shear",
        "concrete_shear_capacity": "shear", "transverse_reinforcement_required": "shear",
        "minimum_shear_reinforcement": "shear", "shear_reinforcement_capacity": "shear",
        "transverse_shear_leg_spacing": "shear",
        "short_term_deflection": "serviceability", "long_term_deflection": "serviceability",
        "span_depth_check": "serviceability", "general_crack_control": "crack_control",
        "crack_table_method": "crack_control", "direct_crack_width": "crack_control",
        "reinforcement_fit": "reinforcement_fit", "durability_cover": "reinforcement_fit",
        "geometry_proportion": "geometry",
    }
    group_order = {group: index for index, group in enumerate(required_groups)}
    return tuple(sorted(
        unique,
        key=lambda check: group_order.get(check_groups.get(check.check_id, ""), len(group_order)),
    ))


def clause_references_from_checks(checks: tuple[EngineeringCheck, ...]) -> tuple[ClauseReference, ...]:
    refs = [check.clause_reference for check in checks if check.clause_reference is not None]
    return tuple(dict((ref.check_id, ref) for ref in refs).values())

@dataclass(frozen=True, slots=True)
class TargetBandBlocker:
    check_id: str
    blocker_code: str
    blocked_action: str
    governing_requirement: str
    clause_reference: ClauseReference | None = None

@dataclass(frozen=True, slots=True)
class EngineeringAdviceResult:
    current_checks: tuple[EngineeringCheck, ...]
    proposed_checks: tuple[EngineeringCheck, ...]
    recommended_changes: tuple[DesignChange, ...]
    engineering_effects: tuple[str, ...]
    governing_check: str
    clause_references: tuple[ClauseReference, ...]
    verified_compliance: bool
    apply_allowed: bool
    blocked_reason: str | None
    outcome_type: str
    blocker: TargetBandBlocker | None = None

def format_engineering_advice(advice: EngineeringAdviceResult) -> str:
    """Render concise senior-engineer advice from family-owned facts."""
    change = _natural_changes(advice.recommended_changes)
    if not change:
        change = "Retain the current design."
    current = _check_summary("Current", advice.current_checks)
    proposed_label = "Verified result" if advice.apply_allowed else "Assessed result"
    proposed = _check_summary(proposed_label, advice.proposed_checks)
    if (
        advice.outcome_type == "EXACT_STOP_PROVEN"
        and advice.verified_compliance
        and not advice.apply_allowed
    ):
        proposed = ""
    why = " ".join(advice.engineering_effects) if advice.engineering_effects else "No further safe change is available."
    if (
        not advice.apply_allowed
        and advice.blocked_reason
        and advice.outcome_type == "EXACT_STOP_PROVEN"
        and advice.verified_compliance
    ):
        why = advice.blocked_reason.rstrip(".") + ". The current design remains compliant."
    elif not advice.apply_allowed and advice.blocked_reason:
        blocker = advice.blocked_reason.rstrip(".")
        if len(blocker) > 1 and blocker[0].isupper() and blocker[1].islower():
            blocker = blocker[0].lower() + blocker[1:]
        why = f"{why} This revision cannot yet be applied because {blocker}."
    refs = "; ".join(dict.fromkeys(
        f"{ref.standard} {ref.edition} Clause {ref.clause}: {ref.title}"
        for ref in advice.clause_references
    ))
    missing = tuple(dict.fromkeys(
        check.display_name
        for check in advice.current_checks + advice.proposed_checks
        if check.standard and check.clause_reference is None
    ))
    reference_text = f"References: {refs}." if refs else ""
    if missing:
        fallback = f"Clause reference unavailable — review required for: {', '.join(missing)}."
        reference_text = f"{reference_text} {fallback}".strip()
    if advice.apply_allowed:
        change_text = f"Recommended revision: {change}"
    elif advice.recommended_changes:
        # A blocked trial is evidence from the search, not an instruction to
        # modify the design.  Keep that distinction visible in every family.
        change_text = f"Assessed revision: {change}"
    else:
        change_text = change
    # Keep clause metadata on the typed advice contract for reports and
    # diagnostics, but omit the separate References paragraph from the
    # compact Design Brain card.
    sections = (current, change_text, proposed, why)
    return "\n\n".join(section for section in sections if section).strip()


def _check_summary(label: str, checks: tuple[EngineeringCheck, ...]) -> str:
    """Summarise authoritative checks without inventing engineering facts."""
    if not checks:
        return ""
    failed = tuple(check for check in checks if check.status == "fail")
    # Family owners publish checks in governing order.  When everything
    # passes, report that primary check rather than whichever supporting
    # limit happens to have the largest numerical ratio (for example k_u).
    primary_ids = {
        "bending_capacity",
        "shear_strength",
        "direct_crack_width",
        "short_term_deflection",
        "long_term_deflection",
    }
    primary_numeric = tuple(
        check for check in checks
        if check.check_id in primary_ids and check.utilisation is not None
    )
    if not primary_numeric:
        first_numeric = next((check for check in checks if check.utilisation is not None), None)
        primary_numeric = (first_numeric,) if first_numeric is not None else ()
    selected = failed or primary_numeric
    if not selected:
        return ""

    statements: list[str] = []
    for check in selected:
        status = "fails" if check.status == "fail" else (
            "passes" if check.status == "pass" else check.status.replace("_", " ")
        )
        if check.utilisation is None:
            statements.append(f"{check.display_name} {status}")
        else:
            statements.append(f"{check.display_name} {status} at {check.utilisation:.2f} utilisation")
    return f"{label}: {'; '.join(statements)}."


def _natural_changes(changes: tuple[DesignChange, ...]) -> str:
    """Turn canonical field changes into compact structural-engineering prose."""
    if not changes:
        return "Retain the current design."
    by_type = {c.change_type: c for c in changes}
    parts: list[str] = []
    def number(value: str) -> str:
        import re
        match = re.search(r"[-+]?\d+(?:\.\d+)?", value)
        if not match:
            return value
        raw = float(match.group())
        return str(int(raw)) if raw.is_integer() else str(raw)
    if "width_mm" in by_type:
        c = by_type["width_mm"]; verb = "Increase" if float(number(c.after)) > float(number(c.before)) else "Reduce"
        parts.append(f"{verb} the beam width from {number(c.before)} mm to {number(c.after)} mm")
    if "depth_mm" in by_type:
        c = by_type["depth_mm"]; verb = "Increase" if float(number(c.after)) > float(number(c.before)) else "Reduce"
        parts.append(f"{verb} the beam depth from {number(c.before)} mm to {number(c.after)} mm")
    if "bottom_bars" in by_type or "bottom_diameter_mm" in by_type:
        count = number(by_type.get("bottom_bars", DesignChange("", "", "", "")).after or by_type.get("bottom_bars", DesignChange("", "", "", "")).before) if "bottom_bars" in by_type else ""
        dia = number(by_type.get("bottom_diameter_mm", DesignChange("", "", "", "")).after or by_type.get("bottom_diameter_mm", DesignChange("", "", "", "")).before) if "bottom_diameter_mm" in by_type else ""
        old_count = number(by_type["bottom_bars"].before) if "bottom_bars" in by_type else count
        old_dia = number(by_type["bottom_diameter_mm"].before) if "bottom_diameter_mm" in by_type else dia
        new = f"{count}-N{dia}" if count and dia else "the revised bottom reinforcement"
        old = f"{old_count}-N{old_dia}" if old_count and old_dia else "the existing bottom reinforcement"
        parts.append(f"revise the bottom reinforcement from {old} to {new} bars")
    if "shear_diameter_mm" in by_type or "shear_spacing_mm" in by_type or "shear_legs" in by_type:
        diameter_change = by_type.get("shear_diameter_mm")
        legs_change = by_type.get("shear_legs")
        spacing_change = by_type.get("shear_spacing_mm")
        dia = number(diameter_change.after) if diameter_change else ""
        legs = number(legs_change.after) if legs_change else ""
        spacing = number(spacing_change.after) if spacing_change else ""
        old_dia = number(diameter_change.before) if diameter_change else dia
        old_legs = number(legs_change.before) if legs_change else legs
        old_spacing = number(spacing_change.before) if spacing_change else spacing
        old_off = old_dia == "0" or old_legs == "0"
        new_off = dia == "0" or legs == "0"
        if new_off:
            parts.append("Remove the shear ligatures")
        elif old_off:
            parts.append(f"Introduce N{dia} {legs}-leg closed ligatures at {spacing} mm centres")
        else:
            parts.append(
                f"Replace N{old_dia} {old_legs}-leg ligatures at {old_spacing} mm centres "
                f"with N{dia} {legs}-leg closed ligatures at {spacing} mm centres"
            )
    if "layer_count" in by_type:
        parts.append(f"arrange the reinforcement in {by_type['layer_count'].after}")
    return "; ".join(parts).capitalize().replace("-n", "-N").replace(" n", " N") + "."

def effects_for_changes(changes: tuple[DesignChange, ...], engineering_purpose: str = "") -> tuple[str, ...]:
    import re

    by_type = {change.change_type: change for change in changes}

    def value(change: DesignChange | None, side: str, default: float = 0.0) -> float:
        if change is None:
            return default
        matches = re.findall(r"[-+]?\d+(?:\.\d+)?", getattr(change, side))
        return float(matches[-1]) if matches else default

    result: list[str] = []
    width = by_type.get("width_mm")
    if width is not None:
        result.append(
            "The wider web increases the concrete shear-resisting area and provides additional reinforcement space."
            if value(width, "after") > value(width, "before")
            else "The narrower section removes excess concrete while preserving reinforcement space and capacity."
        )

    depth = by_type.get("depth_mm")
    if depth is not None:
        result.append(
            "The greater depth increases the internal lever arm and section stiffness."
            if value(depth, "after") > value(depth, "before")
            else "The reduced depth removes excess concrete while retaining the verified strength and detailing requirements."
        )

    bars = by_type.get("bottom_bars")
    diameter = by_type.get("bottom_diameter_mm")
    if bars is not None or diameter is not None:
        old_count = value(bars, "before", value(bars, "after", 1.0))
        new_count = value(bars, "after", old_count)
        old_diameter = value(diameter, "before", value(diameter, "after", 1.0))
        new_diameter = value(diameter, "after", old_diameter)
        old_area_factor = old_count * old_diameter**2
        new_area_factor = new_count * new_diameter**2
        result.append(
            "The revised bottom reinforcement increases tensile resistance while retaining a buildable bar arrangement."
            if new_area_factor > old_area_factor
            else "The revised bottom reinforcement removes unnecessary steel while retaining the verified flexural resistance."
        )

    shear_diameter = by_type.get("shear_diameter_mm")
    shear_legs = by_type.get("shear_legs")
    shear_spacing = by_type.get("shear_spacing_mm")
    if shear_diameter is not None or shear_legs is not None or shear_spacing is not None:
        old_diameter = value(shear_diameter, "before", value(shear_diameter, "after"))
        new_diameter = value(shear_diameter, "after", old_diameter)
        old_legs = value(shear_legs, "before", value(shear_legs, "after"))
        new_legs = value(shear_legs, "after", old_legs)
        old_spacing = max(value(shear_spacing, "before", value(shear_spacing, "after", 1.0)), 1.0)
        new_spacing = max(value(shear_spacing, "after", old_spacing), 1.0)
        old_density = old_diameter**2 * old_legs / old_spacing
        new_density = new_diameter**2 * new_legs / new_spacing
        if new_diameter == 0 or new_legs == 0:
            result.append("Removing the ligatures eliminates unnecessary transverse steel where the verified shear checks permit it.")
        elif old_diameter == 0 or old_legs == 0:
            result.append("The new ligatures provide transverse reinforcement across potential diagonal shear cracks.")
        elif new_density > old_density:
            result.append("The revised ligature arrangement increases the transverse steel effective across the web.")
        else:
            result.append("The revised ligature arrangement removes unnecessary transverse steel while retaining adequate shear resistance.")

    if "layer_count" in by_type:
        result.append("The layered arrangement preserves clear spacing, reinforcement fit and effective depth.")

    # Prefer specific physical explanations over repeating the broader family
    # purpose. Retain that purpose only when there is no field-level change.
    if not result and engineering_purpose:
        result.append(engineering_purpose)
    return tuple(dict.fromkeys(result))

def verified_changes(current, proposal, row_counts: tuple[int, ...] = ()) -> tuple[DesignChange, ...]:
    """Describe only proposal fields that differ from the current model."""
    p = asdict(proposal)
    before = {
        "width_mm": current.width_mm, "depth_mm": current.depth_mm,
        "bottom_bars": current.bottom.bars, "bottom_diameter_mm": current.bottom.diameter_mm,
        "shear_diameter_mm": current.shear.diameter_mm, "shear_legs": current.shear.legs,
        "shear_spacing_mm": current.shear.spacing_mm,
    }
    labels = {
        "width_mm": "beam width", "depth_mm": "beam depth", "bottom_bars": "bottom bar count",
        "bottom_diameter_mm": "bottom bar diameter", "shear_diameter_mm": "shear link diameter",
        "shear_legs": "shear link legs", "shear_spacing_mm": "shear link spacing",
    }
    changes = []
    for key, old in before.items():
        new = p.get(key, old)
        if new != old:
            changes.append(DesignChange(key, f"{labels[key]} {old}", f"{labels[key]} {new}", "verified_family_change"))
    # A reinforcement change is always described as complete N-bar notation.
    # Include the unchanged companion value in the structured contract.
    changed_keys = {c.change_type for c in changes}
    if "bottom_bars" in changed_keys and "bottom_diameter_mm" not in changed_keys:
        changes.append(DesignChange("bottom_diameter_mm", f"bottom bar diameter {current.bottom.diameter_mm}", f"bottom bar diameter {p.get('bottom_diameter_mm', current.bottom.diameter_mm)}", "reinforcement_context"))
    if "bottom_diameter_mm" in changed_keys and "bottom_bars" not in changed_keys:
        changes.append(DesignChange("bottom_bars", f"bottom bar count {current.bottom.bars}", f"bottom bar count {p.get('bottom_bars', current.bottom.bars)}", "reinforcement_context"))
    shear_keys = {"shear_diameter_mm", "shear_legs", "shear_spacing_mm"}
    if changed_keys & shear_keys:
        shear_context = {
            "shear_diameter_mm": (current.shear.diameter_mm, p.get("shear_diameter_mm", current.shear.diameter_mm), "shear link diameter"),
            "shear_legs": (current.shear.legs, p.get("shear_legs", current.shear.legs), "shear link legs"),
            "shear_spacing_mm": (current.shear.spacing_mm, p.get("shear_spacing_mm", current.shear.spacing_mm), "shear link spacing"),
        }
        for key, (old, new, label) in shear_context.items():
            if key not in changed_keys:
                changes.append(DesignChange(key, f"{label} {old}", f"{label} {new}", "reinforcement_context"))
    if row_counts:
        current_rows = (
            tuple(row.bar_count for row in current.bottom_arrangement.rows)
            if current.bottom_arrangement is not None
            else (current.bottom.bars,)
        )
        # A count change within a single row is already expressed in N-bar
        # notation. Publish a layer statement only when the actual row layout
        # changes, or when a multi-row distribution is rearranged.
        if len(row_counts) != len(current_rows) or (len(row_counts) > 1 and tuple(row_counts) != current_rows):
            before_rows = (
                "one reinforcement row"
                if len(current_rows) == 1
                else f"{len(current_rows)} rows ({' + '.join(map(str, current_rows))})"
            )
            after_rows = (
                "one reinforcement row"
                if len(row_counts) == 1
                else f"{len(row_counts)} rows ({' + '.join(map(str, row_counts))})"
            )
            changes.append(DesignChange("layer_count", before_rows, after_rows, "verified_layered_arrangement"))
    return tuple(changes)
