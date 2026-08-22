"""Production adapter from Batch Design rows to the existing Design Brain path."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from batch_design.models import BatchBeamCase, BatchDesignResult, BatchImportWarning
from batch_design.sections import normalise_concrete_section_label, parse_concrete_section_dimensions


DesignGuidanceRunner = Callable[..., dict[str, Any]]
BaseStateProvider = Callable[[], Mapping[str, Any]]


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _selected_action(case: BatchBeamCase, preferred_key: str, fallback_keys: tuple[str, ...]) -> tuple[float, str]:
    preferred = _as_float(getattr(case, preferred_key, None))
    if preferred is not None:
        return preferred, preferred_key
    candidates: list[tuple[float, str]] = []
    for key in fallback_keys:
        value = _as_float(getattr(case, key, None))
        if value is not None:
            candidates.append((value, key))
    if not candidates:
        return 0.0, preferred_key
    value, key = max(candidates, key=lambda item: abs(float(item[0])))
    return float(value), key


def batch_case_to_design_brain_state(
    case: BatchBeamCase,
    base_state: Mapping[str, Any] | None = None,
    *,
    assumptions: Mapping[str, Any] | None = None,
    preserve_base_geometry: bool = False,
) -> dict[str, Any]:
    """Overlay a normalized batch row onto a single-beam Design Brain state.

    The existing Design Brain remains responsible for design calculation and
    recommendation selection. This function only maps final member actions and
    optional imported section metadata into the state shape already consumed by
    the single-beam path.
    """

    state = dict(base_state or {})
    assumed = dict(assumptions or {})
    moment_key = str(assumed.get("moment_component") or assumed.get("moment_axis") or "mz_star").strip()
    shear_key = str(assumed.get("shear_component") or assumed.get("shear_axis") or "vy_star").strip()
    if moment_key not in {"mx_star", "my_star", "mz_star"}:
        moment_key = "mz_star"
    if shear_key not in {"vy_star", "vz_star"}:
        shear_key = "vy_star"

    moment, moment_source = _selected_action(case, moment_key, ("mz_star", "my_star", "mx_star"))
    shear, shear_source = _selected_action(case, shear_key, ("vy_star", "vz_star"))
    axial = float(_as_float(case.n_star) or 0.0)
    torsion = float(_as_float(case.mx_star) or 0.0)

    state.update(
        {
            "uls_Mstar": float(moment),
            "Mu_star": float(moment),
            "uls_Mstar_pos_manual": max(0.0, float(moment)),
            "uls_Mstar_neg_manual": max(0.0, -float(moment)),
            "uls_Vstar": abs(float(shear)),
            "Vu_star": abs(float(shear)),
            "uls_Nstar": axial,
            "N_star": axial,
            "Tu_star": torsion,
            "actions_mode": "manual",
            "actions_source": "batch_design_imported_member_actions",
            "batch_design_member_id": case.member_id,
            "batch_design_source": str(case.source.value if hasattr(case.source, "value") else case.source),
            "batch_design_action_mapping": {
                "moment_component": moment_source,
                "shear_component": shear_source,
            },
        }
    )
    if case.length is not None:
        state["span_L_m"] = float(case.length)

    parsed_section = parse_concrete_section_dimensions(case.existing_section)
    if parsed_section and not preserve_base_geometry:
        state["b"] = parsed_section.width
        state["bw"] = parsed_section.width
        state["D"] = parsed_section.depth
        state["batch_design_concrete_section"] = parsed_section.label()

    return state


def _payload_overview(payload: Mapping[str, Any]) -> dict[str, Any]:
    debug = dict(payload.get("debug_trace") or {})
    overview = debug.get("overview")
    return dict(overview) if isinstance(overview, dict) else {}


def _payload_design_brain_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = payload.get("design_brain_result")
    return dict(result) if isinstance(result, dict) else {}


def batch_design_result_from_design_brain_payload(
    case: BatchBeamCase,
    payload: Mapping[str, Any],
    *,
    mapped_state: Mapping[str, Any] | None = None,
) -> BatchDesignResult:
    overview = _payload_overview(payload)
    design_result = _payload_design_brain_result(payload)
    statuses = dict(overview.get("statuses") or {})
    any_fail = bool(overview.get("any_fail", False))
    all_key_pass = bool(overview.get("all_key_pass", not any_fail))
    passed = bool(all_key_pass and not any_fail)
    selected_section = (
        design_result.get("selected_candidate_label")
        or design_result.get("selected_section")
        or normalise_concrete_section_label(case.existing_section)
    )
    utilisation = _as_float(
        overview.get("worst_util")
        if overview.get("worst_util") is not None
        else design_result.get("utilisation")
    )
    raw_result = {
        "design_brain_payload": dict(payload),
        "mapped_state": dict(mapped_state or {}),
        "statuses": statuses,
    }
    return BatchDesignResult(
        member_id=case.member_id,
        input_case=case,
        passed=passed,
        selected_section=None if selected_section is None else str(selected_section),
        utilisation=utilisation,
        design_brain_result=design_result,
        raw_result=raw_result,
    )


class BatchDesignGuidanceAdapter:
    """Adapter that delegates each batch row to the existing single-beam path."""

    def __init__(
        self,
        *,
        base_state_provider: BaseStateProvider,
        design_guidance_runner: DesignGuidanceRunner,
        request_kind: str = "auto_design",
    ) -> None:
        self._base_state_provider = base_state_provider
        self._design_guidance_runner = design_guidance_runner
        self._request_kind = str(request_kind or "auto_design")

    def evaluate_current_case(
        self,
        case: BatchBeamCase,
        *,
        assumptions: Mapping[str, Any] | None = None,
        base_state: Mapping[str, Any] | None = None,
    ) -> BatchDesignResult:
        """Calculate the entered beam before any optimisation search runs."""

        return self.run_case(
            case,
            assumptions=assumptions,
            base_state=base_state,
            request_kind="current_design",
        )

    def run_case(
        self,
        case: BatchBeamCase,
        *,
        assumptions: Mapping[str, Any] | None = None,
        base_state: Mapping[str, Any] | None = None,
        request_kind: str | None = None,
    ) -> BatchDesignResult:
        mapped_state = batch_case_to_design_brain_state(
            case,
            self._base_state_provider() if base_state is None else base_state,
            assumptions=assumptions,
            preserve_base_geometry=base_state is not None,
        )
        payload = self._design_guidance_runner(
            mapped_state,
            guidance_debug_verbose=True,
            debug_enabled=False,
            request_kind=str(request_kind or self._request_kind),
        )
        if not isinstance(payload, dict):
            return BatchDesignResult(
                member_id=case.member_id,
                input_case=case,
                passed=False,
                error="Design Brain runner returned a non-dict payload.",
                warnings=[
                    BatchImportWarning(
                        row_number=None,
                        member_id=case.member_id,
                        severity="error",
                        message="Design Brain runner returned a non-dict payload.",
                    )
                ],
            )
        return batch_design_result_from_design_brain_payload(
            case,
            payload,
            mapped_state=mapped_state,
        )
