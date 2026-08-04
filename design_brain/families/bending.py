"""Bending-owned Design Brain selection helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Any

from design_brain.contracts import bottom_arrangement_to_shared_updates


def _bottom_reo_complexity_int(value: Any, default: int) -> int:
    if value is None:
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def calculate_bottom_reo_complexity(
    *,
    bar_count: Any = 0,
    row_count: Any = 1,
    reo_congestion_index: Any = 0.0,
    bot1_count: Any = 0,
    bot2_count: Any = 0,
) -> float:
    """Calculate bottom-reo ranking complexity from primitive inputs only."""

    total_bar_count = int(bar_count or 0)
    row_count_value = int(row_count or 1)
    congestion_index = float(reo_congestion_index or 0.0)
    count_1 = _bottom_reo_complexity_int(bot1_count, 0)
    count_2 = _bottom_reo_complexity_int(bot2_count, 0)
    layer_imbalance_penalty = 0.0 if count_2 <= 0 else float(abs(count_1 - count_2))
    return (
        total_bar_count * 1.0
        + row_count_value * 8.0
        + congestion_index * 12.0
        + layer_imbalance_penalty * 3.0
    )


@dataclass(frozen=True)
class BottomReoSelectedCandidateDecision:
    """Typed proof record for normal bottom-reinforcement selection.

    This record describes the already-run page-local selector chain. It does not
    perform ranking, call evaluators, or mutate candidate/result objects.
    """

    filtered_candidate_identities: tuple[str, ...]
    filtered_candidate_order_hash: str | None
    ranked_candidate_identities: tuple[str, ...]
    ranked_candidate_order_hash: str | None
    selected_candidate_id: str | None
    selected_candidate_identity: str | None
    selected_candidate_trace_hash: str | None
    selected_family_tag: str | None
    selected_candidate_update_keys: tuple[str, ...]
    selected_candidate_updates_hash: str | None
    final_result_update_keys: tuple[str, ...]
    final_result_updates_hash: str | None
    selector_input_candidate_id: str | None
    selector_output_candidate_id: str | None
    selector_input_candidate_identity: str | None
    selector_output_candidate_identity: str | None
    compound_preference_changed: bool
    compound_preference_selected: bool
    post_selector_guard_result: str
    no_result_reason: str | None
    selected_score: float | None
    selected_bending_util: float | None
    selected_candidate_post_util: float | None
    target_low: float | None
    target_high: float | None
    selected_reaches_target_band: bool | None
    selected_distance_to_target_band: float | None
    selected_because_reaches_band: bool | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BottomReoSelectorResult:
    """Typed proof record for the local normal-bottom selector outcome."""

    status: str
    selected_reason: str | None
    no_candidate_reason: str | None
    selected_candidate_id: str | None
    selected_candidate_identity: str | None
    selected_candidate_trace_hash: str | None
    selected_update_keys: tuple[str, ...]
    selected_updates_hash: str | None
    strict_band_winner_seen: bool
    strict_band_winner_accepted: bool
    strict_band_rejected_reason: str | None
    legacy_rejection_reason: str | None
    winner_pool_mode: str | None
    selected_because_band: bool
    selected_score: float | None
    selected_bending_util: float | None
    selected_candidate_post_util: float | None
    selected_reaches_target_band: bool | None
    target_low: float | None
    target_high: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_bottom_reo_selector_result_record(
    *,
    status: str,
    selected_reason: str | None,
    no_candidate_reason: str | None,
    selected_candidate_id: Any = None,
    selected_candidate_identity: Any = None,
    selected_candidate_trace_hash: Any = None,
    selected_update_keys: tuple[str, ...] | list[str] | None = None,
    selected_updates_hash: Any = None,
    strict_band_winner_seen: bool = False,
    strict_band_winner_accepted: bool = False,
    strict_band_rejected_reason: str | None = None,
    legacy_rejection_reason: str | None = None,
    winner_pool_mode: Any = None,
    selected_because_band: bool = False,
    selected_score: float | None = None,
    selected_bending_util: float | None = None,
    selected_candidate_post_util: float | None = None,
    selected_reaches_target_band: bool | None = None,
    target_low: float | None = None,
    target_high: float | None = None,
) -> BottomReoSelectorResult:
    """Build the family-owned selector result proof record from plain values."""

    return BottomReoSelectorResult(
        status=str(status or ""),
        selected_reason=str(selected_reason) if selected_reason else None,
        no_candidate_reason=str(no_candidate_reason) if no_candidate_reason else None,
        selected_candidate_id=str(selected_candidate_id) if selected_candidate_id is not None else None,
        selected_candidate_identity=str(selected_candidate_identity) if selected_candidate_identity is not None else None,
        selected_candidate_trace_hash=(
            str(selected_candidate_trace_hash) if selected_candidate_trace_hash is not None else None
        ),
        selected_update_keys=tuple(sorted(str(key) for key in (selected_update_keys or ()))),
        selected_updates_hash=str(selected_updates_hash) if selected_updates_hash is not None else None,
        strict_band_winner_seen=bool(strict_band_winner_seen),
        strict_band_winner_accepted=bool(strict_band_winner_accepted),
        strict_band_rejected_reason=str(strict_band_rejected_reason) if strict_band_rejected_reason else None,
        legacy_rejection_reason=str(legacy_rejection_reason) if legacy_rejection_reason else None,
        winner_pool_mode=str(winner_pool_mode) if winner_pool_mode is not None else None,
        selected_because_band=bool(selected_because_band),
        selected_score=selected_score,
        selected_bending_util=selected_bending_util,
        selected_candidate_post_util=selected_candidate_post_util,
        selected_reaches_target_band=(
            bool(selected_reaches_target_band) if selected_reaches_target_band is not None else None
        ),
        target_low=_record_float(target_low),
        target_high=_record_float(target_high),
    )


def build_bottom_reo_selector_result_record_from_candidate(
    *,
    selected_candidate: dict | None,
    status: str,
    selected_reason: str | None,
    no_candidate_reason: str | None,
    strict_band_winner_seen: bool,
    strict_band_winner_accepted: bool,
    strict_band_rejected_reason: str | None,
    legacy_rejection_reason: str | None,
    target_low: float | None,
    target_high: float | None,
) -> BottomReoSelectorResult:
    """Project selector-result trace identity from a plain selected candidate."""

    selected = dict(selected_candidate or {}) if isinstance(selected_candidate, dict) else {}
    updates = dict(selected.get("updates") or {})
    overview = dict(selected.get("overview") or {})
    utils = dict(overview.get("utils") or {})
    candidate_hash = _stable_boundary_hash(selected) if selected else None
    selected_candidate_id = selected.get("candidate_id") or selected.get("source_candidate_id") or None
    selected_identity = (
        str(selected_candidate_id)
        if selected_candidate_id
        else (f"trace:{candidate_hash}" if candidate_hash else None)
    )
    return build_bottom_reo_selector_result_record(
        status=status,
        selected_reason=selected_reason,
        no_candidate_reason=no_candidate_reason,
        selected_candidate_id=selected_candidate_id,
        selected_candidate_identity=selected_identity,
        selected_candidate_trace_hash=candidate_hash,
        selected_update_keys=tuple(sorted(str(key) for key in updates.keys())),
        selected_updates_hash=_stable_boundary_hash(updates) if selected else None,
        strict_band_winner_seen=strict_band_winner_seen,
        strict_band_winner_accepted=strict_band_winner_accepted,
        strict_band_rejected_reason=strict_band_rejected_reason,
        legacy_rejection_reason=legacy_rejection_reason,
        winner_pool_mode=selected.get("winner_pool_mode") if selected.get("winner_pool_mode") is not None else None,
        selected_because_band=bool(selected.get("winning_candidate_selected_from_band_reachers")),
        selected_score=_record_float(selected.get("score")),
        selected_bending_util=_record_float(utils.get("bending")),
        selected_candidate_post_util=_record_float(selected.get("candidate_post_util")),
        selected_reaches_target_band=(
            bool(selected.get("candidate_reaches_target_band"))
            if selected.get("candidate_reaches_target_band") is not None
            else None
        ),
        target_low=target_low,
        target_high=target_high,
    )


@dataclass(frozen=True)
class BottomReoCandidatePoolBoundary:
    """Typed proof record for the normal bottom-reo candidate pool.

    This boundary describes candidate pool/order surfaces produced by the
    existing page-local recommendation path. It does not generate, rank, select,
    or mutate candidates.
    """

    input_state_hash: str | None
    current_bottom_reo_layout: dict[str, Any]
    generated_candidate_count: int
    generated_candidate_ids: tuple[str, ...]
    generated_candidate_order_hash: str | None
    filtered_candidate_count: int
    filtered_candidate_ids: tuple[str, ...]
    filtered_candidate_order_hash: str | None
    ranked_candidate_count: int
    ranked_candidate_ids: tuple[str, ...]
    ranked_candidate_order_hash: str | None
    selected_candidate_id: str | None
    selected_update_payload: dict[str, Any]
    selected_util_surfaces: dict[str, Any]
    reject_skip_reasons: dict[str, Any]
    target_band_status: dict[str, Any]
    source_family_runtime_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BottomReoEvaluatedCandidateFilterBoundary:
    """Typed proof record for pre-rank bottom-reo evaluation/filtering.

    This boundary records arrangement-to-evaluated-candidate/filter surfaces
    only. It does not rank, select, build CTA/action payloads, publish, or
    mutate candidates.
    """

    input_arrangement_pool_hash: str | None
    source_family_runtime_id: str | None
    evaluated_candidate_count: int
    accepted_prerank_candidate_count: int
    rejected_candidate_count: int
    accepted_prerank_candidate_ids: tuple[str, ...]
    accepted_prerank_order_hash: str | None
    records: tuple[dict[str, Any], ...]
    pre_rank_surface_hash: str | None
    forbidden_fields_present: tuple[str, ...]
    ranking_selection_cta_publication_absent: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BottomReoEvaluatedCandidateFilterRecord:
    """Primitive raw record for bottom-reo evaluation/filter proof.

    This record owns shape/normalization only. It does not observe evaluator
    execution, candidate objects, page trace state, or filtering control flow.
    """

    order_index: int
    band: int
    arrangement_signature: str | None
    arrangement: dict[str, Any]
    arrangement_update_keys: tuple[str, ...]
    arrangement_update_payload_hash: str | None
    evaluator_returned: bool | None
    status: str
    reject_reason: str | None
    accepted_prerank_candidate_identity: str | None
    candidate_update_keys: tuple[str, ...]
    candidate_update_payload_hash: str | None
    utilisation_summary: dict[str, Any]
    target_band_status: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BottomReoAcceptedCandidate:
    """Derived accepted-candidate proof record for pre-rank bottom reo.

    Built only from evaluated/filter boundary records. It does not observe live
    candidate dictionaries, ranking, selection, CTA/action, publication, or
    page/runtime state.
    """

    accepted_order_index: int
    source_record_order_index: int
    candidate_identity: str
    candidate_update_keys: tuple[str, ...]
    candidate_update_payload_hash: str | None
    arrangement_signature: str | None
    arrangement: dict[str, Any]
    utilisation_summary: dict[str, Any]
    acceptance_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BottomReoScoredCandidate:
    """Derived scored-candidate proof record for pre-rank bottom reo.

    Built only from accepted-candidate records and explicit primitive
    score/source values. It does not sort, rank, select, publish, mutate, or
    observe page/runtime state.
    """

    scored_order_index: int
    source_accepted_candidate_index: int
    candidate_identity: str
    candidate_update_keys: tuple[str, ...]
    candidate_update_payload_hash: str | None
    arrangement_signature: str | None
    utilisation_summary: dict[str, Any]
    score_value: float | None
    score_source: str
    score_inputs: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BottomReoRankedCandidate:
    """Post-sort proof record for bottom reo ranking.

    Built from explicit rank result data after the page-local ranking wrapper
    has run. It does not sort, prune, select, publish, mutate, or observe
    page/runtime state.
    """

    ranked_order_index: int
    source_scored_candidate_identity: str
    candidate_identity: str
    rank_status: str
    sort_key_summary: dict[str, Any]
    dedupe_key_summary: dict[str, Any]
    reo_complexity_before: float | None
    reo_complexity_after: float | None
    kept_candidate_hash_inputs: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BottomReoRankingPolicyInput:
    """Family-owned proof record for bottom-reo ranking-policy inputs.

    Built only from explicit primitive/data values gathered by the page-local
    path. It does not run ranking policy, prune candidates, select a result,
    build CTA/action payloads, publish, mutate, or observe UI/session/debug
    state.
    """

    policy_input_order_index: int
    candidate_identity: str
    source_scored_candidate_identity: str
    state_hash: str | None
    state_summary: dict[str, Any]
    resolved_design_action_dedupe_key_hash: str | None
    resolved_design_action_summary: dict[str, Any]
    objective_util: float | None
    util_distance: float | None
    target_band_inputs: dict[str, Any]
    row_bar_congestion_fields: dict[str, Any]
    dimension_primitives: dict[str, Any]
    shallow_tier: Any
    shallow_tier_label: Any
    shallow_metrics: dict[str, Any]
    ductility: dict[str, Any]
    reo_complexity_primitives: dict[str, Any]
    reo_complexity_before_setdefault: float | None
    reo_complexity_after_setdefault: float | None
    sort_key_surface: Any
    dominance_dedupe_surface: dict[str, Any]
    policy_input_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BottomReoRankingWrapperProof:
    """Proof-only bottom-reo ranking wrapper output.

    Built only from explicit ``BottomReoRankingPolicyInput`` records. It does
    not return candidate dictionaries, mutate inputs, select a final
    recommendation, or include CTA/action/publication/UI/session/debug fields.
    """

    ordered_candidate_identities: tuple[str, ...]
    kept_candidate_identities: tuple[str, ...]
    pruned_candidate_identities: tuple[str, ...]
    rank_decisions: tuple[dict[str, Any], ...]
    dominance_decision_summaries: tuple[dict[str, Any], ...]
    sort_key_hash: str | None
    kept_candidate_hash: str | None
    proof_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BottomReoRankingCallbackPolicyProof:
    """Proof-only callback-policy surface for bottom-reo ranking.

    Built from typed policy inputs plus explicit primitive live comparison
    surfaces captured outside the family. It does not receive live candidate
    dictionaries, run product ranking, select a repair, publish, mutate, or
    include CTA/action/UI/session/debug fields.
    """

    bounded_keep_limit: int
    typed_sort_key_by_identity: dict[str, Any]
    typed_dedupe_key_by_identity: dict[str, Any]
    typed_dominance_decisions: tuple[dict[str, Any], ...]
    typed_ordered_identities: tuple[str, ...]
    typed_kept_identities: tuple[str, ...]
    typed_pruned_identities: tuple[str, ...]
    live_sort_key_by_identity: dict[str, Any]
    live_dedupe_key_by_identity: dict[str, Any]
    live_dominance_decisions: tuple[dict[str, Any], ...]
    live_ordered_identities: tuple[str, ...]
    live_kept_identities: tuple[str, ...]
    live_pruned_identities: tuple[str, ...]
    parity_hash_inputs: dict[str, Any]
    proof_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BottomReoRankingResultBoundary:
    """Proof-only bottom-reo ranking result boundary.

    Built from normalized ranking proof surfaces only. It does not consume live
    candidate dictionaries, run ranking, mutate candidates, select a final
    recommendation, build CTA/action payloads, publish, or include UI/session
    debug fields.
    """

    candidate_count: int
    policy_input_hashes: tuple[str, ...]
    ordered_candidate_identities: tuple[str, ...]
    kept_candidate_identities: tuple[str, ...]
    pruned_candidate_identities: tuple[str, ...]
    decision_summaries: tuple[dict[str, Any], ...]
    ordered_hash: str | None
    kept_hash: str | None
    pruned_hash: str | None
    callback_handoff_hash: str | None
    forbidden_fields_present: tuple[str, ...]
    ranking_result_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BottomReoSelectorWrapperProof:
    """Proof-only bottom-reo selector wrapper output.

    Built from explicit primitive/data values emitted by the current
    page-local selector path. It does not receive candidate dictionaries,
    mutate inputs, select live recommendations, build CTA/action payloads,
    publish, or observe UI/session/debug state.
    """

    ranked_candidate_identities: tuple[str, ...]
    kept_candidate_identities: tuple[str, ...]
    kept_candidate_order_hash: str | None
    selected_candidate_identity: str | None
    selected_source: str | None
    selected_source_index: int | None
    selected_update_keys: tuple[str, ...]
    selected_updates_hash: str | None
    selected_candidate_trace_hash: str | None
    selected_update_surface_hash: str
    selection_reason_summary: dict[str, Any]
    selected_in_ranked_identities: bool
    selected_in_kept_identities: bool
    selected_index_matches_kept_order: bool | None
    selected_identity_parity: bool
    zero_accepted_parity: bool
    parity_failures: tuple[str, ...]
    forbidden_fields_present: tuple[str, ...]
    proof_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BottomReoSelectedRecommendation:
    """Proof-only selected bottom-reo recommendation shape.

    Built from explicit primitive/data values gathered after the current
    page-local selection has completed. It does not receive live candidate
    dictionaries, mutate inputs, run CTA/action/publication logic, or observe
    UI/session/debug state.
    """

    selected_candidate_identity: str | None
    selected_source: str | None
    selected_source_index: int | None
    arrangement: dict[str, Any]
    updates: dict[str, Any]
    returned_update_keys: tuple[str, ...]
    returned_updates_hash: str
    actual_ast: float
    required_ast: float
    util: float | None
    label: str
    score: float
    recommendation_compound: bool
    subfamilies: tuple[str, ...]
    recommendation_family_tag: str | None
    guidance_recommendation_title: str | None
    delta_b_mm: float
    delta_D_mm: float
    delta_Ast_bot: float
    guidance_change_lines: tuple[str, ...]
    utilisation_check_summary: dict[str, Any]
    selected_candidate_trace_hash: str | None
    selected_recommendation_shape_hash: str
    forbidden_fields_present: tuple[str, ...]
    proof_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BottomReoRepairBlockedReasonProof:
    """Proof-only bottom-reo repair/blocked reason source surface.

    Built from already-normalized selector/recommendation proof surfaces. It
    does not produce visible wording, build CTA/action payloads, publish,
    render, observe UI/session/debug state, or conflate trace-only reasons with
    visible blocked wording.
    """

    selected_recommendation_identity: str | None
    selected_recommendation_proof_hash: str | None
    selected_recommendation_shape_hash: str | None
    selected_recommendation_handoff_hash: str | None
    selected_candidate_identity: str | None
    selected_candidate_trace_hash: str | None
    selected_update_hash_surface: dict[str, Any]
    selector_guard_outcomes: dict[str, Any]
    selector_trace_reasons: dict[str, Any]
    repair_reason_source_surface: dict[str, Any]
    blocked_reason_source_surface: dict[str, Any]
    reason_visibility_surface: dict[str, Any]
    visible_guidance_text_source: dict[str, Any] | None
    forbidden_fields_present: tuple[str, ...]
    proof_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BottomReoCtaIntentProof:
    """Proof-only bottom-reo CTA/action intent surface.

    Built from selected-recommendation and repair/blocked proof surfaces plus
    explicit action payload identity values. It does not drive final CTA
    rendering, source precedence, publication gating, apply routing, one-click
    fallback, visible wording, or UI/session/debug behaviour.
    """

    schema: str
    proof_kind: str
    product_driving: bool
    selected_recommendation_identity: str | None
    selected_recommendation_proof_hash: str | None
    selected_recommendation_shape_hash: str | None
    repair_blocked_reason_proof_hash: str | None
    selected_update_hash_surface: dict[str, Any]
    action_payload_identity: dict[str, Any]
    action_intent_source: dict[str, Any]
    intent_state: str
    no_action_or_blocked_proof_source: dict[str, Any]
    forbidden_fields_present: tuple[str, ...]
    cta_intent_proof_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BottomReoTighteningRecommendationProof:
    """Proof-only bottom-reo tightening recommendation surface.

    This represents the overdesign-reduction/tightening recommendation proof
    chain. It does not drive final CTA rendering, source precedence,
    publication gating, apply routing, one-click fallback, visible wording, or
    UI/session/debug behaviour.
    """

    input_design_reo_state: dict[str, Any]
    tightening_candidate_options: tuple[dict[str, Any], ...]
    rejected_candidate_reasons: tuple[dict[str, Any], ...]
    accepted_candidate_count: int
    accepted_candidate_identities: tuple[dict[str, Any], ...]
    selected_tightening_recommendation: dict[str, Any] | None
    selected_candidate_summary: dict[str, Any] | None
    no_recommendation_reason: str | None
    update_action_payload_identity: dict[str, Any]
    utilisation_target_band_surface: dict[str, Any]
    repair_blocked_reason_source_surface: dict[str, Any]
    cta_action_intent_source_surface: dict[str, Any]
    forbidden_fields_present: tuple[str, ...]
    tightening_recommendation_hash: str

    def proof_surface(self) -> dict[str, Any]:
        return {
            "input_design_reo_state": self.input_design_reo_state,
            "tightening_candidate_options": list(self.tightening_candidate_options),
            "rejected_candidate_reasons": list(self.rejected_candidate_reasons),
            "accepted_candidate_count": self.accepted_candidate_count,
            "accepted_candidate_identities": list(self.accepted_candidate_identities),
            "selected_tightening_recommendation": self.selected_tightening_recommendation,
            "selected_candidate_summary": self.selected_candidate_summary,
            "no_recommendation_reason": self.no_recommendation_reason,
            "update_action_payload_identity": self.update_action_payload_identity,
            "utilisation_target_band_surface": self.utilisation_target_band_surface,
            "repair_blocked_reason_source_surface": self.repair_blocked_reason_source_surface,
            "cta_action_intent_source_surface": self.cta_action_intent_source_surface,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["proof_surface"] = self.proof_surface()
        return payload


_EVALUATED_FILTER_ALLOWED_RECORD_KEYS = {
    "order_index",
    "band",
    "arrangement_signature",
    "arrangement",
    "arrangement_update_keys",
    "arrangement_update_payload_hash",
    "evaluator_returned",
    "status",
    "reject_reason",
    "accepted_prerank_candidate_identity",
    "candidate_update_keys",
    "candidate_update_payload_hash",
    "utilisation_summary",
    "target_band_status",
}

_EVALUATED_FILTER_FORBIDDEN_RECORD_KEYS = {
    "action_payload",
    "action_type",
    "button_contract",
    "cta",
    "debug",
    "final_selected_repair",
    "mutation",
    "one_click",
    "publication",
    "rank",
    "ranking",
    "ranking_score",
    "render",
    "score",
    "selected_recommendation",
    "session_state",
    "ui",
}


_EVALUATED_FILTER_ALLOWED_STATUSES = {
    "pending_evaluation",
    "evaluated_pending_filter",
    "accepted_prerank",
    "rejected",
}


_EVALUATED_FILTER_ALLOWED_ARRANGEMENT_KEYS = {
    "bot1_count",
    "bot2_count",
    "db_bot_1",
    "db_bot_2",
    "bot_row_count",
    "spacing_bot_1",
    "spacing_bot_2",
    "spec",
}


_SELECTOR_WRAPPER_ALLOWED_REASON_KEYS = {
    "status",
    "selected_reason",
    "no_candidate_reason",
    "post_selector_guard_result",
    "no_result_reason",
    "strict_band_winner_seen",
    "strict_band_winner_accepted",
    "strict_band_rejected_reason",
    "legacy_rejection_reason",
    "winner_pool_mode",
    "selected_because_band",
    "selected_reaches_target_band",
}


_SELECTOR_WRAPPER_FORBIDDEN_REASON_KEYS = {
    "action",
    "action_payload",
    "action_type",
    "button_contract",
    "cta",
    "cta_intent",
    "debug",
    "final_selected_repair",
    "mutation",
    "one_click",
    "one_click_action",
    "publication",
    "published",
    "render",
    "session",
    "session_state",
    "ui",
}


_SELECTED_RECOMMENDATION_ALLOWED_ARRANGEMENT_KEYS = {
    "bar_count",
    "bot1_count",
    "bot2_count",
    "db_bot_1",
    "db_bot_2",
    "row_count",
    "bot_row_count",
    "spacing_bot_1",
    "spacing_bot_2",
    "spec",
}


_SELECTED_RECOMMENDATION_FORBIDDEN_KEYS = {
    "action",
    "action_payload",
    "action_type",
    "button_contract",
    "cta",
    "cta_intent",
    "debug",
    "debug_trace",
    "final_selected_repair",
    "mutation",
    "one_click",
    "one_click_action",
    "publication",
    "published",
    "render",
    "session",
    "session_state",
    "ui",
}


def _record_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _record_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _record_key_tuple(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (list, tuple, set)):
        return tuple(str(value) for value in values)
    return (str(values),)


def _record_dict(value: Any, *, allowed_keys: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    if allowed_keys is None:
        return dict(value)
    return {str(key): value.get(key) for key in allowed_keys if key in value}


def build_bottom_reo_evaluated_candidate_filter_record(
    *,
    order_index: int,
    band: int,
    arrangement_identity: dict[str, Any] | None,
    arrangement_signature: str | None,
    arrangement_update_keys: list[str] | tuple[str, ...],
    arrangement_update_payload_hash: str | None,
    evaluator_returned: bool | None,
    status: str,
    reject_reason: str | None,
    accepted_prerank_candidate_identity: str | None,
    candidate_update_keys: list[str] | tuple[str, ...] | None = None,
    candidate_update_payload_hash: str | None = None,
    utilisation_summary: dict[str, Any] | None = None,
    target_band_status: dict[str, Any] | None = None,
) -> BottomReoEvaluatedCandidateFilterRecord:
    """Build a primitive report-only raw record for pre-rank filtering."""

    status_text = str(status or "pending_evaluation")
    if status_text not in _EVALUATED_FILTER_ALLOWED_STATUSES:
        status_text = "rejected"
    return BottomReoEvaluatedCandidateFilterRecord(
        order_index=_record_int(order_index),
        band=_record_int(band),
        arrangement_signature=str(arrangement_signature) if arrangement_signature is not None else None,
        arrangement=_record_dict(arrangement_identity, allowed_keys=_EVALUATED_FILTER_ALLOWED_ARRANGEMENT_KEYS),
        arrangement_update_keys=_record_key_tuple(arrangement_update_keys),
        arrangement_update_payload_hash=(
            str(arrangement_update_payload_hash) if arrangement_update_payload_hash is not None else None
        ),
        evaluator_returned=evaluator_returned if evaluator_returned is None else bool(evaluator_returned),
        status=status_text,
        reject_reason=str(reject_reason) if reject_reason is not None else None,
        accepted_prerank_candidate_identity=(
            str(accepted_prerank_candidate_identity)
            if accepted_prerank_candidate_identity is not None
            else None
        ),
        candidate_update_keys=_record_key_tuple(candidate_update_keys),
        candidate_update_payload_hash=(
            str(candidate_update_payload_hash) if candidate_update_payload_hash is not None else None
        ),
        utilisation_summary=_record_dict(utilisation_summary),
        target_band_status=_record_dict(target_band_status),
    )


def build_bottom_reo_accepted_candidates(
    *,
    boundary: BottomReoEvaluatedCandidateFilterBoundary | dict[str, Any] | None = None,
    records: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
) -> tuple[BottomReoAcceptedCandidate, ...]:
    """Derive accepted pre-rank candidates from evaluated/filter records only."""

    if records is None:
        if isinstance(boundary, BottomReoEvaluatedCandidateFilterBoundary):
            source_records = list(boundary.records)
        elif isinstance(boundary, dict):
            raw_records = boundary.get("records")
            source_records = list(raw_records or []) if isinstance(raw_records, (list, tuple)) else []
        else:
            source_records = []
    else:
        source_records = list(records or [])
    accepted: list[BottomReoAcceptedCandidate] = []
    for record in source_records:
        if not isinstance(record, dict):
            continue
        if record.get("status") != "accepted_prerank":
            continue
        candidate_identity = str(record.get("accepted_prerank_candidate_identity") or "")
        if not candidate_identity:
            continue
        accepted.append(
            BottomReoAcceptedCandidate(
                accepted_order_index=len(accepted),
                source_record_order_index=_record_int(record.get("order_index"), len(accepted)),
                candidate_identity=candidate_identity,
                candidate_update_keys=_record_key_tuple(record.get("candidate_update_keys")),
                candidate_update_payload_hash=(
                    str(record.get("candidate_update_payload_hash"))
                    if record.get("candidate_update_payload_hash") is not None
                    else None
                ),
                arrangement_signature=(
                    str(record.get("arrangement_signature"))
                    if record.get("arrangement_signature") is not None
                    else None
                ),
                arrangement=_record_dict(
                    record.get("arrangement"),
                    allowed_keys=_EVALUATED_FILTER_ALLOWED_ARRANGEMENT_KEYS,
                ),
                utilisation_summary=_record_dict(record.get("utilisation_summary")),
                acceptance_status="accepted_prerank",
            ),
        )
    return tuple(accepted)


def build_bottom_reo_scored_candidates(
    *,
    accepted_candidates: list[dict[str, Any] | BottomReoAcceptedCandidate]
    | tuple[dict[str, Any] | BottomReoAcceptedCandidate, ...],
    score_records: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> tuple[BottomReoScoredCandidate, ...]:
    """Derive scored pre-rank candidates from accepted records and scores only."""

    accepted_list: list[dict[str, Any]] = []
    for item in list(accepted_candidates or []):
        if isinstance(item, BottomReoAcceptedCandidate):
            accepted_list.append(item.to_dict())
        elif isinstance(item, dict):
            accepted_list.append(dict(item))

    accepted_by_index: dict[int, dict[str, Any]] = {}
    accepted_by_identity: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(accepted_list):
        accepted_index = _record_int(item.get("accepted_order_index"), index)
        accepted_by_index[accepted_index] = item
        identity = str(item.get("candidate_identity") or "")
        if identity:
            accepted_by_identity[identity] = item

    scored: list[BottomReoScoredCandidate] = []
    for index, score_record in enumerate(list(score_records or [])):
        if not isinstance(score_record, dict):
            continue
        source_index_raw = score_record.get("source_accepted_candidate_index")
        source_index = _record_int(source_index_raw, -1)
        identity = str(score_record.get("candidate_identity") or "")
        accepted = accepted_by_index.get(source_index) if source_index_raw is not None else None
        if accepted is None and identity:
            accepted = accepted_by_identity.get(identity)
            source_index = _record_int(accepted.get("accepted_order_index"), source_index) if accepted else source_index
        if accepted is None:
            continue
        accepted_identity = str(accepted.get("candidate_identity") or "")
        scored.append(
            BottomReoScoredCandidate(
                scored_order_index=len(scored),
                source_accepted_candidate_index=source_index,
                candidate_identity=accepted_identity or identity,
                candidate_update_keys=_record_key_tuple(accepted.get("candidate_update_keys")),
                candidate_update_payload_hash=(
                    str(accepted.get("candidate_update_payload_hash"))
                    if accepted.get("candidate_update_payload_hash") is not None
                    else None
                ),
                arrangement_signature=(
                    str(accepted.get("arrangement_signature"))
                    if accepted.get("arrangement_signature") is not None
                    else None
                ),
                utilisation_summary=_record_dict(accepted.get("utilisation_summary")),
                score_value=_record_float(score_record.get("score_value")),
                score_source=str(score_record.get("score_source") or ""),
                score_inputs=_record_dict(score_record.get("score_inputs")),
            ),
        )
    return tuple(scored)


def build_bottom_reo_ranked_candidates(
    *,
    ranked_records: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> tuple[BottomReoRankedCandidate, ...]:
    """Build post-sort ranked proof records from explicit rank data only."""

    ranked: list[BottomReoRankedCandidate] = []
    for index, record in enumerate(list(ranked_records or [])):
        if not isinstance(record, dict):
            continue
        identity = str(record.get("candidate_identity") or record.get("source_scored_candidate_identity") or "")
        if not identity:
            continue
        ranked.append(
            BottomReoRankedCandidate(
                ranked_order_index=_record_int(record.get("ranked_order_index"), len(ranked)),
                source_scored_candidate_identity=str(record.get("source_scored_candidate_identity") or identity),
                candidate_identity=identity,
                rank_status=str(record.get("rank_status") or "unknown"),
                sort_key_summary=_record_dict(record.get("sort_key_summary")),
                dedupe_key_summary=_record_dict(record.get("dedupe_key_summary")),
                reo_complexity_before=_record_float(record.get("reo_complexity_before")),
                reo_complexity_after=_record_float(record.get("reo_complexity_after")),
                kept_candidate_hash_inputs=_record_dict(record.get("kept_candidate_hash_inputs")),
            ),
        )
    return tuple(ranked)


_BOTTOM_REO_RANKING_POLICY_ALLOWED_KEYS = {
    "policy_input_order_index",
    "candidate_identity",
    "source_scored_candidate_identity",
    "state_hash",
    "state_summary",
    "resolved_design_action_dedupe_key_hash",
    "resolved_design_action_summary",
    "objective_util",
    "util_distance",
    "target_band_inputs",
    "row_bar_congestion_fields",
    "dimension_primitives",
    "shallow_tier",
    "shallow_tier_label",
    "shallow_metrics",
    "ductility",
    "reo_complexity_primitives",
    "reo_complexity_before_setdefault",
    "reo_complexity_after_setdefault",
    "sort_key_surface",
    "dominance_dedupe_surface",
}


def build_bottom_reo_ranking_policy_inputs(
    *,
    records: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> tuple[BottomReoRankingPolicyInput, ...]:
    """Build typed bottom-reo ranking-policy input proof records.

    The caller owns live candidate reads, complexity mutation timing, ranking
    policy calls, `_keep_top_candidates(...)`, selection, CTA/action,
    publication, one-click solver, and UI/session/debug behaviour. This helper
    only normalizes explicit record values and computes the per-record proof
    hash.
    """

    policy_inputs: list[BottomReoRankingPolicyInput] = []
    for index, record in enumerate(list(records or [])):
        if not isinstance(record, dict):
            continue
        normalised = {
            key: record.get(key)
            for key in _BOTTOM_REO_RANKING_POLICY_ALLOWED_KEYS
            if key in record
        }
        normalised["policy_input_order_index"] = _record_int(
            normalised.get("policy_input_order_index"),
            index,
        )
        normalised["candidate_identity"] = str(normalised.get("candidate_identity") or "")
        if not normalised["candidate_identity"]:
            continue
        normalised["source_scored_candidate_identity"] = str(
            normalised.get("source_scored_candidate_identity")
            or normalised["candidate_identity"]
        )
        normalised["state_hash"] = (
            str(normalised.get("state_hash")) if normalised.get("state_hash") is not None else None
        )
        normalised["state_summary"] = _record_dict(normalised.get("state_summary"))
        normalised["resolved_design_action_dedupe_key_hash"] = (
            str(normalised.get("resolved_design_action_dedupe_key_hash"))
            if normalised.get("resolved_design_action_dedupe_key_hash") is not None
            else None
        )
        normalised["resolved_design_action_summary"] = _record_dict(
            normalised.get("resolved_design_action_summary"),
        )
        normalised["objective_util"] = _record_float(normalised.get("objective_util"))
        normalised["util_distance"] = _record_float(normalised.get("util_distance"))
        normalised["target_band_inputs"] = _record_dict(normalised.get("target_band_inputs"))
        normalised["row_bar_congestion_fields"] = _record_dict(
            normalised.get("row_bar_congestion_fields"),
        )
        normalised["dimension_primitives"] = _record_dict(
            normalised.get("dimension_primitives"),
        )
        normalised["shallow_metrics"] = _record_dict(normalised.get("shallow_metrics"))
        normalised["ductility"] = _record_dict(normalised.get("ductility"))
        normalised["reo_complexity_primitives"] = _record_dict(
            normalised.get("reo_complexity_primitives"),
        )
        normalised["reo_complexity_before_setdefault"] = _record_float(
            normalised.get("reo_complexity_before_setdefault"),
        )
        normalised["reo_complexity_after_setdefault"] = _record_float(
            normalised.get("reo_complexity_after_setdefault"),
        )
        normalised["dominance_dedupe_surface"] = _record_dict(
            normalised.get("dominance_dedupe_surface"),
        )
        normalised.setdefault("shallow_tier", None)
        normalised.setdefault("shallow_tier_label", None)
        normalised.setdefault("sort_key_surface", None)
        policy_input_hash = _stable_boundary_hash(normalised)
        policy_inputs.append(
            BottomReoRankingPolicyInput(
                policy_input_order_index=normalised["policy_input_order_index"],
                candidate_identity=normalised["candidate_identity"],
                source_scored_candidate_identity=normalised["source_scored_candidate_identity"],
                state_hash=normalised["state_hash"],
                state_summary=normalised["state_summary"],
                resolved_design_action_dedupe_key_hash=normalised[
                    "resolved_design_action_dedupe_key_hash"
                ],
                resolved_design_action_summary=normalised["resolved_design_action_summary"],
                objective_util=normalised["objective_util"],
                util_distance=normalised["util_distance"],
                target_band_inputs=normalised["target_band_inputs"],
                row_bar_congestion_fields=normalised["row_bar_congestion_fields"],
                dimension_primitives=normalised["dimension_primitives"],
                shallow_tier=normalised["shallow_tier"],
                shallow_tier_label=normalised["shallow_tier_label"],
                shallow_metrics=normalised["shallow_metrics"],
                ductility=normalised["ductility"],
                reo_complexity_primitives=normalised["reo_complexity_primitives"],
                reo_complexity_before_setdefault=normalised[
                    "reo_complexity_before_setdefault"
                ],
                reo_complexity_after_setdefault=normalised[
                    "reo_complexity_after_setdefault"
                ],
                sort_key_surface=normalised["sort_key_surface"],
                dominance_dedupe_surface=normalised["dominance_dedupe_surface"],
                policy_input_hash=policy_input_hash,
            )
        )
    return tuple(policy_inputs)


def _stable_boundary_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _ranking_wrapper_safe_sort_key(value: Any) -> Any:
    if isinstance(value, tuple):
        return tuple(_ranking_wrapper_safe_sort_key(item) for item in value)
    if isinstance(value, list):
        return tuple(_ranking_wrapper_safe_sort_key(item) for item in value)
    if isinstance(value, dict):
        return tuple(
            (str(key), _ranking_wrapper_safe_sort_key(val))
            for key, val in sorted(value.items(), key=lambda item: str(item[0]))
        )
    if value is None:
        return (1, "")
    if isinstance(value, bool):
        return (0, int(value))
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return (1, "nan")
        return (0, float(value))
    return (0, str(value))


def _ranking_wrapper_dedupe_hash(record: dict[str, Any]) -> str:
    dominance_surface = record.get("dominance_dedupe_surface")
    if isinstance(dominance_surface, dict):
        explicit_hash = dominance_surface.get("dedupe_key_hash")
        if explicit_hash is not None:
            return str(explicit_hash)
        if "dedupe_key" in dominance_surface:
            return _stable_boundary_hash(dominance_surface.get("dedupe_key"))
    return str(record.get("candidate_identity") or "")


def _ranking_wrapper_dedupe_value(record: dict[str, Any]) -> Any:
    dominance_surface = record.get("dominance_dedupe_surface")
    if isinstance(dominance_surface, dict) and "dedupe_key" in dominance_surface:
        return dominance_surface.get("dedupe_key")
    return _ranking_wrapper_dedupe_hash(record)


def _ranking_wrapper_number(value: Any, default: float = 0.0) -> float:
    parsed = _record_float(value)
    return float(default) if parsed is None else float(parsed)


def _bottom_reo_policy_bool(value: Any) -> bool:
    return bool(value)


def _bottom_reo_policy_int(value: Any, default: int = 0) -> int:
    return _record_int(value, default)


def _bottom_reo_policy_float(value: Any, default: float = 0.0) -> float:
    parsed = _record_float(value)
    return float(default) if parsed is None else float(parsed)


def bottom_reo_sort_key_from_policy_surface(
    *,
    strategy: str = "balanced",
    is_compliant: Any = False,
    is_practical: Any = False,
    violation_score: Any = 0.0,
    fail_count: Any = 0,
    worst_util: Any = float("inf"),
    reo_complexity: Any = 0.0,
    util_distance: Any = 0.0,
    depth: Any = 0.0,
    width: Any = 0.0,
    bar_count: Any = 0,
    row_count: Any = 0,
    steel_area: Any = 0.0,
    shallow_tier: Any = 0,
    shallow_metrics: dict[str, Any] | None = None,
    in_target_band: Any = False,
    ductility_priority: Any = False,
    ductility_util: Any = None,
    ductility_tier: Any = 4,
) -> tuple:
    """Return the bottom-reo callback sort key from primitive policy fields."""

    mode = str(strategy or "balanced")
    compliant_penalty = 0 if _bottom_reo_policy_bool(is_compliant) else 1
    practical_penalty = 0 if _bottom_reo_policy_bool(is_practical) else 1
    violation = _bottom_reo_policy_float(violation_score, 0.0)
    failures = _bottom_reo_policy_int(fail_count, 0)
    worst = _bottom_reo_policy_float(worst_util, float("inf"))
    complexity = _bottom_reo_policy_float(reo_complexity, 0.0)
    distance = _bottom_reo_policy_float(util_distance, 0.0)
    candidate_depth = _bottom_reo_policy_float(depth, 0.0)
    candidate_width = _bottom_reo_policy_float(width, 0.0)
    bars = _bottom_reo_policy_int(bar_count, 0)
    rows = _bottom_reo_policy_int(row_count, 0)
    steel = _bottom_reo_policy_float(steel_area, 0.0)
    tier = _bottom_reo_policy_int(shallow_tier, 0)
    metrics = _record_dict(shallow_metrics)
    materially_shallower = bool(metrics.get("materially_shallower"))
    width_growth = _bottom_reo_policy_float(metrics.get("width_growth"), 0.0)
    reinforcement_growth = _bottom_reo_policy_float(metrics.get("reinforcement_growth"), 0.0)
    if _bottom_reo_policy_bool(ductility_priority):
        ductility_value = _bottom_reo_policy_float(ductility_util, float("inf"))
        resolved_tier = _bottom_reo_policy_int(ductility_tier or 4, 4)
        return (
            compliant_penalty,
            0 if ductility_value <= 1.0 else 1,
            max(ductility_value - 1.0, 0.0),
            ductility_value,
            resolved_tier,
            steel,
            practical_penalty,
            rows,
            bars,
            candidate_depth,
            candidate_width,
            distance,
            complexity,
        )
    if compliant_penalty:
        if mode == "shallow":
            return (
                compliant_penalty,
                failures,
                violation,
                worst,
                0 if materially_shallower else 1,
                tier,
                candidate_depth,
                width_growth,
                reinforcement_growth,
                practical_penalty,
                distance,
                complexity,
                steel,
                candidate_width,
            )
        if mode == "low_reo":
            return (
                compliant_penalty,
                failures,
                violation,
                worst,
                practical_penalty,
                distance,
                complexity,
                rows,
                bars,
                candidate_depth,
                steel,
            )
        return (
            compliant_penalty,
            failures,
            violation,
            worst,
            practical_penalty,
            distance,
            candidate_depth,
            complexity,
            candidate_width,
            steel,
        )
    if mode == "shallow":
        return (
            compliant_penalty,
            0 if materially_shallower else 1,
            tier,
            candidate_depth,
            width_growth,
            reinforcement_growth,
            practical_penalty,
            distance,
            complexity,
            steel,
            candidate_width,
        )
    if mode == "low_reo":
        return (
            compliant_penalty,
            practical_penalty,
            complexity,
            rows,
            bars,
            distance,
            candidate_depth,
            steel,
        )
    return (
        compliant_penalty,
        0 if _bottom_reo_policy_bool(in_target_band) else 1,
        practical_penalty,
        distance,
        candidate_depth,
        complexity,
        candidate_width,
        steel,
    )


def bottom_reo_dominance_from_policy_surface(
    *,
    strategy: str = "balanced",
    existing_is_compliant: Any = False,
    candidate_is_compliant: Any = False,
    existing_util_distance: Any = 0.0,
    candidate_util_distance: Any = 0.0,
    existing_reo_complexity: Any = 0.0,
    candidate_reo_complexity: Any = 0.0,
    existing_depth: Any = 0.0,
    candidate_depth: Any = 0.0,
    existing_row_count: Any = 0,
    candidate_row_count: Any = 0,
    existing_bar_count: Any = 0,
    candidate_bar_count: Any = 0,
    existing_shallow_metrics: dict[str, Any] | None = None,
    candidate_shallow_metrics: dict[str, Any] | None = None,
) -> bool:
    """Return whether the existing bottom-reo policy surface dominates candidate."""

    if not _bottom_reo_policy_bool(existing_is_compliant) or not _bottom_reo_policy_bool(candidate_is_compliant):
        return False
    mode = str(strategy or "balanced")
    util_a = _bottom_reo_policy_float(existing_util_distance, 0.0)
    util_b = _bottom_reo_policy_float(candidate_util_distance, 0.0)
    complexity_a = _bottom_reo_policy_float(existing_reo_complexity, 0.0)
    complexity_b = _bottom_reo_policy_float(candidate_reo_complexity, 0.0)
    depth_a = _bottom_reo_policy_float(existing_depth, 0.0)
    depth_b = _bottom_reo_policy_float(candidate_depth, 0.0)
    if mode == "shallow":
        metrics_a = _record_dict(existing_shallow_metrics)
        metrics_b = _record_dict(candidate_shallow_metrics)
        shallower_a = 0 if bool(metrics_a.get("materially_shallower")) else 1
        shallower_b = 0 if bool(metrics_b.get("materially_shallower")) else 1
        width_growth_a = _bottom_reo_policy_float(metrics_a.get("width_growth"), 0.0)
        width_growth_b = _bottom_reo_policy_float(metrics_b.get("width_growth"), 0.0)
        reo_growth_a = _bottom_reo_policy_float(metrics_a.get("reinforcement_growth"), 0.0)
        reo_growth_b = _bottom_reo_policy_float(metrics_b.get("reinforcement_growth"), 0.0)
        return (
            shallower_a <= shallower_b
            and depth_a <= depth_b
            and width_growth_a <= width_growth_b
            and reo_growth_a <= reo_growth_b
            and complexity_a <= complexity_b
            and util_a <= util_b
            and (
                shallower_a < shallower_b
                or depth_a < depth_b
                or width_growth_a < width_growth_b
                or reo_growth_a < reo_growth_b
                or complexity_a < complexity_b
                or util_a < util_b
            )
        )
    if mode == "low_reo":
        rows_a = _bottom_reo_policy_int(existing_row_count, 0)
        rows_b = _bottom_reo_policy_int(candidate_row_count, 0)
        bars_a = _bottom_reo_policy_int(existing_bar_count, 0)
        bars_b = _bottom_reo_policy_int(candidate_bar_count, 0)
        return (
            complexity_a <= complexity_b
            and rows_a <= rows_b
            and bars_a <= bars_b
            and depth_a <= depth_b
            and util_a <= util_b
            and (
                complexity_a < complexity_b
                or rows_a < rows_b
                or bars_a < bars_b
                or depth_a < depth_b
                or util_a < util_b
            )
        )
    return (
        util_a <= util_b
        and depth_a <= depth_b
        and complexity_a <= complexity_b
        and (util_a < util_b or depth_a < depth_b or complexity_a < complexity_b)
    )


def _ranking_wrapper_dominates(existing: dict[str, Any], candidate: dict[str, Any]) -> bool:
    """Mirror the current balanced dominance proof surface from policy inputs.

    This intentionally uses only primitive fields already present on
    ``BottomReoRankingPolicyInput``. It is a parity/proof adapter, not the live
    product ranking implementation.
    """

    existing_sort = existing.get("sort_key_surface")
    candidate_sort = candidate.get("sort_key_surface")
    existing_compliant_penalty = existing_sort[0] if isinstance(existing_sort, (list, tuple)) and existing_sort else None
    candidate_compliant_penalty = candidate_sort[0] if isinstance(candidate_sort, (list, tuple)) and candidate_sort else None
    if existing_compliant_penalty != 0 or candidate_compliant_penalty != 0:
        return False

    util_a = _ranking_wrapper_number(existing.get("util_distance"), float("inf"))
    util_b = _ranking_wrapper_number(candidate.get("util_distance"), float("inf"))
    dims_a = _record_dict(existing.get("dimension_primitives"))
    dims_b = _record_dict(candidate.get("dimension_primitives"))
    depth_a = _ranking_wrapper_number(dims_a.get("depth"), float("inf"))
    depth_b = _ranking_wrapper_number(dims_b.get("depth"), float("inf"))
    complexity_a = _ranking_wrapper_number(
        existing.get("reo_complexity_after_setdefault"),
        _ranking_wrapper_number(existing.get("reo_complexity_before_setdefault"), 0.0),
    )
    complexity_b = _ranking_wrapper_number(
        candidate.get("reo_complexity_after_setdefault"),
        _ranking_wrapper_number(candidate.get("reo_complexity_before_setdefault"), 0.0),
    )
    return (
        util_a <= util_b
        and depth_a <= depth_b
        and complexity_a <= complexity_b
        and (util_a < util_b or depth_a < depth_b or complexity_a < complexity_b)
    )


def build_bottom_reo_ranking_wrapper_proof(
    *,
    policy_inputs: list[BottomReoRankingPolicyInput] | tuple[BottomReoRankingPolicyInput, ...],
    max_kept_results: int = 4,
) -> BottomReoRankingWrapperProof:
    """Build a proof-only ranking wrapper result from typed policy inputs.

    The helper consumes explicit ``BottomReoRankingPolicyInput`` records only.
    It does not call live ranking, candidate evaluators, selection, CTA/action,
    publication, UI/session/debug, or one-click solver code.
    """

    records = [
        item.to_dict()
        for item in tuple(policy_inputs or ())
        if isinstance(item, BottomReoRankingPolicyInput)
    ]
    deduped: dict[str, dict[str, Any]] = {}
    for record in records:
        identity = str(record.get("candidate_identity") or "")
        if not identity:
            continue
        dedupe_hash = _ranking_wrapper_dedupe_hash(record)
        existing = deduped.get(dedupe_hash)
        if existing is None or _ranking_wrapper_safe_sort_key(
            record.get("sort_key_surface")
        ) < _ranking_wrapper_safe_sort_key(existing.get("sort_key_surface")):
            deduped[dedupe_hash] = dict(record)

    ordered_records = sorted(
        deduped.values(),
        key=lambda record: _ranking_wrapper_safe_sort_key(record.get("sort_key_surface")),
    )
    bounded_limit = max(int(max_kept_results or 0), 0)
    kept_records: list[dict[str, Any]] = []
    rank_decisions: list[dict[str, Any]] = []
    dominance_decisions: list[dict[str, Any]] = []

    for record in ordered_records:
        identity = str(record.get("candidate_identity") or "")
        dominating_identity = None
        for existing in kept_records:
            dominated = _ranking_wrapper_dominates(existing, record)
            dominance_decisions.append(
                {
                    "existing_identity": str(existing.get("candidate_identity") or ""),
                    "candidate_identity": identity,
                    "dominates": bool(dominated),
                }
            )
            if dominated:
                dominating_identity = str(existing.get("candidate_identity") or "")
                break
        if dominating_identity:
            rank_decisions.append(
                {
                    "candidate_identity": identity,
                    "decision": "discarded_dominated",
                    "dominates_by": dominating_identity,
                }
            )
            continue
        if bounded_limit and len(kept_records) >= bounded_limit:
            rank_decisions.append(
                {
                    "candidate_identity": identity,
                    "decision": "discarded_limit",
                    "limit": bounded_limit,
                }
            )
            continue
        kept_records.append(record)
        rank_decisions.append({"candidate_identity": identity, "decision": "kept"})

    ordered_identities = tuple(str(record.get("candidate_identity") or "") for record in ordered_records)
    kept_identities = tuple(str(record.get("candidate_identity") or "") for record in kept_records)
    pruned_identities = tuple(
        str(decision.get("candidate_identity") or "")
        for decision in rank_decisions
        if str(decision.get("decision") or "") != "kept"
    )
    simple_rank_decisions = tuple(
        {
            "candidate_identity": str(decision.get("candidate_identity") or ""),
            "decision": str(decision.get("decision") or ""),
        }
        for decision in rank_decisions
    )
    ranking_surface = {
        "scored_order": tuple(str(record.get("candidate_identity") or "") for record in records),
        "sort_key_by_identity": {
            str(record.get("candidate_identity") or ""): record.get("sort_key_surface")
            for record in records
            if str(record.get("candidate_identity") or "")
        },
        "dedupe_key_by_identity": {
            str(record.get("candidate_identity") or ""): _ranking_wrapper_dedupe_value(record)
            for record in records
            if str(record.get("candidate_identity") or "")
        },
        "ordered": ordered_identities,
        "kept": kept_identities,
        "decisions": simple_rank_decisions,
        "reo_complexity_before": {
            str(record.get("candidate_identity") or ""): record.get("reo_complexity_before_setdefault")
            for record in records
            if str(record.get("candidate_identity") or "")
        },
        "reo_complexity_after": {
            str(record.get("candidate_identity") or ""): record.get("reo_complexity_after_setdefault")
            for record in records
            if str(record.get("candidate_identity") or "")
        },
    }
    sort_key_hash = _stable_boundary_hash(ranking_surface)
    kept_candidate_hash = _stable_boundary_hash(kept_identities)
    proof_payload = {
        "ordered_candidate_identities": ordered_identities,
        "kept_candidate_identities": kept_identities,
        "pruned_candidate_identities": pruned_identities,
        "rank_decisions": simple_rank_decisions,
        "sort_key_hash": sort_key_hash,
        "kept_candidate_hash": kept_candidate_hash,
    }
    return BottomReoRankingWrapperProof(
        ordered_candidate_identities=ordered_identities,
        kept_candidate_identities=kept_identities,
        pruned_candidate_identities=pruned_identities,
        rank_decisions=simple_rank_decisions,
        dominance_decision_summaries=tuple(dominance_decisions),
        sort_key_hash=sort_key_hash,
        kept_candidate_hash=kept_candidate_hash,
        proof_hash=_stable_boundary_hash(proof_payload),
    )


def build_bottom_reo_ranking_callback_policy_proof(
    *,
    policy_inputs: list[BottomReoRankingPolicyInput] | tuple[BottomReoRankingPolicyInput, ...],
    live_sort_key_by_identity: dict[str, Any] | None = None,
    live_dedupe_key_by_identity: dict[str, Any] | None = None,
    live_dominance_decisions: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    live_ordered_identities: list[str] | tuple[str, ...] | None = None,
    live_kept_identities: list[str] | tuple[str, ...] | None = None,
    live_pruned_identities: list[str] | tuple[str, ...] | None = None,
    bounded_keep_limit: int = 0,
) -> BottomReoRankingCallbackPolicyProof:
    """Build a family-owned proof surface for bottom-reo callback policy.

    The helper packages typed sort/dedupe/dominance replay beside explicit
    live primitive comparison surfaces. It is proof-only and intentionally does
    not drive product ranking.
    """

    records = [
        item.to_dict()
        for item in tuple(policy_inputs or ())
        if isinstance(item, BottomReoRankingPolicyInput)
    ]
    keep_limit = max(int(bounded_keep_limit or 0), 0)
    wrapper = build_bottom_reo_ranking_wrapper_proof(
        policy_inputs=policy_inputs,
        max_kept_results=keep_limit,
    ).to_dict()
    typed_sort = {
        str(record.get("candidate_identity") or ""): record.get("sort_key_surface")
        for record in records
        if str(record.get("candidate_identity") or "")
    }
    typed_dedupe = {
        str(record.get("candidate_identity") or ""): _ranking_wrapper_dedupe_value(record)
        for record in records
        if str(record.get("candidate_identity") or "")
    }
    typed_dominance = tuple(
        dict(item)
        for item in tuple(wrapper.get("dominance_decision_summaries") or ())
        if isinstance(item, dict)
    )
    live_sort = dict(live_sort_key_by_identity or {})
    live_dedupe = dict(live_dedupe_key_by_identity or {})
    live_dominance = tuple(
        dict(item)
        for item in tuple(live_dominance_decisions or ())
        if isinstance(item, dict)
    )
    typed_ordered = tuple(str(item) for item in tuple(wrapper.get("ordered_candidate_identities") or ()))
    typed_kept = tuple(str(item) for item in tuple(wrapper.get("kept_candidate_identities") or ()))
    typed_pruned = tuple(str(item) for item in tuple(wrapper.get("pruned_candidate_identities") or ()))
    live_ordered = tuple(str(item) for item in tuple(live_ordered_identities or ()))
    live_kept = tuple(str(item) for item in tuple(live_kept_identities or ()))
    live_pruned = tuple(str(item) for item in tuple(live_pruned_identities or ()))
    parity_hash_inputs = {
        "candidate_identities": tuple(str(record.get("candidate_identity") or "") for record in records),
        "live_sort": live_sort,
        "typed_sort": typed_sort,
        "live_dedupe": live_dedupe,
        "typed_dedupe": typed_dedupe,
        "live_dominance": live_dominance,
        "typed_dominance": typed_dominance,
        "live_ordered": live_ordered,
        "typed_ordered": typed_ordered,
        "live_kept": live_kept,
        "typed_kept": typed_kept,
    }
    return BottomReoRankingCallbackPolicyProof(
        bounded_keep_limit=keep_limit,
        typed_sort_key_by_identity=typed_sort,
        typed_dedupe_key_by_identity=typed_dedupe,
        typed_dominance_decisions=typed_dominance,
        typed_ordered_identities=typed_ordered,
        typed_kept_identities=typed_kept,
        typed_pruned_identities=typed_pruned,
        live_sort_key_by_identity=live_sort,
        live_dedupe_key_by_identity=live_dedupe,
        live_dominance_decisions=live_dominance,
        live_ordered_identities=live_ordered,
        live_kept_identities=live_kept,
        live_pruned_identities=live_pruned,
        parity_hash_inputs=parity_hash_inputs,
        proof_hash=_stable_boundary_hash(parity_hash_inputs),
    )


_BOTTOM_REO_RANKING_RESULT_FORBIDDEN_KEYS = {
    "action_payload",
    "action_type",
    "button_contract",
    "cta",
    "debug",
    "final_selected_repair",
    "one_click",
    "publication",
    "render",
    "selected_recommendation",
    "session_state",
    "ui",
}


def _bottom_reo_ranking_result_forbidden_fields(value: Any) -> tuple[str, ...]:
    found: set[str] = set()

    def _walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, val in item.items():
                key_text = str(key)
                if key_text in _BOTTOM_REO_RANKING_RESULT_FORBIDDEN_KEYS:
                    found.add(key_text)
                _walk(val)
        elif isinstance(item, (list, tuple)):
            for val in item:
                _walk(val)

    _walk(value)
    return tuple(sorted(found))


def _bottom_reo_policy_input_hashes(
    policy_inputs: list[BottomReoRankingPolicyInput] | tuple[BottomReoRankingPolicyInput, ...] | list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> tuple[str, ...]:
    hashes: list[str] = []
    for item in tuple(policy_inputs or ()):
        if isinstance(item, BottomReoRankingPolicyInput):
            value = item.policy_input_hash
        elif isinstance(item, dict):
            value = item.get("policy_input_hash")
        else:
            value = None
        if value is not None:
            hashes.append(str(value))
    return tuple(hashes)


def build_bottom_reo_ranking_result_boundary(
    *,
    policy_inputs: list[BottomReoRankingPolicyInput] | tuple[BottomReoRankingPolicyInput, ...] | list[dict[str, Any]] | tuple[dict[str, Any], ...],
    ordered_identities: list[str] | tuple[str, ...],
    kept_identities: list[str] | tuple[str, ...],
    pruned_identities: list[str] | tuple[str, ...],
    ranking_decisions: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    ordered_hash: str | None = None,
    kept_hash: str | None = None,
    pruned_hash: str | None = None,
    callback_handoff_hash: str | None = None,
) -> BottomReoRankingResultBoundary:
    """Build a proof-only bottom-reo ranking result boundary.

    The builder consumes normalized identities, decisions, policy-input hashes,
    and stable hashes only. It must not receive live candidate dictionaries or
    product-driving selection/CTA/publication surfaces.
    """

    policy_hashes = _bottom_reo_policy_input_hashes(policy_inputs)
    ordered = tuple(str(item) for item in tuple(ordered_identities or ()))
    kept = tuple(str(item) for item in tuple(kept_identities or ()))
    pruned = tuple(str(item) for item in tuple(pruned_identities or ()))
    decisions = tuple(
        {
            "candidate_identity": str(item.get("candidate_identity") or ""),
            "decision": str(item.get("decision") or ""),
            **(
                {"reason": str(item.get("reason") or "")}
                if item.get("reason") is not None
                else {}
            ),
        }
        for item in tuple(ranking_decisions or ())
        if isinstance(item, dict)
    )
    forbidden = _bottom_reo_ranking_result_forbidden_fields(
        {
            "policy_input_hashes": policy_hashes,
            "ordered_candidate_identities": ordered,
            "kept_candidate_identities": kept,
            "pruned_candidate_identities": pruned,
            "decision_summaries": decisions,
        }
    )
    resolved_ordered_hash = str(ordered_hash) if ordered_hash is not None else _stable_boundary_hash(ordered)
    resolved_kept_hash = str(kept_hash) if kept_hash is not None else _stable_boundary_hash(kept)
    resolved_pruned_hash = str(pruned_hash) if pruned_hash is not None else _stable_boundary_hash(pruned)
    resolved_handoff_hash = str(callback_handoff_hash) if callback_handoff_hash is not None else None
    result_surface = {
        "candidate_count": len(policy_hashes),
        "policy_input_hashes": policy_hashes,
        "ordered_candidate_identities": ordered,
        "kept_candidate_identities": kept,
        "pruned_candidate_identities": pruned,
        "decision_summaries": decisions,
        "ordered_hash": resolved_ordered_hash,
        "kept_hash": resolved_kept_hash,
        "pruned_hash": resolved_pruned_hash,
        "callback_handoff_hash": resolved_handoff_hash,
        "forbidden_fields_present": forbidden,
    }
    return BottomReoRankingResultBoundary(
        candidate_count=len(policy_hashes),
        policy_input_hashes=policy_hashes,
        ordered_candidate_identities=ordered,
        kept_candidate_identities=kept,
        pruned_candidate_identities=pruned,
        decision_summaries=decisions,
        ordered_hash=resolved_ordered_hash,
        kept_hash=resolved_kept_hash,
        pruned_hash=resolved_pruned_hash,
        callback_handoff_hash=resolved_handoff_hash,
        forbidden_fields_present=forbidden,
        ranking_result_hash=_stable_boundary_hash(result_surface),
    )


def _selector_wrapper_forbidden_fields(value: Any) -> tuple[str, ...]:
    found: set[str] = set()

    def _walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, val in item.items():
                key_text = str(key)
                if key_text in _SELECTOR_WRAPPER_FORBIDDEN_REASON_KEYS:
                    found.add(key_text)
                _walk(val)
        elif isinstance(item, (list, tuple, set)):
            for val in item:
                _walk(val)

    _walk(value)
    return tuple(sorted(found))


def _selector_wrapper_reason_summary(value: Any) -> dict[str, Any]:
    raw = _record_dict(value)
    summary: dict[str, Any] = {}
    for key in sorted(_SELECTOR_WRAPPER_ALLOWED_REASON_KEYS):
        if key not in raw:
            continue
        val = raw.get(key)
        if isinstance(val, (str, int, float, bool)) or val is None:
            summary[key] = val
        elif isinstance(val, (list, tuple, set)):
            summary[key] = tuple(str(item) for item in val)
        else:
            summary[f"{key}_hash"] = _stable_boundary_hash(val)
    return summary


def build_bottom_reo_selector_wrapper_proof(
    *,
    ranked_candidate_identities: list[str] | tuple[str, ...] | None,
    kept_candidate_identities: list[str] | tuple[str, ...] | None,
    selected_candidate_identity: str | None,
    selected_source_index: int | None = None,
    selected_source: str | None = None,
    selected_update_keys: list[str] | tuple[str, ...] | None = None,
    selected_updates_hash: str | None = None,
    selected_candidate_trace_hash: str | None = None,
    selection_reason_summary: dict[str, Any] | None = None,
) -> BottomReoSelectorWrapperProof:
    """Build a proof-only selected-identity parity wrapper.

    The helper consumes only explicit primitive/data surfaces already emitted by
    the page-local selector path. It does not receive or return live candidate
    dictionaries, mutate inputs, run selector policy, publish, render, or build
    CTA/action payloads.
    """

    ranked_identities = _record_key_tuple(ranked_candidate_identities)
    kept_identities = _record_key_tuple(kept_candidate_identities)
    selected_identity = (
        str(selected_candidate_identity)
        if selected_candidate_identity is not None and str(selected_candidate_identity)
        else None
    )
    source_index = (
        _record_int(selected_source_index)
        if selected_source_index is not None
        else None
    )
    update_keys = tuple(sorted(_record_key_tuple(selected_update_keys)))
    updates_hash = str(selected_updates_hash) if selected_updates_hash is not None else None
    trace_hash = (
        str(selected_candidate_trace_hash)
        if selected_candidate_trace_hash is not None
        else None
    )
    reason_summary = _selector_wrapper_reason_summary(selection_reason_summary)
    forbidden_fields = _selector_wrapper_forbidden_fields(selection_reason_summary)

    selected_in_ranked = bool(selected_identity and selected_identity in ranked_identities)
    selected_in_kept = bool(selected_identity and selected_identity in kept_identities)
    if selected_identity is None or source_index is None:
        selected_index_matches = None
    else:
        selected_index_matches = (
            0 <= int(source_index) < len(kept_identities)
            and kept_identities[int(source_index)] == selected_identity
        )

    failures: list[str] = []
    zero_accepted_parity = selected_identity is None and not kept_identities
    if selected_identity is None:
        if kept_identities:
            failures.append("selected_identity_missing_with_kept_candidates")
    else:
        if not selected_in_ranked:
            failures.append("selected_identity_not_in_ranked_candidates")
        if not selected_in_kept:
            failures.append("selected_identity_not_in_kept_candidates")
        if selected_index_matches is False:
            failures.append("selected_source_index_mismatch")
    if forbidden_fields:
        failures.append("forbidden_selector_surface_present")

    selected_update_surface = {
        "selected_update_keys": update_keys,
        "selected_updates_hash": updates_hash,
        "selected_candidate_trace_hash": trace_hash,
    }
    selected_update_surface_hash = _stable_boundary_hash(selected_update_surface)
    kept_candidate_order_hash = _stable_boundary_hash(kept_identities)
    selected_identity_parity = not failures and (
        zero_accepted_parity
        or (
            selected_identity is not None
            and selected_in_ranked
            and selected_in_kept
            and selected_index_matches is not False
        )
    )
    proof_payload = {
        "ranked_candidate_identities": ranked_identities,
        "kept_candidate_identities": kept_identities,
        "kept_candidate_order_hash": kept_candidate_order_hash,
        "selected_candidate_identity": selected_identity,
        "selected_source": str(selected_source) if selected_source is not None else None,
        "selected_source_index": source_index,
        "selected_update_surface_hash": selected_update_surface_hash,
        "selection_reason_summary": reason_summary,
        "selected_identity_parity": selected_identity_parity,
        "zero_accepted_parity": zero_accepted_parity,
        "parity_failures": tuple(failures),
        "forbidden_fields_present": forbidden_fields,
    }
    return BottomReoSelectorWrapperProof(
        ranked_candidate_identities=ranked_identities,
        kept_candidate_identities=kept_identities,
        kept_candidate_order_hash=kept_candidate_order_hash,
        selected_candidate_identity=selected_identity,
        selected_source=str(selected_source) if selected_source is not None else None,
        selected_source_index=source_index,
        selected_update_keys=update_keys,
        selected_updates_hash=updates_hash,
        selected_candidate_trace_hash=trace_hash,
        selected_update_surface_hash=selected_update_surface_hash,
        selection_reason_summary=reason_summary,
        selected_in_ranked_identities=selected_in_ranked,
        selected_in_kept_identities=selected_in_kept,
        selected_index_matches_kept_order=selected_index_matches,
        selected_identity_parity=bool(selected_identity_parity),
        zero_accepted_parity=bool(zero_accepted_parity),
        parity_failures=tuple(failures),
        forbidden_fields_present=forbidden_fields,
        proof_hash=_stable_boundary_hash(proof_payload),
    )


def select_bottom_reo_recommendation_candidate_by_selector(
    candidates: list[dict] | tuple[dict, ...] | None,
    *,
    seed_candidate: dict | None,
    mode_config: dict | None,
    select_best_candidate_fn: Any,
    strict_band_guard_fn: Any,
    updates_match_state_fn: Any,
    candidate_ductility_util_fn: Any,
    seed_ductility_governs: bool,
    seed_ductility_util: float | None,
    legacy_rejection_reason_fn: Any,
) -> dict[str, Any]:
    """Run the bottom-reo selector policy from plain data and callbacks.

    The caller owns callback implementations and page trace emission. This
    helper owns selector-loop policy: strict band acceptance, no-op/label/util
    rejection, ductility/bending improvement checks, and selected/no-result
    outcome shaping.
    """

    pool = [candidate for candidate in list(candidates or []) if isinstance(candidate, dict) and candidate]
    seed = seed_candidate if isinstance(seed_candidate, dict) else {}
    mode = mode_config if isinstance(mode_config, dict) else {}
    seed_bu = ((seed.get("overview") or {}).get("utils") or {}).get("bending")
    try:
        seed_bu_f = float(seed_bu) if seed_bu is not None else None
    except (TypeError, ValueError):
        seed_bu_f = None
    try:
        seed_du = float(seed_ductility_util) if seed_ductility_util is not None else None
    except (TypeError, ValueError):
        seed_du = None
    ductility_seed = bool(seed_ductility_governs)
    strict_band_winner_seen = False
    strict_band_rejected_reason: str | None = None
    rank_events: list[dict[str, Any]] = []
    trace_entries: list[dict[str, Any]] = []

    def _log(event: str, candidate: dict | None, reason: str, **payload: Any) -> None:
        row = {
            "domain": "bending",
            "event": str(event),
            "candidate": candidate,
            "reason": str(reason),
        }
        row.update(payload)
        rank_events.append(row)

    def _trace(payload: dict[str, Any]) -> None:
        trace_entries.append(dict(payload or {}))

    def _selector_result(
        *,
        selected_candidate: dict | None,
        status: str,
        selected_reason: str | None = None,
        no_candidate_reason: str | None = None,
        strict_band_winner_accepted: bool = False,
        legacy_rejection_reason: str | None = None,
    ) -> dict[str, Any]:
        return {
            "selected_candidate": selected_candidate,
            "status": str(status),
            "selected_reason": selected_reason,
            "no_candidate_reason": no_candidate_reason,
            "strict_band_winner_seen": bool(strict_band_winner_seen),
            "strict_band_winner_accepted": bool(strict_band_winner_accepted),
            "strict_band_rejected_reason": strict_band_rejected_reason,
            "legacy_rejection_reason": legacy_rejection_reason,
        }

    while pool:
        pick = select_best_candidate_fn(pool, mode, seed) if callable(select_best_candidate_fn) else None
        if pick is None:
            return {
                "selected_candidate": None,
                "selector_result": _selector_result(
                    selected_candidate=None,
                    status="no_result",
                    no_candidate_reason="selector_returned_none",
                ),
                "rank_events": tuple(rank_events),
                "trace_entries": tuple(trace_entries),
            }
        band_seen = bool(pick.get("candidate_reaches_target_band")) and bool(pick.get("is_compliant"))
        if band_seen:
            strict_band_winner_seen = True
            strict_reject = False
            strict_reason = ""
            if callable(strict_band_guard_fn):
                guard_result = strict_band_guard_fn(pick)
                if isinstance(guard_result, (list, tuple)) and len(guard_result) >= 2:
                    strict_reject = bool(guard_result[0])
                    strict_reason = str(guard_result[1])
            if strict_reject:
                strict_band_rejected_reason = str(strict_reason)
                _log("rejected", pick, f"strict_band_reject:{strict_reason}")
                _trace(
                    {
                        "final_selector_band_winner_seen": True,
                        "final_selector_band_winner_accepted": False,
                        "final_selector_band_winner_rejected_reason": str(strict_reason),
                        "final_selector_used_strict_band_accept_rule": True,
                        "winner_pool_mode": pick.get("winner_pool_mode"),
                        "selected_because_band": bool(pick.get("winning_candidate_selected_from_band_reachers")),
                    },
                )
                pool = [candidate for candidate in pool if candidate is not pick]
                continue
            legacy_reason = (
                legacy_rejection_reason_fn(pick)
                if callable(legacy_rejection_reason_fn)
                else None
            )
            _log(
                "accepted",
                pick,
                "strict_band_winner_accept",
                util_before=seed_du if ductility_seed else seed_bu_f,
                util_after=(
                    candidate_ductility_util_fn(pick)
                    if ductility_seed and callable(candidate_ductility_util_fn)
                    else pick.get("candidate_post_util")
                ),
            )
            _trace(
                {
                    "final_selector_band_winner_seen": True,
                    "final_selector_band_winner_accepted": True,
                    "final_selector_band_winner_rejected_reason": None,
                    "final_selector_used_strict_band_accept_rule": True,
                    "winner_pool_mode": pick.get("winner_pool_mode"),
                    "selected_because_band": bool(pick.get("winning_candidate_selected_from_band_reachers")),
                    "final_winner_label": str(pick.get("label") or ""),
                    "final_winner_reaches_target_band": bool(pick.get("candidate_reaches_target_band")),
                    "final_winner_post_util": pick.get("candidate_post_util"),
                    "final_winner_goal_score": pick.get("candidate_goal_score"),
                    "final_selector_band_winner_would_have_legacy_reject_reason": legacy_reason,
                    "final_selector_band_winner_accepted_over_legacy_gate": bool(legacy_reason),
                },
            )
            return {
                "selected_candidate": pick,
                "selector_result": _selector_result(
                    selected_candidate=pick,
                    status="selected",
                    selected_reason="strict_band_winner_accept",
                    strict_band_winner_accepted=True,
                    legacy_rejection_reason=legacy_reason,
                ),
                "rank_events": tuple(rank_events),
                "trace_entries": tuple(trace_entries),
            }
        if not str(pick.get("label") or "").strip():
            _log("rejected", pick, "missing_label")
            pool = [candidate for candidate in pool if candidate is not pick]
            continue
        if callable(updates_match_state_fn) and bool(updates_match_state_fn(pick.get("updates") or {})):
            _log("rejected", pick, "noop_updates_match_state")
            pool = [candidate for candidate in pool if candidate is not pick]
            continue
        bu = ((pick.get("overview") or {}).get("utils") or {}).get("bending")
        try:
            bu_f = float(bu) if bu is not None else None
        except (TypeError, ValueError):
            bu_f = None
        if bu_f is None:
            _log("rejected", pick, "missing_bending_util")
            pool = [candidate for candidate in pool if candidate is not pick]
            continue
        if ductility_seed:
            pdu = candidate_ductility_util_fn(pick) if callable(candidate_ductility_util_fn) else None
            if seed_du is not None and pdu is not None and float(pdu) >= float(seed_du) - 1e-9:
                _log(
                    "rejected",
                    pick,
                    "ductility_not_improved",
                    util_before=float(seed_du),
                    util_after=float(pdu),
                )
                pool = [candidate for candidate in pool if candidate is not pick]
                continue
        elif seed_bu_f is not None and float(bu_f) >= float(seed_bu_f) - 1e-9:
            _log(
                "rejected",
                pick,
                "bending_util_not_improved",
                util_before=float(seed_bu_f),
                util_after=float(bu_f),
            )
            pool = [candidate for candidate in pool if candidate is not pick]
            continue
        _log(
            "accepted",
            pick,
            "selector_top_valid",
            util_before=seed_du if ductility_seed else seed_bu_f,
            util_after=(
                candidate_ductility_util_fn(pick)
                if ductility_seed and callable(candidate_ductility_util_fn)
                else bu_f
            ),
        )
        _trace(
            {
                "final_selector_band_winner_seen": False,
                "final_selector_band_winner_accepted": False,
                "final_selector_band_winner_rejected_reason": None,
                "final_selector_used_strict_band_accept_rule": False,
                "winner_pool_mode": pick.get("winner_pool_mode"),
                "selected_because_band": bool(pick.get("winning_candidate_selected_from_band_reachers")),
                "final_winner_label": str(pick.get("label") or ""),
                "final_winner_reaches_target_band": bool(pick.get("candidate_reaches_target_band")),
                "final_winner_post_util": pick.get("candidate_post_util"),
                "final_winner_goal_score": pick.get("candidate_goal_score"),
            },
        )
        return {
            "selected_candidate": pick,
            "selector_result": _selector_result(
                selected_candidate=pick,
                status="selected",
                selected_reason="selector_top_valid",
            ),
            "rank_events": tuple(rank_events),
            "trace_entries": tuple(trace_entries),
        }
    return {
        "selected_candidate": None,
        "selector_result": _selector_result(
            selected_candidate=None,
            status="no_result",
            no_candidate_reason="selector_pool_exhausted",
        ),
        "rank_events": tuple(rank_events),
        "trace_entries": tuple(trace_entries),
    }


def _selected_recommendation_forbidden_fields(value: Any) -> tuple[str, ...]:
    found: set[str] = set()

    def _walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, val in item.items():
                key_text = str(key)
                if key_text in _SELECTED_RECOMMENDATION_FORBIDDEN_KEYS:
                    found.add(key_text)
                _walk(val)
        elif isinstance(item, (list, tuple, set)):
            for val in item:
                _walk(val)

    _walk(value)
    return tuple(sorted(found))


_BOTTOM_REO_CTA_INTENT_FORBIDDEN_KEYS = {
    "apply_actionable",
    "apply_enabled",
    "button_contract",
    "button_contract_enabled",
    "cta_source_precedence",
    "debug",
    "debug_trace",
    "disabled_reason",
    "enabled",
    "final_button_contract",
    "final_enabled",
    "final_rendered_button_label",
    "html",
    "one_click_fallback_route",
    "one_click_routing",
    "publication",
    "publication_gate",
    "published",
    "render",
    "rendered_button_label",
    "selected_family_publication_gate",
    "session",
    "session_state",
    "shared_source_precedence_decision",
    "ui",
    "visible_wording",
}


_BOTTOM_REO_TIGHTENING_PROOF_FORBIDDEN_KEYS = {
    "button_label",
    "button_contract",
    "displayed_primary_button_contract",
    "primary_button_contract",
    "source_precedence",
    "selected_family_publication_gate",
    "publication",
    "published_item",
    "render",
    "rendered",
    "html",
    "visible_wording",
    "visible_blocked_wording",
    "one_click",
    "one_click_fallback",
    "session",
    "session_state",
    "debug",
    "debug_trace",
    "ui",
}


def _bottom_reo_cta_intent_forbidden_fields(value: Any) -> tuple[str, ...]:
    found: set[str] = set()

    def _walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, val in item.items():
                key_text = str(key)
                if key_text in _BOTTOM_REO_CTA_INTENT_FORBIDDEN_KEYS:
                    found.add(key_text)
                _walk(val)
        elif isinstance(item, (list, tuple, set)):
            for val in item:
                _walk(val)

    _walk(value)
    return tuple(sorted(found))


def _bottom_reo_tightening_proof_forbidden_fields(value: Any) -> tuple[str, ...]:
    found: set[str] = set()

    def _walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, val in item.items():
                key_text = str(key)
                if key_text in _BOTTOM_REO_TIGHTENING_PROOF_FORBIDDEN_KEYS:
                    found.add(key_text)
                _walk(val)
        elif isinstance(item, (list, tuple, set)):
            for val in item:
                _walk(val)

    _walk(value)
    return tuple(sorted(found))


def _selected_recommendation_summary(value: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key, val in _record_dict(value).items():
        if isinstance(val, (str, int, float, bool)) or val is None:
            summary[str(key)] = val
        elif isinstance(val, (list, tuple, set)):
            summary[str(key)] = tuple(str(item) for item in val)
        elif isinstance(val, dict):
            summary[str(key)] = {
                str(child_key): child_val
                for child_key, child_val in val.items()
                if isinstance(child_val, (str, int, float, bool)) or child_val is None
            }
        else:
            summary[f"{key}_hash"] = _stable_boundary_hash(val)
    return summary


def build_bottom_reo_selected_recommendation_proof(
    *,
    selected_candidate_identity: str | None,
    selected_source: str | None = None,
    selected_source_index: int | None = None,
    arrangement: dict[str, Any] | None = None,
    updates: dict[str, Any] | None = None,
    actual_ast: float | int | str | None = None,
    required_ast: float | int | str | None = None,
    util: float | int | str | None = None,
    label: str | None = None,
    score: float | int | str | None = None,
    recommendation_compound: bool | None = None,
    subfamilies: list[str] | tuple[str, ...] | None = None,
    recommendation_family_tag: str | None = None,
    guidance_recommendation_title: str | None = None,
    delta_b_mm: float | int | str | None = None,
    delta_D_mm: float | int | str | None = None,
    delta_Ast_bot: float | int | str | None = None,
    guidance_change_lines: list[str] | tuple[str, ...] | None = None,
    utilisation_check_summary: dict[str, Any] | None = None,
    selected_candidate_trace_hash: str | None = None,
) -> BottomReoSelectedRecommendation:
    """Build a proof-only selected-recommendation result shape.

    The helper consumes explicit values gathered after current page-local
    selection. It does not receive candidate dictionaries, mutate inputs, run
    selection, build CTA/action payloads, publish, render, or access
    UI/session/debug state.
    """

    arrangement_shape = _record_dict(
        arrangement,
        allowed_keys=_SELECTED_RECOMMENDATION_ALLOWED_ARRANGEMENT_KEYS,
    )
    update_shape = _record_dict(updates)
    returned_update_keys = tuple(sorted(str(key) for key in update_shape.keys()))
    returned_updates_hash = _stable_boundary_hash(update_shape)
    util_value = _record_float(util)
    line_tuple = _record_key_tuple(guidance_change_lines)
    summary = _selected_recommendation_summary(utilisation_check_summary)
    forbidden_fields = _selected_recommendation_forbidden_fields(
        {
            "arrangement": arrangement_shape,
            "updates": update_shape,
            "utilisation_check_summary": summary,
        }
    )
    shape_payload = {
        "selected_candidate_identity": (
            str(selected_candidate_identity)
            if selected_candidate_identity is not None
            else None
        ),
        "selected_source": str(selected_source) if selected_source is not None else None,
        "selected_source_index": (
            _record_int(selected_source_index)
            if selected_source_index is not None
            else None
        ),
        "arrangement": arrangement_shape,
        "updates": update_shape,
        "returned_update_keys": returned_update_keys,
        "returned_updates_hash": returned_updates_hash,
        "actual_ast": _record_float(actual_ast) or 0.0,
        "required_ast": _record_float(required_ast) or 0.0,
        "util": util_value,
        "label": str(label or ""),
        "score": _record_float(score) or 0.0,
        "recommendation_compound": bool(recommendation_compound),
        "subfamilies": _record_key_tuple(subfamilies),
        "recommendation_family_tag": (
            str(recommendation_family_tag)
            if recommendation_family_tag is not None
            else None
        ),
        "guidance_recommendation_title": (
            str(guidance_recommendation_title)
            if guidance_recommendation_title is not None
            else None
        ),
        "delta_b_mm": _record_float(delta_b_mm) or 0.0,
        "delta_D_mm": _record_float(delta_D_mm) or 0.0,
        "delta_Ast_bot": _record_float(delta_Ast_bot) or 0.0,
        "guidance_change_lines": line_tuple,
        "utilisation_check_summary": summary,
        "selected_candidate_trace_hash": (
            str(selected_candidate_trace_hash)
            if selected_candidate_trace_hash is not None
            else None
        ),
    }
    shape_hash = _stable_boundary_hash(shape_payload)
    proof_payload = {
        **shape_payload,
        "selected_recommendation_shape_hash": shape_hash,
        "forbidden_fields_present": forbidden_fields,
    }
    return BottomReoSelectedRecommendation(
        selected_candidate_identity=shape_payload["selected_candidate_identity"],
        selected_source=shape_payload["selected_source"],
        selected_source_index=shape_payload["selected_source_index"],
        arrangement=arrangement_shape,
        updates=update_shape,
        returned_update_keys=returned_update_keys,
        returned_updates_hash=returned_updates_hash,
        actual_ast=shape_payload["actual_ast"],
        required_ast=shape_payload["required_ast"],
        util=util_value,
        label=shape_payload["label"],
        score=shape_payload["score"],
        recommendation_compound=shape_payload["recommendation_compound"],
        subfamilies=shape_payload["subfamilies"],
        recommendation_family_tag=shape_payload["recommendation_family_tag"],
        guidance_recommendation_title=shape_payload["guidance_recommendation_title"],
        delta_b_mm=shape_payload["delta_b_mm"],
        delta_D_mm=shape_payload["delta_D_mm"],
        delta_Ast_bot=shape_payload["delta_Ast_bot"],
        guidance_change_lines=line_tuple,
        utilisation_check_summary=summary,
        selected_candidate_trace_hash=shape_payload["selected_candidate_trace_hash"],
        selected_recommendation_shape_hash=shape_hash,
        forbidden_fields_present=forbidden_fields,
        proof_hash=_stable_boundary_hash(proof_payload),
    )


def build_bottom_reo_selected_recommendation_proof_from_result(
    *,
    result: dict | None,
    decision: dict | None,
    selector_result: dict | None = None,
    return_status: str,
    return_reason: str,
) -> dict[str, Any]:
    """Project selected-recommendation proof inputs from plain trace records."""

    decision_d = dict(decision or {})
    selector_d = dict(selector_result or {})
    selected_identity = (
        selector_d.get("selected_candidate_identity")
        or decision_d.get("selected_candidate_identity")
        or None
    )
    ranked = [str(value) for value in list(decision_d.get("ranked_candidate_identities") or [])]
    selected_source_index = None
    if selected_identity is not None:
        selected_text = str(selected_identity)
        selected_source_index = ranked.index(selected_text) if selected_text in ranked else None
    result_d = dict(result or {})
    return build_bottom_reo_selected_recommendation_proof(
        selected_candidate_identity=selected_identity,
        selected_source="page_local_bottom_reo_selected_recommendation",
        selected_source_index=selected_source_index,
        arrangement=dict(result_d.get("arrangement") or {}),
        updates=dict(result_d.get("updates") or {}),
        actual_ast=result_d.get("actual_ast"),
        required_ast=result_d.get("required_ast"),
        util=result_d.get("util"),
        label=str(result_d.get("label") or ""),
        score=result_d.get("score"),
        recommendation_compound=bool(result_d.get("recommendation_compound")),
        subfamilies=list(result_d.get("subfamilies") or []),
        recommendation_family_tag=result_d.get("recommendation_family_tag"),
        guidance_recommendation_title=result_d.get("guidance_recommendation_title"),
        delta_b_mm=result_d.get("delta_b_mm"),
        delta_D_mm=result_d.get("delta_D_mm"),
        delta_Ast_bot=result_d.get("delta_Ast_bot"),
        guidance_change_lines=list(result_d.get("guidance_change_lines") or []),
        utilisation_check_summary={
            "selected_bending_util": selector_d.get("selected_bending_util") or decision_d.get("selected_bending_util"),
            "selected_candidate_post_util": selector_d.get("selected_candidate_post_util") or decision_d.get("selected_candidate_post_util"),
            "selected_reaches_target_band": selector_d.get("selected_reaches_target_band") or decision_d.get("selected_reaches_target_band"),
            "target_low": selector_d.get("target_low") or decision_d.get("target_low"),
            "target_high": selector_d.get("target_high") or decision_d.get("target_high"),
            "post_selector_guard_result": decision_d.get("post_selector_guard_result"),
            "return_status": return_status,
            "return_reason": return_reason,
        },
        selected_candidate_trace_hash=(
            selector_d.get("selected_candidate_trace_hash")
            or decision_d.get("selected_candidate_trace_hash")
        ),
    ).to_dict()


def build_bottom_reo_repair_blocked_reason_trace_projection(
    *,
    selected_proof: dict | None,
    decision: dict | None,
    selector_result: dict | None = None,
    ranking_result_boundary: dict | None = None,
    guard_surface: dict | None = None,
) -> dict[str, Any]:
    """Project repair/blocked proof surfaces from plain bottom-reo trace data."""

    proof_d = dict(selected_proof or {})
    decision_d = dict(decision or {})
    selector_d = dict(selector_result or {})
    ranking_d = dict(ranking_result_boundary or {})
    guard_d = dict(guard_surface or {})
    selected = bool(proof_d.get("selected_candidate_identity"))
    selected_update_hash_surface = {
        "selected_candidate_update_keys": list(decision_d.get("selected_candidate_update_keys") or []),
        "selected_candidate_updates_hash": decision_d.get("selected_candidate_updates_hash"),
        "final_result_update_keys": list(decision_d.get("final_result_update_keys") or []),
        "final_result_updates_hash": decision_d.get("final_result_updates_hash"),
        "proof_returned_update_keys": list(proof_d.get("returned_update_keys") or []),
        "proof_returned_updates_hash": proof_d.get("returned_updates_hash"),
    }
    raw_reasons = {
        "decision_no_result_reason": decision_d.get("no_result_reason"),
        "selector_no_candidate_reason": selector_d.get("no_candidate_reason"),
        "selector_legacy_rejection_reason": selector_d.get("legacy_rejection_reason"),
        "selector_strict_band_rejected_reason": selector_d.get("strict_band_rejected_reason"),
        "post_selector_guard_result": decision_d.get("post_selector_guard_result"),
    }
    selector_trace_reasons = {
        "reason_kind": "trace_proof_only",
        "raw_reasons": raw_reasons,
        "tracked_reasons": {
            key: any(str(value or "") == key for value in raw_reasons.values())
            for key in (
                "no_filtered_candidates",
                "no_selected_candidate",
                "growth_blocked_efficiency_reduction",
            )
        },
        "visible_blocked_wording_materialized": False,
        "visible_blocked_wording_source": None,
    }
    if selected:
        repair_reason_source_surface = {
            "reason_kind": "visible_guidance_text_source",
            "source": "selected_recommendation_proof",
            "selected_candidate_identity": proof_d.get("selected_candidate_identity"),
            "label": proof_d.get("label"),
            "guidance_recommendation_title": proof_d.get("guidance_recommendation_title"),
            "guidance_change_lines": list(proof_d.get("guidance_change_lines") or []),
            "utilisation_check_summary": dict(proof_d.get("utilisation_check_summary") or {}),
            "returned_update_keys": list(proof_d.get("returned_update_keys") or []),
            "returned_updates_hash": proof_d.get("returned_updates_hash"),
            "visible_reason_rows_materialized": False,
        }
        blocked_reason_source_surface = {
            "reason_kind": "not_applicable_selected_recommendation",
            "trace_reason_surface": selector_trace_reasons,
            "visible_blocked_wording_materialized": False,
            "visible_blocked_wording_source": None,
        }
    else:
        repair_reason_source_surface = {
            "reason_kind": "not_produced",
            "source": None,
            "visible_guidance_text_source": None,
        }
        blocked_reason_source_surface = {
            "reason_kind": "trace_proof_only",
            "trace_reason_surface": selector_trace_reasons,
            "visible_blocked_wording_materialized": False,
            "visible_blocked_wording_source": None,
        }
    reason_visibility_surface = {
        "selected_result_label": "visible_guidance_text_source" if selected else "not_produced",
        "selected_result_guidance_change_lines": "visible_guidance_text_source" if selected else "not_produced",
        "selector_no_result_reason": "trace_proof_only",
        "selector_no_candidate_reason": "trace_proof_only",
        "blocked_reason": "not_visible_from_bottom_reo_selector",
    }
    visible_guidance_text_source = (
        {
            "source": repair_reason_source_surface.get("source"),
            "selected_candidate_identity": repair_reason_source_surface.get("selected_candidate_identity"),
            "label": repair_reason_source_surface.get("label"),
            "guidance_recommendation_title": repair_reason_source_surface.get("guidance_recommendation_title"),
            "guidance_change_lines": list(repair_reason_source_surface.get("guidance_change_lines") or []),
        }
        if repair_reason_source_surface.get("reason_kind") == "visible_guidance_text_source"
        else None
    )
    selected_recommendation_handoff_hash = _stable_boundary_hash(
        {
            "ranking_result_hash": ranking_d.get("ranking_result_hash"),
            "selector_result": selector_d,
            "selected_candidate_decision": decision_d,
            "selected_recommendation_shape_hash": proof_d.get("selected_recommendation_shape_hash"),
            "selected_recommendation_proof_hash": proof_d.get("proof_hash"),
            "guards": guard_d,
        }
    )
    reason_proof = build_bottom_reo_repair_blocked_reason_proof(
        selected_recommendation_identity=proof_d.get("selected_candidate_identity"),
        selected_recommendation_proof_hash=proof_d.get("proof_hash"),
        selected_recommendation_shape_hash=proof_d.get("selected_recommendation_shape_hash"),
        selected_recommendation_handoff_hash=selected_recommendation_handoff_hash,
        selected_candidate_identity=(
            selector_d.get("selected_candidate_identity")
            or decision_d.get("selected_candidate_identity")
            or None
        ),
        selected_candidate_trace_hash=(
            selector_d.get("selected_candidate_trace_hash")
            or decision_d.get("selected_candidate_trace_hash")
        ),
        selected_update_hash_surface=selected_update_hash_surface,
        selector_guard_outcomes=guard_d,
        selector_trace_reasons=selector_trace_reasons,
        repair_reason_source_surface=repair_reason_source_surface,
        blocked_reason_source_surface=blocked_reason_source_surface,
        reason_visibility_surface=reason_visibility_surface,
        visible_guidance_text_source=visible_guidance_text_source,
    ).to_dict()
    return {
        "selected_recommendation_handoff_hash": selected_recommendation_handoff_hash,
        "selected_update_hash_surface": selected_update_hash_surface,
        "selector_trace_reasons": selector_trace_reasons,
        "repair_reason_source_surface": repair_reason_source_surface,
        "blocked_reason_source_surface": blocked_reason_source_surface,
        "reason_visibility_surface": reason_visibility_surface,
        "visible_guidance_text_source": visible_guidance_text_source,
        "repair_blocked_reason_proof": reason_proof,
        "repair_blocked_reason_proof_hash": reason_proof.get("proof_hash"),
    }


def build_bottom_reo_repair_blocked_reason_proof(
    *,
    selected_recommendation_identity: str | None = None,
    selected_recommendation_proof_hash: str | None = None,
    selected_recommendation_shape_hash: str | None = None,
    selected_recommendation_handoff_hash: str | None = None,
    selected_candidate_identity: str | None = None,
    selected_candidate_trace_hash: str | None = None,
    selected_update_hash_surface: dict[str, Any] | None = None,
    selector_guard_outcomes: dict[str, Any] | None = None,
    selector_trace_reasons: dict[str, Any] | None = None,
    repair_reason_source_surface: dict[str, Any] | None = None,
    blocked_reason_source_surface: dict[str, Any] | None = None,
    reason_visibility_surface: dict[str, Any] | None = None,
    visible_guidance_text_source: dict[str, Any] | None = None,
) -> BottomReoRepairBlockedReasonProof:
    """Build a proof-only repair/blocked reason source surface.

    The helper consumes already-normalized page/verifier surfaces. It does not
    generate visible wording, promote trace-only reasons to visible blocked
    wording, build CTA/action payloads, publish, render, or observe
    UI/session/debug state.
    """

    update_surface = _record_dict(selected_update_hash_surface)
    guard_surface = _record_dict(selector_guard_outcomes)
    trace_surface = _record_dict(selector_trace_reasons)
    repair_surface = _record_dict(repair_reason_source_surface)
    blocked_surface = _record_dict(blocked_reason_source_surface)
    visibility_surface = _record_dict(reason_visibility_surface)
    visible_source = (
        _record_dict(visible_guidance_text_source)
        if isinstance(visible_guidance_text_source, dict)
        else None
    )
    proof_payload = {
        "selected_recommendation_identity": (
            str(selected_recommendation_identity)
            if selected_recommendation_identity is not None
            else None
        ),
        "selected_recommendation_proof_hash": (
            str(selected_recommendation_proof_hash)
            if selected_recommendation_proof_hash is not None
            else None
        ),
        "selected_recommendation_shape_hash": (
            str(selected_recommendation_shape_hash)
            if selected_recommendation_shape_hash is not None
            else None
        ),
        "selected_recommendation_handoff_hash": (
            str(selected_recommendation_handoff_hash)
            if selected_recommendation_handoff_hash is not None
            else None
        ),
        "selected_candidate_identity": (
            str(selected_candidate_identity)
            if selected_candidate_identity is not None
            else None
        ),
        "selected_candidate_trace_hash": (
            str(selected_candidate_trace_hash)
            if selected_candidate_trace_hash is not None
            else None
        ),
        "selected_update_hash_surface": update_surface,
        "selector_guard_outcomes": guard_surface,
        "selector_trace_reasons": trace_surface,
        "repair_reason_source_surface": repair_surface,
        "blocked_reason_source_surface": blocked_surface,
        "reason_visibility_surface": visibility_surface,
        "visible_guidance_text_source": visible_source,
    }
    forbidden_fields = _selected_recommendation_forbidden_fields(proof_payload)
    return BottomReoRepairBlockedReasonProof(
        selected_recommendation_identity=proof_payload["selected_recommendation_identity"],
        selected_recommendation_proof_hash=proof_payload["selected_recommendation_proof_hash"],
        selected_recommendation_shape_hash=proof_payload["selected_recommendation_shape_hash"],
        selected_recommendation_handoff_hash=proof_payload["selected_recommendation_handoff_hash"],
        selected_candidate_identity=proof_payload["selected_candidate_identity"],
        selected_candidate_trace_hash=proof_payload["selected_candidate_trace_hash"],
        selected_update_hash_surface=update_surface,
        selector_guard_outcomes=guard_surface,
        selector_trace_reasons=trace_surface,
        repair_reason_source_surface=repair_surface,
        blocked_reason_source_surface=blocked_surface,
        reason_visibility_surface=visibility_surface,
        visible_guidance_text_source=visible_source,
        forbidden_fields_present=forbidden_fields,
        proof_hash=_stable_boundary_hash(
            {
                **proof_payload,
                "forbidden_fields_present": forbidden_fields,
            }
        ),
    )


def build_bottom_reo_cta_intent_proof(
    *,
    selected_recommendation_identity: str | None = None,
    selected_recommendation_proof_hash: str | None = None,
    selected_recommendation_shape_hash: str | None = None,
    repair_blocked_reason_proof_hash: str | None = None,
    selected_update_hash_surface: dict[str, Any] | None = None,
    action_payload_identity: dict[str, Any] | None = None,
    action_intent_source: dict[str, Any] | None = None,
    intent_state: str | None = None,
    no_action_or_blocked_proof_source: dict[str, Any] | None = None,
) -> BottomReoCtaIntentProof:
    """Build a proof-only bottom-reo CTA/action intent shape.

    The helper consumes explicit proof/identity surfaces only. It does not
    resolve final button enabled state, choose CTA source precedence, publish,
    render visible wording, route apply behaviour, run one-click fallback, or
    observe UI/session/debug state.
    """

    update_surface = _record_dict(selected_update_hash_surface)
    payload_identity = _record_dict(action_payload_identity)
    intent_source = _record_dict(action_intent_source)
    no_action_surface = _record_dict(no_action_or_blocked_proof_source)
    state = str(intent_state or "not_materialized").strip() or "not_materialized"
    proof_payload = {
        "schema": "BottomReoCtaIntentProof.projected.v1",
        "proof_kind": "bottom_reo_cta_action_intent",
        "product_driving": False,
        "selected_recommendation_identity": (
            str(selected_recommendation_identity)
            if selected_recommendation_identity is not None
            else None
        ),
        "selected_recommendation_proof_hash": (
            str(selected_recommendation_proof_hash)
            if selected_recommendation_proof_hash is not None
            else None
        ),
        "selected_recommendation_shape_hash": (
            str(selected_recommendation_shape_hash)
            if selected_recommendation_shape_hash is not None
            else None
        ),
        "repair_blocked_reason_proof_hash": (
            str(repair_blocked_reason_proof_hash)
            if repair_blocked_reason_proof_hash is not None
            else None
        ),
        "selected_update_hash_surface": update_surface,
        "action_payload_identity": payload_identity,
        "action_intent_source": intent_source,
        "intent_state": state,
        "no_action_or_blocked_proof_source": no_action_surface,
    }
    forbidden_fields = _bottom_reo_cta_intent_forbidden_fields(proof_payload)
    proof_hash = _stable_boundary_hash(
        {
            **proof_payload,
            "forbidden_fields_present": forbidden_fields,
        }
    )
    return BottomReoCtaIntentProof(
        schema=proof_payload["schema"],
        proof_kind=proof_payload["proof_kind"],
        product_driving=False,
        selected_recommendation_identity=proof_payload["selected_recommendation_identity"],
        selected_recommendation_proof_hash=proof_payload["selected_recommendation_proof_hash"],
        selected_recommendation_shape_hash=proof_payload["selected_recommendation_shape_hash"],
        repair_blocked_reason_proof_hash=proof_payload["repair_blocked_reason_proof_hash"],
        selected_update_hash_surface=update_surface,
        action_payload_identity=payload_identity,
        action_intent_source=intent_source,
        intent_state=state,
        no_action_or_blocked_proof_source=no_action_surface,
        forbidden_fields_present=forbidden_fields,
        cta_intent_proof_hash=proof_hash,
    )


def build_bottom_reo_cta_intent_trace_projection(
    *,
    selected_proof: dict | None,
    reason_proof: dict | None,
    selected_update_hash_surface: dict | None,
    action_payload_identity: dict | None,
    selector_trace_reasons: dict | None,
    return_reason: str | None,
) -> dict[str, Any]:
    """Project trace-only CTA intent proof from bottom-reo proof surfaces."""

    proof_d = dict(selected_proof or {})
    reason_d = dict(reason_proof or {})
    update_surface = dict(selected_update_hash_surface or {})
    action_identity = dict(action_payload_identity or {})
    trace_reasons = dict(selector_trace_reasons or {})
    action_materialized = bool(action_identity.get("materialized"))
    intent_state = (
        "actionable_candidate"
        if action_materialized
        else (
            "trace_only_no_selection"
            if str(return_reason or "") in {"no_filtered_candidates", "no_selected_candidate"}
            else "not_materialized"
        )
    )
    cta_intent_proof = build_bottom_reo_cta_intent_proof(
        selected_recommendation_identity=proof_d.get("selected_candidate_identity"),
        selected_recommendation_proof_hash=proof_d.get("proof_hash"),
        selected_recommendation_shape_hash=proof_d.get("selected_recommendation_shape_hash"),
        repair_blocked_reason_proof_hash=reason_d.get("proof_hash"),
        selected_update_hash_surface=update_surface,
        action_payload_identity={
            "materialized": action_materialized,
            "action_type": action_identity.get("action_type"),
            "action_type_source": action_identity.get("action_kind_source"),
            "payload_hash": action_identity.get("payload_hash"),
            "update_keys": list(action_identity.get("update_keys") or []),
            "updates_hash": action_identity.get("updates_hash"),
        },
        action_intent_source={
            "source": action_identity.get("source"),
            "recommendation_family_tag": proof_d.get("recommendation_family_tag"),
            "subfamilies": list(proof_d.get("subfamilies") or []),
            "recommendation_compound": bool(proof_d.get("recommendation_compound")),
        },
        intent_state=intent_state,
        no_action_or_blocked_proof_source=(
            trace_reasons
            if not action_materialized
            else {}
        ),
    ).to_dict()
    return {
        "action_materialized": action_materialized,
        "intent_state": intent_state,
        "bottom_reo_cta_intent_proof": cta_intent_proof,
        "bottom_reo_cta_intent_proof_hash": cta_intent_proof.get("cta_intent_proof_hash"),
        "bottom_reo_cta_intent_action_payload_identity": {
            key: value
            for key, value in action_identity.items()
            if key != "payload"
        },
    }


def build_bottom_reo_trace_proof_payload_projection(
    *,
    result: dict | None,
    decision: dict | None,
    selector_result: dict | None = None,
    ranking_result_boundary: dict | None = None,
    guard_surface: dict | None = None,
    return_status: str,
    return_reason: str,
    include_selected_recommendation_proof: bool,
    trace_scenario: str | None = None,
) -> dict[str, Any]:
    """Build the non-authoritative bottom-reo runtime trace proof payload."""

    decision_d = dict(decision or {})
    selector_d = dict(selector_result or {})
    ranking_d = dict(ranking_result_boundary or {})
    guard_d = dict(guard_surface or {})
    selected_proof = build_bottom_reo_selected_recommendation_proof_from_result(
        result=result,
        decision=decision_d,
        selector_result=selector_d,
        return_status=return_status,
        return_reason=return_reason,
    )
    reason_projection = build_bottom_reo_repair_blocked_reason_trace_projection(
        selected_proof=selected_proof,
        decision=decision_d,
        selector_result=selector_d,
        ranking_result_boundary=ranking_d,
        guard_surface=guard_d,
    )
    selected_update_hash_surface = dict(reason_projection.get("selected_update_hash_surface") or {})
    selector_trace_reasons = dict(reason_projection.get("selector_trace_reasons") or {})
    reason_visibility_surface = dict(reason_projection.get("reason_visibility_surface") or {})
    reason_proof = dict(reason_projection.get("repair_blocked_reason_proof") or {})
    action_payload_identity = build_bottom_reo_trace_guidance_action_payload_identity(result)
    cta_projection = build_bottom_reo_cta_intent_trace_projection(
        selected_proof=selected_proof,
        reason_proof=reason_proof,
        selected_update_hash_surface=selected_update_hash_surface,
        action_payload_identity=action_payload_identity,
        selector_trace_reasons=selector_trace_reasons,
        return_reason=return_reason,
    )
    cta_intent_proof = dict(cta_projection.get("bottom_reo_cta_intent_proof") or {})
    scenario = str(trace_scenario or "").strip() or None
    trace_proof_handoff_hash = _stable_boundary_hash(
        {
            "scenario": scenario,
            "decision_identity_hash": _stable_boundary_hash(
                {
                    "selected_candidate_identity": (
                        selector_d.get("selected_candidate_identity")
                        or decision_d.get("selected_candidate_identity")
                        or None
                    ),
                    "selected_candidate_trace_hash": (
                        selector_d.get("selected_candidate_trace_hash")
                        or decision_d.get("selected_candidate_trace_hash")
                    ),
                    "post_selector_guard_result": decision_d.get("post_selector_guard_result"),
                    "no_result_reason": decision_d.get("no_result_reason"),
                }
            ),
            "selected_update_hash_surface": selected_update_hash_surface,
            "selected_recommendation_proof_hash": selected_proof.get("proof_hash"),
            "repair_blocked_reason_proof_hash": reason_proof.get("proof_hash"),
            "no_result_reason_surfaces": selector_trace_reasons,
        }
    )
    payload = {
        "trace_proof_callsite": "inputs_page.py:_compute_bottom_reo_recommendation:selected_candidate_decision_trace",
        "trace_proof_handoff_hash": trace_proof_handoff_hash,
        "repair_blocked_reason_proof": reason_proof,
        "repair_blocked_reason_proof_json": json.dumps(reason_proof, sort_keys=True, default=str),
        "repair_blocked_reason_proof_hash": reason_proof.get("proof_hash"),
        "bottom_reo_cta_intent_proof": cta_intent_proof,
        "bottom_reo_cta_intent_proof_json": json.dumps(cta_intent_proof, sort_keys=True, default=str),
        "bottom_reo_cta_intent_proof_hash": cta_intent_proof.get("cta_intent_proof_hash"),
        "bottom_reo_cta_intent_action_payload_identity": dict(
            cta_projection.get("bottom_reo_cta_intent_action_payload_identity") or {}
        ),
        "selector_trace_reason_surface": selector_trace_reasons,
        "reason_visibility_surface": reason_visibility_surface,
        "visible_blocked_wording_materialized": False,
    }
    if include_selected_recommendation_proof:
        payload.update(
            {
                "selected_recommendation_proof": selected_proof,
                "selected_recommendation_proof_json": json.dumps(selected_proof, sort_keys=True, default=str),
                "selected_recommendation_proof_hash": selected_proof.get("proof_hash"),
                "selected_recommendation_shape_hash": selected_proof.get("selected_recommendation_shape_hash"),
            }
        )
    return payload


def build_bottom_reo_trace_guidance_action_payload_identity(result: dict | None) -> dict[str, Any]:
    """Build trace-only bottom-reo action payload identity from a result dict."""

    result_d = dict(result or {})
    updates = dict(result_d.get("updates") or {})
    if not updates:
        return {
            "materialized": False,
            "source": "bottom_reo_recommendation:no_action",
            "action_type": None,
            "payload": {},
            "payload_hash": _stable_boundary_hash({}),
            "update_keys": [],
            "updates_hash": _stable_boundary_hash({}),
            "action_kind_source": "no_selected_bottom_reo_recommendation",
        }
    title = (
        str(result_d.get("guidance_recommendation_title") or result_d.get("label") or "").strip()
        or "Apply bottom recommendation"
    )
    action_type = (
        "apply_compound_guidance"
        if bool(result_d.get("recommendation_compound"))
        else "apply_bottom_recommendation"
    )
    payload = {
        "updates": updates,
        "guidance_banner_title": title,
        "label": title,
    }
    return {
        "materialized": True,
        "source": "inputs_page.py:_get_one_click_band_reaching_candidate:bottom_recommendation_option",
        "action_type": action_type,
        "payload": payload,
        "payload_hash": _stable_boundary_hash(payload),
        "update_keys": sorted(str(key) for key in updates.keys()),
        "updates_hash": _stable_boundary_hash(updates),
        "action_kind_source": (
            "recommendation_compound"
            if bool(result_d.get("recommendation_compound"))
            else "bottom_recommendation"
        ),
    }


def build_bottom_reo_tightening_recommendation_proof(
    *,
    input_design_reo_state: dict[str, Any] | None = None,
    tightening_candidate_options: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    rejected_candidate_reasons: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    accepted_candidate_count: int | None = None,
    accepted_candidate_identities: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    selected_tightening_recommendation: dict[str, Any] | None = None,
    selected_candidate_summary: dict[str, Any] | None = None,
    no_recommendation_reason: str | None = None,
    update_action_payload_identity: dict[str, Any] | None = None,
    utilisation_target_band_surface: dict[str, Any] | None = None,
    repair_blocked_reason_source_surface: dict[str, Any] | None = None,
    cta_action_intent_source_surface: dict[str, Any] | None = None,
) -> BottomReoTighteningRecommendationProof:
    """Build the proof-only bottom-reo tightening recommendation surface.

    The helper normalizes explicit verifier/page surfaces only. It does not run
    tightening generation, filtering, selection, CTA rendering/source
    precedence, publication, apply routing, one-click fallback, visible wording,
    or UI/session/debug behaviour.
    """

    options = tuple(_record_dict(item) for item in (tightening_candidate_options or ()))
    rejects = tuple(_record_dict(item) for item in (rejected_candidate_reasons or ()))
    accepted = tuple(_record_dict(item) for item in (accepted_candidate_identities or ()))
    selected = (
        _record_dict(selected_tightening_recommendation)
        if isinstance(selected_tightening_recommendation, dict)
        else None
    )
    selected_summary = (
        _record_dict(selected_candidate_summary)
        if isinstance(selected_candidate_summary, dict)
        else None
    )
    proof_surface = {
        "input_design_reo_state": _record_dict(input_design_reo_state),
        "tightening_candidate_options": list(options),
        "rejected_candidate_reasons": list(rejects),
        "accepted_candidate_count": (
            _record_int(accepted_candidate_count)
            if accepted_candidate_count is not None
            else len(accepted)
        ),
        "accepted_candidate_identities": list(accepted),
        "selected_tightening_recommendation": selected,
        "selected_candidate_summary": selected_summary,
        "no_recommendation_reason": (
            str(no_recommendation_reason)
            if no_recommendation_reason is not None
            else None
        ),
        "update_action_payload_identity": _record_dict(update_action_payload_identity),
        "utilisation_target_band_surface": _record_dict(utilisation_target_band_surface),
        "repair_blocked_reason_source_surface": _record_dict(repair_blocked_reason_source_surface),
        "cta_action_intent_source_surface": _record_dict(cta_action_intent_source_surface),
    }
    forbidden_fields = _bottom_reo_tightening_proof_forbidden_fields(proof_surface)
    return BottomReoTighteningRecommendationProof(
        input_design_reo_state=proof_surface["input_design_reo_state"],
        tightening_candidate_options=options,
        rejected_candidate_reasons=rejects,
        accepted_candidate_count=proof_surface["accepted_candidate_count"],
        accepted_candidate_identities=accepted,
        selected_tightening_recommendation=selected,
        selected_candidate_summary=selected_summary,
        no_recommendation_reason=proof_surface["no_recommendation_reason"],
        update_action_payload_identity=proof_surface["update_action_payload_identity"],
        utilisation_target_band_surface=proof_surface["utilisation_target_band_surface"],
        repair_blocked_reason_source_surface=proof_surface["repair_blocked_reason_source_surface"],
        cta_action_intent_source_surface=proof_surface["cta_action_intent_source_surface"],
        forbidden_fields_present=forbidden_fields,
        tightening_recommendation_hash=_stable_boundary_hash(proof_surface),
    )


def build_bottom_reo_evaluated_candidate_filter_boundary(
    *,
    records: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    input_arrangement_pool_hash: str | None = None,
    source_family_runtime_id: str | None = None,
) -> BottomReoEvaluatedCandidateFilterBoundary:
    """Normalize a report-only pre-rank evaluation/filter boundary."""

    normalised_records: list[dict[str, Any]] = []
    forbidden_fields: set[str] = set()
    for index, record in enumerate(records):
        normalised: dict[str, Any] = {"order_index": index}
        for key in sorted(record.keys()):
            if key in _EVALUATED_FILTER_FORBIDDEN_RECORD_KEYS:
                forbidden_fields.add(key)
                continue
            if key in _EVALUATED_FILTER_ALLOWED_RECORD_KEYS:
                normalised[key] = record.get(key)
        normalised_records.append(normalised)

    accepted_records = [
        record
        for record in normalised_records
        if record.get("status") == "accepted_prerank"
    ]
    accepted_ids = tuple(
        str(record.get("accepted_prerank_candidate_identity") or "")
        for record in accepted_records
    )
    return BottomReoEvaluatedCandidateFilterBoundary(
        input_arrangement_pool_hash=input_arrangement_pool_hash,
        source_family_runtime_id=source_family_runtime_id,
        evaluated_candidate_count=len(normalised_records),
        accepted_prerank_candidate_count=len(accepted_records),
        rejected_candidate_count=len(normalised_records) - len(accepted_records),
        accepted_prerank_candidate_ids=accepted_ids,
        accepted_prerank_order_hash=_stable_boundary_hash(accepted_ids) if accepted_ids else None,
        records=tuple(normalised_records),
        pre_rank_surface_hash=_stable_boundary_hash(normalised_records)
        if normalised_records
        else None,
        forbidden_fields_present=tuple(sorted(forbidden_fields)),
        ranking_selection_cta_publication_absent=not forbidden_fields,
    )


def build_bottom_reo_arrangement_pool(
    *,
    current_bot1_count: int,
    current_bot2_count: int,
    current_db_bot_1: int,
    design_width: float,
    cover_side: float,
    rowgap_bot: float,
    search_strategy: str,
    bar_diameters: list[int] | tuple[int, ...],
    band: int,
    ductility_priority: bool = False,
    limit: int | None = None,
    default_limit: int = 1,
    layout_fit_cache: dict | None = None,
) -> list[dict[str, Any]]:
    """Build the ordered bottom-reinforcement arrangement/spec pool.

    This helper owns only family-specific arrangement/spec generation. It does
    not evaluate, filter by utilisation, rank candidates, select a winner, emit
    trace/debug events, or build update payloads.
    """
    strategy = str(search_strategy or "balanced")
    count_1 = _as_int(current_bot1_count, 0)
    count_2 = _as_int(current_bot2_count, 0)
    dia = _as_int(current_db_bot_1, 20)
    resolved_band = max(_as_int(band, 0), 0)
    total_bars = max(count_1 + count_2, 2)
    diameters = [_as_int(item, 0) for item in list(bar_diameters or []) if _as_int(item, 0) > 0]

    if ductility_priority:
        dia_values = _bottom_reo_option_window(diameters, dia, down_steps=1 + resolved_band, up_steps=0)
        count_1_values = list(range(max(2, count_1 - 2 - resolved_band), min(12, count_1 + 1) + 1))
        count_2_values = sorted(set([0, max(0, count_2 - 1), max(0, count_2)]))
        if count_2 <= 0:
            count_2_values = [0]
    elif strategy == "shallow":
        dia_values = _bottom_reo_option_window(diameters, dia, down_steps=0, up_steps=1 + resolved_band)
        count_1_values = list(range(max(2, count_1), min(12, count_1 + 2 + resolved_band) + 1))
        count_2_values = (
            [0]
            if count_2 <= 0
            else list(range(max(0, count_2), min(12, count_2 + 1 + resolved_band) + 1))
        )
        if count_2 <= 0:
            count_2_values.extend([2, 3 + resolved_band])
    elif strategy == "low_reo":
        dia_values = _bottom_reo_option_window(diameters, dia, down_steps=0, up_steps=1 + resolved_band)
        count_1_values = list(range(max(2, count_1 - 2 - resolved_band), min(12, count_1 + 1) + 1))
        count_2_values = [0, max(0, count_2 - 1), count_2]
        count_1_values.extend([
            max(2, total_bars - 2 - resolved_band),
            max(2, total_bars - 1),
            total_bars,
        ])
    else:
        dia_values = _bottom_reo_option_window(diameters, dia, down_steps=min(1, resolved_band), up_steps=1 + resolved_band)
        count_1_values = list(range(max(2, count_1 - 1 - resolved_band), min(12, count_1 + 2) + 1))
        count_2_values = [0] + list(range(max(0, count_2 - 1), min(12, count_2 + 1 + resolved_band) + 1))

    arrangements: dict[tuple[int, int, int], dict[str, Any]] = {}
    layout_cache = layout_fit_cache if isinstance(layout_fit_cache, dict) else {}
    for candidate_dia in dia_values:
        for candidate_count_1 in count_1_values:
            for candidate_count_2 in count_2_values:
                arrangement = _normalise_bottom_reo_layer_order({
                    "bot1_layout_mode": "Count",
                    "bot1_count": int(candidate_count_1),
                    "db_bot_1": int(candidate_dia),
                    "bot2_layout_mode": "Count",
                    "bot2_count": int(max(candidate_count_2, 0)),
                    "db_bot_2": int(candidate_dia),
                })
                signature = (
                    int(arrangement.get("bot1_count", 0) or 0),
                    int(arrangement.get("bot2_count", 0) or 0),
                    int(arrangement.get("db_bot_1", 0) or 0),
                )
                if signature in arrangements:
                    continue
                if not _bottom_reo_arrangement_fits(
                    arrangement,
                    design_width=design_width,
                    cover_side=cover_side,
                    rowgap_bot=rowgap_bot,
                    layout_cache=layout_cache,
                ):
                    continue
                arrangements[signature] = arrangement

    def _arrangement_rank(item: dict) -> tuple:
        c1 = int(item.get("bot1_count", 0) or 0)
        c2 = int(item.get("bot2_count", 0) or 0)
        total = c1 + c2
        rows = 2 if c2 > 0 else 1
        candidate_dia = int(item.get("db_bot_1", 0) or 0)
        if ductility_priority:
            return (rows, total, candidate_dia)
        if strategy == "shallow":
            return (rows, -candidate_dia, -total)
        if strategy == "low_reo":
            return (rows, total, -candidate_dia)
        return (abs(total - total_bars), rows, abs(candidate_dia - dia))

    resolved_limit = _as_int(default_limit, 1) if limit is None else max(_as_int(limit, 1), 1)
    return [dict(item) for item in sorted(arrangements.values(), key=_arrangement_rank)[:resolved_limit]]


def _bottom_reo_design_width_value_from_state(state: dict[str, Any]) -> float:
    sec_shape = str(state.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return _as_float(state.get("bw", state.get("b", 300.0)), 300.0)
    if sec_shape == "I":
        return _as_float(state.get("tw", state.get("b", 200.0)), 200.0)
    return _as_float(state.get("b", 400.0), 400.0)


def build_bottom_reo_arrangement_pool_from_state(
    state: dict[str, Any],
    mode_config: dict[str, Any],
    *,
    band: int,
    context: dict[str, Any] | None = None,
    limit: int | None = None,
    bar_diameters: list[int] | tuple[int, ...],
    default_limit: int,
) -> list[dict[str, Any]]:
    """Build bottom-reo arrangement pool from plain state/config inputs.

    This owns only family-specific arrangement-pool invocation and primitive
    state/config normalization. It does not evaluate, filter, rank, select,
    publish, render, or touch UI/session state.
    """

    source_state = dict(state or {})
    config = dict(mode_config or {})
    layout_cache = context.setdefault("layout_fit_cache", {}) if isinstance(context, dict) else {}
    return build_bottom_reo_arrangement_pool(
        current_bot1_count=_as_int(source_state.get("bot1_count"), 0),
        current_bot2_count=_as_int(source_state.get("bot2_count"), 0),
        current_db_bot_1=_as_int(source_state.get("db_bot_1"), 20),
        design_width=_bottom_reo_design_width_value_from_state(source_state),
        cover_side=_as_float(source_state.get("cover_side"), 40.0),
        rowgap_bot=_as_float(source_state.get("rowgap_bot"), 60.0),
        search_strategy=str(config.get("search_strategy", "balanced") or "balanced"),
        bar_diameters=tuple(_as_int(item, 0) for item in list(bar_diameters or []) if _as_int(item, 0) > 0),
        band=_as_int(band, 0),
        ductility_priority=bool((context or {}).get("ductility_priority")),
        limit=limit,
        default_limit=_as_int(default_limit, 1),
        layout_fit_cache=layout_cache,
    )


def _bottom_reo_option_window(
    options: list[int] | tuple[int, ...],
    current_value: int,
    *,
    down_steps: int,
    up_steps: int,
) -> list[int]:
    values = list(options or [])
    if not values:
        return []
    if current_value in values:
        index = values.index(current_value)
    else:
        index = min(range(len(values)), key=lambda idx: abs(values[idx] - current_value))
    start = max(0, index - int(down_steps))
    stop = min(len(values), index + int(up_steps) + 1)
    return list(dict.fromkeys(values[start:stop]))


def _normalise_bottom_reo_layer_order(arrangement: dict) -> dict:
    normalised = dict(arrangement)
    bot1_count = int(normalised.get("bot1_count", 0) or 0)
    bot2_count = int(normalised.get("bot2_count", 0) or 0)
    db1 = int(normalised.get("db_bot_1", 0) or 0)
    db2 = int(normalised.get("db_bot_2", 0) or 0)

    layer2_is_preferred = False
    if db2 > db1:
        layer2_is_preferred = True
    elif db2 == db1 and bot2_count > bot1_count:
        layer2_is_preferred = True

    if layer2_is_preferred:
        normalised["bot1_layout_mode"], normalised["bot2_layout_mode"] = (
            normalised.get("bot2_layout_mode", "Count"),
            normalised.get("bot1_layout_mode", "Count"),
        )
        normalised["bot1_count"], normalised["bot2_count"] = bot2_count, bot1_count
        normalised["db_bot_1"], normalised["db_bot_2"] = db2, db1
    return normalised


def _bottom_reo_arrangement_fits(
    arrangement: dict,
    *,
    design_width: float,
    cover_side: float,
    rowgap_bot: float,
    layout_cache: dict | None = None,
) -> bool:
    from section_layout import compute_bar_layout_pure

    b = _as_float(design_width, 0.0)
    side_cover = _as_float(cover_side, 40.0)
    rowgap = _as_float(rowgap_bot, 60.0)
    dia = int(arrangement.get("db_bot_1", 0) or 0)
    count_1 = int(arrangement.get("bot1_count", 0) or 0)
    count_2 = int(arrangement.get("bot2_count", 0) or 0)
    if count_1 < 2 or dia <= 0:
        return False
    s_min = max(float(dia), 25.0)
    cache = layout_cache if isinstance(layout_cache, dict) else {}
    key_1 = (float(b), float(side_cover), float(rowgap), int(dia), int(count_1))
    layout_1 = cache.get(key_1)
    if layout_1 is None:
        layout_1 = compute_bar_layout_pure(
            b=b,
            cover_side=side_cover,
            nb_or_s=float(count_1),
            db=float(dia),
            s_min=s_min,
            rowgap=rowgap,
        )
        cache[key_1] = layout_1
    if not layout_1.get("fits_single_row", False):
        return False
    if count_2 > 0:
        if count_2 < 2:
            return False
        key_2 = (float(b), float(side_cover), float(rowgap), int(dia), int(count_2))
        layout_2 = cache.get(key_2)
        if layout_2 is None:
            layout_2 = compute_bar_layout_pure(
                b=b,
                cover_side=side_cover,
                nb_or_s=float(count_2),
                db=float(dia),
                s_min=s_min,
                rowgap=rowgap,
            )
            cache[key_2] = layout_2
        if not layout_2.get("fits_single_row", False):
            return False
    return True


def build_bottom_reo_candidate_pool_boundary(
    *,
    input_state_hash: str | None,
    current_bottom_reo_layout: dict[str, Any],
    generated_candidate_count: int,
    generated_candidate_ids: tuple[str, ...] | list[str],
    generated_candidate_order_hash: str | None,
    filtered_candidate_count: int,
    filtered_candidate_ids: tuple[str, ...] | list[str],
    filtered_candidate_order_hash: str | None,
    ranked_candidate_count: int,
    ranked_candidate_ids: tuple[str, ...] | list[str],
    ranked_candidate_order_hash: str | None,
    selected_candidate_id: str | None,
    selected_update_payload: dict[str, Any],
    selected_util_surfaces: dict[str, Any],
    reject_skip_reasons: dict[str, Any],
    target_band_status: dict[str, Any],
    source_family_runtime_id: str,
) -> BottomReoCandidatePoolBoundary:
    """Normalize the explicit bottom-reo candidate-pool proof boundary.

    The caller owns trace hashing and page-local candidate inspection. This
    helper only copies and normalizes already-resolved boundary fields.
    """
    return BottomReoCandidatePoolBoundary(
        input_state_hash=str(input_state_hash) if input_state_hash else None,
        current_bottom_reo_layout=dict(current_bottom_reo_layout or {}),
        generated_candidate_count=_as_int(generated_candidate_count, 0),
        generated_candidate_ids=tuple(str(item) for item in list(generated_candidate_ids or [])),
        generated_candidate_order_hash=(
            str(generated_candidate_order_hash) if generated_candidate_order_hash else None
        ),
        filtered_candidate_count=_as_int(filtered_candidate_count, 0),
        filtered_candidate_ids=tuple(str(item) for item in list(filtered_candidate_ids or [])),
        filtered_candidate_order_hash=(
            str(filtered_candidate_order_hash) if filtered_candidate_order_hash else None
        ),
        ranked_candidate_count=_as_int(ranked_candidate_count, 0),
        ranked_candidate_ids=tuple(str(item) for item in list(ranked_candidate_ids or [])),
        ranked_candidate_order_hash=str(ranked_candidate_order_hash) if ranked_candidate_order_hash else None,
        selected_candidate_id=str(selected_candidate_id) if selected_candidate_id else None,
        selected_update_payload=dict(selected_update_payload or {}),
        selected_util_surfaces=dict(selected_util_surfaces or {}),
        reject_skip_reasons=dict(reject_skip_reasons or {}),
        target_band_status=dict(target_band_status or {}),
        source_family_runtime_id=str(source_family_runtime_id or "normal_bottom_reo_recommendation"),
    )


def is_strictly_rejectable_bottom_reo_band_winner(
    *,
    candidate_is_valid: bool,
    is_compliant: bool,
    candidate_reaches_target_band: bool,
    updates_present: bool,
    updates_match_state: bool,
    label_present: bool,
) -> tuple[bool, str]:
    """Return the existing strict-band bottom-reo winner rejection decision."""
    if not bool(candidate_is_valid):
        return True, "invalid_candidate"
    if not bool(is_compliant):
        return True, "noncompliant_candidate"
    if not bool(candidate_reaches_target_band):
        return True, "not_target_band_candidate"
    if not bool(updates_present):
        return True, "missing_or_unusable_updates"
    if bool(updates_match_state):
        return True, "noop_updates_match_state"
    if not bool(label_present):
        return True, "missing_label"
    return False, "ok"


def assess_bottom_reo_strict_band_winner_candidate(
    candidate: dict | None,
    *,
    updates_match_state: bool,
) -> tuple[bool, str]:
    """Assess strict-band bottom-reo winner rejection from a plain candidate.

    The caller owns state comparison and passes `updates_match_state` as a
    primitive boolean. This keeps page/session state out of the family helper
    while moving the bottom-reo candidate interpretation into the family.
    """

    candidate_is_valid = isinstance(candidate, dict)
    updates = candidate.get("updates") if candidate_is_valid else None
    updates_present = isinstance(updates, dict) and bool(updates)
    return is_strictly_rejectable_bottom_reo_band_winner(
        candidate_is_valid=candidate_is_valid,
        is_compliant=bool(candidate.get("is_compliant")) if candidate_is_valid else False,
        candidate_reaches_target_band=(
            bool(candidate.get("candidate_reaches_target_band"))
            if candidate_is_valid
            else False
        ),
        updates_present=updates_present,
        updates_match_state=bool(updates_match_state) if updates_present else False,
        label_present=bool(str(candidate.get("label") or "").strip()) if candidate_is_valid else False,
    )


def resolve_bottom_reo_legacy_local_rejection_reason(
    pick: dict | None,
    *,
    seed_bending_util: float | int | str | None,
    ductility_seed: bool,
    seed_ductility_util: float | int | str | None,
) -> str | None:
    """Return the legacy local bottom-reo rejection reason for a candidate."""

    candidate = pick if isinstance(pick, dict) else {}
    bu = ((candidate.get("overview") or {}).get("utils") or {}).get("bending")
    try:
        bu_f = float(bu) if bu is not None else None
    except (TypeError, ValueError):
        bu_f = None
    if bu_f is None:
        return "missing_bending_util"
    try:
        seed_bu_f = float(seed_bending_util) if seed_bending_util is not None else None
    except (TypeError, ValueError):
        seed_bu_f = None
    try:
        seed_du_f = float(seed_ductility_util) if seed_ductility_util is not None else None
    except (TypeError, ValueError):
        seed_du_f = None
    if bool(ductility_seed):
        pdu = candidate_ductility_util(candidate)
        if seed_du_f is not None and pdu is not None and float(pdu) >= float(seed_du_f) - 1e-9:
            return "ductility_not_improved"
        return None
    if seed_bu_f is not None and float(bu_f) >= float(seed_bu_f) - 1e-9:
        return "bending_util_not_improved"
    return None


def resolve_bottom_reo_geometry_trial_axis(
    candidate: dict | None,
    *,
    width_key: str | None,
) -> str | None:
    """Return the bottom-reo geometry trial axis from plain candidate updates."""

    if not isinstance(candidate, dict) or not candidate.get("recommendation_geometry_trial"):
        return None
    updates = candidate.get("updates") or {}
    if not isinstance(updates, dict):
        return None
    if "D" in updates:
        return "depth"
    width_key_text = str(width_key or "").strip()
    if width_key_text and width_key_text in updates:
        return "width"
    return None


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value if value is not None else default)
    except (TypeError, ValueError):
        return int(default)


def _bending_util(candidate: dict) -> float:
    return _as_float(((candidate.get("overview") or {}).get("utils") or {}).get("bending"), 0.0)


def candidate_bending_component_util(candidate: dict, key: str) -> float | None:
    if not isinstance(candidate, dict):
        return None
    components = candidate.get("bending_components", {}) or {}
    raw = components.get(key)
    try:
        value = float(raw)
    except Exception:
        return None
    if math.isnan(value):
        return None
    return value


def candidate_ductility_util(candidate: dict) -> float | None:
    return candidate_bending_component_util(candidate, "ductility_util")


def candidate_flexural_util(candidate: dict) -> float | None:
    return candidate_bending_component_util(candidate, "flexural_util")


def candidate_min_steel_util(candidate: dict) -> float | None:
    return candidate_bending_component_util(candidate, "min_steel_util")


def candidate_ductility_governs(candidate: dict | None) -> bool:
    if not isinstance(candidate, dict):
        return False
    ductility_util = candidate_ductility_util(candidate)
    if ductility_util is None:
        return False
    governing = [
        value
        for value in (
            candidate_flexural_util(candidate),
            candidate_min_steel_util(candidate),
            ductility_util,
        )
        if value is not None
    ]
    if not governing:
        return False
    return ductility_util >= max(governing) - 1e-6 and ductility_util >= 0.85


_BOTTOM_REO_GUIDANCE_CHANGE_ARROW = (
    "\xc3\u0192\xc6\u2019\xc3\u2020\xe2\u20ac\u2122\xc3\u0192\xe2\u20ac\xa0"
    "\xc3\xa2\xe2\u201a\xac\xe2\u201e\xa2\xc3\u0192\xc6\u2019\xc3\xa2\xe2\u201a"
    "\xac\xc2\xa0\xc3\u0192\xc2\xa2\xc3\xa2\xe2\u20ac\u0161\xc2\xac\xc3\xa2"
    "\xe2\u20ac\u017e\xc2\xa2\xc3\u0192\xc6\u2019\xc3\u2020\xe2\u20ac\u2122"
    "\xc3\u0192\xc2\xa2\xc3\xa2\xe2\u20ac\u0161\xc2\xac\xc3\u2026\xc2\xa1"
    "\xc3\u0192\xc6\u2019\xc3\xa2\xe2\u201a\xac\xc5\xa1\xc3\u0192\xe2\u20ac"
    "\u0161\xc3\u201a\xc2\xa2\xc3\u0192\xc6\u2019\xc3\u2020\xe2\u20ac\u2122"
    "\xc3\u0192\xe2\u20ac\xa0\xc3\xa2\xe2\u201a\xac\xe2\u201e\xa2\xc3\u0192"
    "\xc6\u2019\xc3\xa2\xe2\u201a\xac\xc5\xa1\xc3\u0192\xe2\u20ac\u0161"
    "\xc3\u201a\xc2\xa2\xc3\u0192\xc6\u2019\xc3\u2020\xe2\u20ac\u2122\xc3"
    "\u0192\xe2\u20ac\u0161\xc3\u201a\xc2\xa2\xc3\u0192\xc6\u2019\xc3\u201a"
    "\xc2\xa2\xc3\u0192\xc2\xa2\xc3\xa2\xe2\u201a\xac\xc5\xa1\xc3\u201a"
    "\xc2\xac\xc3\u0192\xe2\u20ac\xa6\xc3\u201a\xc2\xa1\xc3\u0192\xc6\u2019"
    "\xc3\xa2\xe2\u201a\xac\xc5\xa1\xc3\u0192\xe2\u20ac\u0161\xc3\u201a"
    "\xc2\xac\xc3\u0192\xc6\u2019\xc3\u2020\xe2\u20ac\u2122\xc3\u0192\xc2"
    "\xa2\xc3\xa2\xe2\u20ac\u0161\xc2\xac\xc3\u2026\xc2\xa1\xc3\u0192"
    "\xc6\u2019\xc3\xa2\xe2\u201a\xac\xc5\xa1\xc3\u0192\xe2\u20ac\u0161"
    "\xc3\u201a\xc2\xa0\xc3\u0192\xc6\u2019\xc3\u2020\xe2\u20ac\u2122"
    "\xc3\u0192\xe2\u20ac\xa0\xc3\xa2\xe2\u201a\xac\xe2\u201e\xa2\xc3"
    "\u0192\xc6\u2019\xc3\xa2\xe2\u201a\xac\xc5\xa1\xc3\u0192\xe2\u20ac"
    "\u0161\xc3\u201a\xc2\xa2\xc3\u0192\xc6\u2019\xc3\u2020\xe2\u20ac"
    "\u2122\xc3\u0192\xe2\u20ac\u0161\xc3\u201a\xc2\xa2\xc3\u0192\xc6"
    "\u2019\xc3\u201a\xc2\xa2\xc3\u0192\xc2\xa2\xc3\xa2\xe2\u201a\xac"
    "\xc5\xa1\xc3\u201a\xc2\xac\xc3\u0192\xe2\u20ac\xa6\xc3\u201a\xc2"
    "\xa1\xc3\u0192\xc6\u2019\xc3\xa2\xe2\u201a\xac\xc5\xa1\xc3\u0192"
    "\xe2\u20ac\u0161\xc3\u201a\xc2\xac\xc3\u0192\xc6\u2019\xc3\u2020"
    "\xe2\u20ac\u2122\xc3\u0192\xe2\u20ac\u0161\xc3\u201a\xc2\xa2\xc3"
    "\u0192\xc6\u2019\xc3\u201a\xc2\xa2\xc3\u0192\xc2\xa2\xc3\xa2\xe2"
    "\u201a\xac\xc5\xa1\xc3\u201a\xc2\xac\xc3\u0192\xe2\u20ac\xa6\xc3"
    "\u201a\xc2\xbe\xc3\u0192\xc6\u2019\xc3\xa2\xe2\u201a\xac\xc5\xa1"
    "\xc3\u0192\xe2\u20ac\u0161\xc3\u201a\xc2\xa2"
)
# Preserve the current production wording. The preceding value is legacy
# mojibake retained only to keep this narrow migration mechanically reviewable.
_BOTTOM_REO_GUIDANCE_CHANGE_ARROW = "->"


def _bottom_reo_normalized_sec_shape(raw: Any) -> str:
    value = str(raw or "RECT").strip().upper()
    if value in ("T", "T-SECTION", "T_SECTION", "T-BEAM"):
        return "T"
    if value in ("I", "I-SECTION", "I_SECTION", "I-BEAM"):
        return "I"
    return "RECT"


def _bottom_reo_change_line_prefixes(state: dict[str, Any] | None) -> tuple[str, str]:
    raw = (state or {}).get("sec_shape") or (state or {}).get("inputs_sec_shape")
    if _bottom_reo_normalized_sec_shape(raw) in ("T", "I"):
        return "Web bottom reo", "Web top reo"
    return "Bottom reo", "Top reo"


def _bottom_reo_width_context_for_change_lines(state: dict[str, Any]) -> tuple[str, str, float]:
    sec_shape = str(state.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return "bw", "Web width bw (mm)", _as_float(state.get("bw", state.get("b", 300.0)), 300.0)
    if sec_shape == "I":
        return "tw", "Web thickness tw (mm)", _as_float(state.get("tw", state.get("b", 200.0)), 200.0)
    return "b", "Width b (mm)", _as_float(state.get("b", 400.0), 400.0)


def _bottom_reo_practical_label(count_1: int, count_2: int, dia: int) -> str:
    if count_2 > 0:
        return f"{count_1}N{dia} + {count_2}N{dia}"
    return f"{count_1}N{dia}"


def _bottom_reo_change_line_bottom_label(state: dict[str, Any]) -> str:
    mode_1 = str(state.get("bot1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("bot2_layout_mode", "Count") or "Count")
    if mode_1 == "Count" and mode_2 == "Count":
        count_1 = _as_int(state.get("bot1_count"), 0)
        count_2 = _as_int(state.get("bot2_count"), 0)
        dia = _as_int(state.get("db_bot_1", state.get("db_bot", 0)), 0)
        if count_1 > 0:
            return _bottom_reo_practical_label(count_1, count_2, dia)
    spacing_1 = _as_float(state.get("bot1_spacing"), 0.0)
    dia_1 = _as_int(state.get("db_bot_1"), 0)
    return f"N{dia_1} @ {int(spacing_1)}"


def _bottom_reo_change_line_top_label(state: dict[str, Any]) -> str:
    mode_1 = str(state.get("top1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("top2_layout_mode", "Count") or "Count")
    count_1 = _as_int(state.get("top1_count"), 0)
    count_2 = _as_int(state.get("top2_count"), 0)
    if mode_1 == "Count" and mode_2 == "Count":
        dia = _as_int(state.get("db_top_1", state.get("db_top", 0)), 0)
        if count_1 > 0 or count_2 > 0:
            return _bottom_reo_practical_label(count_1, count_2, dia)
        return "None"
    spacing_1 = _as_float(state.get("top1_spacing"), 0.0)
    dia_1 = _as_int(state.get("db_top_1"), 0)
    return f"N{dia_1} @ {int(spacing_1)}"


def _bottom_reo_change_line_shear_fragment(state: dict[str, Any]) -> str | None:
    legs = _as_int(state.get("lig_legs"), 0)
    if legs <= 0:
        return None
    return f"N{_as_int(state.get('lig_d'), 0)}, {legs}-leg @{int(_as_float(state.get('s_lig'), 0.0))}"


def build_bottom_reo_guidance_change_lines_for_updates(
    before: dict[str, Any] | None,
    updates: dict[str, Any] | None,
) -> list[str]:
    """Build the visible change-line projection for bottom-reo recommendations."""

    if not updates:
        return []
    before_state = dict(before or {}) if isinstance(before, dict) else {}
    after_state = dict(before_state)
    after_state.update(dict(updates or {}))
    arrow = _BOTTOM_REO_GUIDANCE_CHANGE_ARROW
    lines: list[str] = []
    _, _, before_width = _bottom_reo_width_context_for_change_lines(before_state)
    _, _, after_width = _bottom_reo_width_context_for_change_lines(after_state)
    try:
        if abs(float(after_width) - float(before_width)) > 1e-6:
            lines.append(
                f"Width: {int(round(float(before_width)))} {arrow} {int(round(float(after_width)))} mm",
            )
    except (TypeError, ValueError):
        pass
    try:
        before_depth = _as_float(before_state.get("D"), 0.0)
        after_depth = _as_float(after_state.get("D"), 0.0)
        if abs(after_depth - before_depth) > 1e-6:
            lines.append(f"Depth: {int(round(before_depth))} {arrow} {int(round(after_depth))} mm")
    except (TypeError, ValueError):
        pass
    before_bottom = _bottom_reo_change_line_bottom_label(before_state)
    after_bottom = _bottom_reo_change_line_bottom_label(after_state)
    bottom_phrase, top_phrase = _bottom_reo_change_line_prefixes(after_state)
    if before_bottom != after_bottom:
        lines.append(f"{bottom_phrase}: {before_bottom} {arrow} {after_bottom}")
    before_top = _bottom_reo_change_line_top_label(before_state)
    after_top = _bottom_reo_change_line_top_label(after_state)
    if before_top != after_top:
        lines.append(f"{top_phrase}: {before_top} {arrow} {after_top}")
    before_shear = _bottom_reo_change_line_shear_fragment(before_state)
    after_shear = _bottom_reo_change_line_shear_fragment(after_state)
    if before_shear != after_shear:
        if after_shear is None:
            lines.append(f"Shear links: {before_shear} {arrow} removed")
        elif before_shear is None:
            lines.append(f"Shear links: none {arrow} {after_shear}")
        else:
            lines.append(f"Shear links: {before_shear} {arrow} {after_shear}")
    return lines


def build_bottom_reo_required_ast_arrangement_input(
    selected_candidate: dict[str, Any] | None,
    selected_bending: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the exact arrangement payload used by bottom-reo required-Ast search."""

    candidate = selected_candidate if isinstance(selected_candidate, dict) else {}
    bending = selected_bending if isinstance(selected_bending, dict) else {}
    return {
        "Ast_bot": _as_float(candidate.get("actual_ast"), 0.0),
        "db_bot": _as_float(bending.get("db_bot"), 0.0),
        "nb_bot": _as_int(bending.get("nb_bot"), 0),
        "d_centroid": _as_float(bending.get("d_centroid"), 0.0),
    }


def build_bottom_reo_recommendation_result(
    selected_candidate: dict,
    *,
    arrangement: dict,
    required_ast: float,
    display_label: str,
    guidance_change_lines: list[str] | tuple[str, ...],
) -> dict:
    """Assemble the existing normal bottom-reinforcement result shape.

    The caller owns candidate generation, ranking, selector decisions, and page
    trace hooks. The family owns the bottom-reo visible change-line projection.
    """
    best = dict(selected_candidate or {})
    return {
        "arrangement": dict(arrangement or {}),
        "updates": dict(best.get("updates") or {}),
        "actual_ast": _as_float(best.get("actual_ast"), 0.0),
        "required_ast": _as_float(required_ast, 0.0),
        "util": _bending_util(best),
        "label": str(display_label or ""),
        "score": _as_float(best.get("score"), 0.0),
        "recommendation_compound": bool(best.get("recommendation_compound")),
        "subfamilies": list(best.get("subfamilies") or []),
        "recommendation_family_tag": best.get("recommendation_family_tag"),
        "guidance_recommendation_title": best.get("guidance_recommendation_title"),
        "delta_b_mm": _as_float(best.get("delta_b_mm"), 0.0),
        "delta_D_mm": _as_float(best.get("delta_D_mm"), 0.0),
        "delta_Ast_bot": _as_float(best.get("delta_Ast_bot"), 0.0),
        "guidance_change_lines": list(guidance_change_lines or []),
    }


def calculate_bottom_reo_required_ast_for_arrangement(
    *,
    compute_bending_capacity_fn: Any,
    b: float,
    D: float,
    fc: float,
    fsy: float,
    phi: float,
    Mu_star: float,
    cover_bot: float,
    rowgap_bot: float,
    arrangement: dict,
    iterations: int = 40,
) -> float:
    """Calculate required bottom Ast for an already-selected arrangement.

    The caller supplies the existing bending-capacity callback so this family
    helper does not import page, Streamlit, session, or cached UI concerns.
    """

    compute_fn = compute_bending_capacity_fn
    if not callable(compute_fn):
        return 0.0
    arr = arrangement if isinstance(arrangement, dict) else {}
    low = 0.0
    high = _as_float(arr.get("Ast_bot"), 0.0)
    for _ in range(max(int(iterations or 0), 0)):
        trial = 0.5 * (low + high)
        trial_results = compute_fn(
            b=_as_float(b, 0.0),
            D=_as_float(D, 0.0),
            fc=_as_float(fc, 0.0),
            fsy=_as_float(fsy, 0.0),
            Ast=trial,
            Mu_star=_as_float(Mu_star, 0.0),
            phi=_as_float(phi, 0.0),
            d_input=arr.get("d_centroid"),
            cover_bot=_as_float(cover_bot, 0.0),
            db_bot=arr.get("db_bot"),
            nb_bot=arr.get("nb_bot"),
            rowgap_bot=_as_float(rowgap_bot, 0.0),
        )
        util = _as_float((trial_results or {}).get("Mu_util"), float("inf"))
        if util <= 1.0:
            high = trial
        else:
            low = trial
    return float(high)


def resolve_bottom_reo_post_selector_guard(
    selected_candidate: dict | None,
    *,
    updates_match_state: bool,
    growth_rejected: bool = False,
) -> dict[str, Any]:
    """Classify the bottom-reo post-selector guard outcome."""

    if not selected_candidate or bool(updates_match_state):
        return {
            "post_selector_guard_result": "no_result",
            "no_result_reason": "no_selected_candidate",
            "selected": False,
        }
    if bool(growth_rejected):
        return {
            "post_selector_guard_result": "no_result",
            "no_result_reason": "growth_blocked_efficiency_reduction",
            "selected": False,
        }
    return {
        "post_selector_guard_result": "selected",
        "no_result_reason": None,
        "selected": True,
    }


def resolve_bottom_reo_result_display_label(selected_candidate: dict | None) -> str:
    """Resolve the visible bottom-reo result label from plain candidate data."""

    candidate = selected_candidate if isinstance(selected_candidate, dict) else {}
    label = str(candidate.get("label") or "")
    if candidate.get("recommendation_compound"):
        return str(candidate.get("guidance_recommendation_title") or label)
    return label


def prefer_compound_over_pure_geometry(
    best: dict | None,
    ranked_candidates: list[dict] | tuple[dict, ...],
    *,
    geometry_axis: str | None,
    search_strategy: str,
    seed_depth: float,
    score_margin: float,
) -> dict | None:
    """Prefer a matching compound geometry-bottom candidate when it is close enough.

    The caller owns geometry-axis resolution and mode/config lookup.
    """
    if not best:
        return best
    if best.get("recommendation_compound"):
        return best
    if not best.get("recommendation_geometry_trial"):
        return best
    axis = str(geometry_axis or "")
    if axis not in ("width", "depth"):
        return best
    try:
        best_score = float(best.get("score", 1e9) or 1e9)
    except (TypeError, ValueError):
        best_score = 1e9
    strategy = str(search_strategy or "balanced")
    try:
        seed_d = float(seed_depth)
    except (TypeError, ValueError):
        seed_d = 0.0
    try:
        margin = float(score_margin)
    except (TypeError, ValueError):
        margin = 0.0
    pick: dict | None = None
    pick_score = float("inf")
    for candidate in list(ranked_candidates or []):
        if not isinstance(candidate, dict):
            continue
        if not candidate.get("recommendation_compound"):
            continue
        if str(candidate.get("compound_geo_axis") or "") != axis:
            continue
        if not (best.get("is_compliant") and candidate.get("is_compliant")):
            continue
        if axis == "width" and strategy == "shallow":
            try:
                candidate_depth = float(candidate.get("depth", seed_d) or seed_d)
            except (TypeError, ValueError):
                continue
            if candidate_depth > seed_d + 1e-9:
                continue
        try:
            score = float(candidate.get("score", 1e9) or 1e9)
        except (TypeError, ValueError):
            continue
        if score <= best_score + margin and score < pick_score:
            pick = candidate
            pick_score = score
    if pick is not None:
        return pick
    return best


def select_bottom_reo_compound_preference_candidate(
    best: dict | None,
    ranked_candidates: list[dict] | tuple[dict, ...],
    *,
    width_key: str | None,
    mode_config: dict | None,
    seed_candidate: dict | None,
    score_margin: float,
) -> dict | None:
    """Select a compound bottom-reo candidate when family policy prefers it.

    The caller owns page/state collection. This helper owns the bending-family
    interpretation of geometry-axis, strategy, seed-depth, and score margin
    inputs before applying the compound-vs-pure-geometry preference policy.
    """

    mode = mode_config if isinstance(mode_config, dict) else {}
    seed = seed_candidate if isinstance(seed_candidate, dict) else {}
    return prefer_compound_over_pure_geometry(
        best,
        ranked_candidates,
        geometry_axis=resolve_bottom_reo_geometry_trial_axis(best, width_key=width_key),
        search_strategy=str(mode.get("search_strategy", "balanced") or "balanced"),
        seed_depth=_as_float(seed.get("depth"), 0.0),
        score_margin=_as_float(score_margin, 0.0),
    )


def _bottom_reo_compound_geo_sort_key(candidate: dict) -> float:
    bending_util = ((candidate.get("overview") or {}).get("utils") or {}).get("bending")
    return _as_float(bending_util, 999.0)


def select_bottom_reo_compound_geometry_seed_candidates(
    candidates: list[dict] | tuple[dict, ...],
    *,
    axis: str,
    width_key: str | None,
    limit: int,
) -> list[dict]:
    """Select unique geometry seeds for geometry+bottom compound attempts."""

    axis_text = str(axis or "")
    if axis_text not in ("width", "depth"):
        return []
    width_key_text = str(width_key or "").strip()
    geo = [
        dict(candidate)
        for candidate in list(candidates or [])
        if isinstance(candidate, dict)
        and candidate.get("recommendation_geometry_trial")
        and resolve_bottom_reo_geometry_trial_axis(candidate, width_key=width_key_text) == axis_text
    ]
    picked: list[dict] = []
    seen_marker: set[tuple[str, float]] = set()
    for candidate in sorted(geo, key=_bottom_reo_compound_geo_sort_key):
        updates = candidate.get("updates") or {}
        if not isinstance(updates, dict):
            continue
        if axis_text == "width":
            if not width_key_text or width_key_text not in updates:
                continue
            try:
                marker = ("width", round(float(updates[width_key_text]), 3))
            except (TypeError, ValueError):
                continue
        else:
            if "D" not in updates:
                continue
            try:
                marker = ("depth", round(float(updates["D"]), 3))
            except (TypeError, ValueError):
                continue
        if marker in seen_marker:
            continue
        seen_marker.add(marker)
        picked.append(candidate)
        if len(picked) >= max(_as_int(limit, 0), 0):
            break
    return picked


def build_bottom_reo_compound_attempt_rows(
    *,
    state: dict[str, Any],
    candidates: list[dict] | tuple[dict, ...],
    mode_config: dict[str, Any],
    context: dict[str, Any] | None,
    axis: str,
    width_key: str | None,
    seed_limit: int,
    bar_diameters: list[int] | tuple[int, ...],
    default_limit: int,
    arrangement_limit: int = 18,
    max_attempts: int = 26,
) -> dict[str, Any]:
    """Build geometry+bottom compound attempt rows from plain data.

    This owns only bending-family geometry seed selection and bottom arrangement
    regeneration on each geometry-adjusted state. It does not run evaluator
    callbacks, decide final acceptance, mutate live candidate pools, publish,
    render, or build CTA/apply payloads.
    """

    state_d = dict(state or {})
    mode = dict(mode_config or {})
    ctx = context if isinstance(context, dict) else {}
    axis_text = str(axis or "")
    seeds = select_bottom_reo_compound_geometry_seed_candidates(
        candidates,
        axis=axis_text,
        width_key=width_key,
        limit=seed_limit,
    )
    rows: list[dict[str, Any]] = []
    for geometry_candidate in seeds:
        geo_updates = dict(geometry_candidate.get("updates") or {})
        base_state = dict(state_d)
        base_state.update(geo_updates)
        local_arrangements: list[dict[str, Any]] = []
        seen_arrangements: set[tuple[int, int, int]] = set()
        for band in (0, 1):
            arrangements = build_bottom_reo_arrangement_pool_from_state(
                base_state,
                mode,
                band=band,
                context=ctx,
                limit=arrangement_limit,
                bar_diameters=bar_diameters,
                default_limit=default_limit,
            )
            for arrangement in arrangements:
                arrangement_d = dict(arrangement or {})
                signature = (
                    _as_int(arrangement_d.get("bot1_count"), 0),
                    _as_int(arrangement_d.get("bot2_count"), 0),
                    _as_int(arrangement_d.get("db_bot_1"), 0),
                )
                if signature in seen_arrangements:
                    continue
                seen_arrangements.add(signature)
                local_arrangements.append(arrangement_d)
                if len(local_arrangements) >= max(_as_int(max_attempts, 1), 1):
                    break
            if len(local_arrangements) >= max(_as_int(max_attempts, 1), 1):
                break
        for arrangement in local_arrangements:
            count_1 = _as_int(arrangement.get("bot1_count"), 0)
            count_2 = _as_int(arrangement.get("bot2_count"), 0)
            diameter = _as_int(arrangement.get("db_bot_1"), 0)
            bottom_updates = bottom_arrangement_to_shared_updates(arrangement)
            bottom_label = f"{count_1}N{diameter} + {count_2}N{diameter}" if count_2 > 0 else f"{count_1}N{diameter}"
            rows.append(
                {
                    "axis": axis_text,
                    "geometry_candidate": dict(geometry_candidate),
                    "geometry_updates": geo_updates,
                    "geometry_label": str(geometry_candidate.get("label") or ""),
                    "base_state": dict(base_state),
                    "arrangement": dict(arrangement),
                    "bottom_updates": dict(bottom_updates),
                    "bottom_label": bottom_label,
                }
            )
    return {
        "axis": axis_text,
        "selected_geometry_seed_count": len(seeds),
        "selected_geometry_seeds": [dict(seed) for seed in seeds],
        "attempt_rows": rows,
    }


def classify_bottom_reo_compound_attempt_merge_policy(
    *,
    bottom_updates_match_geometry_state: bool,
    duplicate_signature: bool,
    invalid_empty_updates: bool,
    updates_match_current_state: bool,
    layout_fits: bool,
) -> dict[str, Any]:
    """Classify pure geometry+bottom compound merge/reject policy.

    The page owns the callback facts (state/update equality and layout-fit
    checks). This family helper owns the bending-family rejection order and
    reason/stat projection for compound bottom-reo attempts.
    """

    if bool(bottom_updates_match_geometry_state):
        return {
            "accepted_for_evaluation": False,
            "compound_stats_key": "rejected_no_layout_variation",
            "trace_result": "rejected",
            "trace_reason": "no_layout_variation_vs_geometry_adjusted_state",
        }
    if bool(duplicate_signature):
        return {
            "accepted_for_evaluation": False,
            "compound_stats_key": "rejected_duplicate_signature",
            "trace_result": "rejected",
            "trace_reason": "duplicate_signature",
        }
    if bool(invalid_empty_updates):
        return {
            "accepted_for_evaluation": False,
            "compound_stats_key": "rejected_invalid_merge",
            "trace_result": "rejected",
            "trace_reason": "invalid_merge_empty_updates",
        }
    if bool(updates_match_current_state):
        return {
            "accepted_for_evaluation": False,
            "compound_stats_key": "rejected_same_as_current",
            "trace_result": "rejected",
            "trace_reason": "same_as_current_live_state",
        }
    if not bool(layout_fits):
        return {
            "accepted_for_evaluation": False,
            "compound_stats_key": "compound_layout_reject_count",
            "trace_result": "rejected",
            "trace_reason": "layout_no_fit",
        }
    return {
        "accepted_for_evaluation": True,
        "compound_stats_key": None,
        "trace_result": "accepted_for_evaluation",
        "trace_reason": "ready_for_candidate_evaluation",
    }


def build_bottom_reo_compound_accepted_candidate_projection(
    *,
    candidate: dict[str, Any] | None,
    axis: str,
    arrangement: dict[str, Any] | None,
    geometry_label: str | None,
) -> dict[str, Any]:
    """Build accepted compound geometry+bottom candidate metadata projection."""

    axis_text = str(axis or "")
    label = str(geometry_label or "").strip()
    if axis_text == "width":
        title = "Increase width and rebalance bottom reinforcement"
    elif axis_text == "depth":
        title = "Increase depth and adjust bottom reinforcement"
    else:
        title = f"Adjust geometry and bottom reinforcement ({label})" if label else "Adjust geometry and bottom reinforcement"
    candidate_d = dict(candidate or {})
    arrangement_d = dict(arrangement or {})
    return {
        "recommendation_compound": True,
        "recommendation_geometry_trial": True,
        "recommendation_bottom_trial": True,
        "subfamilies": ["geometry", "bottom_reo"],
        "recommendation_family_tag": f"compound_{axis_text}_bottom",
        "compound_geo_axis": axis_text,
        "arrangement": arrangement_d,
        "actual_ast": _as_float(candidate_d.get("Ast_bot"), 0.0),
        "guidance_recommendation_title": title,
    }


def build_bottom_reo_geometry_trial_plan_rows(
    *,
    mode_config: dict[str, Any] | None,
    geometry_trial_deltas_mm: list[int | float] | tuple[int | float, ...],
) -> list[dict[str, Any]]:
    """Build the pure bottom-reo geometry trial action rows."""

    mode = dict(mode_config or {})
    geo_axes = (
        ("increase_width", "increase_depth")
        if str(mode.get("search_strategy", "balanced") or "balanced") == "shallow"
        else ("increase_depth", "increase_width")
    )
    rows: list[dict[str, Any]] = []
    for delta in list(geometry_trial_deltas_mm or []):
        delta_f = float(delta)
        for action_type in geo_axes:
            label = (
                f"Increase depth D by {int(delta)} mm"
                if action_type == "increase_depth"
                else f"Increase section width by {int(delta)} mm"
            )
            rows.append(
                {
                    "action_type": action_type,
                    "payload": {"delta_mm": delta_f},
                    "label": label,
                    "delta_mm": delta_f,
                }
            )
    return rows


def build_bottom_reo_geometry_trial_candidate_projection(
    *,
    candidate: dict[str, Any] | None,
    width_key: str | None,
) -> dict[str, Any]:
    """Build metadata for an accepted pure geometry bottom-reo trial."""

    candidate_d = dict(candidate or {})
    axis = resolve_bottom_reo_geometry_trial_axis(candidate_d, width_key=width_key)
    return {
        "recommendation_geometry_trial": True,
        "actual_ast": float(candidate_d.get("Ast_bot", 0.0) or 0.0),
        "recommendation_family_tag": (
            f"pure_geometry_{axis}" if axis in ("width", "depth") else "pure_geometry"
        ),
    }


def build_bottom_reo_candidate_delta_projection(
    *,
    seed_depth: int | float,
    candidate_depth: int | float,
    seed_width: int | float,
    candidate_width: int | float,
    seed_ast: int | float,
    candidate_ast: int | float,
) -> dict[str, Any]:
    """Build bottom-reo candidate delta evidence from plain numeric inputs."""

    return {
        "delta_D_mm": round(float(candidate_depth) - float(seed_depth), 3),
        "delta_b_mm": round(float(candidate_width) - float(seed_width), 3),
        "delta_Ast_bot": round(float(candidate_ast) - float(seed_ast), 3),
    }


def select_bottom_reo_tightening_recommendation_result(
    candidates: list[dict] | tuple[dict, ...] | None,
    *,
    target_low: float,
    target_high: float,
    target_mid: float,
    candidate_updates: list[dict] | tuple[dict, ...] | None = None,
    candidate_summaries: list[dict] | tuple[dict, ...] | None = None,
) -> dict:
    """Select the final bottom-reinforcement tightening result.

    The caller owns option generation, evaluation, candidate filtering, trace
    emission, and candidate-summary construction. This helper only selects
    from already-evaluated candidates and assembles the existing result shape.
    """
    indexed_candidates = [
        (index, dict(candidate))
        for index, candidate in enumerate(list(candidates or []))
        if isinstance(candidate, dict)
    ]
    if not indexed_candidates:
        return {
            "status": "no_result",
            "return_reason": "no_valid_candidates",
            "selected_candidate": None,
            "result": None,
        }

    updates_by_index = [
        dict(item) if isinstance(item, dict) else {}
        for item in list(candidate_updates or [])
    ]
    summaries_by_index = [
        dict(item) if isinstance(item, dict) else {}
        for item in list(candidate_summaries or [])
    ]

    best_index, best = min(
        indexed_candidates,
        key=lambda indexed_item: (
            0 if float(target_low) <= _bending_util(indexed_item[1]) <= float(target_high) else 1,
            abs(_bending_util(indexed_item[1]) - float(target_mid)),
            _as_int(indexed_item[1].get("row_count"), 1),
            _as_int(indexed_item[1].get("bar_count"), 0),
            _as_float(indexed_item[1].get("Ast_bot"), 0.0),
        ),
    )
    arrangement = dict(best.get("arrangement") or {})
    updates = dict(updates_by_index[best_index]) if best_index < len(updates_by_index) else {}
    summary = dict(summaries_by_index[best_index]) if best_index < len(summaries_by_index) else {}
    result = {
        "arrangement": arrangement,
        "updates": updates,
        "actual_ast": _as_float(best.get("actual_ast"), 0.0),
        "util": _bending_util(best),
        "label": str(best.get("label") or ""),
        "score": _as_float(best.get("score"), 0.0),
        "candidate_summary": summary,
        "candidate_type": "bottom",
    }
    return {
        "status": "selected",
        "return_reason": "selected",
        "selected_candidate": dict(best),
        "result": result,
    }
