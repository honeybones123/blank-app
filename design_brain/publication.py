"""Design Brain publication and CTA eligibility helpers.

This module owns pure publication classification and CTA/publication payload
normalisation. It does not render UI, bind session state, execute Apply, search
for candidates, evaluate formulas, or run solver maths.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields as dataclass_fields
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from design_brain.candidates import normalise_candidate_row
from design_brain.evidence import candidate_rows_from_evidence
from design_brain.family_chooser import (
    FAMILY_SELECTION_CONTRACT_VIOLATION,
    classify_family_from_raw_flags,
)
from design_brain.optimisation import clean_safe_combined_evidence
from design_brain.repair import (
    _parse_util_value as _repair_parse_util_value,
    active_failure_blocker_visible_reason_text as _repair_active_failure_blocker_visible_reason_text,
    active_failure_exact_blockers_for_families as _repair_active_failure_exact_blockers_for_families,
    candidate_preview_statuses_have_explicit_fail as _repair_candidate_preview_statuses_have_explicit_fail,
)


@dataclass(frozen=True)
class DesignGuidePublicationContext:
    """Explicit context for final Design Guide publication resolution."""

    current_summary_state: dict[str, Any] = field(default_factory=dict)
    current_overview: dict[str, Any] = field(default_factory=dict)
    candidate_items: list[dict[str, Any]] = field(default_factory=list)
    resolved_inputs_summary: dict[str, Any] = field(default_factory=dict)
    resolved_summary_debug: dict[str, Any] = field(default_factory=dict)
    shared_state_snapshot: dict[str, Any] = field(default_factory=dict)
    final_seed_state: dict[str, Any] = field(default_factory=dict)
    guidance_state_snapshot: dict[str, Any] = field(default_factory=dict)
    design_actions_context: dict[str, Any] = field(default_factory=dict)
    current_design_overview: dict[str, Any] = field(default_factory=dict)
    direct_failure_state: dict[str, Any] = field(default_factory=dict)
    family_state: dict[str, Any] = field(default_factory=dict)
    cta_apply_state: dict[str, Any] = field(default_factory=dict)
    repair_optimisation_evidence: dict[str, Any] = field(default_factory=dict)
    contract_publication_binding_inputs: dict[str, Any] = field(default_factory=dict)
    route_owner_fallback_evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuidePublicationDependencies:
    """Callable dependency boundary for final Design Guide publication."""

    active_fail_near_current_repair_item: Callable[..., Any]
    active_repair_with_residual_shear_target_cleanup: Callable[..., Any]
    bending_fail_publication_snapshot_for_state: Callable[..., Any]
    bending_only_target_band_cleanup_item: Callable[..., Any]
    build_bending_check_rows_from_state: Callable[..., Any]
    build_design_actions_context: Callable[..., Any]
    build_shear_check_rows_from_state: Callable[..., Any]
    collect_design_overview: Callable[..., Any]
    combine_best_safe_shear_with_bending_cleanup_item: Callable[..., Any]
    combined_low_util_exact_blocker_final_item: Callable[..., Any]
    design_guide_apply_button_contracts_to_items: Callable[..., Any]
    design_guide_preview_contract_for_updates: Callable[..., Any]
    design_mode_config: Callable[..., Any]
    design_optimisation_goal: Callable[..., Any]
    direct_target_band_guidance_item: Callable[..., Any]
    evaluate_auto_design_candidate: Callable[..., Any]
    exact_cleanup_blocker_for_outside_target_action: Callable[..., Any]
    float_from_state: Callable[..., Any]
    guidance_change_lines_for_updates: Callable[..., Any]
    guidance_cleanup_candidate_id: Callable[..., Any]
    guidance_compact_change_text: Callable[..., Any]
    guidance_default_alternatives_text: Callable[..., Any]
    guidance_item_from_resolved_candidate: Callable[..., Any]
    guidance_state_snapshot: Callable[..., Any]
    local_cleanup_post_apply_acceptance_matches: Callable[..., Any]
    overview_active_failure_keys: Callable[..., Any]
    overview_required_checks_acceptable: Callable[..., Any]
    parse_util_value: Callable[..., Any]
    post_active_repair_residual_shear_exact_blocker: Callable[..., Any]
    post_active_repair_target_accepted_item: Callable[..., Any]
    post_click_accepted_green_audit: Callable[..., Any]
    post_click_applied_residual_shear_exact_blocker: Callable[..., Any]
    post_click_low_bending_resolution_item: Callable[..., Any]
    probe_equivalent_bending_cleanup_action_item: Callable[..., Any]
    resolve_design_actions_from_state: Callable[..., Any]
    resolve_recommendation_updates: Callable[..., Any]
    resolved_inputs_summary_state: Callable[..., Any]
    shared_state_snapshot: Callable[..., Any]
    shear_best_safe_cleanup_item_from_evidence: Callable[..., Any]
    shear_cleanup_exact_blocker_guidance_item: Callable[..., Any]
    shear_demands_negligible: Callable[..., Any]
    shear_low_util_target_cleanup_item: Callable[..., Any]
    suppress_design_guide_blocker_cta: Callable[..., Any]
    updates_match_state: Callable[..., Any]
    visible_cleanup_blocker_from_action: Callable[..., Any]


@dataclass(frozen=True)
class DesignGuideComputeLateEvidenceSyncResult:
    """Typed proof surface for compute-stage late evidence synchronization."""

    evidence_hash: str | None = None
    evidence_keys: list[str] = field(default_factory=list)
    item_hash_before: str | None = None
    item_hash_after: str | None = None
    item_candidate_id_before: Any = None
    item_candidate_id_after: Any = None
    item_source_candidate_id_before: Any = None
    item_source_candidate_id_after: Any = None
    action_payload_hash_before: str | None = None
    action_payload_hash_after: str | None = None
    action_payload_source_candidate_id: Any = None
    action_payload_evidence_hash: str | None = None
    resolved_candidate_hash_before: str | None = None
    resolved_candidate_hash_after: str | None = None
    resolved_candidate_id: Any = None
    resolved_candidate_source_candidate_id: Any = None
    resolved_candidate_evidence_hash: str | None = None
    button_contract_hash_before: str | None = None
    button_contract_hash_after: str | None = None
    button_contract_family: Any = None
    button_contract_action_type: Any = None
    button_contract_actionable: Any = None
    button_contract_preview_pass: Any = None
    button_contract_source_candidate_id: Any = None
    button_contract_candidate_id: Any = None
    button_contract_blocking_reason: Any = None
    debug_candidate_search_evidence_hash: str | None = None
    debug_exact_blockers_hash: str | None = None
    debug_cleanup_evidence_hash: str | None = None
    debug_local_cleanup_search_ran: Any = None
    debug_local_cleanup_search_exhaustive: Any = None
    debug_safe_local_cleanup_count: Any = None
    debug_executable_safe_cleanup_count: Any = None
    active_under_capacity_blocker: bool = False
    exact_blockers_present: bool = False
    changed_fields: list[str] = field(default_factory=list)
    parity_checks: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideApplyButtonPromotionBranchInputs:
    """Typed inputs used by the page-local apply-button promotion branch."""

    item_index: int = 0
    copied_item_identity: str | None = None
    family: str | None = None
    check_key: str | None = None
    selected_action_family: str | None = None
    guidance_intent: str | None = None
    current_action_type: str | None = None
    block_reason: str | None = None
    promotion_branch_evaluated: bool = False
    current_button_contract: dict[str, Any] = field(default_factory=dict)
    current_button_contract_summary: dict[str, Any] = field(default_factory=dict)
    current_action_state: dict[str, Any] = field(default_factory=dict)
    contract_updates: dict[str, Any] = field(default_factory=dict)
    expected_util: Any = None
    target_band_low: Any = None
    target_band_high: Any = None
    target_band_eps: Any = None
    target_band_candidate_count: int = 0
    target_band_candidate_updates: dict[str, Any] = field(default_factory=dict)
    target_band_candidate_util: Any = None
    closest_safe_candidate_updates: dict[str, Any] = field(default_factory=dict)
    closest_safe_candidate_util: Any = None
    selected_candidate_updates: dict[str, Any] = field(default_factory=dict)
    selected_candidate_util: Any = None
    evidence_updates: dict[str, Any] = field(default_factory=dict)
    evidence_util: Any = None
    evidence_candidate_id: Any = None
    active_failures: list[Any] = field(default_factory=list)
    strength_text: str | None = None
    is_strength_required_fix: bool = False
    safe_executor_backed_candidates_count: int = 0
    safe_candidate_count: int = 0
    executable_candidate_count: int = 0
    advisory_conversion_eligible: bool = False
    design_mode_goal: str | None = None
    efficiency_target_band_source: str | None = None
    safe_executor_evidence_recounted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideApplyButtonPromotionBranchPredicates:
    """Pure branch predicate result for apply-button promotion decisions."""

    target_band_promotion: bool = False
    safe_strength_promotion: bool = False
    existing_contract_promotion: bool = False
    advisory_conversion: bool = False
    decision_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideApplyButtonPromotionBranchSetup:
    """Initial apply-button promotion/advisory branch state."""

    block_reason: str = ""
    original_item_for_decision: dict[str, Any] | None = None
    original_button_contract_for_decision: dict[str, Any] | None = None
    decision_reason: str = "button_contract_bound_without_promotion"
    repair_promotion_occurred: bool = False
    advisory_conversion_occurred: bool = False
    promotion_branch_evaluated: bool = False
    branch_inputs: DesignGuideApplyButtonPromotionBranchInputs = field(
        default_factory=DesignGuideApplyButtonPromotionBranchInputs
    )
    branch_predicates: DesignGuideApplyButtonPromotionBranchPredicates = field(
        default_factory=DesignGuideApplyButtonPromotionBranchPredicates
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideApplyButtonPromotionEvidenceAssembly:
    """Resolved evidence and enriched branch inputs for apply-button promotion."""

    branch_inputs: DesignGuideApplyButtonPromotionBranchInputs = field(
        default_factory=DesignGuideApplyButtonPromotionBranchInputs
    )
    evidence_updates: dict[str, Any] = field(default_factory=dict)
    evidence_util: Any = None
    evidence_candidate_id: Any = None
    strength_text: str | None = None
    is_strength_required_fix: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideApplyButtonPromotionTitleSelection:
    """Pure target-family/title-main selection for promotion rewrites."""

    target_family: str | None = None
    title_main: str | None = None
    decision_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideApplyButtonPromotionEffectPlan:
    """Pure scalar plan for applying an already-selected promotion branch."""

    decision_reason: str | None = None
    contract_updates: dict[str, Any] = field(default_factory=dict)
    expected_util: Any = None
    evidence_candidate_id: Any = None
    rewrite_action_payload: bool = False
    repair_promotion_occurred: bool = False
    decision_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideSafeExecutorEvidenceRows:
    """Typed copy/rewrite record for safe-executor evidence row recounting."""

    item_index: int = 0
    input_evidence_identity: str | None = None
    input_evidence_hash: str | None = None
    input_row_count: int = 0
    counted_safe_executor_rows: int = 0
    output_evidence_identity: str | None = None
    output_evidence_hash: str | None = None
    output_row_count: int = 0
    evidence_object_copied: bool | None = None
    evidence_object_reused: bool | None = None
    fields_added: list[str] = field(default_factory=list)
    fields_removed: list[str] = field(default_factory=list)
    fields_rewritten: list[str] = field(default_factory=list)
    counted_candidate_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideApplyButtonPromotionDecision:
    """Typed snapshot of one apply-button promotion/advisory decision."""

    item_index: int = 0
    input_item_identity: str | None = None
    output_item_identity: str | None = None
    promotion_branch_evaluated: bool = False
    repair_promotion_occurred: bool = False
    advisory_conversion_occurred: bool = False
    original_action_state: dict[str, Any] = field(default_factory=dict)
    final_action_state: dict[str, Any] = field(default_factory=dict)
    original_apply_payload_identity: str | None = None
    original_apply_payload_hash: str | None = None
    final_apply_payload_identity: str | None = None
    final_apply_payload_hash: str | None = None
    cta_label: str | None = None
    cta_enabled: bool | None = None
    cta_reason: str | None = None
    original_button_contract_summary: dict[str, Any] = field(default_factory=dict)
    final_button_contract_summary: dict[str, Any] = field(default_factory=dict)
    decision_reason: str | None = None
    branch_inputs: dict[str, Any] = field(default_factory=dict)
    branch_predicates: dict[str, Any] = field(default_factory=dict)
    copied_field_rewrites: list[str] = field(default_factory=list)
    added_fields: list[str] = field(default_factory=list)
    removed_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideApplyButtonPromotionRewriteResult:
    """Pure result for copied-item apply-button promotion rewrites."""

    item: dict[str, Any] = field(default_factory=dict)
    button_contract: dict[str, Any] = field(default_factory=dict)
    target_family: str | None = None
    action_payload_rewritten: bool = False
    rewritten_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideApplyButtonContractInputs:
    """Typed input boundary for page-local apply-button contract construction."""

    item_index: int = 0
    item_identity: str | None = None
    item_hash: str | None = None
    state_hash: str | None = None
    family: str | None = None
    action_type: str | None = None
    guidance_intent: str | None = None
    cta_label: str | None = None
    apply_payload_identity: str | None = None
    apply_payload_hash: str | None = None
    candidate_payload_identity: str | None = None
    candidate_payload_hash: str | None = None
    blocking_reason_override: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideApplyButtonContractResult:
    """Typed output boundary for page-local apply-button contract construction."""

    item_index: int = 0
    item_identity: str | None = None
    family: str | None = None
    action_type: str | None = None
    cta_label: str | None = None
    cta_enabled: bool | None = None
    actionable: bool | None = None
    preview_pass: bool | None = None
    disabled_reason: str | None = None
    blocking_reason: str | None = None
    expected_util: Any = None
    apply_payload_identity: str | None = None
    apply_payload_hash: str | None = None
    candidate_payload_identity: str | None = None
    candidate_payload_hash: str | None = None
    contract_hash: str | None = None
    contract_updates_hash: str | None = None
    final_button_contract: dict[str, Any] = field(default_factory=dict)
    contract_scalars: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractScalars:
    """Typed proof record for final button-contract scalar construction."""

    item_index: int = 0
    item_identity: str | None = None
    final_enabled: bool | None = None
    final_disabled: bool | None = None
    final_reason: str | None = None
    final_label: str | None = None
    final_action_text: str | None = None
    final_action_type: str | None = None
    final_family: str | None = None
    final_item_id: str | None = None
    apply_payload_identity: str | None = None
    apply_payload_hash: str | None = None
    candidate_payload_identity: str | None = None
    candidate_payload_hash: str | None = None
    final_state_fingerprint: Any = None
    final_contract_hash: str | None = None
    final_contract_updates_hash: str | None = None
    final_contract_keys: list[str] = field(default_factory=list)
    final_contract: dict[str, Any] = field(default_factory=dict)
    fields_added_to_button_contract: list[str] = field(default_factory=list)
    fields_rewritten_on_button_contract: list[str] = field(default_factory=list)
    decision_reason: str | None = None
    decision_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideVisibleBlockerDisabledContractResult:
    """Typed result for a visible-blocker disabled button contract."""

    item_index: int = 0
    item_identity: str | None = None
    visible_blocker_reason: str | None = None
    visible_blocker_source: str | None = None
    final_disabled_contract: dict[str, Any] = field(default_factory=dict)
    final_disabled_contract_hash: str | None = None
    final_enabled: bool = False
    final_actionable: bool = False
    final_blocking_reason: str | None = None
    apply_payload_identity: str | None = None
    apply_payload_hash: str | None = None
    candidate_payload_identity: str | None = None
    candidate_payload_hash: str | None = None
    emitted_record_kinds: list[str] = field(default_factory=list)
    emitted_record_count: int = 0
    proof_record_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractActionabilityHelperOutputs:
    """Typed bundle for page-local helper outputs used by actionability resolution."""

    item_index: int = 0
    item_identity: str | None = None
    executor_contract_evaluated: bool = False
    executor_allowed: bool | None = None
    executor_reason: str | None = None
    executor_exception_type: str | None = None
    preview_evaluated: bool = False
    preview_pass: bool | None = None
    preview_util: Any = None
    preview_reason: str | None = None
    safe_incremental_below_threshold: bool | None = None
    family_exact_cleanup_blocker: bool | None = None
    local_cleanup_post_apply_acceptance_matches: bool | None = None
    best_safe_partial_cleanup: bool | None = None
    low_util_exact_blocker: bool | None = None
    accepted_band_cleanup_evaluated: bool = False
    accepted_band_cleanup: bool | None = None
    accepted_band_family_preview_util: Any = None
    accepted_band_override_applied: bool = False
    partial_cleanup_override_applied: bool = False
    exact_blocker_override_applied: bool = False
    family_truth_probe_evaluated: bool = False
    family_truth_probe_exception_type: str | None = None
    family_truth_probe_expected_util: Any = None
    combined_truth_probe_evaluated: bool = False
    combined_truth_probe_exception_type: str | None = None
    combined_truth_probe_expected_util: Any = None
    final_executor_allowed: bool | None = None
    final_blocking_reason: str | None = None
    final_preview_pass: bool | None = None
    final_expected_util: Any = None
    helper_output_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractActionabilityProbeInputs:
    """Typed raw/config inputs consumed by page-local actionability probes."""

    item_index: int = 0
    item_identity: str | None = None
    final_accepted_min_family_util: Any = None
    target_band_eps: Any = None
    compound_shear_update_keys: list[str] = field(default_factory=list)
    compound_bottom_update_keys: list[str] = field(default_factory=list)
    family: str | None = None
    action_type: str | None = None
    effective_action_type: str | None = None
    selected_update_source: str | None = None
    update_decision_reason: str | None = None
    update_keys: list[str] = field(default_factory=list)
    updates_hash: str | None = None
    updates_present: bool = False
    updates_touch_compound_shear: bool = False
    updates_touch_compound_bottom: bool = False
    work_hash: str | None = None
    work_action_payload_identity: str | None = None
    work_action_payload_hash: str | None = None
    work_candidate_payload_identity: str | None = None
    work_candidate_payload_hash: str | None = None
    item_action_payload_identity: str | None = None
    item_action_payload_hash: str | None = None
    item_candidate_payload_identity: str | None = None
    item_candidate_payload_hash: str | None = None
    blocking_reason_before_probe: str | None = None
    executor_allowed_before_probe: bool | None = None
    preview_pass_before_probe: bool | None = None
    expected_util_before_probe: Any = None
    family_before_probe: str | None = None
    actionable_before_probe: bool | None = None
    enabled_before_probe: bool | None = None
    guidance_intent: str | None = None
    item_guidance_intent: str | None = None
    work_guidance_intent: str | None = None
    title_label: str | None = None
    combined_title_label: str | None = None
    combined_contract_text_hash: str | None = None
    candidate_search_evidence_hash: str | None = None
    candidate_search_evidence_family: str | None = None
    accepted_band_action_type: str | None = None
    probe_input_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractActionabilityProbeOutputs:
    """Typed proof record for page-local actionability probe outputs."""

    item_index: int = 0
    item_identity: str | None = None
    executor_contract_evaluated: bool = False
    executor_allowed: bool | None = None
    executor_reason: str | None = None
    executor_exception_type: str | None = None
    executor_probe_hash: str | None = None
    preview_evaluated: bool = False
    preview_pass: bool | None = None
    preview_util: Any = None
    preview_reason: str | None = None
    preview_probe_hash: str | None = None
    safe_incremental_below_threshold: bool | None = None
    family_exact_cleanup_blocker: bool | None = None
    local_cleanup_post_apply_acceptance_matches: bool | None = None
    best_safe_partial_cleanup: bool | None = None
    low_util_exact_blocker: bool | None = None
    accepted_band_cleanup_evaluated: bool = False
    accepted_band_cleanup: bool | None = None
    accepted_band_family_preview_util: Any = None
    accepted_band_probe_hash: str | None = None
    accepted_band_override_applied: bool = False
    partial_cleanup_override_applied: bool = False
    exact_blocker_override_applied: bool = False
    family_truth_probe_evaluated: bool = False
    family_truth_probe_exception_type: str | None = None
    family_truth_probe_expected_util: Any = None
    family_truth_probe_hash: str | None = None
    combined_truth_probe_evaluated: bool = False
    combined_truth_probe_exception_type: str | None = None
    combined_truth_probe_expected_util: Any = None
    combined_truth_probe_hash: str | None = None
    final_family: str | None = None
    final_expected_util: Any = None
    final_blocking_reason: str | None = None
    final_executor_allowed: bool | None = None
    final_preview_pass: bool | None = None
    final_probe_hash: str | None = None
    probe_output_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractActionabilityResolution:
    """Typed proof record for final actionability scalar resolution."""

    item_index: int = 0
    item_identity: str | None = None
    blocking_reason_before: str | None = None
    blocking_reason_after: str | None = None
    executor_allowed_before: bool | None = None
    executor_allowed_after: bool | None = None
    preview_pass_before: bool | None = None
    preview_pass_after: bool | None = None
    expected_util_before: Any = None
    expected_util_after: Any = None
    family_before: str | None = None
    family_after: str | None = None
    actionable_before: bool | None = None
    actionable_after: bool | None = None
    enabled_before: bool | None = None
    enabled_after: bool | None = None
    reason_before: str | None = None
    reason_after: str | None = None
    selected_actionability_source: str | None = None
    decision_reason: str | None = None
    decision_source: str | None = None
    scalar_changed: bool = False
    changed_fields: list[str] = field(default_factory=list)
    final_contract_hash: str | None = None
    final_contract_updates_hash: str | None = None
    resolution_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractActionabilityScalarResolutionResult:
    """Pure scalar-resolution result after page-owned actionability probes run."""

    blocking_reason: str | None = None
    executor_allowed: bool | None = None
    preview_pass: bool | None = None
    expected_util: Any = None
    family: str | None = None
    actionable: bool | None = None
    enabled: bool | None = None
    probe_outputs: DesignGuideButtonContractActionabilityProbeOutputs | None = None
    resolution: DesignGuideButtonContractActionabilityResolution | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractFinalResult:
    """Final button-contract wrapper from already-resolved page/publication scalars."""

    final_contract: dict[str, Any] = field(default_factory=dict)
    actionable: bool = False
    source_candidate_id: str | None = None
    family: str | None = None
    action_type: str | None = None
    updates_hash: str | None = None
    contract_hash: str | None = None
    contract_result: DesignGuideApplyButtonContractResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DesignGuideButtonContractEmissionContext:
    """Typed context for emitting button-contract proof records."""

    item_index: int = 0
    item: dict | None = None
    work_after: dict | None = None
    updates: dict | None = None
    updates_source: str | None = None
    final_contract: dict | None = None
    action_type: str | None = None
    effective_action_type: str | None = None
    family: str | None = None
    expected_util: Any = None
    blocking_reason: str | None = None
    executor_allowed: bool | None = None
    executor_reason: str | None = None
    executor_exception_type: str | None = None
    executor_contract_evaluated: bool = False
    preview_pass: bool | None = None
    preview_util: Any = None
    preview_reason: str | None = None
    preview_evaluated: bool = False
    source_candidate_id: str | None = None
    actionable: bool = False
    update_decision_reason: str | None = None
    update_exception_type: str | None = None
    safe_incremental_below_threshold: bool | None = None
    family_exact_cleanup_blocker: bool | None = None
    local_cleanup_post_apply_acceptance_matches: bool | None = None
    best_safe_partial_cleanup: bool | None = None
    low_util_exact_blocker: bool | None = None
    accepted_band_cleanup_evaluated: bool = False
    accepted_band_cleanup: bool | None = None
    accepted_band_family_preview_util: Any = None
    accepted_band_override_applied: bool = False
    partial_cleanup_override_applied: bool = False
    exact_blocker_override_applied: bool = False
    family_truth_probe_evaluated: bool = False
    family_truth_probe_exception_type: str | None = None
    family_truth_probe_expected_util: Any = None
    combined_truth_probe_evaluated: bool = False
    combined_truth_probe_exception_type: str | None = None
    combined_truth_probe_expected_util: Any = None
    resolution_blocking_reason_before: str | None = None
    resolution_executor_allowed_before: bool | None = None
    resolution_preview_pass_before: bool | None = None
    resolution_expected_util_before: Any = None
    resolution_family_before: str | None = None
    resolution_actionable_before: bool | None = None
    resolution_enabled_before: bool | None = None
    update_resolution_input_record: DesignGuideButtonContractUpdateResolutionInputs | None = None
    update_resolution_applicable: bool = False
    update_family_before: str | None = None
    update_action_type_before: str | None = None
    update_expected_util_before: Any = None
    blocking_reason_override: str | None = None
    work_before: dict | None = None
    item_snapshot_before: dict | None = None
    work_mutation_record: DesignGuideButtonContractWorkMutation | None = None
    work_mutation_input_snapshot: dict | None = None
    work_mutation_output_snapshot: dict | None = None
    work_mutation_selected_source: str | None = None
    work_mutation_selected_updates: dict | None = None
    work_mutation_selected_candidate_id: str | None = None
    work_mutation_selected_util: Any = None
    work_mutation_applied: bool = False
    work_mutation_object_id_before: int | None = None
    work_mutation_object_id_after: int | None = None
    actionability_resolution_records: list[DesignGuideButtonContractActionabilityResolution] | None = None
    actionability_probe_output_records: list[DesignGuideButtonContractActionabilityProbeOutputs] | None = None
    actionability_helper_output_records: list[DesignGuideButtonContractActionabilityHelperOutputs] | None = None
    actionability_input_records: list[DesignGuideButtonContractActionabilityInputs] | None = None
    actionability_predicate_records: list[DesignGuideButtonContractActionabilityPredicates] | None = None
    actionability_application_records: list[DesignGuideButtonContractActionabilityApplication] | None = None
    actionability_decision_records: list[DesignGuideButtonContractActionabilityDecision] | None = None
    update_resolution_input_records: list[DesignGuideButtonContractUpdateResolutionInputs] | None = None
    update_resolution_decision_records: list[DesignGuideButtonContractUpdateResolutionDecision] | None = None
    scalar_records: list[DesignGuideButtonContractScalars] | None = None
    work_mutation_records: list[DesignGuideButtonContractWorkMutation] | None = None
    update_resolution_records: list[DesignGuideButtonContractUpdateResolution] | None = None
    actionability_resolution_source_override: str | None = None

    @classmethod
    def from_button_contract_scope(
        cls,
        scope: Mapping[str, Any],
        *,
        item_index: int,
        item: dict | None,
        updates: dict | None,
        final_contract: dict | None,
        actionable: bool,
        actionability_resolution_source_override: str | None = None,
    ) -> "DesignGuideButtonContractEmissionContext":
        return cls(
            item_index=int(item_index),
            item=item,
            work_after=scope.get("work_after"),
            updates=dict(updates or {}),
            updates_source=scope.get("updates_source"),
            final_contract=final_contract,
            action_type=scope.get("action_type"),
            effective_action_type=scope.get("effective_action_type"),
            family=scope.get("family"),
            expected_util=scope.get("expected_util"),
            blocking_reason=scope.get("blocking_reason"),
            executor_allowed=scope.get("executor_allowed"),
            executor_reason=scope.get("executor_reason"),
            executor_exception_type=scope.get("executor_exception_type"),
            executor_contract_evaluated=bool(scope.get("executor_contract_evaluated")),
            preview_pass=scope.get("preview_pass"),
            preview_util=scope.get("preview_util"),
            preview_reason=scope.get("preview_reason"),
            preview_evaluated=bool(scope.get("preview_evaluated")),
            source_candidate_id=scope.get("source_candidate_id"),
            actionable=bool(actionable),
            update_decision_reason=scope.get("update_decision_reason"),
            update_exception_type=scope.get("update_exception_type"),
            safe_incremental_below_threshold=scope.get("safe_incremental_below_threshold"),
            family_exact_cleanup_blocker=scope.get("family_exact_cleanup_blocker"),
            local_cleanup_post_apply_acceptance_matches=scope.get("local_cleanup_post_apply_acceptance_matches"),
            best_safe_partial_cleanup=scope.get("best_safe_partial_cleanup"),
            low_util_exact_blocker=scope.get("low_util_exact_blocker"),
            accepted_band_cleanup_evaluated=bool(scope.get("accepted_band_cleanup_evaluated")),
            accepted_band_cleanup=scope.get("accepted_band_cleanup"),
            accepted_band_family_preview_util=scope.get("accepted_band_family_preview_util"),
            accepted_band_override_applied=bool(scope.get("accepted_band_override_applied")),
            partial_cleanup_override_applied=bool(scope.get("partial_cleanup_override_applied")),
            exact_blocker_override_applied=bool(scope.get("exact_blocker_override_applied")),
            family_truth_probe_evaluated=bool(scope.get("family_truth_probe_evaluated")),
            family_truth_probe_exception_type=scope.get("family_truth_probe_exception_type"),
            family_truth_probe_expected_util=scope.get("family_truth_probe_expected_util"),
            combined_truth_probe_evaluated=bool(scope.get("combined_truth_probe_evaluated")),
            combined_truth_probe_exception_type=scope.get("combined_truth_probe_exception_type"),
            combined_truth_probe_expected_util=scope.get("combined_truth_probe_expected_util"),
            resolution_blocking_reason_before=scope.get("resolution_blocking_reason_before"),
            resolution_executor_allowed_before=scope.get("resolution_executor_allowed_before"),
            resolution_preview_pass_before=scope.get("resolution_preview_pass_before"),
            resolution_expected_util_before=scope.get("resolution_expected_util_before"),
            resolution_family_before=scope.get("resolution_family_before"),
            resolution_actionable_before=scope.get("resolution_actionable_before"),
            resolution_enabled_before=scope.get("resolution_enabled_before"),
            update_resolution_input_record=scope.get("update_resolution_input_record"),
            update_resolution_applicable=bool(scope.get("update_resolution_applicable")),
            update_family_before=scope.get("update_family_before"),
            update_action_type_before=scope.get("update_action_type_before"),
            update_expected_util_before=scope.get("update_expected_util_before"),
            blocking_reason_override=scope.get("blocking_reason_override"),
            work_before=scope.get("work_before"),
            item_snapshot_before=scope.get("item_snapshot_before"),
            work_mutation_record=scope.get("work_mutation_record"),
            work_mutation_input_snapshot=scope.get("work_mutation_input_snapshot"),
            work_mutation_output_snapshot=scope.get("work_mutation_output_snapshot"),
            work_mutation_selected_source=scope.get("work_mutation_selected_source"),
            work_mutation_selected_updates=scope.get("work_mutation_selected_updates"),
            work_mutation_selected_candidate_id=scope.get("work_mutation_selected_candidate_id"),
            work_mutation_selected_util=scope.get("work_mutation_selected_util"),
            work_mutation_applied=bool(scope.get("work_mutation_applied")),
            work_mutation_object_id_before=scope.get("work_mutation_object_id_before"),
            work_mutation_object_id_after=scope.get("work_mutation_object_id_after"),
            actionability_resolution_records=scope.get("actionability_resolution_records"),
            actionability_probe_output_records=scope.get("actionability_probe_output_records"),
            actionability_helper_output_records=scope.get("actionability_helper_output_records"),
            actionability_input_records=scope.get("actionability_input_records"),
            actionability_predicate_records=scope.get("actionability_predicate_records"),
            actionability_application_records=scope.get("actionability_application_records"),
            actionability_decision_records=scope.get("actionability_decision_records"),
            update_resolution_input_records=scope.get("update_resolution_input_records"),
            update_resolution_decision_records=scope.get("update_resolution_decision_records"),
            scalar_records=scope.get("scalar_records"),
            work_mutation_records=scope.get("work_mutation_records"),
            update_resolution_records=scope.get("update_resolution_records"),
            actionability_resolution_source_override=actionability_resolution_source_override,
        )

    def to_kwargs(self) -> dict[str, Any]:
        return {
            field_info.name: getattr(self, field_info.name)
            for field_info in dataclass_fields(self)
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_design_guide_button_contract_actionability_probe_inputs(
    *,
    item_index: int,
    item: dict | None,
    work: dict | None,
    updates: dict | None,
    family: str | None = None,
    action_type: str | None = None,
    effective_action_type: str | None = None,
    selected_update_source: str | None = None,
    update_decision_reason: str | None = None,
    final_accepted_min_family_util: Any = None,
    target_band_eps: Any = None,
    compound_shear_update_keys: Iterable[Any] | None = None,
    compound_bottom_update_keys: Iterable[Any] | None = None,
    blocking_reason_before_probe: str | None = None,
    executor_allowed_before_probe: bool | None = None,
    preview_pass_before_probe: bool | None = None,
    expected_util_before_probe: Any = None,
    actionable_before_probe: bool | None = None,
    enabled_before_probe: bool | None = None,
    candidate_search_evidence: dict | None = None,
) -> DesignGuideButtonContractActionabilityProbeInputs:
    """Record raw/config inputs for actionability probes without executing probes."""

    item_d = dict(item or {}) if isinstance(item, dict) else {}
    work_d = dict(work or {}) if isinstance(work, dict) else {}
    updates_d = dict(updates or {})
    update_key_set = set(str(key) for key in updates_d.keys())
    shear_keys = sorted(str(key) for key in (compound_shear_update_keys or []))
    bottom_keys = sorted(str(key) for key in (compound_bottom_update_keys or []))
    shear_key_set = set(shear_keys)
    bottom_key_set = set(bottom_keys)
    identity = _apply_button_binding_item_identity(item_d, item_index)
    work_action_payload = dict(work_d.get("action_payload") or {})
    work_candidate_payload = dict(
        work_d.get("resolved_candidate")
        or work_d.get("candidate")
        or work_d.get("candidate_payload")
        or {}
    )
    item_action_payload = dict(item_d.get("action_payload") or {})
    item_candidate_payload = dict(
        item_d.get("resolved_candidate")
        or item_d.get("candidate")
        or item_d.get("candidate_payload")
        or {}
    )
    evidence = dict(candidate_search_evidence or {})
    work_guidance_intent = str(work_d.get("guidance_intent") or "").strip() or None
    item_guidance_intent = str(item_d.get("guidance_intent") or "").strip() or None
    title_label = str(item_d.get("title_main") or item_d.get("title") or "").strip() or None
    combined_title_label = str(item_d.get("title_main") or item_d.get("title") or "Combined cleanup").strip()
    combined_text = " ".join(
        str(value or "")
        for value in (
            family,
            item_d.get("candidate_id"),
            item_d.get("source_candidate_id"),
            title_label,
            evidence.get("family"),
            evidence.get("primary_action_family"),
            evidence.get("merged_action_family"),
            evidence.get("same_click_merged_payload_family"),
            evidence.get("selected_candidate_id"),
            evidence.get("search_scope"),
        )
    ).lower()
    payload = {
        "item_identity": identity,
        "final_accepted_min_family_util": final_accepted_min_family_util,
        "target_band_eps": target_band_eps,
        "compound_shear_update_keys": shear_keys,
        "compound_bottom_update_keys": bottom_keys,
        "family": str(family or "").strip().lower() or None,
        "action_type": str(action_type or "").strip() or None,
        "effective_action_type": str(effective_action_type or "").strip() or None,
        "selected_update_source": str(selected_update_source or "").strip() or None,
        "update_decision_reason": str(update_decision_reason or "").strip() or None,
        "update_keys": sorted(update_key_set),
        "updates_hash": publication_snapshot_hash(updates_d),
        "updates_present": bool(updates_d),
        "updates_touch_compound_shear": bool(update_key_set & shear_key_set),
        "updates_touch_compound_bottom": bool(update_key_set & bottom_key_set),
        "work_hash": publication_snapshot_hash(work_d),
        "work_action_payload_identity": _apply_button_binding_payload_identity(work_action_payload, identity),
        "work_action_payload_hash": publication_snapshot_hash(work_action_payload),
        "work_candidate_payload_identity": _apply_button_binding_payload_identity(work_candidate_payload, identity),
        "work_candidate_payload_hash": publication_snapshot_hash(work_candidate_payload),
        "item_action_payload_identity": _apply_button_binding_payload_identity(item_action_payload, identity),
        "item_action_payload_hash": publication_snapshot_hash(item_action_payload),
        "item_candidate_payload_identity": _apply_button_binding_payload_identity(item_candidate_payload, identity),
        "item_candidate_payload_hash": publication_snapshot_hash(item_candidate_payload),
        "blocking_reason_before_probe": str(blocking_reason_before_probe or "").strip() or None,
        "executor_allowed_before_probe": (
            executor_allowed_before_probe
            if executor_allowed_before_probe is None
            else bool(executor_allowed_before_probe)
        ),
        "preview_pass_before_probe": preview_pass_before_probe if preview_pass_before_probe is None else bool(preview_pass_before_probe),
        "expected_util_before_probe": expected_util_before_probe,
        "family_before_probe": str(family or "").strip().lower() or None,
        "actionable_before_probe": actionable_before_probe if actionable_before_probe is None else bool(actionable_before_probe),
        "enabled_before_probe": enabled_before_probe if enabled_before_probe is None else bool(enabled_before_probe),
        "guidance_intent": work_guidance_intent or item_guidance_intent,
        "item_guidance_intent": item_guidance_intent,
        "work_guidance_intent": work_guidance_intent,
        "title_label": title_label,
        "combined_title_label": combined_title_label,
        "combined_contract_text_hash": publication_snapshot_hash(combined_text),
        "candidate_search_evidence_hash": publication_snapshot_hash(evidence),
        "candidate_search_evidence_family": str(evidence.get("family") or "").strip().lower() or None,
        "accepted_band_action_type": str(effective_action_type or action_type or "").strip() or None,
    }
    return DesignGuideButtonContractActionabilityProbeInputs(
        item_index=int(item_index),
        probe_input_hash=publication_snapshot_hash(payload),
        **payload,
    )


@dataclass(frozen=True)
class DesignGuideButtonContractActionabilityInputs:
    """Typed input boundary for final button-contract actionability resolution."""

    item_index: int = 0
    item_identity: str | None = None
    requested_action_type: str | None = None
    effective_action_type: str | None = None
    requested_updates_hash: str | None = None
    requested_updates_keys: list[str] = field(default_factory=list)
    selected_update_source: str | None = None
    selected_updates_hash: str | None = None
    selected_updates_keys: list[str] = field(default_factory=list)
    selected_evidence_candidate_id: str | None = None
    selected_parsed_util: Any = None
    resolved_work_hash: str | None = None
    resolved_work_action_payload_identity: str | None = None
    resolved_work_action_payload_hash: str | None = None
    resolved_work_candidate_payload_identity: str | None = None
    resolved_work_candidate_payload_hash: str | None = None
    executor_allowed: bool | None = None
    executor_reason: str | None = None
    preview_pass: bool | None = None
    preview_reason: str | None = None
    helper_outputs: DesignGuideButtonContractActionabilityHelperOutputs | None = None
    expected_util: Any = None
    blocking_reason_before_final_decision: str | None = None
    family: str | None = None
    source_candidate_id: str | None = None
    update_decision_reason: str | None = None
    update_exception_type: str | None = None
    decision_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractActionabilityDecision:
    """Typed output boundary for final button-contract actionability resolution."""

    item_index: int = 0
    item_identity: str | None = None
    input_hash: str | None = None
    final_actionable: bool | None = None
    final_enabled: bool | None = None
    final_disabled: bool | None = None
    final_reason: str | None = None
    final_cta_label: str | None = None
    final_action_type: str | None = None
    final_family: str | None = None
    final_apply_payload_identity: str | None = None
    final_apply_payload_hash: str | None = None
    final_candidate_payload_identity: str | None = None
    final_candidate_payload_hash: str | None = None
    final_contract_hash: str | None = None
    final_contract_updates_hash: str | None = None
    decision_reason: str | None = None
    decision_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractActionabilityPredicates:
    """Pure predicate result for final button-contract actionability checks."""

    item_index: int = 0
    item_identity: str | None = None
    requested_action_present: bool = False
    selected_updates_present: bool = False
    action_allowed_by_executor: bool | None = None
    action_allowed_by_preview: bool | None = None
    disabled_by_executor: bool = False
    disabled_by_preview: bool = False
    safe_executor_actionable_override_applies: bool = False
    accepted_band_override_applies: bool = False
    partial_cleanup_override_applies: bool = False
    exact_blocker_override_applies: bool = False
    payload_action_mismatch_blocks_apply: bool = False
    final_override_candidate_applies: bool = False
    final_actionable_predicate: bool = False
    deterministic_reason: str | None = None
    decision_source: str | None = None
    predicate_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractActionabilityApplication:
    """Typed proof record for applying final actionability scalars to a contract."""

    item_index: int = 0
    item_identity: str | None = None
    predicate_hash: str | None = None
    predicate_final_actionable: bool | None = None
    scalar_inputs: dict[str, Any] = field(default_factory=dict)
    scalar_inputs_hash: str | None = None
    original_actionable: bool | None = None
    original_blocking_reason: str | None = None
    final_actionable: bool | None = None
    final_blocking_reason: str | None = None
    final_enabled: bool | None = None
    final_disabled: bool | None = None
    final_contract_hash: str | None = None
    final_contract_updates_hash: str | None = None
    decision_reason: str | None = None
    decision_source: str | None = None
    application_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractUpdateResolution:
    """Typed proof record for production button-contract update resolution."""

    item_index: int = 0
    item_identity: str | None = None
    production_button_contract_exercised: bool = True
    button_contract_update_resolution_applicable: bool = False
    family_before: str | None = None
    family_after: str | None = None
    input_action_type: str | None = None
    resolved_action_type: str | None = None
    input_updates_hash: str | None = None
    resolved_updates_hash: str | None = None
    resolved_updates_keys: list[str] = field(default_factory=list)
    resolved_enabled: bool | None = None
    resolved_disabled_reason: str | None = None
    expected_util_before: Any = None
    expected_util_after: Any = None
    apply_payload_identity_before: str | None = None
    apply_payload_identity_after: str | None = None
    apply_payload_hash_before: str | None = None
    apply_payload_hash_after: str | None = None
    candidate_payload_identity_before: str | None = None
    candidate_payload_identity_after: str | None = None
    candidate_payload_hash_before: str | None = None
    candidate_payload_hash_after: str | None = None
    work_hash_before: str | None = None
    work_hash_after: str | None = None
    work_object_copied: bool | None = None
    action_payload_object_copied: bool | None = None
    resolved_candidate_object_copied: bool | None = None
    work_fields_added: list[str] = field(default_factory=list)
    work_fields_removed: list[str] = field(default_factory=list)
    work_fields_rewritten: list[str] = field(default_factory=list)
    action_payload_fields_added: list[str] = field(default_factory=list)
    action_payload_fields_rewritten: list[str] = field(default_factory=list)
    resolved_candidate_fields_added: list[str] = field(default_factory=list)
    resolved_candidate_fields_rewritten: list[str] = field(default_factory=list)
    input_contract_hash: str | None = None
    final_contract_hash: str | None = None
    final_contract_enabled: bool | None = None
    final_contract_keys: list[str] = field(default_factory=list)
    contract_fields_added: list[str] = field(default_factory=list)
    contract_fields_rewritten: list[str] = field(default_factory=list)
    updates_source: str | None = None
    decision_reason: str | None = None
    exception_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractUpdateResolutionInputs:
    """Typed input boundary before production button-contract update resolution."""

    item_index: int = 0
    item_identity: str | None = None
    update_resolution_applicable: bool = False
    family_before: str | None = None
    input_action_type: str | None = None
    input_updates_hash: str | None = None
    input_updates_keys: list[str] = field(default_factory=list)
    blocking_reason_override: str | None = None
    expected_util_before: Any = None
    apply_payload_identity: str | None = None
    apply_payload_hash: str | None = None
    candidate_payload_identity: str | None = None
    candidate_payload_hash: str | None = None
    work_hash_before: str | None = None
    work_object_copied: bool | None = None
    action_payload_object_copied: bool | None = None
    resolved_candidate_object_copied: bool | None = None
    payload_resolution_attempted: bool = False
    payload_resolution_exception_type: str | None = None
    recommendation_updates: dict[str, Any] = field(default_factory=dict)
    recommendation_updates_hash: str | None = None
    recommendation_updates_keys: list[str] = field(default_factory=list)
    candidate_search_evidence: dict[str, Any] = field(default_factory=dict)
    candidate_search_evidence_hash: str | None = None
    candidate_search_evidence_family: str | None = None
    evidence_updates: dict[str, Any] = field(default_factory=dict)
    evidence_updates_hash: str | None = None
    evidence_updates_keys: list[str] = field(default_factory=list)
    evidence_updates_match_state: bool | None = None
    normalised_evidence_candidate_id: str | None = None
    evidence_expected_util: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractUpdateResolutionDecision:
    """Typed output boundary after production button-contract update resolution."""

    item_index: int = 0
    item_identity: str | None = None
    update_resolution_applicable: bool = False
    family_before: str | None = None
    family_after: str | None = None
    input_action_type: str | None = None
    resolved_action_type: str | None = None
    resolved_updates_hash: str | None = None
    resolved_updates_keys: list[str] = field(default_factory=list)
    resolved_enabled: bool | None = None
    resolved_disabled_reason: str | None = None
    expected_util_before: Any = None
    expected_util_after: Any = None
    executor_allowed: bool | None = None
    executor_reason: str | None = None
    preview_pass: bool | None = None
    preview_reason: str | None = None
    final_contract_hash: str | None = None
    final_contract_enabled: bool | None = None
    final_contract_keys: list[str] = field(default_factory=list)
    work_hash_after: str | None = None
    work_fields_added: list[str] = field(default_factory=list)
    work_fields_rewritten: list[str] = field(default_factory=list)
    action_payload_hash_after: str | None = None
    candidate_payload_hash_after: str | None = None
    contract_fields_added: list[str] = field(default_factory=list)
    contract_fields_rewritten: list[str] = field(default_factory=list)
    updates_source: str | None = None
    decision_reason: str | None = None
    exception_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractUpdateSourceSelection:
    """Pure selection result for button-contract update source."""

    selected_update_source: str | None = None
    selected_updates: dict[str, Any] = field(default_factory=dict)
    selected_reason: str | None = None
    selected_evidence_candidate_id: str | None = None
    selected_parsed_util: Any = None
    payload_resolution_attempted: bool = False
    payload_resolution_exception_type: str | None = None
    stable_decision_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractWorkMutation:
    """Typed proof record for applying the selected update source to local work."""

    item_index: int = 0
    item_identity: str | None = None
    work_mutation_applied: bool = False
    selected_update_source: str | None = None
    selected_updates_hash: str | None = None
    selected_updates_keys: list[str] = field(default_factory=list)
    selected_evidence_candidate_id: str | None = None
    selected_parsed_util: Any = None
    input_work_hash: str | None = None
    output_work_hash: str | None = None
    work_object_copied: bool | None = None
    work_mutated_in_place: bool | None = None
    action_payload_identity_before: str | None = None
    action_payload_identity_after: str | None = None
    action_payload_hash_before: str | None = None
    action_payload_hash_after: str | None = None
    action_payload_fields_added: list[str] = field(default_factory=list)
    action_payload_fields_rewritten: list[str] = field(default_factory=list)
    resolved_candidate_identity_before: str | None = None
    resolved_candidate_identity_after: str | None = None
    resolved_candidate_hash_before: str | None = None
    resolved_candidate_hash_after: str | None = None
    resolved_candidate_fields_added: list[str] = field(default_factory=list)
    resolved_candidate_fields_rewritten: list[str] = field(default_factory=list)
    applied_work_fields: list[str] = field(default_factory=list)
    work_fields_added: list[str] = field(default_factory=list)
    work_fields_rewritten: list[str] = field(default_factory=list)
    button_contract_fields_affected: list[str] = field(default_factory=list)
    decision_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractWorkApplicationResult:
    """Copy-return result for applying a selected update source to button-contract work."""

    work: dict[str, Any] = field(default_factory=dict)
    family: str | None = None
    effective_action_type: str | None = None
    expected_util: Any = None
    mutation: DesignGuideButtonContractWorkMutation | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractPayloadUpdateAdapterResult:
    """Explicit result for payload/update-source adaptation before actionability probes."""

    work: dict[str, Any] = field(default_factory=dict)
    family: str | None = None
    effective_action_type: str | None = None
    expected_util: Any = None
    updates: dict[str, Any] = field(default_factory=dict)
    selected_update_source: str | None = None
    selected_update_keys: list[str] = field(default_factory=list)
    selected_evidence_candidate_id: str | None = None
    selected_parsed_util: Any = None
    selected_payload_identity: str | None = None
    selected_payload_hash: str | None = None
    resolved_candidate_identity: str | None = None
    resolved_candidate_hash: str | None = None
    action_payload_identity_before: str | None = None
    action_payload_identity_after: str | None = None
    action_payload_hash_before: str | None = None
    action_payload_hash_after: str | None = None
    update_source_reason: str | None = None
    adapter_changed_anything: bool = False
    update_source_selection: DesignGuideButtonContractUpdateSourceSelection | None = None
    work_application: DesignGuideButtonContractWorkApplicationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideButtonContractPayloadUpdateEvidence:
    """Pure evidence extracted from copied work before update-source selection."""

    candidate_search_evidence: dict[str, Any] = field(default_factory=dict)
    evidence_updates: dict[str, Any] = field(default_factory=dict)
    evidence_family: str | None = None
    evidence_expected_util: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideComputeLateEvidenceSyncState:
    """Copy-return state for compute-stage late evidence synchronization."""

    primary_item: dict[str, Any] = field(default_factory=dict)
    debug_trace: dict[str, Any] = field(default_factory=dict)
    result: DesignGuideComputeLateEvidenceSyncResult = field(default_factory=DesignGuideComputeLateEvidenceSyncResult)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_item": dict(self.primary_item),
            "debug_trace": dict(self.debug_trace),
            "result": self.result.to_dict(),
        }


@dataclass(frozen=True)
class DesignGuideApplyButtonBindingResult:
    """Typed copy-return boundary for Design Guide apply-button binding."""

    bound_items: list[dict[str, Any]] = field(default_factory=list)
    selected_family: str | None = None
    published_family: str | None = None
    apply_family: str | None = None
    cta_label: str | None = None
    cta_enabled: bool | None = None
    cta_reason: str | None = None
    button_contract_enabled: bool | None = None
    disabled_reason: str | None = None
    state_fingerprint: Any = None
    apply_payload_identity: str | None = None
    apply_payload_hash: str | None = None
    candidate_payload_identity: str | None = None
    candidate_payload_hash: str | None = None
    button_contract_summary: dict[str, Any] = field(default_factory=dict)
    input_item_count: int = 0
    output_item_count: int = 0
    item_ids_before: list[str] = field(default_factory=list)
    item_ids_after: list[str] = field(default_factory=list)
    input_hashes_before: list[str] = field(default_factory=list)
    input_hashes_after_call: list[str] = field(default_factory=list)
    input_items_mutated_in_place: bool | None = None
    output_reuses_input_object: bool | None = None
    same_object_indices: list[int] = field(default_factory=list)
    contract_debug_data_added_to_items: list[dict[str, Any]] = field(default_factory=list)
    button_contract_inputs: list[DesignGuideApplyButtonContractInputs] = field(default_factory=list)
    button_contract_results: list[DesignGuideApplyButtonContractResult] = field(default_factory=list)
    button_contract_scalars: list[DesignGuideButtonContractScalars] = field(default_factory=list)
    button_contract_actionability_probe_inputs: list[DesignGuideButtonContractActionabilityProbeInputs] = field(default_factory=list)
    button_contract_actionability_probe_outputs: list[DesignGuideButtonContractActionabilityProbeOutputs] = field(default_factory=list)
    button_contract_actionability_resolutions: list[DesignGuideButtonContractActionabilityResolution] = field(default_factory=list)
    button_contract_actionability_helper_outputs: list[DesignGuideButtonContractActionabilityHelperOutputs] = field(default_factory=list)
    button_contract_actionability_inputs: list[DesignGuideButtonContractActionabilityInputs] = field(default_factory=list)
    button_contract_actionability_predicates: list[DesignGuideButtonContractActionabilityPredicates] = field(default_factory=list)
    button_contract_actionability_applications: list[DesignGuideButtonContractActionabilityApplication] = field(default_factory=list)
    button_contract_actionability_decisions: list[DesignGuideButtonContractActionabilityDecision] = field(default_factory=list)
    button_contract_update_resolution_inputs: list[DesignGuideButtonContractUpdateResolutionInputs] = field(default_factory=list)
    button_contract_update_resolution_decisions: list[DesignGuideButtonContractUpdateResolutionDecision] = field(default_factory=list)
    button_contract_update_resolutions: list[DesignGuideButtonContractUpdateResolution] = field(default_factory=list)
    button_contract_work_mutations: list[DesignGuideButtonContractWorkMutation] = field(default_factory=list)
    promotion_decisions: list[DesignGuideApplyButtonPromotionDecision] = field(default_factory=list)
    safe_executor_evidence_rows: list[DesignGuideSafeExecutorEvidenceRows] = field(default_factory=list)
    items_before: list[dict[str, Any]] = field(default_factory=list)
    items_after: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def publication_snapshot_hash(value: object) -> str:
    try:
        payload = json.dumps(value or {}, default=str, sort_keys=True)
    except (TypeError, ValueError):
        payload = str(value or "")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _compute_late_evidence_sync_hash(value: object) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def guidance_item_source_candidate_id(item: Mapping[str, Any] | None) -> str | None:
    """Return the first stable source candidate identity carried by an item."""

    if not isinstance(item, Mapping):
        return None
    payload = dict(item.get("action_payload") or {})
    resolved = dict(item.get("resolved_candidate") or {})
    for key in (
        "source_candidate_id",
        "candidate_id",
        "resolved_candidate_id",
        "local_cleanup_candidate_id",
        "canonical_candidate_id",
    ):
        value = item.get(key)
        if value is None:
            value = payload.get(key)
        if value is None:
            value = resolved.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return None


def build_late_evidence_primary_item_sync(
    *,
    primary_item: Mapping[str, Any] | None,
    existing_evidence: Mapping[str, Any] | None,
    debug_trace: Mapping[str, Any] | None,
) -> DesignGuideComputeLateEvidenceSyncState:
    """Return synchronized late-evidence item/debug state without mutating inputs."""

    item = dict(primary_item or {})
    evidence = dict(existing_evidence or {})
    debug = dict(debug_trace or {})

    item_before_hash = _compute_late_evidence_sync_hash(item)
    item_candidate_id_before = item.get("candidate_id")
    item_source_candidate_id_before = item.get("source_candidate_id")
    action_payload_before = dict(item.get("action_payload") or {})
    resolved_candidate_before = dict(item.get("resolved_candidate") or {})
    button_contract_before = dict(item.get("button_contract") or {})

    item["candidate_search_evidence"] = dict(evidence)
    item["candidate_id"] = evidence.get("selected_candidate_id")
    item["source_candidate_id"] = evidence.get("selected_candidate_id")

    evidence_payload = dict(item.get("action_payload") or {})
    evidence_payload["candidate_search_evidence"] = dict(evidence)
    evidence_payload["source_candidate_id"] = evidence.get("selected_candidate_id")
    item["action_payload"] = evidence_payload

    evidence_resolved = dict(item.get("resolved_candidate") or {})
    evidence_resolved["candidate_search_evidence"] = dict(evidence)
    evidence_resolved["candidate_id"] = evidence.get("selected_candidate_id")
    evidence_resolved["source_candidate_id"] = evidence.get("selected_candidate_id")
    item["resolved_candidate"] = evidence_resolved

    evidence_contract = dict(item.get("button_contract") or {})
    if evidence_contract:
        if evidence.get("active_under_capacity_blocker_family"):
            evidence_contract["family"] = evidence.get("active_under_capacity_blocker_family")
            evidence_contract["blocking_reason"] = evidence.get("active_under_capacity_blocker_reason")
            evidence_contract["source_candidate_id"] = None
            evidence_contract["candidate_id"] = None
            evidence_contract["updates"] = {}
            evidence_contract["action_type"] = None
            evidence_contract["actionable"] = False
            evidence_contract["preview_pass"] = False
        else:
            evidence_contract["source_candidate_id"] = evidence.get("selected_candidate_id")
        item["button_contract"] = evidence_contract

    debug["candidate_search_evidence"] = dict(evidence)
    if evidence.get("exact_blockers_by_family"):
        debug["exact_blockers_by_family"] = dict(evidence.get("exact_blockers_by_family") or {})
        debug["cleanup_evidence_by_family"] = dict(evidence.get("exact_blockers_by_family") or {})
        debug["local_cleanup_search_ran"] = True
        debug["local_cleanup_search_exhaustive"] = True
        debug["safe_local_cleanup_count"] = 0
        debug["executable_safe_cleanup_count"] = 0

    action_payload_after = dict(item.get("action_payload") or {})
    resolved_candidate_after = dict(item.get("resolved_candidate") or {})
    button_contract_after = dict(item.get("button_contract") or {})

    changed_fields: list[str] = []
    if item_before_hash != _compute_late_evidence_sync_hash(item):
        changed_fields.append("item")
    if _compute_late_evidence_sync_hash(action_payload_before) != _compute_late_evidence_sync_hash(action_payload_after):
        changed_fields.append("action_payload")
    if _compute_late_evidence_sync_hash(resolved_candidate_before) != _compute_late_evidence_sync_hash(resolved_candidate_after):
        changed_fields.append("resolved_candidate")
    if _compute_late_evidence_sync_hash(button_contract_before) != _compute_late_evidence_sync_hash(button_contract_after):
        changed_fields.append("button_contract")
    if _compute_late_evidence_sync_hash(debug.get("candidate_search_evidence") or {}) == _compute_late_evidence_sync_hash(evidence):
        changed_fields.append("debug_candidate_search_evidence")
    if evidence.get("exact_blockers_by_family"):
        changed_fields.append("debug_exact_blockers")
        changed_fields.append("debug_cleanup_evidence")

    result = DesignGuideComputeLateEvidenceSyncResult(
        evidence_hash=_compute_late_evidence_sync_hash(evidence),
        evidence_keys=sorted(str(k) for k in evidence.keys())[:80],
        item_hash_before=item_before_hash,
        item_hash_after=_compute_late_evidence_sync_hash(item),
        item_candidate_id_before=item_candidate_id_before,
        item_candidate_id_after=item.get("candidate_id"),
        item_source_candidate_id_before=item_source_candidate_id_before,
        item_source_candidate_id_after=item.get("source_candidate_id"),
        action_payload_hash_before=_compute_late_evidence_sync_hash(action_payload_before),
        action_payload_hash_after=_compute_late_evidence_sync_hash(action_payload_after),
        action_payload_source_candidate_id=action_payload_after.get("source_candidate_id"),
        action_payload_evidence_hash=_compute_late_evidence_sync_hash(
            action_payload_after.get("candidate_search_evidence") or {}
        ),
        resolved_candidate_hash_before=_compute_late_evidence_sync_hash(resolved_candidate_before),
        resolved_candidate_hash_after=_compute_late_evidence_sync_hash(resolved_candidate_after),
        resolved_candidate_id=resolved_candidate_after.get("candidate_id"),
        resolved_candidate_source_candidate_id=resolved_candidate_after.get("source_candidate_id"),
        resolved_candidate_evidence_hash=_compute_late_evidence_sync_hash(
            resolved_candidate_after.get("candidate_search_evidence") or {}
        ),
        button_contract_hash_before=_compute_late_evidence_sync_hash(button_contract_before),
        button_contract_hash_after=_compute_late_evidence_sync_hash(button_contract_after),
        button_contract_family=button_contract_after.get("family"),
        button_contract_action_type=button_contract_after.get("action_type"),
        button_contract_actionable=button_contract_after.get("actionable"),
        button_contract_preview_pass=button_contract_after.get("preview_pass"),
        button_contract_source_candidate_id=button_contract_after.get("source_candidate_id"),
        button_contract_candidate_id=button_contract_after.get("candidate_id"),
        button_contract_blocking_reason=button_contract_after.get("blocking_reason"),
        debug_candidate_search_evidence_hash=_compute_late_evidence_sync_hash(
            debug.get("candidate_search_evidence") or {}
        ),
        debug_exact_blockers_hash=_compute_late_evidence_sync_hash(debug.get("exact_blockers_by_family") or {}),
        debug_cleanup_evidence_hash=_compute_late_evidence_sync_hash(debug.get("cleanup_evidence_by_family") or {}),
        debug_local_cleanup_search_ran=debug.get("local_cleanup_search_ran"),
        debug_local_cleanup_search_exhaustive=debug.get("local_cleanup_search_exhaustive"),
        debug_safe_local_cleanup_count=debug.get("safe_local_cleanup_count"),
        debug_executable_safe_cleanup_count=debug.get("executable_safe_cleanup_count"),
        active_under_capacity_blocker=bool(evidence.get("active_under_capacity_blocker")),
        exact_blockers_present=bool(evidence.get("exact_blockers_by_family")),
        changed_fields=list(changed_fields),
        parity_checks={
            "item_candidate_evidence_matches": (
                _compute_late_evidence_sync_hash(item.get("candidate_search_evidence") or {})
                == _compute_late_evidence_sync_hash(evidence)
            ),
            "action_payload_evidence_matches": (
                _compute_late_evidence_sync_hash(action_payload_after.get("candidate_search_evidence") or {})
                == _compute_late_evidence_sync_hash(evidence)
            ),
            "resolved_candidate_evidence_matches": (
                _compute_late_evidence_sync_hash(resolved_candidate_after.get("candidate_search_evidence") or {})
                == _compute_late_evidence_sync_hash(evidence)
            ),
            "debug_evidence_matches": (
                _compute_late_evidence_sync_hash(debug.get("candidate_search_evidence") or {})
                == _compute_late_evidence_sync_hash(evidence)
            ),
            "item_candidate_id_matches_selected": (
                item.get("candidate_id") == evidence.get("selected_candidate_id")
            ),
            "action_payload_source_candidate_matches_selected": (
                action_payload_after.get("source_candidate_id")
                == evidence.get("selected_candidate_id")
            ),
            "resolved_candidate_id_matches_selected": (
                resolved_candidate_after.get("candidate_id")
                == evidence.get("selected_candidate_id")
            ),
        },
    )
    return DesignGuideComputeLateEvidenceSyncState(
        primary_item=dict(item),
        debug_trace=dict(debug),
        result=result,
    )


def build_missing_candidate_search_evidence_from_records(
    *,
    candidate_records: Iterable[Mapping[str, Any]] | None,
    target_low: float,
    target_high: float,
    selected_title: str | None,
    evidence_builder: Callable[..., Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]:
    """Build late evidence candidates from pre-resolved displayed-item records."""

    evidence_candidates: list[dict[str, Any]] = []
    for record in list(candidate_records or []):
        if not isinstance(record, Mapping):
            continue
        preview_util = record.get("preview_util")
        evidence_candidates.append(
            {
                "candidate_id": record.get("source_candidate_id") or record.get("fallback_candidate_id"),
                "label": record.get("title_main") or record.get("fallback_title"),
                "updates": dict(record.get("updates") or {}),
                "candidate_post_util": preview_util,
                "worst_util": preview_util,
                "is_compliant": bool(
                    record.get("preview_pass") and record.get("blocking_reason") in (None, "")
                ),
                "overview": {},
            }
        )
    selected_for_evidence = evidence_candidates[0] if evidence_candidates else None
    existing_evidence = evidence_builder(
        selected_candidate=selected_for_evidence,
        all_candidates=evidence_candidates,
        target_low=float(target_low),
        target_high=float(target_high),
        exhaustive=True,
        search_scope="final_displayed_design_guide_candidates",
        selected_title=str(selected_title or ""),
    )
    return dict(existing_evidence), list(evidence_candidates), selected_for_evidence


def build_design_guide_button_contract_update_resolution(
    *,
    item_index: int,
    item: dict | None,
    family_before: str | None,
    family_after: str | None,
    action_type_before: str | None,
    action_type_after: str | None,
    updates_before: dict | None,
    updates_after: dict | None,
    expected_util_before,
    expected_util_after,
    blocking_reason: str | None,
    work_before: dict | None,
    work_after: dict | None,
    final_contract: dict | None,
    update_resolution_applicable: bool,
    updates_source: str | None,
    decision_reason: str | None,
    exception_type: str | None = None,
) -> DesignGuideButtonContractUpdateResolution:
    item_d = dict(item or {}) if isinstance(item, dict) else {}
    before_work = dict(work_before or item_d or {})
    after_work = dict(work_after or before_work or {})
    payload_before = dict(before_work.get("action_payload") or {})
    payload_after = dict(after_work.get("action_payload") or {})
    candidate_before = dict(before_work.get("resolved_candidate") or {})
    candidate_after = dict(after_work.get("resolved_candidate") or {})
    contract_before = dict(item_d.get("button_contract") or {})
    contract_after = dict(final_contract or {})

    def _payload_identity(payload: dict | None, fallback: str | None = None) -> str | None:
        if not isinstance(payload, dict):
            return fallback
        value = (
            payload.get("id")
            or payload.get("payload_id")
            or payload.get("candidate_id")
            or payload.get("source_candidate_id")
            or fallback
        )
        return str(value) if value not in (None, "") else None

    def _rewritten_keys(before: dict, after: dict) -> list[str]:
        return sorted(
            str(key)
            for key in set(before.keys()) & set(after.keys())
            if publication_snapshot_hash(before.get(key)) != publication_snapshot_hash(after.get(key))
        )

    item_identity = str(
        item_d.get("id")
        or item_d.get("candidate_id")
        or item_d.get("source_candidate_id")
        or item_d.get("title_main")
        or item_d.get("title")
        or f"item_{item_index}"
    )
    return DesignGuideButtonContractUpdateResolution(
        item_index=int(item_index),
        item_identity=item_identity,
        production_button_contract_exercised=True,
        button_contract_update_resolution_applicable=bool(update_resolution_applicable),
        family_before=family_before,
        family_after=family_after,
        input_action_type=str(action_type_before or "").strip() or None,
        resolved_action_type=str(action_type_after or "").strip() or None,
        input_updates_hash=publication_snapshot_hash(updates_before or {}),
        resolved_updates_hash=publication_snapshot_hash(updates_after or {}),
        resolved_updates_keys=sorted(str(key) for key in dict(updates_after or {}).keys()),
        resolved_enabled=bool(updates_after),
        resolved_disabled_reason=blocking_reason,
        expected_util_before=expected_util_before,
        expected_util_after=expected_util_after,
        apply_payload_identity_before=_payload_identity(payload_before, item_identity),
        apply_payload_identity_after=_payload_identity(payload_after, item_identity),
        apply_payload_hash_before=publication_snapshot_hash(payload_before),
        apply_payload_hash_after=publication_snapshot_hash(payload_after),
        candidate_payload_identity_before=_payload_identity(candidate_before, item_identity),
        candidate_payload_identity_after=_payload_identity(candidate_after, item_identity),
        candidate_payload_hash_before=publication_snapshot_hash(candidate_before),
        candidate_payload_hash_after=publication_snapshot_hash(candidate_after),
        work_hash_before=publication_snapshot_hash(before_work),
        work_hash_after=publication_snapshot_hash(after_work),
        work_object_copied=isinstance(item, dict) and id(after_work) != id(item),
        action_payload_object_copied=isinstance(item, dict)
        and id(payload_after) != id(item_d.get("action_payload")),
        resolved_candidate_object_copied=isinstance(item, dict)
        and id(candidate_after) != id(item_d.get("resolved_candidate")),
        work_fields_added=sorted(str(key) for key in set(after_work.keys()) - set(before_work.keys())),
        work_fields_removed=sorted(str(key) for key in set(before_work.keys()) - set(after_work.keys())),
        work_fields_rewritten=_rewritten_keys(before_work, after_work),
        action_payload_fields_added=sorted(
            str(key) for key in set(payload_after.keys()) - set(payload_before.keys())
        ),
        action_payload_fields_rewritten=_rewritten_keys(payload_before, payload_after),
        resolved_candidate_fields_added=sorted(
            str(key) for key in set(candidate_after.keys()) - set(candidate_before.keys())
        ),
        resolved_candidate_fields_rewritten=_rewritten_keys(candidate_before, candidate_after),
        input_contract_hash=publication_snapshot_hash(contract_before),
        final_contract_hash=publication_snapshot_hash(contract_after),
        final_contract_enabled=bool(design_guide_button_contract_enabled(contract_after)),
        final_contract_keys=sorted(str(key) for key in contract_after.keys()),
        contract_fields_added=sorted(str(key) for key in set(contract_after.keys()) - set(contract_before.keys())),
        contract_fields_rewritten=_rewritten_keys(contract_before, contract_after),
        updates_source=str(updates_source or "").strip() or None,
        decision_reason=str(decision_reason or "").strip() or None,
        exception_type=str(exception_type or "").strip() or None,
    )


def build_design_guide_button_contract_update_resolution_inputs(
    *,
    item_index: int,
    item: dict | None,
    family_before: str | None,
    action_type_before: str | None,
    updates_before: dict | None,
    expected_util_before,
    blocking_reason_override: str | None,
    work_before: dict | None,
    update_resolution_applicable: bool,
    payload_resolution_attempted: bool = False,
    payload_resolution_exception_type: str | None = None,
    recommendation_updates: dict | None = None,
    candidate_search_evidence: dict | None = None,
    evidence_updates: dict | None = None,
    evidence_updates_match_state: bool | None = None,
    normalised_evidence_candidate_id: str | None = None,
    evidence_expected_util: Any = None,
) -> DesignGuideButtonContractUpdateResolutionInputs:
    item_d = dict(item or {}) if isinstance(item, dict) else {}
    before_work = dict(work_before or item_d or {})
    action_payload = dict(before_work.get("action_payload") or {})
    candidate_payload = dict(before_work.get("resolved_candidate") or {})
    recommendation_updates_d = dict(recommendation_updates or {})
    candidate_search_evidence_d = dict(candidate_search_evidence or {})
    evidence_updates_d = dict(evidence_updates or {})
    evidence_family = str(candidate_search_evidence_d.get("family") or "").strip().lower() or None
    item_identity = _apply_button_binding_item_identity(item_d, item_index)
    return DesignGuideButtonContractUpdateResolutionInputs(
        item_index=int(item_index),
        item_identity=item_identity,
        update_resolution_applicable=bool(update_resolution_applicable),
        family_before=family_before,
        input_action_type=str(action_type_before or "").strip() or None,
        input_updates_hash=publication_snapshot_hash(updates_before or {}),
        input_updates_keys=sorted(str(key) for key in dict(updates_before or {}).keys()),
        blocking_reason_override=str(blocking_reason_override or "").strip() or None,
        expected_util_before=expected_util_before,
        apply_payload_identity=_apply_button_binding_payload_identity(action_payload, item_identity),
        apply_payload_hash=publication_snapshot_hash(action_payload),
        candidate_payload_identity=_apply_button_binding_payload_identity(candidate_payload, item_identity),
        candidate_payload_hash=publication_snapshot_hash(candidate_payload),
        work_hash_before=publication_snapshot_hash(before_work),
        work_object_copied=isinstance(item, dict) and id(before_work) != id(item),
        action_payload_object_copied=isinstance(item, dict)
        and id(action_payload) != id(item_d.get("action_payload")),
        resolved_candidate_object_copied=isinstance(item, dict)
        and id(candidate_payload) != id(item_d.get("resolved_candidate")),
        payload_resolution_attempted=bool(payload_resolution_attempted),
        payload_resolution_exception_type=str(payload_resolution_exception_type or "").strip() or None,
        recommendation_updates=dict(recommendation_updates_d),
        recommendation_updates_hash=publication_snapshot_hash(recommendation_updates_d),
        recommendation_updates_keys=sorted(str(key) for key in recommendation_updates_d.keys()),
        candidate_search_evidence=dict(candidate_search_evidence_d),
        candidate_search_evidence_hash=publication_snapshot_hash(candidate_search_evidence_d),
        candidate_search_evidence_family=evidence_family,
        evidence_updates=dict(evidence_updates_d),
        evidence_updates_hash=publication_snapshot_hash(evidence_updates_d),
        evidence_updates_keys=sorted(str(key) for key in evidence_updates_d.keys()),
        evidence_updates_match_state=evidence_updates_match_state,
        normalised_evidence_candidate_id=str(normalised_evidence_candidate_id or "").strip() or None,
        evidence_expected_util=evidence_expected_util,
    )


def build_design_guide_button_contract_update_resolution_decision(
    *,
    item_index: int,
    item: dict | None,
    family_before: str | None,
    family_after: str | None,
    action_type_before: str | None,
    action_type_after: str | None,
    updates_after: dict | None,
    expected_util_before,
    expected_util_after,
    blocking_reason: str | None,
    work_before: dict | None,
    work_after: dict | None,
    final_contract: dict | None,
    update_resolution_applicable: bool,
    updates_source: str | None,
    decision_reason: str | None,
    exception_type: str | None = None,
    executor_allowed: bool | None = None,
    executor_reason: str | None = None,
    preview_pass: bool | None = None,
    preview_reason: str | None = None,
) -> DesignGuideButtonContractUpdateResolutionDecision:
    item_d = dict(item or {}) if isinstance(item, dict) else {}
    before_work = dict(work_before or item_d or {})
    after_work = dict(work_after or before_work or {})
    action_payload_after = dict(after_work.get("action_payload") or {})
    candidate_payload_after = dict(after_work.get("resolved_candidate") or {})
    contract_before = dict(item_d.get("button_contract") or {})
    contract_after = dict(final_contract or {})

    def _rewritten_keys(before: dict, after: dict) -> list[str]:
        return sorted(
            str(key)
            for key in set(before.keys()) & set(after.keys())
            if publication_snapshot_hash(before.get(key)) != publication_snapshot_hash(after.get(key))
        )

    return DesignGuideButtonContractUpdateResolutionDecision(
        item_index=int(item_index),
        item_identity=_apply_button_binding_item_identity(item_d, item_index),
        update_resolution_applicable=bool(update_resolution_applicable),
        family_before=family_before,
        family_after=family_after,
        input_action_type=str(action_type_before or "").strip() or None,
        resolved_action_type=str(action_type_after or "").strip() or None,
        resolved_updates_hash=publication_snapshot_hash(updates_after or {}),
        resolved_updates_keys=sorted(str(key) for key in dict(updates_after or {}).keys()),
        resolved_enabled=bool(updates_after),
        resolved_disabled_reason=blocking_reason,
        expected_util_before=expected_util_before,
        expected_util_after=expected_util_after,
        executor_allowed=executor_allowed,
        executor_reason=str(executor_reason or "").strip() or None,
        preview_pass=preview_pass,
        preview_reason=str(preview_reason or "").strip() or None,
        final_contract_hash=publication_snapshot_hash(contract_after),
        final_contract_enabled=bool(design_guide_button_contract_enabled(contract_after)),
        final_contract_keys=sorted(str(key) for key in contract_after.keys()),
        work_hash_after=publication_snapshot_hash(after_work),
        work_fields_added=sorted(str(key) for key in set(after_work.keys()) - set(before_work.keys())),
        work_fields_rewritten=_rewritten_keys(before_work, after_work),
        action_payload_hash_after=publication_snapshot_hash(action_payload_after),
        candidate_payload_hash_after=publication_snapshot_hash(candidate_payload_after),
        contract_fields_added=sorted(str(key) for key in set(contract_after.keys()) - set(contract_before.keys())),
        contract_fields_rewritten=_rewritten_keys(contract_before, contract_after),
        updates_source=str(updates_source or "").strip() or None,
        decision_reason=str(decision_reason or "").strip() or None,
        exception_type=str(exception_type or "").strip() or None,
    )


def select_design_guide_button_contract_update_source(
    inputs: DesignGuideButtonContractUpdateResolutionInputs,
) -> DesignGuideButtonContractUpdateSourceSelection:
    """Select an already pre-resolved update source without mutating product state."""

    if not bool(inputs.update_resolution_applicable):
        return DesignGuideButtonContractUpdateSourceSelection(
            selected_update_source="not_applicable",
            payload_resolution_attempted=bool(inputs.payload_resolution_attempted),
            payload_resolution_exception_type=inputs.payload_resolution_exception_type,
            stable_decision_reason=None,
        )

    if inputs.payload_resolution_exception_type:
        return DesignGuideButtonContractUpdateSourceSelection(
            selected_update_source="exception",
            payload_resolution_attempted=bool(inputs.payload_resolution_attempted),
            payload_resolution_exception_type=inputs.payload_resolution_exception_type,
            stable_decision_reason="update_resolution_exception",
        )

    recommendation_updates = dict(inputs.recommendation_updates or {})
    if recommendation_updates:
        return DesignGuideButtonContractUpdateSourceSelection(
            selected_update_source="resolve_recommendation_updates",
            selected_updates=recommendation_updates,
            selected_reason="resolved_from_recommendation_updates",
            payload_resolution_attempted=bool(inputs.payload_resolution_attempted),
            payload_resolution_exception_type=inputs.payload_resolution_exception_type,
            stable_decision_reason="resolved_from_recommendation_updates",
        )

    evidence_updates = dict(inputs.evidence_updates or {})
    evidence_family = str(inputs.candidate_search_evidence_family or "").strip().lower()
    if (
        evidence_updates
        and evidence_family in {"bending", "shear", "combined"}
        and not bool(inputs.evidence_updates_match_state)
    ):
        return DesignGuideButtonContractUpdateSourceSelection(
            selected_update_source="candidate_search_evidence",
            selected_updates=evidence_updates,
            selected_reason="resolved_from_candidate_search_evidence",
            selected_evidence_candidate_id=inputs.normalised_evidence_candidate_id,
            selected_parsed_util=inputs.evidence_expected_util,
            payload_resolution_attempted=bool(inputs.payload_resolution_attempted),
            payload_resolution_exception_type=inputs.payload_resolution_exception_type,
            stable_decision_reason="resolved_from_candidate_search_evidence",
        )

    return DesignGuideButtonContractUpdateSourceSelection(
        selected_update_source="none",
        payload_resolution_attempted=bool(inputs.payload_resolution_attempted),
        payload_resolution_exception_type=inputs.payload_resolution_exception_type,
        stable_decision_reason=None,
    )


def build_design_guide_button_contract_work_mutation(
    *,
    item_index: int,
    item: dict | None,
    work_before: dict | None,
    work_after: dict | None,
    selected_update_source: str | None,
    selected_updates: dict | None,
    selected_evidence_candidate_id: str | None = None,
    selected_parsed_util: Any = None,
    work_mutation_applied: bool = False,
    work_object_id_before: int | None = None,
    work_object_id_after: int | None = None,
    decision_reason: str | None = None,
) -> DesignGuideButtonContractWorkMutation:
    """Assemble a typed record for local work mutation without mutating anything."""

    item_d = dict(item or {}) if isinstance(item, dict) else {}
    before_work = dict(work_before or item_d or {})
    after_work = dict(work_after or before_work or {})
    selected_updates_d = dict(selected_updates or {})
    payload_before = dict(before_work.get("action_payload") or {})
    payload_after = dict(after_work.get("action_payload") or {})
    candidate_before = dict(before_work.get("resolved_candidate") or {})
    candidate_after = dict(after_work.get("resolved_candidate") or {})
    item_identity = _apply_button_binding_item_identity(item_d, item_index)

    def _rewritten_keys(before: dict, after: dict) -> list[str]:
        return sorted(
            str(key)
            for key in set(before.keys()) & set(after.keys())
            if publication_snapshot_hash(before.get(key)) != publication_snapshot_hash(after.get(key))
        )

    work_fields_added = sorted(str(key) for key in set(after_work.keys()) - set(before_work.keys()))
    work_fields_rewritten = _rewritten_keys(before_work, after_work)
    button_contract_fields_affected = (
        [
            "action_type",
            "candidate_id",
            "expected_util",
            "family",
            "source_candidate_id",
            "updates",
        ]
        if bool(work_mutation_applied)
        else []
    )
    return DesignGuideButtonContractWorkMutation(
        item_index=int(item_index),
        item_identity=item_identity,
        work_mutation_applied=bool(work_mutation_applied),
        selected_update_source=str(selected_update_source or "").strip() or None,
        selected_updates_hash=publication_snapshot_hash(selected_updates_d),
        selected_updates_keys=sorted(str(key) for key in selected_updates_d.keys()),
        selected_evidence_candidate_id=str(selected_evidence_candidate_id or "").strip() or None,
        selected_parsed_util=selected_parsed_util,
        input_work_hash=publication_snapshot_hash(before_work),
        output_work_hash=publication_snapshot_hash(after_work),
        work_object_copied=isinstance(item, dict) and work_object_id_after is not None and work_object_id_after != id(item),
        work_mutated_in_place=(
            bool(work_mutation_applied)
            and work_object_id_before is not None
            and work_object_id_after is not None
            and work_object_id_before == work_object_id_after
        ),
        action_payload_identity_before=_apply_button_binding_payload_identity(payload_before, item_identity),
        action_payload_identity_after=_apply_button_binding_payload_identity(payload_after, item_identity),
        action_payload_hash_before=publication_snapshot_hash(payload_before),
        action_payload_hash_after=publication_snapshot_hash(payload_after),
        action_payload_fields_added=sorted(
            str(key) for key in set(payload_after.keys()) - set(payload_before.keys())
        ),
        action_payload_fields_rewritten=_rewritten_keys(payload_before, payload_after),
        resolved_candidate_identity_before=_apply_button_binding_payload_identity(candidate_before, item_identity),
        resolved_candidate_identity_after=_apply_button_binding_payload_identity(candidate_after, item_identity),
        resolved_candidate_hash_before=publication_snapshot_hash(candidate_before),
        resolved_candidate_hash_after=publication_snapshot_hash(candidate_after),
        resolved_candidate_fields_added=sorted(
            str(key) for key in set(candidate_after.keys()) - set(candidate_before.keys())
        ),
        resolved_candidate_fields_rewritten=_rewritten_keys(candidate_before, candidate_after),
        applied_work_fields=sorted(set(work_fields_added) | set(work_fields_rewritten)),
        work_fields_added=work_fields_added,
        work_fields_rewritten=work_fields_rewritten,
        button_contract_fields_affected=button_contract_fields_affected,
        decision_reason=str(decision_reason or "").strip() or None,
    )


def apply_design_guide_button_contract_work_updates(
    *,
    item_index: int,
    item: dict | None,
    work: dict | None,
    selection: DesignGuideButtonContractUpdateSourceSelection,
    candidate_search_evidence: dict | None,
    candidate_search_evidence_family: str | None,
    current_family: str | None,
    current_effective_action_type: str | None,
    current_expected_util: Any = None,
    source_candidate_id_fallback: str | None = None,
    decision_reason: str | None = None,
) -> DesignGuideButtonContractWorkApplicationResult:
    """Apply an already-selected update source to a copied work mapping."""

    out = dict(work or {})
    out["action_payload"] = dict(out.get("action_payload") or {})
    input_snapshot = dict(out)
    object_id_before = id(out)
    selected_source = str(selection.selected_update_source or "none").strip() or "none"
    updates = dict(selection.selected_updates or {})
    family = str(current_family or "").strip().lower() or None
    effective_action_type = str(current_effective_action_type or "").strip() or None
    expected_util = current_expected_util
    mutation_applied = False

    if selected_source == "candidate_search_evidence":
        evidence = dict(candidate_search_evidence or {})
        evidence_family = str(candidate_search_evidence_family or family or "").strip().lower()
        if updates and evidence_family in {"bending", "shear", "combined"}:
            effective_action_type = "apply_resolved_candidate"
            evidence_candidate_id = (
                str(selection.selected_evidence_candidate_id or "").strip()
                or str(source_candidate_id_fallback or "").strip()
                or None
            )
            out["family"] = evidence_family
            out["check_key"] = evidence_family
            out["selected_action_family"] = evidence_family
            family = evidence_family
            payload_for_updates = dict(out.get("action_payload") or {})
            payload_for_updates.update(
                {
                    "updates": dict(updates),
                    "resolved_candidate_updates": dict(updates),
                    "resolved_candidate_action_type": "apply_resolved_candidate",
                    "resolved_candidate_family_tag": evidence_family,
                    "source_candidate_id": evidence_candidate_id,
                    "candidate_id": evidence_candidate_id,
                    "candidate_search_evidence": dict(evidence),
                }
            )
            out["action_payload"] = payload_for_updates
            resolved_for_updates = dict(out.get("resolved_candidate") or {})
            resolved_for_updates.update(
                {
                    "updates": dict(updates),
                    "action_type": "apply_resolved_candidate",
                    "family": evidence_family,
                    "source_candidate_id": evidence_candidate_id,
                    "candidate_id": evidence_candidate_id,
                    "candidate_search_evidence": dict(evidence),
                }
            )
            out["resolved_candidate"] = resolved_for_updates
            if expected_util is None:
                expected_util = selection.selected_parsed_util
            mutation_applied = True

    output_snapshot = dict(out)
    mutation = build_design_guide_button_contract_work_mutation(
        item_index=item_index,
        item=item,
        work_before=input_snapshot,
        work_after=output_snapshot,
        selected_update_source=selected_source,
        selected_updates=updates,
        selected_evidence_candidate_id=selection.selected_evidence_candidate_id,
        selected_parsed_util=selection.selected_parsed_util,
        work_mutation_applied=mutation_applied,
        work_object_id_before=object_id_before,
        work_object_id_after=id(out),
        decision_reason=decision_reason,
    )
    return DesignGuideButtonContractWorkApplicationResult(
        work=out,
        family=family,
        effective_action_type=effective_action_type,
        expected_util=expected_util,
        mutation=mutation,
    )


def collect_design_guide_button_contract_payload_update_evidence(
    work: dict | None,
    *,
    family: str | None = None,
) -> DesignGuideButtonContractPayloadUpdateEvidence:
    """Extract candidate-search evidence fields without reading page state."""

    work_d = dict(work or {})
    candidate_search_evidence = dict(
        work_d.get("candidate_search_evidence")
        or (work_d.get("action_payload") or {}).get("candidate_search_evidence")
        or (work_d.get("resolved_candidate") or {}).get("candidate_search_evidence")
        or {}
    )
    evidence_updates = dict(
        candidate_search_evidence.get("selected_candidate_updates")
        or candidate_search_evidence.get("best_safe_candidate_updates")
        or candidate_search_evidence.get("closest_safe_candidate_updates")
        or {}
    )
    evidence_family = str(candidate_search_evidence.get("family") or family or "").strip().lower()
    evidence_expected_util = _repair_parse_util_value(
        candidate_search_evidence.get("best_safe_final_util")
        or candidate_search_evidence.get("selected_candidate_util")
        or candidate_search_evidence.get("closest_safe_candidate_util")
    )
    return DesignGuideButtonContractPayloadUpdateEvidence(
        candidate_search_evidence=candidate_search_evidence,
        evidence_updates=evidence_updates,
        evidence_family=evidence_family or None,
        evidence_expected_util=evidence_expected_util,
    )


def build_design_guide_button_contract_payload_update_resolution_inputs(
    *,
    item_index: int,
    item: dict | None,
    family_before: str | None,
    action_type_before: str | None,
    updates_before: dict | None,
    expected_util_before,
    blocking_reason_override: str | None,
    work_before: dict | None,
    update_resolution_applicable: bool,
    payload_resolution_attempted: bool,
    payload_resolution_exception_type: str | None,
    recommendation_updates: dict | None,
    evidence: DesignGuideButtonContractPayloadUpdateEvidence,
    evidence_updates_match_state: bool | None,
    normalised_evidence_candidate_id: str | None,
) -> DesignGuideButtonContractUpdateResolutionInputs:
    """Build update-resolution inputs from explicit page-resolved evidence values."""

    return build_design_guide_button_contract_update_resolution_inputs(
        item_index=item_index,
        item=item,
        family_before=family_before,
        action_type_before=action_type_before,
        updates_before=updates_before,
        expected_util_before=expected_util_before,
        blocking_reason_override=blocking_reason_override,
        work_before=work_before,
        update_resolution_applicable=update_resolution_applicable,
        payload_resolution_attempted=payload_resolution_attempted,
        payload_resolution_exception_type=payload_resolution_exception_type,
        recommendation_updates=recommendation_updates,
        candidate_search_evidence=evidence.candidate_search_evidence,
        evidence_updates=evidence.evidence_updates,
        evidence_updates_match_state=evidence_updates_match_state,
        normalised_evidence_candidate_id=normalised_evidence_candidate_id,
        evidence_expected_util=evidence.evidence_expected_util,
    )


def adapt_design_guide_button_contract_payload_updates(
    *,
    item_index: int,
    item: dict | None,
    work: dict | None,
    update_resolution_inputs: DesignGuideButtonContractUpdateResolutionInputs,
    current_family: str | None,
    current_effective_action_type: str | None,
    current_expected_util: Any = None,
    source_candidate_id_fallback: str | None = None,
) -> DesignGuideButtonContractPayloadUpdateAdapterResult:
    """Adapt an explicit update-resolution input into copied work for later probes."""

    work_before = dict(work or {})
    payload_before = dict(work_before.get("action_payload") or {})
    update_source_selection = select_design_guide_button_contract_update_source(
        update_resolution_inputs
    )
    updates = dict(update_source_selection.selected_updates or {})
    selected_source = str(update_source_selection.selected_update_source or "none").strip() or "none"
    update_decision_reason = update_source_selection.stable_decision_reason
    if updates:
        update_decision_reason = update_source_selection.selected_reason
    work_application = apply_design_guide_button_contract_work_updates(
        item_index=item_index,
        item=item,
        work=work_before,
        selection=update_source_selection,
        candidate_search_evidence=update_resolution_inputs.candidate_search_evidence,
        candidate_search_evidence_family=update_resolution_inputs.candidate_search_evidence_family,
        current_family=current_family,
        current_effective_action_type=current_effective_action_type,
        current_expected_util=current_expected_util,
        source_candidate_id_fallback=source_candidate_id_fallback,
        decision_reason=update_decision_reason,
    )
    out = dict(work_application.work)
    payload_after = dict(out.get("action_payload") or {})
    candidate_after = dict(out.get("resolved_candidate") or {})
    item_identity = _apply_button_binding_item_identity(item or {}, item_index)
    return DesignGuideButtonContractPayloadUpdateAdapterResult(
        work=out,
        family=work_application.family or current_family,
        effective_action_type=work_application.effective_action_type or current_effective_action_type,
        expected_util=work_application.expected_util,
        updates=updates,
        selected_update_source=selected_source,
        selected_update_keys=sorted(str(key) for key in updates.keys()),
        selected_evidence_candidate_id=update_source_selection.selected_evidence_candidate_id,
        selected_parsed_util=update_source_selection.selected_parsed_util,
        selected_payload_identity=_apply_button_binding_payload_identity(payload_after, item_identity),
        selected_payload_hash=publication_snapshot_hash(payload_after),
        resolved_candidate_identity=_apply_button_binding_payload_identity(candidate_after, item_identity),
        resolved_candidate_hash=publication_snapshot_hash(candidate_after),
        action_payload_identity_before=_apply_button_binding_payload_identity(payload_before, item_identity),
        action_payload_identity_after=_apply_button_binding_payload_identity(payload_after, item_identity),
        action_payload_hash_before=publication_snapshot_hash(payload_before),
        action_payload_hash_after=publication_snapshot_hash(payload_after),
        update_source_reason=update_decision_reason,
        adapter_changed_anything=publication_snapshot_hash(work_before) != publication_snapshot_hash(out),
        update_source_selection=update_source_selection,
        work_application=work_application,
    )


def evidence_with_safe_executor_rows_counted(
    evidence: dict | None,
    *,
    item_index: int,
    preview_statuses_have_explicit_fail: Callable[[dict], bool] | None = None,
    parse_util_value: Callable[[Any], float | None] = _repair_parse_util_value,
) -> tuple[dict[str, Any], DesignGuideSafeExecutorEvidenceRows]:
    """Return copied evidence with safe-executor rows counted plus proof metadata."""

    preview_fail_predicate = preview_statuses_have_explicit_fail or _repair_candidate_preview_statuses_have_explicit_fail
    input_evidence = evidence if isinstance(evidence, dict) else {}
    input_keys = set(input_evidence.keys())
    input_row_values = list(input_evidence.get("candidate_rows") or [])
    input_hash = publication_snapshot_hash(input_evidence)
    input_identity = str(
        input_evidence.get("evidence_id")
        or input_evidence.get("source")
        or input_evidence.get("selected_candidate_id")
        or input_evidence.get("closest_safe_candidate_id")
        or f"evidence_{item_index}"
    )
    out = dict(evidence or {})
    rows = [
        dict(row)
        for row in list(out.get("candidate_rows") or [])
        if isinstance(row, dict)
        and bool(row.get("safe_executor_backed"))
        and bool(row.get("is_executable"))
        and bool(row.get("preview_pass"))
        and dict(row.get("proposed_updates") or row.get("updates") or {})
        and not preview_fail_predicate(dict(row.get("preview_statuses") or {}))
    ]
    counted_candidate_ids = [
        str(row.get("candidate_id") or row.get("source_candidate_id") or index)
        for index, row in enumerate(rows)
    ]

    def _record(output_evidence: dict) -> DesignGuideSafeExecutorEvidenceRows:
        output_keys = set(output_evidence.keys())
        return DesignGuideSafeExecutorEvidenceRows(
            item_index=item_index,
            input_evidence_identity=input_identity,
            input_evidence_hash=input_hash,
            input_row_count=len(input_row_values),
            counted_safe_executor_rows=len(rows),
            output_evidence_identity=str(
                output_evidence.get("evidence_id")
                or output_evidence.get("source")
                or output_evidence.get("selected_candidate_id")
                or output_evidence.get("closest_safe_candidate_id")
                or input_identity
            ),
            output_evidence_hash=publication_snapshot_hash(output_evidence),
            output_row_count=len(list(output_evidence.get("candidate_rows") or [])),
            evidence_object_copied=isinstance(evidence, dict) and id(output_evidence) != id(evidence),
            evidence_object_reused=isinstance(evidence, dict) and id(output_evidence) == id(evidence),
            fields_added=sorted(str(key) for key in output_keys - input_keys),
            fields_removed=sorted(str(key) for key in input_keys - output_keys),
            fields_rewritten=sorted(
                str(key)
                for key in input_keys & output_keys
                if publication_snapshot_hash(input_evidence.get(key))
                != publication_snapshot_hash(output_evidence.get(key))
            ),
            counted_candidate_ids=counted_candidate_ids,
        )

    if not rows:
        return out, _record(out)
    if int(out.get("safe_executor_backed_candidates_count") or 0) < len(rows):
        out["safe_executor_backed_candidates_count"] = len(rows)
        out["safe_candidate_count"] = max(
            len(rows),
            int(out.get("safe_candidate_count") or 0),
        )
        out["executable_candidate_count"] = max(
            len(rows),
            int(out.get("executable_candidate_count") or 0),
        )
        out["safe_executor_backed_candidates"] = list(rows[:80])
    closest_id = str(out.get("closest_safe_candidate_id") or "").strip()
    closest_row = next(
        (row for row in rows if str(row.get("candidate_id") or "").strip() == closest_id),
        None,
    )
    if closest_row is None:
        closest_row = rows[0]
        out["closest_safe_candidate_id"] = closest_row.get("candidate_id")
    closest_updates = dict(closest_row.get("proposed_updates") or closest_row.get("updates") or {})
    if closest_updates:
        out["closest_safe_candidate_updates"] = dict(closest_updates)
    if closest_row.get("title") not in (None, ""):
        out.setdefault("closest_safe_candidate_title", closest_row.get("title"))
    closest_util = parse_util_value(
        closest_row.get("preview_util")
        or closest_row.get("candidate_post_util")
        or closest_row.get("worst_util")
    )
    if closest_util is not None:
        out["closest_safe_candidate_util"] = float(closest_util)
    if closest_row.get("distance_to_band") not in (None, ""):
        out["closest_safe_candidate_distance_to_band"] = closest_row.get("distance_to_band")
    out["active_fail_safe_executor_count_recomputed_from_candidate_rows"] = True
    return out, _record(out)


def build_design_guide_apply_button_contract_inputs(
    *,
    item_index: int,
    item: dict | None,
    state: dict | None,
    blocking_reason_override: str | None = None,
) -> DesignGuideApplyButtonContractInputs:
    item_d = dict(item or {}) if isinstance(item, dict) else {}
    action_payload = dict(item_d.get("action_payload") or {})
    candidate_payload = dict(
        item_d.get("resolved_candidate")
        or item_d.get("candidate")
        or item_d.get("candidate_payload")
        or {}
    )
    identity = _apply_button_binding_item_identity(item_d, item_index)
    family = (
        item_d.get("selected_action_family")
        or item_d.get("family")
        or item_d.get("check_key")
        or action_payload.get("family")
        or candidate_payload.get("family")
    )
    return DesignGuideApplyButtonContractInputs(
        item_index=int(item_index),
        item_identity=identity,
        item_hash=publication_snapshot_hash(item_d),
        state_hash=publication_snapshot_hash(state or {}),
        family=str(family).strip().lower() if family not in (None, "") else None,
        action_type=str(item_d.get("action_type") or action_payload.get("action_type") or "").strip() or None,
        guidance_intent=str(item_d.get("guidance_intent") or "").strip() or None,
        cta_label=item_d.get("primary_action") or item_d.get("cta_label") or action_payload.get("label"),
        apply_payload_identity=_apply_button_binding_payload_identity(action_payload, identity),
        apply_payload_hash=publication_snapshot_hash(action_payload or item_d.get("updates") or {}),
        candidate_payload_identity=_apply_button_binding_payload_identity(candidate_payload, identity),
        candidate_payload_hash=publication_snapshot_hash(candidate_payload),
        blocking_reason_override=str(blocking_reason_override or "").strip() or None,
    )


def build_design_guide_apply_button_contract_result(
    *,
    item_index: int,
    item: dict | None,
    button_contract: dict | None,
) -> DesignGuideApplyButtonContractResult:
    item_d = dict(item or {}) if isinstance(item, dict) else {}
    contract = dict(button_contract or {})
    action_payload = dict(item_d.get("action_payload") or {})
    candidate_payload = dict(
        item_d.get("resolved_candidate")
        or item_d.get("candidate")
        or item_d.get("candidate_payload")
        or {}
    )
    identity = _apply_button_binding_item_identity(item_d, item_index)
    disabled_reason = (
        contract.get("disabled_reason")
        or contract.get("blocking_reason")
        or item_d.get("blocking_reason")
        or item_d.get("cta_reason")
    )
    family = contract.get("family") or item_d.get("selected_action_family") or item_d.get("family") or item_d.get("check_key")
    contract_scalars = {
        "keys": sorted(str(key) for key in contract.keys()),
        "updates_hash": publication_snapshot_hash(contract.get("updates") or {}),
        "source_candidate_id": contract.get("source_candidate_id"),
        "candidate_id": contract.get("candidate_id"),
    }
    return DesignGuideApplyButtonContractResult(
        item_index=int(item_index),
        item_identity=identity,
        family=str(family).strip().lower() if family not in (None, "") else None,
        action_type=str(contract.get("action_type") or item_d.get("action_type") or "").strip() or None,
        cta_label=item_d.get("primary_action") or item_d.get("cta_label") or contract.get("label"),
        cta_enabled=bool(design_guide_button_contract_enabled(contract)),
        actionable=bool(contract.get("actionable")),
        preview_pass=bool(contract.get("preview_pass")),
        disabled_reason=disabled_reason,
        blocking_reason=contract.get("blocking_reason"),
        expected_util=contract.get("expected_util"),
        apply_payload_identity=_apply_button_binding_payload_identity(action_payload, _apply_button_binding_payload_identity(contract, identity)),
        apply_payload_hash=publication_snapshot_hash(action_payload or contract.get("updates") or {}),
        candidate_payload_identity=_apply_button_binding_payload_identity(candidate_payload, identity),
        candidate_payload_hash=publication_snapshot_hash(candidate_payload),
        contract_hash=publication_snapshot_hash(contract),
        contract_updates_hash=publication_snapshot_hash(contract.get("updates") or {}),
        final_button_contract=contract,
        contract_scalars=contract_scalars,
    )


def build_design_guide_button_contract_final_contract(
    *,
    actionable: bool,
    action_type: str | None,
    family: str | None,
    updates: dict | None,
    preview_pass: bool,
    expected_util: Any = None,
    blocking_reason: str | None = None,
    source_candidate_id: str | None = None,
) -> dict[str, Any]:
    """Assemble the final button-contract mapping from already-resolved scalars."""

    return {
        "actionable": bool(actionable),
        "action_type": action_type or None,
        "family": family,
        "updates": dict(updates or {}),
        "preview_pass": bool(preview_pass),
        "expected_util": expected_util,
        "blocking_reason": blocking_reason,
        "source_candidate_id": source_candidate_id,
        "candidate_id": source_candidate_id,
    }


def build_design_guide_button_contract_result(
    *,
    actionable: bool,
    action_type: str | None,
    family: str | None,
    updates: dict | None,
    preview_pass: bool,
    expected_util: Any = None,
    blocking_reason: str | None = None,
    source_candidate_id: str | None = None,
) -> DesignGuideButtonContractFinalResult:
    """Build final button-contract result from already-resolved scalars."""

    contract = build_design_guide_button_contract_final_contract(
        actionable=actionable,
        action_type=action_type,
        family=family,
        updates=updates,
        preview_pass=preview_pass,
        expected_util=expected_util,
        blocking_reason=blocking_reason,
        source_candidate_id=source_candidate_id,
    )
    return DesignGuideButtonContractFinalResult(
        final_contract=contract,
        actionable=bool(actionable),
        source_candidate_id=source_candidate_id,
        family=family,
        action_type=action_type,
        updates_hash=publication_snapshot_hash(dict(updates or {})),
        contract_hash=publication_snapshot_hash(contract),
    )


def build_design_guide_button_contract_actionability_helper_outputs(
    *,
    item_index: int,
    item: dict | None,
    executor_contract_evaluated: bool = False,
    executor_allowed: bool | None = None,
    executor_reason: str | None = None,
    executor_exception_type: str | None = None,
    preview_evaluated: bool = False,
    preview_pass: bool | None = None,
    preview_util: Any = None,
    preview_reason: str | None = None,
    safe_incremental_below_threshold: bool | None = None,
    family_exact_cleanup_blocker: bool | None = None,
    local_cleanup_post_apply_acceptance_matches: bool | None = None,
    best_safe_partial_cleanup: bool | None = None,
    low_util_exact_blocker: bool | None = None,
    accepted_band_cleanup_evaluated: bool = False,
    accepted_band_cleanup: bool | None = None,
    accepted_band_family_preview_util: Any = None,
    accepted_band_override_applied: bool = False,
    partial_cleanup_override_applied: bool = False,
    exact_blocker_override_applied: bool = False,
    family_truth_probe_evaluated: bool = False,
    family_truth_probe_exception_type: str | None = None,
    family_truth_probe_expected_util: Any = None,
    combined_truth_probe_evaluated: bool = False,
    combined_truth_probe_exception_type: str | None = None,
    combined_truth_probe_expected_util: Any = None,
    final_executor_allowed: bool | None = None,
    final_blocking_reason: str | None = None,
    final_preview_pass: bool | None = None,
    final_expected_util: Any = None,
) -> DesignGuideButtonContractActionabilityHelperOutputs:
    """Bundle already-resolved page-local helper outputs without deciding actionability."""

    item_d = dict(item or {}) if isinstance(item, dict) else {}
    identity = _apply_button_binding_item_identity(item_d, item_index)
    payload = {
        "executor_contract_evaluated": bool(executor_contract_evaluated),
        "executor_allowed": executor_allowed if executor_allowed is None else bool(executor_allowed),
        "executor_reason": str(executor_reason or "").strip() or None,
        "executor_exception_type": str(executor_exception_type or "").strip() or None,
        "preview_evaluated": bool(preview_evaluated),
        "preview_pass": preview_pass if preview_pass is None else bool(preview_pass),
        "preview_util": preview_util,
        "preview_reason": str(preview_reason or "").strip() or None,
        "safe_incremental_below_threshold": (
            safe_incremental_below_threshold
            if safe_incremental_below_threshold is None
            else bool(safe_incremental_below_threshold)
        ),
        "family_exact_cleanup_blocker": (
            family_exact_cleanup_blocker
            if family_exact_cleanup_blocker is None
            else bool(family_exact_cleanup_blocker)
        ),
        "local_cleanup_post_apply_acceptance_matches": (
            local_cleanup_post_apply_acceptance_matches
            if local_cleanup_post_apply_acceptance_matches is None
            else bool(local_cleanup_post_apply_acceptance_matches)
        ),
        "best_safe_partial_cleanup": best_safe_partial_cleanup if best_safe_partial_cleanup is None else bool(best_safe_partial_cleanup),
        "low_util_exact_blocker": low_util_exact_blocker if low_util_exact_blocker is None else bool(low_util_exact_blocker),
        "accepted_band_cleanup_evaluated": bool(accepted_band_cleanup_evaluated),
        "accepted_band_cleanup": accepted_band_cleanup if accepted_band_cleanup is None else bool(accepted_band_cleanup),
        "accepted_band_family_preview_util": accepted_band_family_preview_util,
        "accepted_band_override_applied": bool(accepted_band_override_applied),
        "partial_cleanup_override_applied": bool(partial_cleanup_override_applied),
        "exact_blocker_override_applied": bool(exact_blocker_override_applied),
        "family_truth_probe_evaluated": bool(family_truth_probe_evaluated),
        "family_truth_probe_exception_type": str(family_truth_probe_exception_type or "").strip() or None,
        "family_truth_probe_expected_util": family_truth_probe_expected_util,
        "combined_truth_probe_evaluated": bool(combined_truth_probe_evaluated),
        "combined_truth_probe_exception_type": str(combined_truth_probe_exception_type or "").strip() or None,
        "combined_truth_probe_expected_util": combined_truth_probe_expected_util,
        "final_executor_allowed": final_executor_allowed if final_executor_allowed is None else bool(final_executor_allowed),
        "final_blocking_reason": str(final_blocking_reason or "").strip() or None,
        "final_preview_pass": final_preview_pass if final_preview_pass is None else bool(final_preview_pass),
        "final_expected_util": final_expected_util,
    }
    return DesignGuideButtonContractActionabilityHelperOutputs(
        item_index=int(item_index),
        item_identity=identity,
        helper_output_hash=publication_snapshot_hash(payload),
        **payload,
    )


def build_design_guide_button_contract_actionability_probe_outputs(
    *,
    item_index: int,
    item: dict | None,
    executor_contract_evaluated: bool = False,
    executor_allowed: bool | None = None,
    executor_reason: str | None = None,
    executor_exception_type: str | None = None,
    preview_evaluated: bool = False,
    preview_pass: bool | None = None,
    preview_util: Any = None,
    preview_reason: str | None = None,
    safe_incremental_below_threshold: bool | None = None,
    family_exact_cleanup_blocker: bool | None = None,
    local_cleanup_post_apply_acceptance_matches: bool | None = None,
    best_safe_partial_cleanup: bool | None = None,
    low_util_exact_blocker: bool | None = None,
    accepted_band_cleanup_evaluated: bool = False,
    accepted_band_cleanup: bool | None = None,
    accepted_band_family_preview_util: Any = None,
    accepted_band_override_applied: bool = False,
    partial_cleanup_override_applied: bool = False,
    exact_blocker_override_applied: bool = False,
    family_truth_probe_evaluated: bool = False,
    family_truth_probe_exception_type: str | None = None,
    family_truth_probe_expected_util: Any = None,
    combined_truth_probe_evaluated: bool = False,
    combined_truth_probe_exception_type: str | None = None,
    combined_truth_probe_expected_util: Any = None,
    final_family: str | None = None,
    final_expected_util: Any = None,
    final_blocking_reason: str | None = None,
    final_executor_allowed: bool | None = None,
    final_preview_pass: bool | None = None,
) -> DesignGuideButtonContractActionabilityProbeOutputs:
    """Record already-resolved page-local actionability probes."""

    item_d = dict(item or {}) if isinstance(item, dict) else {}
    identity = _apply_button_binding_item_identity(item_d, item_index)
    executor_payload = {
        "evaluated": bool(executor_contract_evaluated),
        "allowed": executor_allowed if executor_allowed is None else bool(executor_allowed),
        "reason": str(executor_reason or "").strip() or None,
        "exception_type": str(executor_exception_type or "").strip() or None,
    }
    preview_payload = {
        "evaluated": bool(preview_evaluated),
        "pass": preview_pass if preview_pass is None else bool(preview_pass),
        "util": preview_util,
        "reason": str(preview_reason or "").strip() or None,
    }
    accepted_payload = {
        "evaluated": bool(accepted_band_cleanup_evaluated),
        "cleanup": accepted_band_cleanup if accepted_band_cleanup is None else bool(accepted_band_cleanup),
        "family_preview_util": accepted_band_family_preview_util,
        "override_applied": bool(accepted_band_override_applied),
    }
    family_truth_payload = {
        "evaluated": bool(family_truth_probe_evaluated),
        "exception_type": str(family_truth_probe_exception_type or "").strip() or None,
        "expected_util": family_truth_probe_expected_util,
    }
    combined_truth_payload = {
        "evaluated": bool(combined_truth_probe_evaluated),
        "exception_type": str(combined_truth_probe_exception_type or "").strip() or None,
        "expected_util": combined_truth_probe_expected_util,
    }
    final_payload = {
        "family": str(final_family or "").strip().lower() or None,
        "expected_util": final_expected_util,
        "blocking_reason": str(final_blocking_reason or "").strip() or None,
        "executor_allowed": final_executor_allowed if final_executor_allowed is None else bool(final_executor_allowed),
        "preview_pass": final_preview_pass if final_preview_pass is None else bool(final_preview_pass),
        "partial_cleanup_override_applied": bool(partial_cleanup_override_applied),
        "exact_blocker_override_applied": bool(exact_blocker_override_applied),
    }
    payload = {
        "executor": executor_payload,
        "preview": preview_payload,
        "accepted_band": accepted_payload,
        "family_truth": family_truth_payload,
        "combined_truth": combined_truth_payload,
        "final": final_payload,
        "safe_incremental_below_threshold": (
            safe_incremental_below_threshold
            if safe_incremental_below_threshold is None
            else bool(safe_incremental_below_threshold)
        ),
        "family_exact_cleanup_blocker": (
            family_exact_cleanup_blocker
            if family_exact_cleanup_blocker is None
            else bool(family_exact_cleanup_blocker)
        ),
        "local_cleanup_post_apply_acceptance_matches": (
            local_cleanup_post_apply_acceptance_matches
            if local_cleanup_post_apply_acceptance_matches is None
            else bool(local_cleanup_post_apply_acceptance_matches)
        ),
        "best_safe_partial_cleanup": best_safe_partial_cleanup if best_safe_partial_cleanup is None else bool(best_safe_partial_cleanup),
        "low_util_exact_blocker": low_util_exact_blocker if low_util_exact_blocker is None else bool(low_util_exact_blocker),
    }
    return DesignGuideButtonContractActionabilityProbeOutputs(
        item_index=int(item_index),
        item_identity=identity,
        executor_contract_evaluated=executor_payload["evaluated"],
        executor_allowed=executor_payload["allowed"],
        executor_reason=executor_payload["reason"],
        executor_exception_type=executor_payload["exception_type"],
        executor_probe_hash=publication_snapshot_hash(executor_payload),
        preview_evaluated=preview_payload["evaluated"],
        preview_pass=preview_payload["pass"],
        preview_util=preview_payload["util"],
        preview_reason=preview_payload["reason"],
        preview_probe_hash=publication_snapshot_hash(preview_payload),
        safe_incremental_below_threshold=payload["safe_incremental_below_threshold"],
        family_exact_cleanup_blocker=payload["family_exact_cleanup_blocker"],
        local_cleanup_post_apply_acceptance_matches=payload["local_cleanup_post_apply_acceptance_matches"],
        best_safe_partial_cleanup=payload["best_safe_partial_cleanup"],
        low_util_exact_blocker=payload["low_util_exact_blocker"],
        accepted_band_cleanup_evaluated=accepted_payload["evaluated"],
        accepted_band_cleanup=accepted_payload["cleanup"],
        accepted_band_family_preview_util=accepted_payload["family_preview_util"],
        accepted_band_probe_hash=publication_snapshot_hash(accepted_payload),
        accepted_band_override_applied=accepted_payload["override_applied"],
        partial_cleanup_override_applied=bool(partial_cleanup_override_applied),
        exact_blocker_override_applied=bool(exact_blocker_override_applied),
        family_truth_probe_evaluated=family_truth_payload["evaluated"],
        family_truth_probe_exception_type=family_truth_payload["exception_type"],
        family_truth_probe_expected_util=family_truth_payload["expected_util"],
        family_truth_probe_hash=publication_snapshot_hash(family_truth_payload),
        combined_truth_probe_evaluated=combined_truth_payload["evaluated"],
        combined_truth_probe_exception_type=combined_truth_payload["exception_type"],
        combined_truth_probe_expected_util=combined_truth_payload["expected_util"],
        combined_truth_probe_hash=publication_snapshot_hash(combined_truth_payload),
        final_family=final_payload["family"],
        final_expected_util=final_payload["expected_util"],
        final_blocking_reason=final_payload["blocking_reason"],
        final_executor_allowed=final_payload["executor_allowed"],
        final_preview_pass=final_payload["preview_pass"],
        final_probe_hash=publication_snapshot_hash(final_payload),
        probe_output_hash=publication_snapshot_hash(payload),
    )


def resolve_design_guide_button_contract_actionability_scalars(
    *,
    item_index: int,
    item: dict | None,
    updates: dict | None,
    action_type: str | None,
    update_decision_reason: str | None,
    updates_source: str | None,
    probe_inputs: DesignGuideButtonContractActionabilityProbeInputs | None,
    raw_probe_outputs: DesignGuideButtonContractActionabilityProbeOutputs,
    blocking_reason_before: str | None = None,
    executor_allowed_before: bool | None = None,
    preview_pass_before: bool | None = None,
    expected_util_before: Any = None,
    family_before: str | None = None,
    actionable_before: bool | None = None,
    enabled_before: bool | None = None,
) -> DesignGuideButtonContractActionabilityScalarResolutionResult:
    """Apply pure scalar-resolution rules to already-collected page probe outputs."""

    updates_d = dict(updates or {})
    family = str(family_before or "").strip().lower() or None
    expected_util = expected_util_before
    blocking_reason = str(blocking_reason_before or "").strip() or None
    executor_allowed = bool(raw_probe_outputs.executor_allowed)
    executor_reason = raw_probe_outputs.executor_reason
    preview_pass = bool(raw_probe_outputs.preview_pass)
    preview_util = raw_probe_outputs.preview_util
    preview_reason = raw_probe_outputs.preview_reason
    safe_incremental_below_threshold = raw_probe_outputs.safe_incremental_below_threshold
    family_exact_cleanup_blocker = raw_probe_outputs.family_exact_cleanup_blocker
    local_cleanup_post_apply_acceptance_matches = raw_probe_outputs.local_cleanup_post_apply_acceptance_matches
    best_safe_partial_cleanup = raw_probe_outputs.best_safe_partial_cleanup
    low_util_exact_blocker = raw_probe_outputs.low_util_exact_blocker
    accepted_band_cleanup = raw_probe_outputs.accepted_band_cleanup
    accepted_band_family_preview_util = raw_probe_outputs.accepted_band_family_preview_util
    accepted_band_override_applied = False
    partial_cleanup_override_applied = False
    exact_blocker_override_applied = False
    final_min = (
        probe_inputs.final_accepted_min_family_util
        if isinstance(probe_inputs, DesignGuideButtonContractActionabilityProbeInputs)
        else None
    )
    eps = (
        probe_inputs.target_band_eps
        if isinstance(probe_inputs, DesignGuideButtonContractActionabilityProbeInputs)
        else None
    )

    if not updates_d:
        blocking_reason = blocking_reason or "missing_updates"
    if not executor_allowed:
        blocking_reason = blocking_reason or executor_reason or "executor_contract_blocked"
    if updates_d:
        if expected_util is None:
            expected_util = preview_util
        if not preview_pass:
            below_final_min = False
            if preview_util is not None and final_min is not None and eps is not None:
                try:
                    below_final_min = float(preview_util) < float(final_min) - float(eps)
                except (TypeError, ValueError):
                    below_final_min = False
            if (
                safe_incremental_below_threshold
                and local_cleanup_post_apply_acceptance_matches
                and below_final_min
            ):
                blocking_reason = "post_click_safe_incremental_cleanup_requires_exact_blocker"
            if (
                raw_probe_outputs.partial_cleanup_override_applied
                and str(preview_reason or "").strip()
                in {
                    "candidate_preview_not_in_target_band",
                    "candidate_preview_not_in_target_band_after_active_failure",
                }
            ):
                preview_pass = True
                blocking_reason = None
                executor_allowed = True
                partial_cleanup_override_applied = True
            elif str(preview_reason or "").strip() in {
                "candidate_preview_not_in_target_band",
                "candidate_preview_not_in_target_band_after_active_failure",
            }:
                if accepted_band_cleanup and (executor_allowed or not executor_reason):
                    preview_pass = True
                    expected_util = (
                        accepted_band_family_preview_util
                        if accepted_band_family_preview_util is not None
                        else expected_util
                    )
                    blocking_reason = None
                    executor_allowed = True
                    accepted_band_override_applied = True
                else:
                    blocking_reason = blocking_reason or preview_reason or "preview_failed"
            else:
                blocking_reason = blocking_reason or preview_reason or "preview_failed"
        elif raw_probe_outputs.partial_cleanup_override_applied:
            executor_allowed = True
            blocking_reason = None
            best_safe_partial_cleanup = True
            partial_cleanup_override_applied = True
        elif raw_probe_outputs.exact_blocker_override_applied:
            executor_allowed = True
            blocking_reason = None
            low_util_exact_blocker = True
            exact_blocker_override_applied = True
        elif (
            raw_probe_outputs.family_truth_probe_evaluated
            and raw_probe_outputs.family_truth_probe_expected_util is not None
        ):
            expected_util = float(raw_probe_outputs.family_truth_probe_expected_util)

    if raw_probe_outputs.combined_truth_probe_evaluated:
        family = "combined"
        if raw_probe_outputs.combined_truth_probe_expected_util is not None:
            expected_util = float(raw_probe_outputs.combined_truth_probe_expected_util)

    actionable = bool(action_type and updates_d and executor_allowed and not blocking_reason)
    enabled = bool(actionable and updates_d and preview_pass and blocking_reason is None)
    resolved_probe_outputs = build_design_guide_button_contract_actionability_probe_outputs(
        item_index=item_index,
        item=item,
        executor_contract_evaluated=raw_probe_outputs.executor_contract_evaluated,
        executor_allowed=executor_allowed,
        executor_reason=raw_probe_outputs.executor_reason,
        executor_exception_type=raw_probe_outputs.executor_exception_type,
        preview_evaluated=raw_probe_outputs.preview_evaluated,
        preview_pass=preview_pass,
        preview_util=raw_probe_outputs.preview_util,
        preview_reason=raw_probe_outputs.preview_reason,
        safe_incremental_below_threshold=safe_incremental_below_threshold,
        family_exact_cleanup_blocker=family_exact_cleanup_blocker,
        local_cleanup_post_apply_acceptance_matches=local_cleanup_post_apply_acceptance_matches,
        best_safe_partial_cleanup=best_safe_partial_cleanup,
        low_util_exact_blocker=low_util_exact_blocker,
        accepted_band_cleanup_evaluated=raw_probe_outputs.accepted_band_cleanup_evaluated,
        accepted_band_cleanup=accepted_band_cleanup,
        accepted_band_family_preview_util=accepted_band_family_preview_util,
        accepted_band_override_applied=accepted_band_override_applied,
        partial_cleanup_override_applied=partial_cleanup_override_applied,
        exact_blocker_override_applied=exact_blocker_override_applied,
        family_truth_probe_evaluated=raw_probe_outputs.family_truth_probe_evaluated,
        family_truth_probe_exception_type=raw_probe_outputs.family_truth_probe_exception_type,
        family_truth_probe_expected_util=raw_probe_outputs.family_truth_probe_expected_util,
        combined_truth_probe_evaluated=raw_probe_outputs.combined_truth_probe_evaluated,
        combined_truth_probe_exception_type=raw_probe_outputs.combined_truth_probe_exception_type,
        combined_truth_probe_expected_util=raw_probe_outputs.combined_truth_probe_expected_util,
        final_family=family,
        final_expected_util=expected_util,
        final_blocking_reason=blocking_reason,
        final_executor_allowed=executor_allowed,
        final_preview_pass=preview_pass,
    )
    resolution = build_design_guide_button_contract_actionability_resolution(
        item_index=item_index,
        item=item,
        blocking_reason_before=blocking_reason_before,
        blocking_reason_after=blocking_reason,
        executor_allowed_before=executor_allowed_before,
        executor_allowed_after=executor_allowed,
        preview_pass_before=preview_pass_before,
        preview_pass_after=preview_pass,
        expected_util_before=expected_util_before,
        expected_util_after=expected_util,
        family_before=family_before,
        family_after=family,
        actionable_before=actionable_before,
        actionable_after=actionable,
        enabled_before=enabled_before,
        enabled_after=enabled,
        reason_before=blocking_reason_before,
        reason_after=blocking_reason,
        selected_actionability_source=_design_guide_button_contract_actionability_resolution_source(
            accepted_band_override_applied=accepted_band_override_applied,
            partial_cleanup_override_applied=partial_cleanup_override_applied,
            exact_blocker_override_applied=exact_blocker_override_applied,
            combined_truth_probe_evaluated=raw_probe_outputs.combined_truth_probe_evaluated,
            family_truth_probe_evaluated=raw_probe_outputs.family_truth_probe_evaluated,
            blocking_reason=blocking_reason,
            actionable=actionable,
        ),
        decision_reason=update_decision_reason,
        decision_source=updates_source,
    )
    return DesignGuideButtonContractActionabilityScalarResolutionResult(
        blocking_reason=blocking_reason,
        executor_allowed=executor_allowed,
        preview_pass=preview_pass,
        expected_util=expected_util,
        family=family,
        actionable=actionable,
        enabled=enabled,
        probe_outputs=resolved_probe_outputs,
        resolution=resolution,
    )


def build_design_guide_button_contract_actionability_resolution(
    *,
    item_index: int,
    item: dict | None,
    blocking_reason_before: str | None = None,
    blocking_reason_after: str | None = None,
    executor_allowed_before: bool | None = None,
    executor_allowed_after: bool | None = None,
    preview_pass_before: bool | None = None,
    preview_pass_after: bool | None = None,
    expected_util_before: Any = None,
    expected_util_after: Any = None,
    family_before: str | None = None,
    family_after: str | None = None,
    actionable_before: bool | None = None,
    actionable_after: bool | None = None,
    enabled_before: bool | None = None,
    enabled_after: bool | None = None,
    reason_before: str | None = None,
    reason_after: str | None = None,
    selected_actionability_source: str | None = None,
    decision_reason: str | None = None,
    decision_source: str | None = None,
    final_contract: dict | None = None,
) -> DesignGuideButtonContractActionabilityResolution:
    """Record before/after actionability scalar resolution without deciding it."""

    item_d = dict(item or {}) if isinstance(item, dict) else {}
    contract = dict(final_contract or {})
    identity = _apply_button_binding_item_identity(item_d, item_index)
    before = {
        "blocking_reason": str(blocking_reason_before or "").strip() or None,
        "executor_allowed": executor_allowed_before if executor_allowed_before is None else bool(executor_allowed_before),
        "preview_pass": preview_pass_before if preview_pass_before is None else bool(preview_pass_before),
        "expected_util": expected_util_before,
        "family": str(family_before or "").strip().lower() or None,
        "actionable": actionable_before if actionable_before is None else bool(actionable_before),
        "enabled": enabled_before if enabled_before is None else bool(enabled_before),
        "reason": str(reason_before or "").strip() or None,
    }
    after = {
        "blocking_reason": str(blocking_reason_after or "").strip() or None,
        "executor_allowed": executor_allowed_after if executor_allowed_after is None else bool(executor_allowed_after),
        "preview_pass": preview_pass_after if preview_pass_after is None else bool(preview_pass_after),
        "expected_util": expected_util_after,
        "family": str(family_after or "").strip().lower() or None,
        "actionable": actionable_after if actionable_after is None else bool(actionable_after),
        "enabled": enabled_after if enabled_after is None else bool(enabled_after),
        "reason": str(reason_after or "").strip() or None,
    }
    changed_fields = sorted(key for key in before if before.get(key) != after.get(key))
    payload = {
        "before": before,
        "after": after,
        "selected_actionability_source": str(selected_actionability_source or "").strip() or None,
        "decision_reason": str(decision_reason or "").strip() or None,
        "decision_source": str(decision_source or "").strip() or None,
        "changed_fields": changed_fields,
        "final_contract_hash": publication_snapshot_hash(contract),
        "final_contract_updates_hash": publication_snapshot_hash(contract.get("updates") or {}),
    }
    return DesignGuideButtonContractActionabilityResolution(
        item_index=int(item_index),
        item_identity=identity,
        blocking_reason_before=before["blocking_reason"],
        blocking_reason_after=after["blocking_reason"],
        executor_allowed_before=before["executor_allowed"],
        executor_allowed_after=after["executor_allowed"],
        preview_pass_before=before["preview_pass"],
        preview_pass_after=after["preview_pass"],
        expected_util_before=before["expected_util"],
        expected_util_after=after["expected_util"],
        family_before=before["family"],
        family_after=after["family"],
        actionable_before=before["actionable"],
        actionable_after=after["actionable"],
        enabled_before=before["enabled"],
        enabled_after=after["enabled"],
        reason_before=before["reason"],
        reason_after=after["reason"],
        selected_actionability_source=payload["selected_actionability_source"],
        decision_reason=payload["decision_reason"],
        decision_source=payload["decision_source"],
        scalar_changed=bool(changed_fields),
        changed_fields=changed_fields,
        final_contract_hash=payload["final_contract_hash"],
        final_contract_updates_hash=payload["final_contract_updates_hash"],
        resolution_hash=publication_snapshot_hash(payload),
    )


def build_design_guide_button_contract_actionability_inputs(
    *,
    item_index: int,
    item: dict | None,
    work: dict | None,
    requested_updates: dict | None,
    selected_update_source: str | None,
    selected_updates: dict | None,
    selected_evidence_candidate_id: str | None = None,
    selected_parsed_util: Any = None,
    requested_action_type: str | None = None,
    effective_action_type: str | None = None,
    executor_allowed: bool | None = None,
    executor_reason: str | None = None,
    preview_pass: bool | None = None,
    preview_reason: str | None = None,
    helper_outputs: DesignGuideButtonContractActionabilityHelperOutputs | None = None,
    expected_util: Any = None,
    blocking_reason: str | None = None,
    family: str | None = None,
    source_candidate_id: str | None = None,
    update_decision_reason: str | None = None,
    update_exception_type: str | None = None,
    decision_source: str | None = None,
) -> DesignGuideButtonContractActionabilityInputs:
    """Record already-resolved final actionability inputs without deciding them."""

    item_d = dict(item or {}) if isinstance(item, dict) else {}
    work_d = dict(work or {}) if isinstance(work, dict) else {}
    requested_updates_d = dict(requested_updates or {})
    selected_updates_d = dict(selected_updates or {})
    action_payload = dict(work_d.get("action_payload") or item_d.get("action_payload") or {})
    candidate_payload = dict(
        work_d.get("resolved_candidate")
        or item_d.get("resolved_candidate")
        or item_d.get("candidate")
        or item_d.get("candidate_payload")
        or {}
    )
    identity = _apply_button_binding_item_identity(item_d, item_index)
    return DesignGuideButtonContractActionabilityInputs(
        item_index=int(item_index),
        item_identity=identity,
        requested_action_type=str(requested_action_type or item_d.get("action_type") or "").strip() or None,
        effective_action_type=str(effective_action_type or "").strip() or None,
        requested_updates_hash=publication_snapshot_hash(requested_updates_d),
        requested_updates_keys=sorted(str(key) for key in requested_updates_d.keys()),
        selected_update_source=str(selected_update_source or "").strip() or None,
        selected_updates_hash=publication_snapshot_hash(selected_updates_d),
        selected_updates_keys=sorted(str(key) for key in selected_updates_d.keys()),
        selected_evidence_candidate_id=str(selected_evidence_candidate_id or "").strip() or None,
        selected_parsed_util=selected_parsed_util,
        resolved_work_hash=publication_snapshot_hash(work_d),
        resolved_work_action_payload_identity=_apply_button_binding_payload_identity(action_payload, identity),
        resolved_work_action_payload_hash=publication_snapshot_hash(action_payload),
        resolved_work_candidate_payload_identity=_apply_button_binding_payload_identity(candidate_payload, identity),
        resolved_work_candidate_payload_hash=publication_snapshot_hash(candidate_payload),
        executor_allowed=executor_allowed if executor_allowed is None else bool(executor_allowed),
        executor_reason=str(executor_reason or "").strip() or None,
        preview_pass=preview_pass if preview_pass is None else bool(preview_pass),
        preview_reason=str(preview_reason or "").strip() or None,
        helper_outputs=helper_outputs,
        expected_util=expected_util,
        blocking_reason_before_final_decision=str(blocking_reason or "").strip() or None,
        family=str(family or "").strip().lower() or None,
        source_candidate_id=str(source_candidate_id or "").strip() or None,
        update_decision_reason=str(update_decision_reason or "").strip() or None,
        update_exception_type=str(update_exception_type or "").strip() or None,
        decision_source=str(decision_source or "").strip() or None,
    )


def build_design_guide_button_contract_actionability_decision(
    *,
    inputs: DesignGuideButtonContractActionabilityInputs | None,
    item_index: int,
    item: dict | None,
    final_contract: dict | None,
    decision_reason: str | None = None,
    decision_source: str | None = None,
) -> DesignGuideButtonContractActionabilityDecision:
    """Record final actionability output from the already-built contract."""

    item_d = dict(item or {}) if isinstance(item, dict) else {}
    contract = dict(final_contract or {})
    action_payload = dict(item_d.get("action_payload") or {})
    candidate_payload = dict(
        item_d.get("resolved_candidate")
        or item_d.get("candidate")
        or item_d.get("candidate_payload")
        or {}
    )
    identity = (
        inputs.item_identity
        if isinstance(inputs, DesignGuideButtonContractActionabilityInputs) and inputs.item_identity
        else _apply_button_binding_item_identity(item_d, item_index)
    )
    input_payload = inputs.to_dict() if isinstance(inputs, DesignGuideButtonContractActionabilityInputs) else {}
    if isinstance(input_payload, dict):
        input_payload.pop("helper_outputs", None)
    enabled = bool(design_guide_button_contract_enabled(contract))
    reason = (
        contract.get("disabled_reason")
        or contract.get("blocking_reason")
        or item_d.get("blocking_reason")
        or item_d.get("cta_reason")
    )
    return DesignGuideButtonContractActionabilityDecision(
        item_index=int(item_index),
        item_identity=identity,
        input_hash=publication_snapshot_hash(input_payload),
        final_actionable=bool(contract.get("actionable")),
        final_enabled=enabled,
        final_disabled=not enabled,
        final_reason=reason,
        final_cta_label=item_d.get("primary_action") or item_d.get("cta_label") or contract.get("label"),
        final_action_type=str(contract.get("action_type") or item_d.get("action_type") or "").strip() or None,
        final_family=str(contract.get("family") or item_d.get("selected_action_family") or item_d.get("family") or item_d.get("check_key") or "").strip().lower() or None,
        final_apply_payload_identity=_apply_button_binding_payload_identity(
            action_payload,
            _apply_button_binding_payload_identity(contract, identity),
        ),
        final_apply_payload_hash=publication_snapshot_hash(action_payload or contract.get("updates") or {}),
        final_candidate_payload_identity=_apply_button_binding_payload_identity(candidate_payload, identity),
        final_candidate_payload_hash=publication_snapshot_hash(candidate_payload),
        final_contract_hash=publication_snapshot_hash(contract),
        final_contract_updates_hash=publication_snapshot_hash(contract.get("updates") or {}),
        decision_reason=str(decision_reason or "").strip() or None,
        decision_source=str(decision_source or "").strip() or None,
    )


def resolve_design_guide_button_contract_actionability_predicates(
    inputs: DesignGuideButtonContractActionabilityInputs | None,
    helper_outputs: DesignGuideButtonContractActionabilityHelperOutputs | None = None,
) -> DesignGuideButtonContractActionabilityPredicates:
    """Resolve pure actionability predicates from typed input/helper-output records."""

    inp = inputs if isinstance(inputs, DesignGuideButtonContractActionabilityInputs) else DesignGuideButtonContractActionabilityInputs()
    helper = (
        helper_outputs
        if isinstance(helper_outputs, DesignGuideButtonContractActionabilityHelperOutputs)
        else inp.helper_outputs
        if isinstance(inp.helper_outputs, DesignGuideButtonContractActionabilityHelperOutputs)
        else DesignGuideButtonContractActionabilityHelperOutputs()
    )
    requested_action_present = bool(str(inp.requested_action_type or "").strip())
    selected_updates_present = bool(list(inp.selected_updates_keys or []))
    executor_allowed = helper.final_executor_allowed
    if executor_allowed is None:
        executor_allowed = inp.executor_allowed
    preview_allowed = helper.final_preview_pass
    if preview_allowed is None:
        preview_allowed = inp.preview_pass
    final_blocking_reason = str(helper.final_blocking_reason or inp.blocking_reason_before_final_decision or "").strip()
    accepted_band_override = bool(helper.accepted_band_override_applied)
    partial_override = bool(helper.partial_cleanup_override_applied)
    exact_override = bool(helper.exact_blocker_override_applied)
    safe_override = bool(accepted_band_override or partial_override or exact_override)
    effective_action = str(inp.effective_action_type or "").strip()
    payload_action_mismatch = bool(effective_action == "apply_resolved_candidate" and not selected_updates_present)
    final_actionable = bool(
        requested_action_present
        and selected_updates_present
        and bool(executor_allowed)
        and not final_blocking_reason
    )
    if payload_action_mismatch:
        reason = "payload_action_mismatch_blocks_apply"
    elif not requested_action_present:
        reason = "missing_action_type"
    elif not selected_updates_present:
        reason = "missing_updates"
    elif not bool(executor_allowed):
        reason = str(helper.executor_reason or inp.executor_reason or "executor_contract_blocked")
    elif final_blocking_reason:
        reason = final_blocking_reason
    elif preview_allowed is False:
        reason = str(helper.preview_reason or inp.preview_reason or "preview_failed")
    elif safe_override:
        reason = "safe_actionability_override_applied"
    else:
        reason = "actionable"
    payload = {
        "requested_action_present": requested_action_present,
        "selected_updates_present": selected_updates_present,
        "action_allowed_by_executor": None if executor_allowed is None else bool(executor_allowed),
        "action_allowed_by_preview": None if preview_allowed is None else bool(preview_allowed),
        "disabled_by_executor": bool(executor_allowed is False),
        "disabled_by_preview": bool(preview_allowed is False),
        "safe_executor_actionable_override_applies": safe_override,
        "accepted_band_override_applies": accepted_band_override,
        "partial_cleanup_override_applies": partial_override,
        "exact_blocker_override_applies": exact_override,
        "payload_action_mismatch_blocks_apply": payload_action_mismatch,
        "final_override_candidate_applies": safe_override,
        "final_actionable_predicate": final_actionable,
        "deterministic_reason": reason,
        "decision_source": inp.decision_source,
    }
    return DesignGuideButtonContractActionabilityPredicates(
        item_index=int(inp.item_index or 0),
        item_identity=inp.item_identity,
        predicate_hash=publication_snapshot_hash(payload),
        **payload,
    )


def build_design_guide_button_contract_actionability_application(
    *,
    predicate: DesignGuideButtonContractActionabilityPredicates | None,
    item_index: int,
    item: dict | None,
    final_contract: dict | None,
    action_type: str | None = None,
    effective_action_type: str | None = None,
    updates: dict | None = None,
    executor_allowed: bool | None = None,
    preview_pass: bool | None = None,
    expected_util: Any = None,
    source_candidate_id: str | None = None,
    original_actionable: bool | None = None,
    original_blocking_reason: str | None = None,
    decision_reason: str | None = None,
    decision_source: str | None = None,
) -> DesignGuideButtonContractActionabilityApplication:
    """Record the final actionability application without constructing the contract."""

    item_d = dict(item or {}) if isinstance(item, dict) else {}
    contract = dict(final_contract or {})
    updates_d = dict(updates or contract.get("updates") or {})
    identity = _apply_button_binding_item_identity(item_d, item_index)
    scalar_inputs = {
        "action_type": str(action_type or "").strip() or None,
        "effective_action_type": str(effective_action_type or contract.get("action_type") or "").strip() or None,
        "updates_hash": publication_snapshot_hash(updates_d),
        "updates_keys": sorted(str(key) for key in updates_d.keys()),
        "executor_allowed": executor_allowed if executor_allowed is None else bool(executor_allowed),
        "preview_pass": preview_pass if preview_pass is None else bool(preview_pass),
        "expected_util": expected_util,
        "source_candidate_id": str(source_candidate_id or contract.get("source_candidate_id") or "").strip() or None,
    }
    final_actionable = bool(contract.get("actionable"))
    final_blocking_reason = str(contract.get("blocking_reason") or "").strip() or None
    enabled = bool(design_guide_button_contract_enabled(contract))
    app_payload = {
        "predicate_hash": predicate.predicate_hash if isinstance(predicate, DesignGuideButtonContractActionabilityPredicates) else None,
        "predicate_final_actionable": (
            predicate.final_actionable_predicate
            if isinstance(predicate, DesignGuideButtonContractActionabilityPredicates)
            else None
        ),
        "scalar_inputs_hash": publication_snapshot_hash(scalar_inputs),
        "original_actionable": original_actionable if original_actionable is None else bool(original_actionable),
        "original_blocking_reason": str(original_blocking_reason or "").strip() or None,
        "final_actionable": final_actionable,
        "final_blocking_reason": final_blocking_reason,
        "final_enabled": enabled,
        "final_contract_hash": publication_snapshot_hash(contract),
        "decision_reason": str(decision_reason or "").strip() or None,
        "decision_source": str(decision_source or "").strip() or None,
    }
    return DesignGuideButtonContractActionabilityApplication(
        item_index=int(item_index),
        item_identity=identity,
        predicate_hash=app_payload["predicate_hash"],
        predicate_final_actionable=app_payload["predicate_final_actionable"],
        scalar_inputs=scalar_inputs,
        scalar_inputs_hash=app_payload["scalar_inputs_hash"],
        original_actionable=app_payload["original_actionable"],
        original_blocking_reason=app_payload["original_blocking_reason"],
        final_actionable=final_actionable,
        final_blocking_reason=final_blocking_reason,
        final_enabled=enabled,
        final_disabled=not enabled,
        final_contract_hash=app_payload["final_contract_hash"],
        final_contract_updates_hash=publication_snapshot_hash(contract.get("updates") or {}),
        decision_reason=app_payload["decision_reason"],
        decision_source=app_payload["decision_source"],
        application_hash=publication_snapshot_hash(app_payload),
    )


def apply_design_guide_button_contract_actionability(
    *,
    inputs: DesignGuideButtonContractActionabilityInputs | None,
    helper_outputs: DesignGuideButtonContractActionabilityHelperOutputs | None = None,
    predicates: DesignGuideButtonContractActionabilityPredicates | None = None,
    item: dict | None = None,
    final_contract: dict | None = None,
    original_actionable: bool | None = None,
) -> DesignGuideButtonContractActionabilityApplication:
    """Apply already-resolved actionability fields to the typed proof record."""

    inp = inputs if isinstance(inputs, DesignGuideButtonContractActionabilityInputs) else DesignGuideButtonContractActionabilityInputs()
    helper = (
        helper_outputs
        if isinstance(helper_outputs, DesignGuideButtonContractActionabilityHelperOutputs)
        else inp.helper_outputs
        if isinstance(inp.helper_outputs, DesignGuideButtonContractActionabilityHelperOutputs)
        else DesignGuideButtonContractActionabilityHelperOutputs()
    )
    predicate = (
        predicates
        if isinstance(predicates, DesignGuideButtonContractActionabilityPredicates)
        else resolve_design_guide_button_contract_actionability_predicates(inp, helper)
    )
    return build_design_guide_button_contract_actionability_application(
        predicate=predicate,
        item_index=int(inp.item_index or 0),
        item=item,
        final_contract=final_contract,
        action_type=inp.requested_action_type,
        effective_action_type=inp.effective_action_type,
        updates=dict((final_contract or {}).get("updates") or {}),
        executor_allowed=helper.final_executor_allowed
        if helper.final_executor_allowed is not None
        else inp.executor_allowed,
        preview_pass=helper.final_preview_pass if helper.final_preview_pass is not None else inp.preview_pass,
        expected_util=helper.final_expected_util if helper.final_expected_util is not None else inp.expected_util,
        source_candidate_id=inp.source_candidate_id,
        original_actionable=original_actionable,
        original_blocking_reason=inp.blocking_reason_before_final_decision,
        decision_reason=inp.update_decision_reason,
        decision_source=inp.decision_source,
    )


def build_design_guide_button_contract_scalars(
    *,
    item_index: int,
    item: dict | None,
    final_contract: dict | None,
    decision_reason: str | None = None,
    decision_source: str | None = None,
) -> DesignGuideButtonContractScalars:
    """Assemble final button-contract scalar proof without changing the contract."""

    item_d = dict(item or {}) if isinstance(item, dict) else {}
    contract = dict(final_contract or {})
    existing_contract = dict(item_d.get("button_contract") or {})
    action_payload = dict(item_d.get("action_payload") or {})
    candidate_payload = dict(
        item_d.get("resolved_candidate")
        or item_d.get("candidate")
        or item_d.get("candidate_payload")
        or {}
    )
    identity = _apply_button_binding_item_identity(item_d, item_index)

    def _rewritten_keys(before: dict, after: dict) -> list[str]:
        return sorted(
            str(key)
            for key in set(before.keys()) & set(after.keys())
            if publication_snapshot_hash(before.get(key)) != publication_snapshot_hash(after.get(key))
        )

    enabled = bool(design_guide_button_contract_enabled(contract))
    reason = (
        contract.get("disabled_reason")
        or contract.get("blocking_reason")
        or item_d.get("blocking_reason")
        or item_d.get("cta_reason")
    )
    label = item_d.get("primary_action") or item_d.get("cta_label") or contract.get("label")
    action_type = str(contract.get("action_type") or item_d.get("action_type") or "").strip() or None
    family = contract.get("family") or item_d.get("selected_action_family") or item_d.get("family") or item_d.get("check_key")
    final_item_id = (
        contract.get("candidate_id")
        or contract.get("source_candidate_id")
        or item_d.get("candidate_id")
        or item_d.get("source_candidate_id")
        or identity
    )
    state_fingerprint = (
        contract.get("state_fingerprint")
        or item_d.get("state_fingerprint")
        or item_d.get("final_visible_state_fingerprint")
        or action_payload.get("state_fingerprint")
        or candidate_payload.get("state_fingerprint")
    )
    return DesignGuideButtonContractScalars(
        item_index=int(item_index),
        item_identity=identity,
        final_enabled=enabled,
        final_disabled=not enabled,
        final_reason=reason,
        final_label=label,
        final_action_text=action_type,
        final_action_type=action_type,
        final_family=str(family).strip().lower() if family not in (None, "") else None,
        final_item_id=str(final_item_id) if final_item_id not in (None, "") else None,
        apply_payload_identity=_apply_button_binding_payload_identity(
            action_payload,
            _apply_button_binding_payload_identity(contract, identity),
        ),
        apply_payload_hash=publication_snapshot_hash(action_payload or contract.get("updates") or {}),
        candidate_payload_identity=_apply_button_binding_payload_identity(candidate_payload, identity),
        candidate_payload_hash=publication_snapshot_hash(candidate_payload),
        final_state_fingerprint=state_fingerprint,
        final_contract_hash=publication_snapshot_hash(contract),
        final_contract_updates_hash=publication_snapshot_hash(contract.get("updates") or {}),
        final_contract_keys=sorted(str(key) for key in contract.keys()),
        final_contract=contract,
        fields_added_to_button_contract=sorted(str(key) for key in set(contract.keys()) - set(existing_contract.keys())),
        fields_rewritten_on_button_contract=_rewritten_keys(existing_contract, contract),
        decision_reason=str(decision_reason or "").strip() or None,
        decision_source=str(decision_source or "").strip() or None,
    )


def record_design_guide_button_contract_update_resolution(
    records: list[DesignGuideButtonContractUpdateResolution] | None,
    *,
    item_index: int,
    item: dict | None,
    family_before: str | None,
    family_after: str | None,
    action_type_before: str | None,
    action_type_after: str | None,
    updates_before: dict | None,
    updates_after: dict | None,
    expected_util_before: Any,
    expected_util_after: Any,
    blocking_reason: str | None,
    work_before: dict | None,
    work_after: dict | None,
    final_contract: dict | None,
    update_resolution_applicable: bool,
    updates_source: str | None,
    decision_reason: str | None,
    exception_type: str | None = None,
    decision: DesignGuideButtonContractUpdateResolutionDecision | None = None,
) -> None:
    """Append update-resolution proof from already-resolved button-contract values."""

    if records is None:
        return
    if decision is not None:
        family_before = decision.family_before
        family_after = decision.family_after
        action_type_before = decision.input_action_type
        action_type_after = decision.resolved_action_type
        updates_after = dict(updates_after or {})
        expected_util_before = decision.expected_util_before
        expected_util_after = decision.expected_util_after
        blocking_reason = decision.resolved_disabled_reason
        update_resolution_applicable = decision.update_resolution_applicable
        updates_source = decision.updates_source
        decision_reason = decision.decision_reason
        exception_type = decision.exception_type
    records.append(
        build_design_guide_button_contract_update_resolution(
            item_index=item_index,
            item=item,
            family_before=family_before,
            family_after=family_after,
            action_type_before=action_type_before,
            action_type_after=action_type_after,
            updates_before=updates_before,
            updates_after=updates_after,
            expected_util_before=expected_util_before,
            expected_util_after=expected_util_after,
            blocking_reason=blocking_reason,
            work_before=work_before,
            work_after=work_after,
            final_contract=final_contract,
            update_resolution_applicable=update_resolution_applicable,
            updates_source=updates_source,
            decision_reason=decision_reason,
            exception_type=exception_type,
        )
    )


def record_design_guide_button_contract_work_mutation(
    records: list[DesignGuideButtonContractWorkMutation] | None,
    *,
    item_index: int,
    item: dict | None,
    work_before: dict | None,
    work_after: dict | None,
    selected_update_source: str | None,
    selected_updates: dict | None,
    selected_evidence_candidate_id: str | None = None,
    selected_parsed_util: Any = None,
    work_mutation_applied: bool = False,
    work_object_id_before: int | None = None,
    work_object_id_after: int | None = None,
    decision_reason: str | None = None,
) -> None:
    """Append work-mutation proof from already-resolved work snapshots."""

    if records is None:
        return
    records.append(
        build_design_guide_button_contract_work_mutation(
            item_index=item_index,
            item=item,
            work_before=work_before,
            work_after=work_after,
            selected_update_source=selected_update_source,
            selected_updates=selected_updates,
            selected_evidence_candidate_id=selected_evidence_candidate_id,
            selected_parsed_util=selected_parsed_util,
            work_mutation_applied=work_mutation_applied,
            work_object_id_before=work_object_id_before,
            work_object_id_after=work_object_id_after,
            decision_reason=decision_reason,
        )
    )


def record_design_guide_button_contract_scalars(
    records: list[DesignGuideButtonContractScalars] | None,
    *,
    item_index: int,
    item: dict | None,
    final_contract: dict | None,
    decision_reason: str | None,
    decision_source: str | None,
) -> None:
    """Append final button-contract scalar proof."""

    if records is None:
        return
    records.append(
        build_design_guide_button_contract_scalars(
            item_index=item_index,
            item=item,
            final_contract=final_contract,
            decision_reason=decision_reason,
            decision_source=decision_source,
        )
    )


def record_design_guide_button_contract_actionability(
    helper_output_records: list[DesignGuideButtonContractActionabilityHelperOutputs] | None,
    input_records: list[DesignGuideButtonContractActionabilityInputs] | None,
    predicate_records: list[DesignGuideButtonContractActionabilityPredicates] | None,
    application_records: list[DesignGuideButtonContractActionabilityApplication] | None,
    decision_records: list[DesignGuideButtonContractActionabilityDecision] | None,
    *,
    item_index: int,
    item: dict | None,
    work: dict | None,
    requested_updates: dict | None,
    selected_update_source: str | None,
    selected_updates: dict | None,
    selected_evidence_candidate_id: str | None = None,
    selected_parsed_util: Any = None,
    requested_action_type: str | None = None,
    effective_action_type: str | None = None,
    executor_allowed: bool | None = None,
    executor_reason: str | None = None,
    preview_pass: bool | None = None,
    preview_reason: str | None = None,
    helper_outputs: DesignGuideButtonContractActionabilityHelperOutputs | None = None,
    expected_util: Any = None,
    blocking_reason: str | None = None,
    family: str | None = None,
    source_candidate_id: str | None = None,
    update_decision_reason: str | None = None,
    update_exception_type: str | None = None,
    decision_source: str | None = None,
    final_contract: dict | None = None,
    original_actionable: bool | None = None,
) -> None:
    """Append actionability proof records from already-resolved actionability values."""

    if (
        helper_output_records is None
        and input_records is None
        and predicate_records is None
        and application_records is None
        and decision_records is None
    ):
        return
    if helper_outputs is not None and helper_output_records is not None:
        helper_output_records.append(helper_outputs)
    inputs = build_design_guide_button_contract_actionability_inputs(
        item_index=item_index,
        item=item,
        work=work,
        requested_updates=requested_updates,
        selected_update_source=selected_update_source,
        selected_updates=selected_updates,
        selected_evidence_candidate_id=selected_evidence_candidate_id,
        selected_parsed_util=selected_parsed_util,
        requested_action_type=requested_action_type,
        effective_action_type=effective_action_type,
        executor_allowed=executor_allowed,
        executor_reason=executor_reason,
        preview_pass=preview_pass,
        preview_reason=preview_reason,
        helper_outputs=helper_outputs,
        expected_util=expected_util,
        blocking_reason=blocking_reason,
        family=family,
        source_candidate_id=source_candidate_id,
        update_decision_reason=update_decision_reason,
        update_exception_type=update_exception_type,
        decision_source=decision_source,
    )
    if input_records is not None:
        input_records.append(inputs)
    predicates = resolve_design_guide_button_contract_actionability_predicates(inputs, helper_outputs)
    if predicate_records is not None:
        predicate_records.append(predicates)
    if application_records is not None:
        application_records.append(
            apply_design_guide_button_contract_actionability(
                inputs=inputs,
                helper_outputs=helper_outputs,
                predicates=predicates,
                item=item,
                final_contract=final_contract,
                original_actionable=original_actionable,
            )
        )
    if decision_records is not None:
        decision_records.append(
            build_design_guide_button_contract_actionability_decision(
                inputs=inputs,
                item_index=item_index,
                item=item,
                final_contract=final_contract,
                decision_reason=update_decision_reason,
                decision_source=decision_source,
            )
        )


def _design_guide_button_contract_actionability_resolution_source(
    *,
    accepted_band_override_applied: bool,
    partial_cleanup_override_applied: bool,
    exact_blocker_override_applied: bool,
    combined_truth_probe_evaluated: bool,
    family_truth_probe_evaluated: bool,
    blocking_reason: str | None,
    actionable: bool,
) -> str:
    if accepted_band_override_applied:
        return "accepted_band_override"
    if partial_cleanup_override_applied:
        return "partial_cleanup_override"
    if exact_blocker_override_applied:
        return "exact_blocker_override"
    if combined_truth_probe_evaluated:
        return "combined_truth_probe"
    if family_truth_probe_evaluated:
        return "family_truth_probe"
    if blocking_reason:
        return str(blocking_reason)
    if actionable:
        return "actionable"
    return "not_actionable"


def _emit_design_guide_button_contract_records_explicit(
    *,
    item_index: int,
    item: dict | None,
    work_after: dict | None,
    updates: dict | None,
    updates_source: str | None,
    final_contract: dict | None,
    action_type: str | None,
    effective_action_type: str | None,
    family: str | None,
    expected_util: Any,
    blocking_reason: str | None,
    executor_allowed: bool | None,
    executor_reason: str | None,
    executor_exception_type: str | None,
    executor_contract_evaluated: bool,
    preview_pass: bool | None,
    preview_util: Any,
    preview_reason: str | None,
    preview_evaluated: bool,
    source_candidate_id: str | None,
    actionable: bool,
    update_decision_reason: str | None,
    update_exception_type: str | None,
    safe_incremental_below_threshold: bool | None,
    family_exact_cleanup_blocker: bool | None,
    local_cleanup_post_apply_acceptance_matches: bool | None,
    best_safe_partial_cleanup: bool | None,
    low_util_exact_blocker: bool | None,
    accepted_band_cleanup_evaluated: bool,
    accepted_band_cleanup: bool | None,
    accepted_band_family_preview_util: Any,
    accepted_band_override_applied: bool,
    partial_cleanup_override_applied: bool,
    exact_blocker_override_applied: bool,
    family_truth_probe_evaluated: bool,
    family_truth_probe_exception_type: str | None,
    family_truth_probe_expected_util: Any,
    combined_truth_probe_evaluated: bool,
    combined_truth_probe_exception_type: str | None,
    combined_truth_probe_expected_util: Any,
    resolution_blocking_reason_before: str | None,
    resolution_executor_allowed_before: bool | None,
    resolution_preview_pass_before: bool | None,
    resolution_expected_util_before: Any,
    resolution_family_before: str | None,
    resolution_actionable_before: bool | None,
    resolution_enabled_before: bool | None,
    update_resolution_input_record: DesignGuideButtonContractUpdateResolutionInputs | None,
    update_resolution_applicable: bool,
    update_family_before: str | None,
    update_action_type_before: str | None,
    update_expected_util_before: Any,
    blocking_reason_override: str | None,
    work_before: dict | None,
    item_snapshot_before: dict | None,
    work_mutation_record: DesignGuideButtonContractWorkMutation | None,
    work_mutation_input_snapshot: dict | None,
    work_mutation_output_snapshot: dict | None,
    work_mutation_selected_source: str | None,
    work_mutation_selected_updates: dict | None,
    work_mutation_selected_candidate_id: str | None,
    work_mutation_selected_util: Any,
    work_mutation_applied: bool,
    work_mutation_object_id_before: int | None,
    work_mutation_object_id_after: int | None,
    actionability_resolution_records: list[DesignGuideButtonContractActionabilityResolution] | None,
    actionability_probe_output_records: list[DesignGuideButtonContractActionabilityProbeOutputs] | None,
    actionability_helper_output_records: list[DesignGuideButtonContractActionabilityHelperOutputs] | None,
    actionability_input_records: list[DesignGuideButtonContractActionabilityInputs] | None,
    actionability_predicate_records: list[DesignGuideButtonContractActionabilityPredicates] | None,
    actionability_application_records: list[DesignGuideButtonContractActionabilityApplication] | None,
    actionability_decision_records: list[DesignGuideButtonContractActionabilityDecision] | None,
    update_resolution_input_records: list[DesignGuideButtonContractUpdateResolutionInputs] | None,
    update_resolution_decision_records: list[DesignGuideButtonContractUpdateResolutionDecision] | None,
    scalar_records: list[DesignGuideButtonContractScalars] | None,
    work_mutation_records: list[DesignGuideButtonContractWorkMutation] | None,
    update_resolution_records: list[DesignGuideButtonContractUpdateResolution] | None,
    actionability_resolution_source_override: str | None = None,
) -> dict:
    """Emit already-resolved button-contract proof records without changing decisions."""

    updates_d = dict(updates or {})
    actionability_resolution_source = (
        str(actionability_resolution_source_override or "").strip()
        or _design_guide_button_contract_actionability_resolution_source(
            accepted_band_override_applied=accepted_band_override_applied,
            partial_cleanup_override_applied=partial_cleanup_override_applied,
            exact_blocker_override_applied=exact_blocker_override_applied,
            combined_truth_probe_evaluated=combined_truth_probe_evaluated,
            family_truth_probe_evaluated=family_truth_probe_evaluated,
            blocking_reason=blocking_reason,
            actionable=bool(actionable),
        )
    )
    if actionability_resolution_records is not None:
        actionability_resolution_records.append(
            build_design_guide_button_contract_actionability_resolution(
                item_index=item_index,
                item=item,
                blocking_reason_before=resolution_blocking_reason_before,
                blocking_reason_after=blocking_reason,
                executor_allowed_before=resolution_executor_allowed_before,
                executor_allowed_after=executor_allowed,
                preview_pass_before=resolution_preview_pass_before,
                preview_pass_after=preview_pass,
                expected_util_before=resolution_expected_util_before,
                expected_util_after=expected_util,
                family_before=resolution_family_before,
                family_after=family,
                actionable_before=resolution_actionable_before,
                actionable_after=actionable,
                enabled_before=resolution_enabled_before,
                enabled_after=design_guide_button_contract_enabled(final_contract),
                reason_before=resolution_blocking_reason_before,
                reason_after=blocking_reason,
                selected_actionability_source=actionability_resolution_source,
                decision_reason=update_decision_reason,
                decision_source=updates_source,
                final_contract=final_contract,
            )
        )
    if actionability_probe_output_records is not None:
        actionability_probe_output_records.append(
            build_design_guide_button_contract_actionability_probe_outputs(
                item_index=item_index,
                item=item,
                executor_contract_evaluated=executor_contract_evaluated,
                executor_allowed=executor_allowed,
                executor_reason=executor_reason,
                executor_exception_type=executor_exception_type,
                preview_evaluated=preview_evaluated,
                preview_pass=preview_pass,
                preview_util=preview_util,
                preview_reason=preview_reason,
                safe_incremental_below_threshold=safe_incremental_below_threshold,
                family_exact_cleanup_blocker=family_exact_cleanup_blocker,
                local_cleanup_post_apply_acceptance_matches=local_cleanup_post_apply_acceptance_matches,
                best_safe_partial_cleanup=best_safe_partial_cleanup,
                low_util_exact_blocker=low_util_exact_blocker,
                accepted_band_cleanup_evaluated=accepted_band_cleanup_evaluated,
                accepted_band_cleanup=accepted_band_cleanup,
                accepted_band_family_preview_util=accepted_band_family_preview_util,
                accepted_band_override_applied=accepted_band_override_applied,
                partial_cleanup_override_applied=partial_cleanup_override_applied,
                exact_blocker_override_applied=exact_blocker_override_applied,
                family_truth_probe_evaluated=family_truth_probe_evaluated,
                family_truth_probe_exception_type=family_truth_probe_exception_type,
                family_truth_probe_expected_util=family_truth_probe_expected_util,
                combined_truth_probe_evaluated=combined_truth_probe_evaluated,
                combined_truth_probe_exception_type=combined_truth_probe_exception_type,
                combined_truth_probe_expected_util=combined_truth_probe_expected_util,
                final_family=family,
                final_expected_util=expected_util,
                final_blocking_reason=blocking_reason,
                final_executor_allowed=executor_allowed,
                final_preview_pass=preview_pass,
            )
        )
    helper_outputs = build_design_guide_button_contract_actionability_helper_outputs(
        item_index=item_index,
        item=item,
        executor_contract_evaluated=executor_contract_evaluated,
        executor_allowed=executor_allowed,
        executor_reason=executor_reason,
        executor_exception_type=executor_exception_type,
        preview_evaluated=preview_evaluated,
        preview_pass=preview_pass,
        preview_util=preview_util,
        preview_reason=preview_reason,
        safe_incremental_below_threshold=safe_incremental_below_threshold,
        family_exact_cleanup_blocker=family_exact_cleanup_blocker,
        local_cleanup_post_apply_acceptance_matches=local_cleanup_post_apply_acceptance_matches,
        best_safe_partial_cleanup=best_safe_partial_cleanup,
        low_util_exact_blocker=low_util_exact_blocker,
        accepted_band_cleanup_evaluated=accepted_band_cleanup_evaluated,
        accepted_band_cleanup=accepted_band_cleanup,
        accepted_band_family_preview_util=accepted_band_family_preview_util,
        accepted_band_override_applied=accepted_band_override_applied,
        partial_cleanup_override_applied=partial_cleanup_override_applied,
        exact_blocker_override_applied=exact_blocker_override_applied,
        family_truth_probe_evaluated=family_truth_probe_evaluated,
        family_truth_probe_exception_type=family_truth_probe_exception_type,
        family_truth_probe_expected_util=family_truth_probe_expected_util,
        combined_truth_probe_evaluated=combined_truth_probe_evaluated,
        combined_truth_probe_exception_type=combined_truth_probe_exception_type,
        combined_truth_probe_expected_util=combined_truth_probe_expected_util,
        final_executor_allowed=executor_allowed,
        final_blocking_reason=blocking_reason,
        final_preview_pass=preview_pass,
        final_expected_util=expected_util,
    )
    record_design_guide_button_contract_actionability(
        actionability_helper_output_records,
        actionability_input_records,
        actionability_predicate_records,
        actionability_application_records,
        actionability_decision_records,
        item_index=item_index,
        item=item,
        work=work_after,
        requested_updates=updates_d,
        selected_update_source=updates_source,
        selected_updates=updates_d,
        selected_evidence_candidate_id=work_mutation_selected_candidate_id,
        selected_parsed_util=work_mutation_selected_util,
        requested_action_type=action_type,
        effective_action_type=effective_action_type,
        executor_allowed=executor_allowed,
        executor_reason=executor_reason,
        preview_pass=preview_pass,
        preview_reason=preview_reason,
        helper_outputs=helper_outputs,
        expected_util=expected_util,
        blocking_reason=blocking_reason,
        family=family,
        source_candidate_id=source_candidate_id,
        update_decision_reason=update_decision_reason,
        update_exception_type=update_exception_type,
        decision_source=updates_source,
        final_contract=final_contract,
        original_actionable=actionable,
    )
    if update_resolution_input_record is None:
        update_resolution_input_record = build_design_guide_button_contract_update_resolution_inputs(
            item_index=item_index,
            item=item,
            family_before=update_family_before,
            action_type_before=update_action_type_before,
            updates_before=dict((item_snapshot_before or {}).get("updates") or {}),
            expected_util_before=update_expected_util_before,
            blocking_reason_override=blocking_reason_override,
            work_before=work_before,
            update_resolution_applicable=update_resolution_applicable,
        )
        if update_resolution_input_records is not None:
            update_resolution_input_records.append(update_resolution_input_record)
    update_resolution_decision = build_design_guide_button_contract_update_resolution_decision(
        item_index=item_index,
        item=item,
        family_before=update_family_before,
        family_after=family,
        action_type_before=update_action_type_before,
        action_type_after=effective_action_type,
        updates_after=updates_d,
        expected_util_before=update_expected_util_before,
        expected_util_after=expected_util,
        blocking_reason=blocking_reason,
        work_before=work_before,
        work_after=work_after,
        final_contract=final_contract,
        update_resolution_applicable=update_resolution_applicable,
        updates_source=updates_source,
        decision_reason=update_decision_reason,
        exception_type=update_exception_type,
        executor_allowed=executor_allowed,
        executor_reason=executor_reason,
        preview_pass=preview_pass,
        preview_reason=preview_reason,
    )
    if update_resolution_decision_records is not None:
        update_resolution_decision_records.append(update_resolution_decision)
    record_design_guide_button_contract_scalars(
        scalar_records,
        item_index=item_index,
        item=item,
        final_contract=final_contract,
        decision_reason=update_decision_reason,
        decision_source=updates_source,
    )
    if work_mutation_records is not None and work_mutation_record is not None:
        work_mutation_records.append(work_mutation_record)
    else:
        record_design_guide_button_contract_work_mutation(
            work_mutation_records,
            item_index=item_index,
            item=item,
            work_before=work_mutation_input_snapshot,
            work_after=work_mutation_output_snapshot,
            selected_update_source=work_mutation_selected_source,
            selected_updates=work_mutation_selected_updates,
            selected_evidence_candidate_id=work_mutation_selected_candidate_id,
            selected_parsed_util=work_mutation_selected_util,
            work_mutation_applied=work_mutation_applied,
            work_object_id_before=work_mutation_object_id_before,
            work_object_id_after=work_mutation_object_id_after,
            decision_reason=update_decision_reason,
        )
    record_design_guide_button_contract_update_resolution(
        update_resolution_records,
        item_index=item_index,
        item=item,
        family_before=update_family_before,
        family_after=family,
        action_type_before=update_action_type_before,
        action_type_after=effective_action_type,
        updates_before=dict((item_snapshot_before or {}).get("updates") or {}),
        updates_after=updates_d,
        expected_util_before=update_expected_util_before,
        expected_util_after=expected_util,
        blocking_reason=blocking_reason,
        work_before=work_before,
        work_after=work_after,
        final_contract=final_contract,
        update_resolution_applicable=update_resolution_applicable,
        updates_source=updates_source,
        decision_reason=update_decision_reason,
        exception_type=update_exception_type,
        decision=update_resolution_decision,
    )
    return final_contract if isinstance(final_contract, dict) else {}


def emit_design_guide_button_contract_records(
    *,
    context: DesignGuideButtonContractEmissionContext | None = None,
    **kwargs,
) -> dict:
    """Emit button-contract proof records from a typed context."""

    if context is None:
        context = DesignGuideButtonContractEmissionContext(**kwargs)
    return _emit_design_guide_button_contract_records_explicit(**context.to_kwargs())


def resolve_design_guide_visible_blocker_disabled_contract(
    *,
    item_index: int,
    item: dict | None,
    family: str | None,
    action_type: str | None,
    effective_action_type: str | None,
    expected_util: Any,
    blocking_reason: str | None,
    blocking_reason_override: str | None,
    updates_source: str | None,
    update_family_before: str | None,
    update_action_type_before: str | None,
    update_expected_util_before: Any,
    work_before: dict | None,
    work_after: dict | None,
    item_snapshot_before: dict | None,
    final_accepted_min_family_util: Any,
    target_band_eps: Any,
    compound_shear_update_keys: Iterable[Any],
    compound_bottom_update_keys: Iterable[Any],
    update_resolution_input_records: list[DesignGuideButtonContractUpdateResolutionInputs] | None,
    update_resolution_decision_records: list[DesignGuideButtonContractUpdateResolutionDecision] | None,
    update_resolution_records: list[DesignGuideButtonContractUpdateResolution] | None,
    work_mutation_records: list[DesignGuideButtonContractWorkMutation] | None,
    scalar_records: list[DesignGuideButtonContractScalars] | None,
    actionability_probe_input_records: list[DesignGuideButtonContractActionabilityProbeInputs] | None,
    actionability_resolution_records: list[DesignGuideButtonContractActionabilityResolution] | None,
    actionability_probe_output_records: list[DesignGuideButtonContractActionabilityProbeOutputs] | None,
    actionability_helper_output_records: list[DesignGuideButtonContractActionabilityHelperOutputs] | None,
    actionability_input_records: list[DesignGuideButtonContractActionabilityInputs] | None,
    actionability_predicate_records: list[DesignGuideButtonContractActionabilityPredicates] | None,
    actionability_application_records: list[DesignGuideButtonContractActionabilityApplication] | None,
    actionability_decision_records: list[DesignGuideButtonContractActionabilityDecision] | None,
) -> DesignGuideVisibleBlockerDisabledContractResult:
    """Build and prove the disabled contract for an already-detected visible blocker."""

    reason = str(blocking_reason or design_guide_blocker_reason(item) or "").strip() or "specific_blocker"
    disabled_contract = disabled_design_guide_button_contract(
        item,
        family=family,
        reason=reason,
    )
    emitted_record_kinds: list[str] = []
    if actionability_probe_input_records is not None:
        actionability_probe_input_records.append(
            build_design_guide_button_contract_actionability_probe_inputs(
                item_index=item_index,
                item=item,
                work=work_after,
                updates={},
                family=family,
                action_type=action_type,
                effective_action_type=effective_action_type,
                selected_update_source=updates_source,
                update_decision_reason="visible_blocker_disabled_contract",
                final_accepted_min_family_util=final_accepted_min_family_util,
                target_band_eps=target_band_eps,
                compound_shear_update_keys=compound_shear_update_keys,
                compound_bottom_update_keys=compound_bottom_update_keys,
                blocking_reason_before_probe=blocking_reason,
                executor_allowed_before_probe=False,
                preview_pass_before_probe=False,
                expected_util_before_probe=expected_util,
                actionable_before_probe=False,
                enabled_before_probe=False,
            )
        )
        emitted_record_kinds.append("actionability_probe_inputs")
    final_contract = emit_design_guide_button_contract_records(
        item_index=item_index,
        item=item,
        work_after=work_after,
        updates={},
        updates_source=updates_source,
        final_contract=disabled_contract,
        action_type=action_type,
        effective_action_type=effective_action_type,
        family=family,
        expected_util=expected_util,
        blocking_reason=disabled_contract.get("blocking_reason"),
        executor_allowed=False,
        executor_reason=disabled_contract.get("blocking_reason"),
        executor_exception_type=None,
        executor_contract_evaluated=False,
        preview_pass=False,
        preview_util=None,
        preview_reason=None,
        preview_evaluated=False,
        source_candidate_id=disabled_contract.get("source_candidate_id"),
        actionable=False,
        update_decision_reason="visible_blocker_disabled_contract",
        update_exception_type=None,
        safe_incremental_below_threshold=None,
        family_exact_cleanup_blocker=None,
        local_cleanup_post_apply_acceptance_matches=None,
        best_safe_partial_cleanup=None,
        low_util_exact_blocker=None,
        accepted_band_cleanup_evaluated=False,
        accepted_band_cleanup=None,
        accepted_band_family_preview_util=None,
        accepted_band_override_applied=False,
        partial_cleanup_override_applied=False,
        exact_blocker_override_applied=False,
        family_truth_probe_evaluated=False,
        family_truth_probe_exception_type=None,
        family_truth_probe_expected_util=None,
        combined_truth_probe_evaluated=False,
        combined_truth_probe_exception_type=None,
        combined_truth_probe_expected_util=None,
        resolution_blocking_reason_before=blocking_reason,
        resolution_executor_allowed_before=False,
        resolution_preview_pass_before=False,
        resolution_expected_util_before=expected_util,
        resolution_family_before=family,
        resolution_actionable_before=False,
        resolution_enabled_before=False,
        update_resolution_input_record=None,
        update_resolution_applicable=False,
        update_family_before=update_family_before,
        update_action_type_before=update_action_type_before,
        update_expected_util_before=update_expected_util_before,
        blocking_reason_override=blocking_reason_override,
        work_before=work_before,
        item_snapshot_before=item_snapshot_before,
        work_mutation_record=None,
        work_mutation_input_snapshot=work_before,
        work_mutation_output_snapshot=work_after,
        work_mutation_selected_source=updates_source,
        work_mutation_selected_updates={},
        work_mutation_selected_candidate_id=None,
        work_mutation_selected_util=None,
        work_mutation_applied=False,
        work_mutation_object_id_before=id(work_before),
        work_mutation_object_id_after=id(work_after),
        actionability_resolution_records=actionability_resolution_records,
        actionability_probe_output_records=actionability_probe_output_records,
        actionability_helper_output_records=actionability_helper_output_records,
        actionability_input_records=actionability_input_records,
        actionability_predicate_records=actionability_predicate_records,
        actionability_application_records=actionability_application_records,
        actionability_decision_records=actionability_decision_records,
        update_resolution_input_records=update_resolution_input_records,
        update_resolution_decision_records=update_resolution_decision_records,
        scalar_records=scalar_records,
        work_mutation_records=work_mutation_records,
        update_resolution_records=update_resolution_records,
        actionability_resolution_source_override="visible_blocker_disabled_contract",
    )
    emitted_record_kinds.extend(
        kind
        for kind, records in (
            ("actionability_resolutions", actionability_resolution_records),
            ("actionability_probe_outputs", actionability_probe_output_records),
            ("actionability_helper_outputs", actionability_helper_output_records),
            ("actionability_inputs", actionability_input_records),
            ("actionability_predicates", actionability_predicate_records),
            ("actionability_applications", actionability_application_records),
            ("actionability_decisions", actionability_decision_records),
            ("update_resolution_inputs", update_resolution_input_records),
            ("update_resolution_decisions", update_resolution_decision_records),
            ("button_contract_scalars", scalar_records),
            ("work_mutations", work_mutation_records),
            ("update_resolutions", update_resolution_records),
        )
        if records is not None
    )
    item_d = dict(item or {}) if isinstance(item, dict) else {}
    action_payload = dict(item_d.get("action_payload") or {})
    candidate_payload = dict(
        item_d.get("resolved_candidate")
        or item_d.get("candidate")
        or item_d.get("candidate_payload")
        or {}
    )
    item_identity = _apply_button_binding_item_identity(item_d, item_index)
    proof_payload = {
        "item_identity": item_identity,
        "reason": reason,
        "contract_hash": publication_snapshot_hash(final_contract),
        "emitted_record_kinds": emitted_record_kinds,
    }
    return DesignGuideVisibleBlockerDisabledContractResult(
        item_index=int(item_index),
        item_identity=item_identity,
        visible_blocker_reason=reason,
        visible_blocker_source="visible_blocker_disabled_contract",
        final_disabled_contract=dict(final_contract or {}),
        final_disabled_contract_hash=publication_snapshot_hash(final_contract),
        final_enabled=design_guide_button_contract_enabled(final_contract),
        final_actionable=bool((final_contract or {}).get("actionable")),
        final_blocking_reason=str((final_contract or {}).get("blocking_reason") or "").strip() or None,
        apply_payload_identity=_apply_button_binding_payload_identity(action_payload, item_identity),
        apply_payload_hash=publication_snapshot_hash(action_payload),
        candidate_payload_identity=_apply_button_binding_payload_identity(candidate_payload, item_identity),
        candidate_payload_hash=publication_snapshot_hash(candidate_payload),
        emitted_record_kinds=list(emitted_record_kinds),
        emitted_record_count=len(emitted_record_kinds),
        proof_record_hash=publication_snapshot_hash(proof_payload),
    )


def _apply_button_binding_item_identity(item: dict | None, index: int) -> str:
    if not isinstance(item, dict):
        return f"non_dict_{index}"
    identity = (
        item.get("id")
        or item.get("candidate_id")
        or item.get("source_candidate_id")
        or item.get("title_main")
        or item.get("title")
        or f"item_{index}"
    )
    return str(identity)


def _apply_button_binding_payload_identity(
    payload: dict | None,
    fallback: str | None = None,
) -> str | None:
    if not isinstance(payload, dict):
        return fallback
    value = (
        payload.get("id")
        or payload.get("payload_id")
        or payload.get("candidate_id")
        or payload.get("source_candidate_id")
        or fallback
    )
    return str(value) if value not in (None, "") else None


def _apply_button_binding_item_snapshot(item: dict | None, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "index": index,
            "identity": _apply_button_binding_item_identity(item, index),
            "is_dict": False,
        }
    contract = dict(item.get("button_contract") or {})
    action_payload = dict(item.get("action_payload") or {})
    candidate_payload = dict(
        item.get("resolved_candidate")
        or item.get("candidate")
        or item.get("candidate_payload")
        or {}
    )
    disabled_reason = (
        contract.get("disabled_reason")
        or contract.get("blocking_reason")
        or item.get("blocking_reason")
        or item.get("cta_reason")
    )
    selected_family = item.get("selected_family") or item.get("family") or item.get("check_key")
    return {
        "index": index,
        "identity": _apply_button_binding_item_identity(item, index),
        "is_dict": True,
        "hash": publication_snapshot_hash(item),
        "keys": sorted(str(key) for key in item.keys()),
        "selected_family": selected_family,
        "published_family": item.get("published_family_id") or item.get("selected_family_id"),
        "apply_family": (
            item.get("selected_action_family")
            or action_payload.get("family")
            or contract.get("family")
            or selected_family
        ),
        "cta_label": item.get("primary_action") or item.get("cta_label") or contract.get("label"),
        "cta_enabled": bool(design_guide_button_contract_enabled(contract)),
        "cta_reason": disabled_reason,
        "button_contract_enabled": bool(design_guide_button_contract_enabled(contract)),
        "disabled_reason": disabled_reason,
        "button_contract_action_type": contract.get("action_type"),
        "button_contract_keys": sorted(str(key) for key in contract.keys()),
        "button_contract_hash": publication_snapshot_hash(contract),
        "button_contract_updates_hash": publication_snapshot_hash(contract.get("updates") or {}),
        "apply_payload_identity": _apply_button_binding_payload_identity(
            action_payload,
            _apply_button_binding_payload_identity(contract),
        ),
        "apply_payload_hash": publication_snapshot_hash(
            action_payload or contract.get("updates") or {}
        ),
        "candidate_payload_identity": _apply_button_binding_payload_identity(
            candidate_payload,
            _apply_button_binding_item_identity(item, index),
        ),
        "candidate_payload_hash": publication_snapshot_hash(candidate_payload),
        "state_fingerprint": item.get("state_fingerprint")
        or item.get("final_visible_state_fingerprint")
        or contract.get("state_fingerprint"),
        "debug_keys": sorted(
            str(key)
            for key in item.keys()
            if "debug" in str(key).lower() or "contract" in str(key).lower()
        ),
    }


def _apply_button_contract_summary(contract: dict | None) -> dict[str, Any]:
    c = dict(contract or {})
    return {
        "enabled": bool(design_guide_button_contract_enabled(c)),
        "disabled_reason": c.get("disabled_reason") or c.get("blocking_reason"),
        "action_type": c.get("action_type"),
        "contract_hash": publication_snapshot_hash(c),
        "updates_hash": publication_snapshot_hash(c.get("updates") or {}),
        "keys": sorted(str(key) for key in c.keys()),
    }


def _apply_button_action_state(item: dict | None, contract: dict | None) -> dict[str, Any]:
    payload = dict((item or {}).get("action_payload") or {})
    resolved_candidate = dict((item or {}).get("resolved_candidate") or {})
    c = dict(contract or {})
    return {
        "action_type": (item or {}).get("action_type") or c.get("action_type"),
        "updates_hash": publication_snapshot_hash((item or {}).get("updates") or c.get("updates") or {}),
        "candidate_id": (item or {}).get("candidate_id") or c.get("candidate_id"),
        "source_candidate_id": (item or {}).get("source_candidate_id") or c.get("source_candidate_id"),
        "family": (item or {}).get("selected_action_family")
        or (item or {}).get("family")
        or (item or {}).get("check_key")
        or c.get("family"),
        "title": (item or {}).get("title"),
        "title_main": (item or {}).get("title_main"),
        "guidance_intent": (item or {}).get("guidance_intent"),
        "action_payload_hash": publication_snapshot_hash(payload),
        "resolved_candidate_hash": publication_snapshot_hash(resolved_candidate),
        "button_contract_enabled": bool(design_guide_button_contract_enabled(c)),
        "button_contract_blocking_reason": c.get("blocking_reason"),
    }


def apply_button_promotion_branch_predicates(
    branch_inputs: DesignGuideApplyButtonPromotionBranchInputs,
) -> DesignGuideApplyButtonPromotionBranchPredicates:
    """Return pure promotion/advisory predicates from resolved branch inputs."""

    if not bool(branch_inputs.promotion_branch_evaluated):
        return DesignGuideApplyButtonPromotionBranchPredicates()

    target_band_low = float(branch_inputs.target_band_low)
    target_band_high = float(branch_inputs.target_band_high)
    target_band_eps = float(branch_inputs.target_band_eps)
    evidence_util = branch_inputs.evidence_util
    expected_util = branch_inputs.expected_util

    target_band_promotion = bool(
        int(branch_inputs.target_band_candidate_count or 0) > 0
        and branch_inputs.evidence_updates
        and evidence_util is not None
        and target_band_low - target_band_eps <= float(evidence_util) <= target_band_high + target_band_eps
    )
    safe_strength_promotion = bool(
        branch_inputs.is_strength_required_fix
        and int(branch_inputs.safe_executor_backed_candidates_count or 0) > 0
        and branch_inputs.evidence_updates
        and evidence_util is not None
    )
    existing_contract_promotion = bool(
        expected_util is not None
        and branch_inputs.contract_updates
        and target_band_low - target_band_eps <= float(expected_util) <= target_band_high + target_band_eps
    )
    advisory_conversion = bool(
        branch_inputs.advisory_conversion_eligible
        and not target_band_promotion
        and not safe_strength_promotion
        and not existing_contract_promotion
    )
    decision_reason = None
    if target_band_promotion:
        decision_reason = "promoted_from_target_band_evidence"
    elif safe_strength_promotion:
        decision_reason = "promoted_from_safe_strength_evidence"
    elif existing_contract_promotion:
        decision_reason = "promoted_from_existing_button_contract"
    elif advisory_conversion:
        decision_reason = "converted_to_advisory"

    return DesignGuideApplyButtonPromotionBranchPredicates(
        target_band_promotion=target_band_promotion,
        safe_strength_promotion=safe_strength_promotion,
        existing_contract_promotion=existing_contract_promotion,
        advisory_conversion=advisory_conversion,
        decision_reason=decision_reason,
    )


def build_design_guide_apply_button_promotion_branch_setup(
    *,
    item_index: int,
    copied_item: dict | None,
    button_contract: dict | None,
    blocking_reason_override: str | None,
    snapshot_contract_binding: bool,
) -> DesignGuideApplyButtonPromotionBranchSetup:
    item = dict(copied_item or {})
    contract = dict(button_contract or {})
    block_reason = str(contract.get("blocking_reason") or blocking_reason_override or "").strip()
    promotion_branch_evaluated = bool(
        block_reason
        in {
            "missing_action_type",
            "candidate_preview_still_fails_active_check",
            "candidate_preview_not_compliant_after_active_failure",
            "candidate_preview_not_in_target_band_after_active_failure",
        }
        and str(item.get("guidance_intent") or "").strip() == "required_fix"
    )
    branch_inputs = DesignGuideApplyButtonPromotionBranchInputs(
        item_index=item_index,
        copied_item_identity=str(
            item.get("id")
            or item.get("candidate_id")
            or item.get("source_candidate_id")
            or item_index
        ),
        family=str(item.get("family") or "").strip().lower() or None,
        check_key=str(item.get("check_key") or "").strip().lower() or None,
        selected_action_family=str(item.get("selected_action_family") or "").strip().lower() or None,
        guidance_intent=str(item.get("guidance_intent") or "").strip() or None,
        current_action_type=str(item.get("action_type") or "").strip() or None,
        block_reason=block_reason or None,
        promotion_branch_evaluated=promotion_branch_evaluated,
        current_button_contract=dict(contract),
        current_button_contract_summary={
            "enabled": bool(design_guide_button_contract_enabled(contract)),
            "action_type": contract.get("action_type"),
            "family": contract.get("family"),
            "blocking_reason": contract.get("blocking_reason"),
            "updates_hash": publication_snapshot_hash(contract.get("updates") or {}),
        },
        current_action_state={
            "action_type": item.get("action_type"),
            "updates_hash": publication_snapshot_hash(item.get("updates") or {}),
            "action_payload_hash": publication_snapshot_hash(item.get("action_payload") or {}),
            "resolved_candidate_hash": publication_snapshot_hash(item.get("resolved_candidate") or {}),
        },
        advisory_conversion_eligible=promotion_branch_evaluated,
    )
    return DesignGuideApplyButtonPromotionBranchSetup(
        block_reason=block_reason,
        original_item_for_decision=dict(item) if snapshot_contract_binding else None,
        original_button_contract_for_decision=dict(contract) if snapshot_contract_binding else None,
        decision_reason="button_contract_bound_without_promotion",
        repair_promotion_occurred=False,
        advisory_conversion_occurred=False,
        promotion_branch_evaluated=promotion_branch_evaluated,
        branch_inputs=branch_inputs,
        branch_predicates=DesignGuideApplyButtonPromotionBranchPredicates(),
    )


def build_design_guide_apply_button_enriched_promotion_branch_inputs(
    *,
    item_index: int,
    copied_item: dict | None,
    button_contract: dict | None,
    block_reason: str | None,
    promotion_branch_evaluated: bool,
    contract_updates: dict | None,
    expected_util: Any,
    target_band_low: Any,
    target_band_high: Any,
    target_band_eps: Any,
    evidence_for_promotion: dict | None,
    evidence_util: Any,
    target_band_candidate_util: Any,
    closest_safe_candidate_util: Any,
    selected_candidate_util: Any,
    design_mode_goal: str | None,
    efficiency_target_band_source: str | None,
) -> DesignGuideApplyButtonPromotionEvidenceAssembly:
    """Build enriched branch inputs from already-resolved promotion evidence."""

    item = dict(copied_item or {})
    contract = dict(button_contract or {})
    evidence = dict(evidence_for_promotion or {})
    updates = dict(contract_updates or {})
    evidence_updates = dict(
        evidence.get("best_target_band_candidate_updates")
        or evidence.get("closest_safe_candidate_updates")
        or evidence.get("selected_candidate_updates")
        or {}
    )
    active_failures = list(evidence.get("active_failures") or [])
    strength_text = " ".join(
        str(part or "")
        for part in (
            item.get("title_main"),
            item.get("title"),
            item.get("check_key"),
            item.get("family"),
            " ".join(str(x or "") for x in active_failures),
        )
    ).lower()
    is_strength_required_fix = bool(
        "bend" in strength_text
        or "shear" in strength_text
        or "combined" in strength_text
    )
    evidence_candidate_id = (
        evidence.get("best_target_band_candidate_id")
        or evidence.get("closest_safe_candidate_id")
        or evidence.get("selected_candidate_id")
        or item.get("candidate_id")
        or item.get("source_candidate_id")
    )
    branch_inputs = DesignGuideApplyButtonPromotionBranchInputs(
        item_index=item_index,
        copied_item_identity=str(
            item.get("id")
            or item.get("candidate_id")
            or item.get("source_candidate_id")
            or item_index
        ),
        family=str(item.get("family") or "").strip().lower() or None,
        check_key=str(item.get("check_key") or "").strip().lower() or None,
        selected_action_family=str(item.get("selected_action_family") or "").strip().lower() or None,
        guidance_intent=str(item.get("guidance_intent") or "").strip() or None,
        current_action_type=str(item.get("action_type") or "").strip() or None,
        block_reason=block_reason or None,
        promotion_branch_evaluated=bool(promotion_branch_evaluated),
        current_button_contract=dict(contract),
        current_button_contract_summary={
            "enabled": bool(design_guide_button_contract_enabled(contract)),
            "action_type": contract.get("action_type"),
            "family": contract.get("family"),
            "blocking_reason": contract.get("blocking_reason"),
            "updates_hash": publication_snapshot_hash(contract.get("updates") or {}),
        },
        current_action_state={
            "action_type": item.get("action_type"),
            "updates_hash": publication_snapshot_hash(item.get("updates") or {}),
            "action_payload_hash": publication_snapshot_hash(item.get("action_payload") or {}),
            "resolved_candidate_hash": publication_snapshot_hash(item.get("resolved_candidate") or {}),
        },
        contract_updates=dict(updates),
        expected_util=expected_util,
        target_band_low=target_band_low,
        target_band_high=target_band_high,
        target_band_eps=target_band_eps,
        target_band_candidate_count=int(evidence.get("target_band_candidate_count") or 0),
        target_band_candidate_updates=dict(evidence.get("best_target_band_candidate_updates") or {}),
        target_band_candidate_util=target_band_candidate_util,
        closest_safe_candidate_updates=dict(evidence.get("closest_safe_candidate_updates") or {}),
        closest_safe_candidate_util=closest_safe_candidate_util,
        selected_candidate_updates=dict(evidence.get("selected_candidate_updates") or {}),
        selected_candidate_util=selected_candidate_util,
        evidence_updates=dict(evidence_updates),
        evidence_util=evidence_util,
        evidence_candidate_id=evidence_candidate_id,
        active_failures=active_failures,
        strength_text=strength_text,
        is_strength_required_fix=is_strength_required_fix,
        safe_executor_backed_candidates_count=int(evidence.get("safe_executor_backed_candidates_count") or 0),
        safe_candidate_count=int(evidence.get("safe_candidate_count") or 0),
        executable_candidate_count=int(evidence.get("executable_candidate_count") or 0),
        advisory_conversion_eligible=True,
        design_mode_goal=str(design_mode_goal or "").strip() or None,
        efficiency_target_band_source=efficiency_target_band_source,
        safe_executor_evidence_recounted=bool(
            evidence.get("active_fail_safe_executor_count_recomputed_from_candidate_rows")
        ),
    )
    return DesignGuideApplyButtonPromotionEvidenceAssembly(
        branch_inputs=branch_inputs,
        evidence_updates=dict(evidence_updates),
        evidence_util=evidence_util,
        evidence_candidate_id=evidence_candidate_id,
        strength_text=strength_text,
        is_strength_required_fix=is_strength_required_fix,
    )


def resolve_design_guide_apply_button_promotion_title_selection(
    *,
    check_key: str | None,
    family: str | None,
    strength_text: str | None,
    is_strength_required_fix: bool,
) -> DesignGuideApplyButtonPromotionTitleSelection:
    """Select promotion target family and title-main without formatting markup."""

    target_key = str(check_key or family or "").strip().lower()
    strength = str(strength_text or "")
    if target_key == "shear":
        return DesignGuideApplyButtonPromotionTitleSelection(
            target_family="shear",
            title_main="Shear capacity is low",
            decision_source="check_key_or_family_shear",
        )
    if target_key == "bending":
        return DesignGuideApplyButtonPromotionTitleSelection(
            target_family="bending",
            title_main="Bending capacity is low",
            decision_source="check_key_or_family_bending",
        )
    if bool(is_strength_required_fix) and "shear" in strength and "bend" in strength:
        return DesignGuideApplyButtonPromotionTitleSelection(
            target_family="combined",
            title_main="Bending and shear capacity are low",
            decision_source="strength_text_combined",
        )
    return DesignGuideApplyButtonPromotionTitleSelection(decision_source="no_target_title_selection")


def build_design_guide_apply_button_promotion_effect_plan(
    *,
    branch_predicates: DesignGuideApplyButtonPromotionBranchPredicates,
    current_decision_reason: str | None,
    current_contract_updates: dict | None,
    current_expected_util: Any,
    evidence_updates: dict | None,
    evidence_util: Any,
    evidence_for_promotion: dict | None,
    copied_item: dict | None,
) -> DesignGuideApplyButtonPromotionEffectPlan:
    """Resolve promotion effect scalars without mutating items or payloads."""

    predicates = branch_predicates or DesignGuideApplyButtonPromotionBranchPredicates()
    evidence = dict(evidence_for_promotion or {})
    item = dict(copied_item or {})
    has_evidence_target_candidate = bool(predicates.target_band_promotion)
    has_evidence_safe_strength_repair = bool(predicates.safe_strength_promotion)
    decision_reason = current_decision_reason
    decision_source = "promoted_from_existing_button_contract"
    if predicates.decision_reason:
        decision_reason = predicates.decision_reason
        decision_source = str(predicates.decision_reason)
    elif has_evidence_target_candidate:
        decision_reason = "promoted_from_target_band_evidence"
        decision_source = "promoted_from_target_band_evidence"
    elif has_evidence_safe_strength_repair:
        decision_reason = "promoted_from_safe_strength_evidence"
        decision_source = "promoted_from_safe_strength_evidence"
    else:
        decision_reason = "promoted_from_existing_button_contract"

    contract_updates = dict(current_contract_updates or {})
    expected_util = current_expected_util
    evidence_candidate_id = (
        item.get("candidate_id")
        or item.get("source_candidate_id")
        or "active_failure_strength_repair_candidate"
    )
    if has_evidence_target_candidate or has_evidence_safe_strength_repair:
        contract_updates = dict(evidence_updates or {})
        expected_util = evidence_util
        evidence_candidate_id = (
            evidence.get("best_target_band_candidate_id")
            or evidence.get("closest_safe_candidate_id")
            or evidence.get("selected_candidate_id")
            or item.get("candidate_id")
            or item.get("source_candidate_id")
            or "active_failure_strength_repair_candidate"
        )
    return DesignGuideApplyButtonPromotionEffectPlan(
        decision_reason=decision_reason,
        contract_updates=dict(contract_updates),
        expected_util=expected_util,
        evidence_candidate_id=evidence_candidate_id,
        rewrite_action_payload=bool(has_evidence_target_candidate or has_evidence_safe_strength_repair),
        repair_promotion_occurred=True,
        decision_source=decision_source,
    )


def build_design_guide_apply_button_promotion_decision(
    *,
    item_index: int,
    original_item: dict | None,
    final_item: dict | None,
    original_button_contract: dict | None,
    final_button_contract: dict | None,
    decision_reason: str | None,
    promotion_branch_evaluated: bool,
    repair_promotion_occurred: bool,
    advisory_conversion_occurred: bool,
    branch_inputs: DesignGuideApplyButtonPromotionBranchInputs | dict | None = None,
    branch_predicates: DesignGuideApplyButtonPromotionBranchPredicates | dict | None = None,
) -> DesignGuideApplyButtonPromotionDecision:
    original_item_d = dict(original_item or {})
    final_item_d = dict(final_item or {})
    original_contract = dict(original_button_contract or {})
    final_contract = dict(final_button_contract or {})
    original_action_payload = dict(original_item_d.get("action_payload") or {})
    final_action_payload = dict(final_item_d.get("action_payload") or {})
    original_keys = set(original_item_d.keys())
    final_keys = set(final_item_d.keys())
    shared_keys = sorted(original_keys & final_keys)
    copied_field_rewrites = [
        key
        for key in shared_keys
        if publication_snapshot_hash(original_item_d.get(key)) != publication_snapshot_hash(final_item_d.get(key))
    ]
    cta_reason = (
        final_contract.get("disabled_reason")
        or final_contract.get("blocking_reason")
        or final_item_d.get("blocking_reason")
        or final_item_d.get("cta_reason")
    )
    if hasattr(branch_inputs, "to_dict"):
        branch_inputs_d = dict(branch_inputs.to_dict())
    else:
        branch_inputs_d = dict(branch_inputs or {})
    if hasattr(branch_predicates, "to_dict"):
        branch_predicates_d = dict(branch_predicates.to_dict())
    else:
        branch_predicates_d = dict(branch_predicates or {})
    return DesignGuideApplyButtonPromotionDecision(
        item_index=int(item_index),
        input_item_identity=_apply_button_binding_item_identity(original_item_d, item_index),
        output_item_identity=_apply_button_binding_item_identity(final_item_d, item_index),
        promotion_branch_evaluated=bool(promotion_branch_evaluated),
        repair_promotion_occurred=bool(repair_promotion_occurred),
        advisory_conversion_occurred=bool(advisory_conversion_occurred),
        original_action_state=_apply_button_action_state(original_item_d, original_contract),
        final_action_state=_apply_button_action_state(final_item_d, final_contract),
        original_apply_payload_identity=_apply_button_binding_payload_identity(original_action_payload),
        original_apply_payload_hash=publication_snapshot_hash(
            original_action_payload or original_contract.get("updates") or {}
        ),
        final_apply_payload_identity=_apply_button_binding_payload_identity(final_action_payload),
        final_apply_payload_hash=publication_snapshot_hash(
            final_action_payload or final_contract.get("updates") or {}
        ),
        cta_label=final_item_d.get("primary_action") or final_item_d.get("cta_label") or final_contract.get("label"),
        cta_enabled=bool(design_guide_button_contract_enabled(final_contract)),
        cta_reason=cta_reason,
        original_button_contract_summary=_apply_button_contract_summary(original_contract),
        final_button_contract_summary=_apply_button_contract_summary(final_contract),
        decision_reason=str(decision_reason or "").strip() or None,
        branch_inputs=branch_inputs_d,
        branch_predicates=branch_predicates_d,
        copied_field_rewrites=copied_field_rewrites,
        added_fields=sorted(final_keys - original_keys),
        removed_fields=sorted(original_keys - final_keys),
    )


def append_design_guide_apply_button_promotion_output(
    *,
    output_items: list[dict] | None,
    promotion_decisions: list[DesignGuideApplyButtonPromotionDecision] | None,
    snapshot_contract_binding: bool,
    item_index: int,
    final_item: dict,
    final_button_contract: dict | None,
    original_item: dict | None,
    original_button_contract: dict | None,
    decision_reason: str | None,
    promotion_branch_evaluated: bool,
    repair_promotion_occurred: bool,
    advisory_conversion_occurred: bool,
    branch_inputs: DesignGuideApplyButtonPromotionBranchInputs | dict | None = None,
    branch_predicates: DesignGuideApplyButtonPromotionBranchPredicates | dict | None = None,
) -> tuple[list[dict], list[DesignGuideApplyButtonPromotionDecision]]:
    next_output_items = list(output_items or [])
    next_promotion_decisions = list(promotion_decisions or [])
    if snapshot_contract_binding:
        next_promotion_decisions.append(
            build_design_guide_apply_button_promotion_decision(
                item_index=item_index,
                original_item=original_item,
                final_item=final_item,
                original_button_contract=original_button_contract,
                final_button_contract=dict(final_item.get("button_contract") or final_button_contract or {}),
                decision_reason=decision_reason,
                promotion_branch_evaluated=promotion_branch_evaluated,
                repair_promotion_occurred=repair_promotion_occurred,
                advisory_conversion_occurred=advisory_conversion_occurred,
                branch_inputs=branch_inputs,
                branch_predicates=branch_predicates,
            )
        )
    next_output_items.append(final_item)
    return next_output_items, next_promotion_decisions


def apply_button_promotion_rewrite_item(
    *,
    copied_item: dict | None,
    button_contract: dict | None,
    contract_updates: dict | None,
    expected_util: Any,
    evidence_candidate_id: Any,
    candidate_search_evidence: dict | None = None,
    target_family: str | None = None,
    target_title_main: str | None = None,
    target_title: str | None = None,
    rewrite_action_payload: bool = False,
) -> DesignGuideApplyButtonPromotionRewriteResult:
    """Rewrite an already-promoted copied item without deciding promotion."""

    out = dict(copied_item or {})
    contract = dict(button_contract or {})
    updates = dict(contract_updates or {})
    rewritten_fields: set[str] = set()

    if rewrite_action_payload:
        candidate_id = (
            evidence_candidate_id
            or out.get("candidate_id")
            or out.get("source_candidate_id")
            or "active_failure_strength_repair_candidate"
        )
        out["action_type"] = "apply_resolved_candidate"
        out["updates"] = dict(updates)
        out["candidate_id"] = candidate_id
        out["source_candidate_id"] = candidate_id
        out["resolved_candidate"] = {
            "updates": dict(updates),
            "action_type": "apply_resolved_candidate",
            "label": str(out.get("title_main") or "Apply Design Guide repair"),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "candidate_post_util": expected_util,
            "candidate_search_evidence": dict(candidate_search_evidence or {}),
        }
        rewritten_fields.update(
            {
                "action_type",
                "updates",
                "candidate_id",
                "source_candidate_id",
                "resolved_candidate",
            }
        )

    family = str(target_family or "").strip().lower()
    if family:
        if target_title_main is not None:
            out["title_main"] = target_title_main
            rewritten_fields.add("title_main")
        if target_title is not None:
            out["title"] = target_title
            rewritten_fields.add("title")
        out["family"] = family
        out["check_key"] = family
        out["selected_action_family"] = family
        rewritten_fields.update({"family", "check_key", "selected_action_family"})

    active_repair_family = str(out.get("family") or out.get("check_key") or "").strip().lower()
    final_contract = {
        **contract,
        "action_type": "apply_resolved_candidate",
        "family": active_repair_family or contract.get("family"),
        "updates": dict(updates),
        "expected_util": expected_util,
        "actionable": True,
        "preview_pass": True,
        "blocking_reason": None,
        "source_candidate_id": out.get("source_candidate_id"),
        "candidate_id": out.get("candidate_id"),
    }
    out["button_contract"] = dict(final_contract)
    rewritten_fields.add("button_contract")

    return DesignGuideApplyButtonPromotionRewriteResult(
        item=out,
        button_contract=final_contract,
        target_family=family or None,
        action_payload_rewritten=bool(rewrite_action_payload),
        rewritten_fields=sorted(rewritten_fields),
    )


def build_design_guide_apply_button_binding_result(
    *,
    input_items: list,
    output_items: list[dict],
    input_hashes_before: list[str],
    input_object_ids: list[int],
    state_fingerprint: Any,
    button_contract_inputs: list[DesignGuideApplyButtonContractInputs] | None = None,
    button_contract_results: list[DesignGuideApplyButtonContractResult] | None = None,
    button_contract_scalars: list[DesignGuideButtonContractScalars] | None = None,
    button_contract_actionability_probe_inputs: list[DesignGuideButtonContractActionabilityProbeInputs] | None = None,
    button_contract_actionability_probe_outputs: list[DesignGuideButtonContractActionabilityProbeOutputs] | None = None,
    button_contract_actionability_resolutions: list[DesignGuideButtonContractActionabilityResolution] | None = None,
    button_contract_actionability_helper_outputs: list[DesignGuideButtonContractActionabilityHelperOutputs] | None = None,
    button_contract_actionability_inputs: list[DesignGuideButtonContractActionabilityInputs] | None = None,
    button_contract_actionability_predicates: list[DesignGuideButtonContractActionabilityPredicates] | None = None,
    button_contract_actionability_applications: list[DesignGuideButtonContractActionabilityApplication] | None = None,
    button_contract_actionability_decisions: list[DesignGuideButtonContractActionabilityDecision] | None = None,
    button_contract_update_resolution_inputs: list[DesignGuideButtonContractUpdateResolutionInputs] | None = None,
    button_contract_update_resolution_decisions: list[DesignGuideButtonContractUpdateResolutionDecision] | None = None,
    button_contract_update_resolutions: list[DesignGuideButtonContractUpdateResolution] | None = None,
    button_contract_work_mutations: list[DesignGuideButtonContractWorkMutation] | None = None,
    promotion_decisions: list[DesignGuideApplyButtonPromotionDecision] | None = None,
    safe_executor_evidence_rows: list[DesignGuideSafeExecutorEvidenceRows] | None = None,
) -> DesignGuideApplyButtonBindingResult:
    input_after_hashes = [
        publication_snapshot_hash(item) if isinstance(item, dict) else publication_snapshot_hash(str(item))
        for item in input_items
    ]
    before_snapshots = [
        _apply_button_binding_item_snapshot(item, index)
        for index, item in enumerate(input_items)
        if isinstance(item, dict)
    ]
    after_snapshots = [
        _apply_button_binding_item_snapshot(item, index)
        for index, item in enumerate(output_items)
        if isinstance(item, dict)
    ]
    added_fields_by_item: list[dict[str, Any]] = []
    for index, after in enumerate(after_snapshots):
        before_keys = set(before_snapshots[index].get("keys") or []) if index < len(before_snapshots) else set()
        after_keys = set(after.get("keys") or [])
        added_fields_by_item.append(
            {
                "index": index,
                "identity": after.get("identity"),
                "added_keys": sorted(after_keys - before_keys),
                "contract_or_debug_keys": list(after.get("debug_keys") or []),
            }
        )
    same_object_indices = [
        index
        for index, item in enumerate(output_items)
        if index < len(input_object_ids) and isinstance(item, dict) and id(item) == input_object_ids[index]
    ]
    primary_after = after_snapshots[0] if after_snapshots else {}
    contract_summary = {
        "enabled": primary_after.get("button_contract_enabled"),
        "disabled_reason": primary_after.get("disabled_reason"),
        "action_type": primary_after.get("button_contract_action_type"),
        "contract_hash": primary_after.get("button_contract_hash"),
        "updates_hash": primary_after.get("button_contract_updates_hash"),
        "keys": primary_after.get("button_contract_keys") or [],
    }
    return DesignGuideApplyButtonBindingResult(
        bound_items=list(output_items),
        selected_family=primary_after.get("selected_family"),
        published_family=primary_after.get("published_family"),
        apply_family=primary_after.get("apply_family"),
        cta_label=primary_after.get("cta_label"),
        cta_enabled=primary_after.get("cta_enabled"),
        cta_reason=primary_after.get("cta_reason"),
        button_contract_enabled=primary_after.get("button_contract_enabled"),
        disabled_reason=primary_after.get("disabled_reason"),
        state_fingerprint=state_fingerprint,
        apply_payload_identity=primary_after.get("apply_payload_identity"),
        apply_payload_hash=primary_after.get("apply_payload_hash"),
        candidate_payload_identity=primary_after.get("candidate_payload_identity"),
        candidate_payload_hash=primary_after.get("candidate_payload_hash"),
        button_contract_summary=contract_summary,
        input_item_count=len(input_items),
        output_item_count=len(output_items),
        item_ids_before=[
            _apply_button_binding_item_identity(item, index)
            for index, item in enumerate(input_items)
        ],
        item_ids_after=[
            _apply_button_binding_item_identity(item, index)
            for index, item in enumerate(output_items)
        ],
        input_hashes_before=list(input_hashes_before),
        input_hashes_after_call=input_after_hashes,
        input_items_mutated_in_place=input_after_hashes != list(input_hashes_before),
        output_reuses_input_object=bool(same_object_indices),
        same_object_indices=same_object_indices,
        contract_debug_data_added_to_items=added_fields_by_item,
        button_contract_inputs=list(button_contract_inputs or []),
        button_contract_results=list(button_contract_results or []),
        button_contract_scalars=list(button_contract_scalars or []),
        button_contract_actionability_probe_inputs=list(button_contract_actionability_probe_inputs or []),
        button_contract_actionability_probe_outputs=list(button_contract_actionability_probe_outputs or []),
        button_contract_actionability_resolutions=list(button_contract_actionability_resolutions or []),
        button_contract_actionability_helper_outputs=list(button_contract_actionability_helper_outputs or []),
        button_contract_actionability_inputs=list(button_contract_actionability_inputs or []),
        button_contract_actionability_predicates=list(button_contract_actionability_predicates or []),
        button_contract_actionability_applications=list(button_contract_actionability_applications or []),
        button_contract_actionability_decisions=list(button_contract_actionability_decisions or []),
        button_contract_update_resolution_inputs=list(button_contract_update_resolution_inputs or []),
        button_contract_update_resolution_decisions=list(button_contract_update_resolution_decisions or []),
        button_contract_update_resolutions=list(button_contract_update_resolutions or []),
        button_contract_work_mutations=list(button_contract_work_mutations or []),
        promotion_decisions=list(promotion_decisions or []),
        safe_executor_evidence_rows=list(safe_executor_evidence_rows or []),
        items_before=before_snapshots,
        items_after=after_snapshots,
    )


def build_design_guide_apply_button_binding_result_from_records(
    *,
    snapshot_contract_binding: bool,
    input_items: list,
    output_items: list[dict],
    input_hashes_before: list[str],
    input_object_ids: list[int],
    state_fingerprint: Any,
    button_contract_inputs: list[DesignGuideApplyButtonContractInputs] | None = None,
    button_contract_results: list[DesignGuideApplyButtonContractResult] | None = None,
    button_contract_scalars: list[DesignGuideButtonContractScalars] | None = None,
    button_contract_actionability_probe_inputs: list[DesignGuideButtonContractActionabilityProbeInputs] | None = None,
    button_contract_actionability_probe_outputs: list[DesignGuideButtonContractActionabilityProbeOutputs] | None = None,
    button_contract_actionability_resolutions: list[DesignGuideButtonContractActionabilityResolution] | None = None,
    button_contract_actionability_helper_outputs: list[DesignGuideButtonContractActionabilityHelperOutputs] | None = None,
    button_contract_actionability_inputs: list[DesignGuideButtonContractActionabilityInputs] | None = None,
    button_contract_actionability_predicates: list[DesignGuideButtonContractActionabilityPredicates] | None = None,
    button_contract_actionability_applications: list[DesignGuideButtonContractActionabilityApplication] | None = None,
    button_contract_actionability_decisions: list[DesignGuideButtonContractActionabilityDecision] | None = None,
    button_contract_update_resolution_inputs: list[DesignGuideButtonContractUpdateResolutionInputs] | None = None,
    button_contract_update_resolution_decisions: list[DesignGuideButtonContractUpdateResolutionDecision] | None = None,
    button_contract_update_resolutions: list[DesignGuideButtonContractUpdateResolution] | None = None,
    button_contract_work_mutations: list[DesignGuideButtonContractWorkMutation] | None = None,
    promotion_decisions: list[DesignGuideApplyButtonPromotionDecision] | None = None,
    safe_executor_evidence_rows: list[DesignGuideSafeExecutorEvidenceRows] | None = None,
) -> DesignGuideApplyButtonBindingResult:
    if snapshot_contract_binding:
        return build_design_guide_apply_button_binding_result(
            input_items=input_items,
            output_items=output_items,
            input_hashes_before=input_hashes_before,
            input_object_ids=input_object_ids,
            state_fingerprint=state_fingerprint,
            button_contract_inputs=button_contract_inputs,
            button_contract_results=button_contract_results,
            button_contract_scalars=button_contract_scalars,
            button_contract_actionability_probe_inputs=button_contract_actionability_probe_inputs,
            button_contract_actionability_probe_outputs=button_contract_actionability_probe_outputs,
            button_contract_actionability_resolutions=button_contract_actionability_resolutions,
            button_contract_actionability_helper_outputs=button_contract_actionability_helper_outputs,
            button_contract_actionability_inputs=button_contract_actionability_inputs,
            button_contract_actionability_predicates=button_contract_actionability_predicates,
            button_contract_actionability_applications=button_contract_actionability_applications,
            button_contract_actionability_decisions=button_contract_actionability_decisions,
            button_contract_update_resolution_inputs=button_contract_update_resolution_inputs,
            button_contract_update_resolution_decisions=button_contract_update_resolution_decisions,
            button_contract_update_resolutions=button_contract_update_resolutions,
            button_contract_work_mutations=button_contract_work_mutations,
            promotion_decisions=promotion_decisions,
            safe_executor_evidence_rows=safe_executor_evidence_rows,
        )
    return DesignGuideApplyButtonBindingResult(
        bound_items=list(output_items),
        input_item_count=len(input_items),
        output_item_count=len(output_items),
        button_contract_inputs=list(button_contract_inputs or []),
        button_contract_results=list(button_contract_results or []),
        button_contract_scalars=list(button_contract_scalars or []),
        button_contract_actionability_probe_inputs=list(button_contract_actionability_probe_inputs or []),
        button_contract_actionability_probe_outputs=list(button_contract_actionability_probe_outputs or []),
        button_contract_actionability_resolutions=list(button_contract_actionability_resolutions or []),
        button_contract_actionability_helper_outputs=list(button_contract_actionability_helper_outputs or []),
        button_contract_actionability_inputs=list(button_contract_actionability_inputs or []),
        button_contract_actionability_predicates=list(button_contract_actionability_predicates or []),
        button_contract_actionability_applications=list(button_contract_actionability_applications or []),
        button_contract_actionability_decisions=list(button_contract_actionability_decisions or []),
        button_contract_update_resolution_inputs=list(button_contract_update_resolution_inputs or []),
        button_contract_update_resolution_decisions=list(button_contract_update_resolution_decisions or []),
        button_contract_update_resolutions=list(button_contract_update_resolutions or []),
        button_contract_work_mutations=list(button_contract_work_mutations or []),
        safe_executor_evidence_rows=list(safe_executor_evidence_rows or []),
    )


def publication_item_family(item: dict | None) -> str:
    if not isinstance(item, dict):
        return "unknown"
    explicit_family = str(
        item.get("selected_action_family")
        or item.get("family")
        or item.get("check_key")
        or ""
    ).strip().lower()
    guidance_intent = str(item.get("guidance_intent") or "").strip()
    final_state_class = str(item.get("final_state_class") or "").strip()
    if (
        (
            guidance_intent in {"required_fix", "specific_blocker"}
            or final_state_class == "blocker"
            or bool(item.get("exact_blockers_by_family"))
        )
        and explicit_family in {"bending", "shear", "combined", "crack", "deflection", "serviceability"}
    ):
        return explicit_family
    action_type = str(item.get("action_type") or "").strip()
    if action_type in {
        "apply_shear_recommendation",
        "increase_link_spacing",
        "reduce_number_of_legs",
        "reduce_link_spacing",
    }:
        return "shear"
    if action_type in {
        "apply_bottom_recommendation",
        "reduce_bottom_reinforcement",
        "reduce_bar_spacing",
        "apply_geometry_recommendation",
        "increase_depth",
        "increase_width",
        "tighten_geometry",
    }:
        return "bending"
    payload = dict(item.get("action_payload") or {})
    updates = dict(payload.get("updates") or payload.get("resolved_candidate_updates") or {})
    keys = set(updates.keys())

    shear_keys = {"lig_d", "lig_legs", "s_lig"}
    bottom_keys = {"db_bot", "db_bot_1", "db_bot_2", "bot1_count", "bot2_count", "nb_bot"}
    geom_keys = {"b", "D"}

    has_shear = bool(keys & shear_keys)
    has_bottom = bool(keys & bottom_keys)
    has_geom = bool(keys & geom_keys)

    if has_shear and (has_bottom or has_geom):
        return "combined"
    if has_shear:
        return "shear"
    if has_bottom or has_geom:
        return "bending"
    return "other"


def design_guide_button_contract_enabled(contract: dict | None) -> bool:
    c = contract if isinstance(contract, dict) else {}
    return bool(
        c.get("actionable")
        and dict(c.get("updates") or {})
        and bool(c.get("preview_pass"))
        and c.get("blocking_reason") is None
    )


def design_guide_blocker_reason(item: dict | None) -> str:
    if not isinstance(item, dict):
        return "specific_blocker"
    contract = dict(item.get("button_contract") or {})
    if str(contract.get("blocking_reason") or "").strip():
        return str(contract.get("blocking_reason") or "").strip()
    for source in (
        item.get("primary_action"),
        item.get("secondary_action"),
        item.get("reasoning"),
        item.get("why"),
        item.get("detail"),
    ):
        if str(source or "").strip():
            return str(source or "").strip()
    blockers = item.get("exact_blockers_by_family") or item.get("post_click_exact_blockers_by_family") or {}
    if isinstance(blockers, dict):
        for blocker in blockers.values():
            if isinstance(blocker, dict) and str(blocker.get("reason") or "").strip():
                return str(blocker.get("reason") or "").strip()
    return "specific_blocker"


def disabled_design_guide_button_contract(
    item: dict | None,
    *,
    family: str | None = None,
    reason: str | None = None,
) -> dict:
    resolved_family = str(family or publication_item_family(item) or "other").strip() or "other"
    return {
        "enabled": False,
        "actionable": False,
        "action_type": None,
        "family": resolved_family,
        "updates": {},
        "preview_pass": False,
        "expected_util": None,
        "blocking_reason": str(reason or "specific_blocker").strip() or "specific_blocker",
        "source_candidate_id": None,
        "candidate_id": None,
    }


def _stable_fingerprint_for_payload(payload: dict | None) -> tuple:
    serialised: list[tuple[str, str]] = []
    for key, value in sorted(dict(payload or {}).items(), key=lambda item: str(item[0])):
        try:
            encoded = json.dumps(value, sort_keys=True, default=str)
        except Exception:
            encoded = repr(value)
        serialised.append((str(key), encoded))
    return tuple(serialised)


def normalise_design_guide_candidate_id(*values: object, family: str | None = None, updates: dict | None = None) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    try:
        fp = _stable_fingerprint_for_payload({"family": str(family or "").strip(), "updates": dict(updates or {})})
        return f"visible_primary:{fp}"
    except Exception:
        return "visible_primary:unidentified"


def is_shear_fail_governs_identity(*sources: object) -> bool:
    dict_sources = [source for source in sources if isinstance(source, dict)]
    if not dict_sources:
        return False
    family_keys = (
        "selected_family_id",
        "published_family_id",
        "cta_family_id",
        "governing_state",
        "governing_family",
        "family_id",
    )
    text_values: list[str] = []
    for source in dict_sources:
        for key in family_keys:
            text_values.append(str(source.get(key) or "").strip())
        evidence = source.get("candidate_search_evidence")
        if isinstance(evidence, dict):
            for key in family_keys + ("family_route_owner",):
                text_values.append(str(evidence.get(key) or "").strip())
    upper_values = {value.upper() for value in text_values if value}
    if "COMBINED_BENDING_SHEAR_FAIL" in upper_values:
        return False
    if "SHEAR_FAIL_GOVERNS" in upper_values:
        return True
    route_owner = " ".join(text_values).lower()
    if "design_brain.families.shear_fail" not in route_owner:
        return False
    simple_families = {
        str(source.get("family") or source.get("selected_action_family") or source.get("check_key") or "").strip().lower()
        for source in dict_sources
    }
    return bool(simple_families & {"", "shear", "unknown"})


def shear_fail_governs_payload_id(*sources: object) -> str:
    updates: dict = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in (
            "updates",
            "visible_updates",
            "button_contract_updates",
            "selected_action_updates",
            "recommended_updates",
            "proposed_updates",
        ):
            candidate_updates = source.get(key)
            if isinstance(candidate_updates, dict) and candidate_updates:
                updates = dict(candidate_updates)
                break
        if updates:
            break
    try:
        fp = _stable_fingerprint_for_payload(
            {
                "family": "SHEAR_FAIL_GOVERNS",
                "owner": "shear_fail",
                "action": "repair",
                "updates": dict(updates),
            }
        )
    except Exception:
        fp = "unidentified"
    return f"SHEAR_FAIL_GOVERNS:shear_fail:repair:{fp}"


def selected_family_id_from_identity_sources(*sources: object) -> str:
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in ("selected_family_id", "published_family_id", "cta_family_id", "governing_family"):
            text = str(source.get(key) or "").strip()
            if text:
                return text
        evidence = source.get("candidate_search_evidence")
        if isinstance(evidence, dict):
            for key in ("selected_family_id", "published_family_id", "cta_family_id", "governing_family"):
                text = str(evidence.get(key) or "").strip()
                if text:
                    return text
    return ""


def generic_family_owned_payload_id(selected_family_id: str, *sources: object) -> str:
    family_id = str(selected_family_id or "").strip()
    updates: dict = {}
    action_kind = "action"
    if "FAIL" in family_id:
        action_kind = "repair"
    elif "OVERDESIGN" in family_id:
        action_kind = "optimisation"
    elif "TARGET" in family_id:
        action_kind = "target_band"
    elif "EXACT" in family_id:
        action_kind = "exact_stop"
    for source in sources:
        if not isinstance(source, dict):
            continue
        text = " ".join(str(source.get(key) or "") for key in ("title", "title_main", "primary_action", "guidance_intent")).lower()
        if "cleanup" in text and "FAIL" not in family_id:
            action_kind = "cleanup"
        for key in ("updates", "visible_updates", "button_contract_updates", "selected_action_updates"):
            candidate_updates = source.get(key)
            if isinstance(candidate_updates, dict) and candidate_updates:
                updates = dict(candidate_updates)
                break
        if updates:
            break
    try:
        fp = _stable_fingerprint_for_payload({"family": family_id, "action": action_kind, "updates": dict(updates)})
    except Exception:
        fp = "unidentified"
    return f"{family_id}:{action_kind}:{fp}" if family_id else f"visible_primary:{fp}"


def _publication_int_from_state(state: dict, key: str, default: int) -> int:
    value = state.get(key)
    if value is None:
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def design_guide_primary_apply_state_fingerprint_from_state(
    state: dict | None,
    *,
    cache_fingerprint: Callable[[dict], Any],
    fallback_state: dict | None = None,
) -> str:
    source = dict(state or {})
    try:
        bot2_count = _publication_int_from_state(
            source,
            "bot2_count",
            _publication_int_from_state(source, "bot_row_2_bars", 0),
        )
        bot_row_2_bars = _publication_int_from_state(source, "bot_row_2_bars", bot2_count)
        if bot2_count <= 0 and bot_row_2_bars <= 0:
            source["db_bot_2"] = 0
            source["bot_row_2_dia"] = 0
        return str(cache_fingerprint(source))
    except Exception:
        return str(cache_fingerprint(dict(fallback_state if fallback_state is not None else state or {})))


def guidance_item_is_active_strength_repair_action(item: dict | None) -> bool:
    if not isinstance(item, dict):
        return False
    action_type = str(item.get("action_type") or "").strip()
    contract = item.get("button_contract") if isinstance(item.get("button_contract"), dict) else {}
    family = str(
        item.get("selected_action_family")
        or item.get("family")
        or item.get("check_key")
        or (contract or {}).get("family")
        or ""
    ).strip().lower()
    title_text = " ".join(
        str(item.get(key) or "")
        for key in ("title_main", "title", "primary_action", "secondary_action")
    ).lower()
    active_strength_title = bool(
        "bending capacity is low" in title_text
        or "shear capacity is low" in title_text
        or "bending and shear capacity" in title_text
    )
    return bool(
        action_type == "apply_resolved_candidate"
        and family in {"bending", "shear", "combined"}
        and (
            str(item.get("guidance_intent") or "").strip() == "required_fix"
            or active_strength_title
        )
    )


def normalise_final_visible_design_guide_item(item: dict | None) -> dict:
    """Ensure a final visible Design Guide item has the card renderer metadata."""
    if not isinstance(item, dict):
        return {}
    out = dict(item)
    missing: list[str] = []

    def _set_default(key: str, value) -> None:
        if key not in out or out.get(key) in (None, ""):
            out[key] = value
            missing.append(key)

    title = str(out.get("title_main") or out.get("title") or "").strip()
    text_blob = " ".join(
        str(out.get(key) or "")
        for key in (
            "title_main",
            "title",
            "title_sub",
            "primary_action",
            "secondary_action",
            "reasoning",
            "guidance_why",
        )
    ).lower()
    button_contract = out.get("button_contract") if isinstance(out.get("button_contract"), dict) else {}
    family = str(
        out.get("family")
        or out.get("selected_action_family")
        or out.get("check_key")
        or button_contract.get("family")
        or ""
    ).strip().lower()
    if not family:
        if "bending and shear" in text_blob or "combined" in text_blob:
            family = "combined"
        elif "shear" in text_blob:
            family = "shear"
        elif "bending" in text_blob or "bottom reinforcement" in text_blob:
            family = "bending"
        else:
            family = "general"
    _set_default("family", family)
    _set_default("check_key", family)

    action_type = str(out.get("action_type") or button_contract.get("action_type") or "").strip()
    contract_actionable = bool(button_contract.get("actionable") or button_contract.get("enabled"))
    exact_blockers = out.get("exact_blockers_by_family")
    has_exact_blocker = isinstance(exact_blockers, dict) and bool(exact_blockers)
    final_state = str(out.get("final_state_type") or out.get("final_state_class") or "").strip().lower()
    status_text = str(out.get("status") or "").strip().upper()
    bucket_text = str(out.get("bucket") or "").strip().lower()

    if not bucket_text:
        if (
            status_text in {"FAIL", "ERROR", "CRITICAL"}
            or str(out.get("guidance_intent") or "").strip() == "required_fix"
            or guidance_item_is_active_strength_repair_action(out)
        ):
            bucket_text = "fail"
        elif (
            has_exact_blocker
            or "blocked" in text_blob
            or "no further safe" in text_blob
            or final_state == "blocker"
        ):
            bucket_text = "efficiency"
        elif (
            "accepted" in text_blob
            or "target achieved" in text_blob
            or "best safe result" in text_blob
            or "green" in final_state
            or str(out.get("design_guide_terminal_state") or "").strip()
        ):
            bucket_text = "pass"
        elif action_type and contract_actionable:
            bucket_text = "efficiency"
        elif status_text in {"PASS", "GOOD", "OK"}:
            bucket_text = "pass"
        else:
            bucket_text = "warn"
        _set_default("bucket", bucket_text)
    else:
        out["bucket"] = bucket_text

    if not status_text:
        if bucket_text == "fail":
            status_text = "FAIL"
        elif bucket_text == "warn":
            status_text = "WARN"
        elif bucket_text == "efficiency":
            status_text = "EFFICIENCY"
        elif bucket_text == "start":
            status_text = "START"
        else:
            status_text = "PASS"
        _set_default("status", status_text)
    else:
        out["status"] = status_text

    if not title:
        if bucket_text == "fail":
            title = "Design repair required"
        elif has_exact_blocker:
            title = "Further cleanup blocked"
        elif action_type and contract_actionable:
            title = "One-click design update available"
        elif bucket_text == "pass":
            title = "Design accepted"
        else:
            title = "Design guidance"
    _set_default("title_main", title)
    _set_default("title", title)
    _set_default(
        "guidance_intent",
        (
            "required_fix"
            if bucket_text == "fail"
            else ("specific_blocker" if has_exact_blocker else ("already_efficient" if bucket_text == "pass" else "efficiency_tightening"))
        ),
    )
    _set_default("primary_action", "Review Design Guide recommendation")
    _set_default("secondary_action", "")
    _set_default("reasoning", "")
    if not isinstance(out.get("button_contract"), dict):
        out["button_contract"] = {}
        missing.append("button_contract")
    if "display_truth" not in out or out.get("display_truth") is None:
        out["display_truth"] = {}
        missing.append("display_truth")
    if missing:
        out["render_metadata_normalised"] = True
        out["render_metadata_missing_fields"] = sorted(set(missing))
    return out


def active_failure_exact_blockers_for_families(
    families: list[str] | set[str] | tuple[str, ...],
    *,
    overview: dict | None = None,
    evidence: dict | None = None,
    primary_family: str | None = None,
    primary_reason: str | None = None,
    final_accepted_min_family_util: float = 0.85,
    efficiency_target_util_min: float = 0.85,
    efficiency_target_util_max: float = 1.0,
) -> dict[str, dict]:
    return _repair_active_failure_exact_blockers_for_families(
        families,
        overview=overview,
        evidence=evidence,
        primary_family=primary_family,
        primary_reason=primary_reason,
        final_accepted_min_family_util=float(final_accepted_min_family_util),
        efficiency_target_util_min=float(efficiency_target_util_min),
        efficiency_target_util_max=float(efficiency_target_util_max),
    )


def active_failure_blocker_visible_reason_text(
    exact_blockers: dict | None,
    active_failures: list[str] | set[str] | tuple[str, ...],
) -> str:
    return _repair_active_failure_blocker_visible_reason_text(exact_blockers, active_failures)


def finalize_design_guide_active_failure_blocker_publication(
    *,
    blocker: dict | None,
    fallback_item: dict | None,
    active_family: str,
    active_title: str,
    active_failures: list[str] | set[str] | tuple[str, ...],
    final_overview: dict | None,
    item_state_fingerprint: str,
    result_state_fingerprint: str,
    debug_probe: dict | None,
) -> dict:
    """Finalize the terminal active-failure blocker publication route."""

    active_family_text = str(active_family or "").strip().lower()
    active_failures_list = sorted(
        {
            str(family or "").strip().lower()
            for family in list(active_failures or [])
            if str(family or "").strip()
        }
    )
    out_blocker = blocker
    if isinstance(out_blocker, dict):
        out_blocker = dict(out_blocker)
        out_blocker["family"] = active_family_text
        out_blocker["check_key"] = active_family_text
        if active_family_text == "combined":
            out_blocker["title_main"] = out_blocker.get("title_main") or "Bending and shear repair blocked"
            out_blocker["title"] = out_blocker.get("title") or "Bending and shear repair blocked"
        elif active_family_text == "shear":
            out_blocker["title_main"] = out_blocker.get("title_main") or "Shear repair blocked by shear/detailing limits"
            out_blocker["title"] = out_blocker.get("title") or "Shear repair blocked by shear/detailing limits"
        else:
            out_blocker["title_main"] = out_blocker.get("title_main") or "Bending repair blocked by reinforcement/detailing limits"
            out_blocker["title"] = out_blocker.get("title") or "Bending repair blocked by reinforcement/detailing limits"
        blocker_evidence = dict(out_blocker.get("candidate_search_evidence") or {})
        evidence_scope = str(
            blocker_evidence.get("active_fail_repair_search_scope")
            or blocker_evidence.get("search_scope")
            or ""
        ).strip().lower()
        cleanup_scope_used_for_active_fail = any(
            token in evidence_scope
            for token in (
                "cleanup",
                "final_threshold",
                "overdesign",
            )
        ) and not evidence_scope.startswith("active_fail_")
        if cleanup_scope_used_for_active_fail:
            blocker_evidence = {
                "search_scope": "active_fail_repair_search_missing",
                "active_fail_repair_search_scope": "active_fail_repair_search_missing",
                "active_failures": list(active_failures_list),
                "repair_search_ran": False,
                "repair_search_exhaustive": False,
                "active_fail_blocker_invalid_reason": (
                    "cleanup_or_final_threshold_evidence_cannot_validate_active_fail_blocker"
                ),
                "cleanup_evidence_rejected_for_active_fail": True,
                "rejected_cleanup_search_scope": evidence_scope,
            }
            out_blocker["candidate_search_evidence"] = dict(blocker_evidence)
        existing_exact_blockers = dict(
            {}
            if cleanup_scope_used_for_active_fail
            else (
                out_blocker.get("exact_blockers_by_family")
                or out_blocker.get("post_click_exact_blockers_by_family")
                or blocker_evidence.get("exact_blockers_by_family")
                or {}
            )
        )
        missing_active_blocker_families = sorted(set(active_failures_list) - set(existing_exact_blockers))
        if missing_active_blocker_families:
            blocker_evidence["active_fail_blocker_missing_family_proof_before_finalisation"] = list(
                missing_active_blocker_families
            )
        generated_exact_blockers = (
            {}
            if cleanup_scope_used_for_active_fail
            else active_failure_exact_blockers_for_families(
                list(active_failures_list),
                overview=dict(final_overview or {}),
                evidence=blocker_evidence,
                primary_family=active_family_text if active_family_text in {"bending", "shear"} else None,
                primary_reason=str(
                    out_blocker.get("primary_action")
                    or out_blocker.get("secondary_action")
                    or out_blocker.get("reasoning")
                    or ""
                ).strip()
                or None,
            )
        )
        exact_blockers = dict(generated_exact_blockers)
        exact_blockers.update(existing_exact_blockers)
        blocker_evidence.update(
            {
                "active_failures": list(active_failures_list),
                "repair_search_ran": True,
                "repair_search_exhaustive": bool(
                    blocker_evidence.get("repair_search_exhaustive")
                    or blocker_evidence.get("candidate_search_exhaustive")
                    or blocker_evidence.get("cleanup_search_exhaustive")
                ),
                "cleanup_search_ran": False,
                "cleanup_search_exhaustive": False,
                "local_cleanup_search_ran": False,
                "local_cleanup_search_exhaustive": False,
                "exact_blockers_by_family": dict(exact_blockers),
                "post_click_exact_blockers_by_family": dict(exact_blockers),
            }
        )
        visible_blocker_reasons = active_failure_blocker_visible_reason_text(
            exact_blockers,
            list(active_failures_list),
        )
        out_blocker.update(
            {
                "bucket": "fail",
                "status": "FAIL",
                "guidance_intent": "specific_blocker",
                "final_state_class": "blocker",
                "active_under_capacity_blocker": True,
                "active_under_capacity_blocker_family": active_family_text,
                "active_fail_blocker_missing_family_proof_before_finalisation": list(
                    missing_active_blocker_families
                ),
                "exact_blockers_by_family": dict(exact_blockers),
                "post_click_exact_blockers_by_family": dict(exact_blockers),
                "candidate_search_evidence": dict(blocker_evidence),
                "local_cleanup_search_ran": False,
                "local_cleanup_search_exhaustive": False,
                "primary_card_actionable": False,
                "primary_action": visible_blocker_reasons or str(out_blocker.get("primary_action") or ""),
                "secondary_action": "",
                "reasoning": f"Why: {visible_blocker_reasons}" if visible_blocker_reasons else str(out_blocker.get("reasoning") or ""),
            }
        )
        out_blocker["button_contract"] = disabled_design_guide_button_contract(
            out_blocker,
            family=active_family_text,
            reason=design_guide_blocker_reason(out_blocker),
        )
        out_blocker["final_visible_state_fingerprint"] = str(item_state_fingerprint or "")
        out_blocker = normalise_final_visible_design_guide_item(out_blocker)
    final_item = dict(out_blocker or fallback_item or {})
    return {
        "item": final_item,
        "overview": dict(final_overview or {}),
        "presentation": {
            "headline": str(final_item.get("title_main") or final_item.get("title") or active_title),
            "subtext": str(final_item.get("primary_action") or ""),
            "guidance_intent": "specific_blocker",
            "css_bucket": "fail",
            "theme": "fail",
            "show_apply_button": False,
            "use_success_style": False,
        },
        "render_reason": "final_visible_active_strength_blocker",
        "state_fingerprint": str(result_state_fingerprint or ""),
        "debug": dict(debug_probe or {}),
    }


ACCEPTED_GREEN_EXACT_BLOCKER_REQUIRED_FIELDS = (
    "family",
    "search_ran",
    "search_exhaustive",
    "current_util",
    "threshold",
    "attempted_candidate_count",
    "executable_candidate_count",
    "target_band_candidate_count",
    "executable_target_band_candidate_count",
    "failed_candidate_id",
    "best_rejected_candidate_id",
    "attempted_updates",
    "failed_check_name",
    "failed_check_status",
    "failed_check_util",
    "failed_check_demand",
    "failed_check_capacity_or_limit",
)


def normalise_accepted_green_exact_blocker(blocker: dict | None) -> dict:
    if not isinstance(blocker, dict):
        return {}
    out = dict(blocker)
    family = str(out.get("family") or "").strip().lower()
    search_ran = bool(
        out.get("search_ran")
        or out.get("repair_search_ran")
        or out.get("target_band_search_ran")
        or out.get("cleanup_search_ran")
        or out.get("local_cleanup_search_ran")
        or (family and out.get(f"{family}_cleanup_search_ran"))
        or (family and out.get(f"post_click_{family}_cleanup_search_ran"))
    )
    search_exhaustive = bool(
        out.get("search_exhaustive")
        or out.get("repair_search_exhaustive")
        or out.get("target_band_search_exhaustive")
        or out.get("cleanup_search_exhaustive")
        or out.get("local_cleanup_search_exhaustive")
        or (family and out.get(f"{family}_cleanup_search_exhaustive"))
        or (family and out.get(f"post_click_{family}_cleanup_search_exhaustive"))
    )
    out["search_ran"] = bool(search_ran)
    out["search_exhaustive"] = bool(search_exhaustive)
    if search_ran:
        out.setdefault("cleanup_search_ran", True)
        out.setdefault("local_cleanup_search_ran", True)
    if search_exhaustive:
        out.setdefault("cleanup_search_exhaustive", True)
        out.setdefault("local_cleanup_search_exhaustive", True)
    out.setdefault("executable_candidate_count", out.get("executable_cleanup_count") or 0)
    out.setdefault("target_band_candidate_count", 0)
    out.setdefault("executable_target_band_candidate_count", 0)
    rejected_id = (
        out.get("failed_candidate_id")
        or out.get("best_rejected_candidate_id")
        or out.get("attempted_candidate_id")
        or out.get("no_link_candidate_id")
    )
    if rejected_id:
        out.setdefault("failed_candidate_id", rejected_id)
        out.setdefault("best_rejected_candidate_id", rejected_id)
    if out.get("failed_check_util") in (None, "", [], {}):
        out["failed_check_util"] = out.get("failed_check_value") or out.get("current_util")
    if out.get("failed_check_capacity_or_limit") in (None, "", [], {}):
        out["failed_check_capacity_or_limit"] = (
            out.get("failed_check_limit")
            or out.get("capacity_or_limit")
            or out.get("threshold")
        )
    return out


def accepted_green_exact_blocker_is_valid(blocker: dict | None) -> bool:
    blocker = normalise_accepted_green_exact_blocker(blocker)
    if not blocker:
        return False
    if not bool(blocker.get("search_ran")) or not bool(blocker.get("search_exhaustive")):
        return False
    if int(blocker.get("executable_candidate_count") or blocker.get("executable_cleanup_count") or 0) > 0:
        if not (bool(blocker.get("best_safe_candidate_applied")) and bool(blocker.get("no_second_cta_required"))):
            return False
    if (
        int(blocker.get("target_band_candidate_count") or 0) > 0
        and int(blocker.get("executable_target_band_candidate_count") or 0) > 0
    ):
        return False
    for field in ACCEPTED_GREEN_EXACT_BLOCKER_REQUIRED_FIELDS:
        value = blocker.get(field)
        if value in (None, "", [], {}) and field == "failed_check_demand":
            value = blocker.get("demand")
        if value in (None, "", [], {}) and field == "failed_check_capacity_or_limit":
            value = blocker.get("capacity_or_limit")
        if value in (None, "", [], {}):
            return False
    reason = str(
        blocker.get("why_reduction_would_hurt_other_design_elements")
        or blocker.get("reason_reducing_this_family_would_affect_other_design_elements")
        or blocker.get("reason")
        or ""
    ).strip().lower()
    if not reason:
        return False
    if reason in {"no safe cleanup found", "candidate failed", "engineering constraint"}:
        return False
    return True


def candidate_preview_statuses_have_explicit_fail(
    preview_statuses: dict | None,
    *,
    fail_status_value: Any = "FAIL",
) -> bool:
    return _repair_candidate_preview_statuses_have_explicit_fail(
        preview_statuses,
        fail_status_value=fail_status_value,
    )


UNDERDESIGN_REPAIR_INVARIANT_CONTRACT_ID = "underdesign_repair_invariant"
UNDERDESIGN_REPAIR_INVARIANT_CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "artifacts"
    / "contracts"
    / "families"
    / "underdesign_repair_invariant.json"
)
FAMILY_SELECTION_CONTRACT_ID = "family_selection_contract"
FAMILY_SELECTION_CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "artifacts"
    / "contracts"
    / "families"
    / "family_selection_contract.json"
)
FAMILY_CHOOSER_CONTRACT_ID = "family_chooser_contract"
FAMILY_CHOOSER_CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "artifacts"
    / "contracts"
    / "families"
    / "family_chooser_contract.json"
)


def _as_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return list(value) if isinstance(value, list) else []


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def button_contract_from_payload(primary: dict, debug: dict) -> dict:
    return _as_dict(
        primary.get("button_contract")
        or debug.get("primary_button_contract")
        or debug.get("button_contract")
    )


def contract_updates_from_publication(contract: dict, primary: dict) -> dict:
    return _as_dict(
        contract.get("updates")
        or primary.get("selected_action_updates")
        or primary.get("updates")
        or _as_dict(primary.get("action_payload")).get("resolved_candidate_updates")
        or _as_dict(primary.get("action_payload")).get("updates")
    )


def contract_enabled(contract: dict) -> bool:
    return bool(contract.get("enabled") or contract.get("actionable"))


def _load_underdesign_repair_invariant_contract() -> dict:
    try:
        with UNDERDESIGN_REPAIR_INVARIANT_CONTRACT_PATH.open("r", encoding="utf-8") as handle:
            contract = json.load(handle)
    except Exception:
        contract = {}
    return contract if isinstance(contract, dict) else {}


def _load_family_selection_contract() -> dict:
    try:
        with FAMILY_SELECTION_CONTRACT_PATH.open("r", encoding="utf-8") as handle:
            contract = json.load(handle)
    except Exception:
        contract = {}
    return contract if isinstance(contract, dict) else {}


def _load_family_chooser_contract() -> dict:
    try:
        with FAMILY_CHOOSER_CONTRACT_PATH.open("r", encoding="utf-8") as handle:
            contract = json.load(handle)
    except Exception:
        contract = {}
    return contract if isinstance(contract, dict) else {}


def _normalise_failure_family(family: Any) -> str | None:
    text = str(family or "").strip().lower()
    if not text:
        return None
    if text in {"bending", "flexure", "moment"}:
        return "bending"
    if text in {"shear", "links", "ligs"}:
        return "shear"
    if text in {"combined", "bending+shear", "bending_shear", "combined_bending_shear"}:
        return "combined"
    if text in {"serviceability", "deflection"}:
        return "serviceability"
    return text


def _active_failures_from_publication_payload(payload: dict, debug: dict, result: dict) -> list[str]:
    active: set[str] = set()
    explicit_payload_active = [
        _normalise_failure_family(item)
        for item in _as_list(payload.get("active_failures"))
        if _normalise_failure_family(item)
    ]
    if explicit_payload_active:
        payload_active = set(explicit_payload_active)
        if "combined" in payload_active:
            payload_active.update({"bending", "shear"})
        return sorted(family for family in payload_active if family in {"bending", "shear", "serviceability"})
    for source in (
        result.get("active_failures"),
        debug.get("active_failures"),
        debug.get("final_active_failures"),
        debug.get("contract_boundary_active_failures"),
    ):
        for item in _as_list(source):
            family = _normalise_failure_family(item)
            if family:
                active.add(family)
    for source in (
        payload.get("overview"),
        debug.get("overview"),
        result.get("overview"),
        debug.get("current_overview"),
    ):
        statuses = _as_dict(_as_dict(source).get("statuses"))
        for family, status in statuses.items():
            if str(status or "").strip().upper() == "FAIL":
                normalised = _normalise_failure_family(family)
                if normalised:
                    active.add(normalised)
    for source in (
        payload.get("family_status_current"),
        debug.get("family_status_current"),
    ):
        for family, row in _as_dict(source).items():
            status = row.get("status") if isinstance(row, dict) else row
            if str(status or "").strip().upper() == "FAIL":
                normalised = _normalise_failure_family(family)
                if normalised:
                    active.add(normalised)
    if "combined" in active:
        active.update({"bending", "shear"})
    return sorted(family for family in active if family in {"bending", "shear", "serviceability"})


def _publication_signals_bending_failure(primary: dict, debug: dict) -> bool:
    text = _publication_text(primary, debug, include_debug=False) or _publication_text(primary, debug)
    return any(
        token in text
        for token in (
            "minimum tensile reinforcement fails",
            "minimum tensile reinforcement",
            "bending utilisation moves",
            "bending utilization moves",
            "bending fail",
            "bending capacity fails",
        )
    )


def _publication_signals_shear_failure(primary: dict, debug: dict) -> bool:
    text = _publication_text(primary, debug, include_debug=False) or _publication_text(primary, debug)
    return any(
        token in text
        for token in (
            "shear utilisation moves",
            "shear utilization moves",
            "shear fail",
            "shear capacity fails",
            "shear capacity is low",
        )
    )


def _utilisation_from_publication(payload: dict, debug: dict, family: str) -> float | None:
    family_key = str(family or "").strip().lower()
    for source in (
        payload.get("overview"),
        debug.get("overview"),
        debug.get("current_overview"),
    ):
        value = _as_dict(_as_dict(source).get("utils")).get(family_key)
        parsed = _as_float(value)
        if parsed is not None:
            return parsed
    return None


def _status_from_publication(payload: dict, debug: dict, family: str) -> str | None:
    family_key = str(family or "").strip().lower()
    for source in (
        payload.get("overview"),
        debug.get("overview"),
        debug.get("current_overview"),
    ):
        status = str(_as_dict(_as_dict(source).get("statuses")).get(family_key) or "").strip().upper()
        if status:
            return status
    return None


def _target_band_from_publication(primary: dict, debug: dict) -> tuple[float, float]:
    for source in (
        _as_dict(primary.get("candidate_search_evidence")),
        _as_dict(primary.get("display_truth")),
        _as_dict(debug.get("primary_display_truth")),
        debug,
    ):
        low = _as_float(_as_dict(source).get("target_low"))
        high = _as_float(_as_dict(source).get("target_high"))
        if low is not None and high is not None and float(low) < float(high):
            return float(low), float(high)
    return 0.85, 1.0


def _raw_state_flags_from_publication(
    payload: dict,
    primary: dict,
    debug: dict,
    result: dict,
) -> tuple[dict[str, Any], dict[str, Any]]:
    active_failures = set(_active_failures_from_publication_payload(payload, debug, result))
    text_signals: dict[str, bool] = {}
    if _publication_signals_bending_failure(primary, debug):
        active_failures.add("bending")
        text_signals["bending_failure"] = True
    if _publication_signals_shear_failure(primary, debug):
        active_failures.add("shear")
        text_signals["shear_failure"] = True
    publication_text = _publication_text(primary, debug, include_debug=False)
    geometry_statuses = {
        family: _status_from_publication(payload, debug, family)
        for family in ("geometry", "detailing", "spacing", "cover")
    }
    geometry_detailing_fail = any(
        str(status or "").strip().upper() == "FAIL"
        for status in geometry_statuses.values()
    ) or any(
        token in publication_text
        for token in (
            "geometry invalid",
            "detailing invalid",
            "spacing invalid",
            "cover invalid",
            "bar fit impossible",
        )
    )
    bending_utilisation = _utilisation_from_publication(payload, debug, "bending")
    shear_utilisation = _utilisation_from_publication(payload, debug, "shear")
    target_low, target_high = _target_band_from_publication(primary, debug)
    bending_status = _status_from_publication(payload, debug, "bending")
    shear_status = _status_from_publication(payload, debug, "shear")
    serviceability_status = _status_from_publication(payload, debug, "serviceability")
    exact_text = "exact" in publication_text and "stop" in publication_text
    efficient_text = "design is efficient" in publication_text or "target band reached" in publication_text
    repair_payload = _repair_action_payload_from_publication(
        primary,
        debug,
        sorted(family for family in active_failures if family in {"bending", "shear", "serviceability"}),
    )
    contract = button_contract_from_payload(primary, debug)
    blocking_reason = str(contract.get("blocking_reason") or primary.get("blocking_reason") or "").strip().lower()
    explicit_lock_signal = any(
        bool(_as_dict(source).get(key))
        for source in (payload, primary, debug, contract)
        for key in (
            "locked_repair_blocked",
            "repair_blocked_by_lock",
            "all_repair_paths_locked",
            "locked_no_repair",
            "user_locked_repair",
        )
    ) or any(
        token in blocking_reason
        for token in ("locked", "user lock", "locked input", "all_repair_paths_locked")
    )
    locked_repair_blocked = bool(explicit_lock_signal and not repair_payload)
    raw_flags = {
        "geometry_detailing_fail": bool(geometry_detailing_fail),
        "serviceability_fail": "serviceability" in active_failures
        or str(serviceability_status or "").strip().upper() == "FAIL",
        "bending_fail": "bending" in active_failures,
        "shear_fail": "shear" in active_failures,
        "min_bending_reo_fail": any(
            token in publication_text
            for token in ("minimum bending reinforcement", "minimum tensile reinforcement", "min bending reo")
        )
        and "bending" not in active_failures,
        "min_shear_reo_fail": any(
            token in publication_text
            for token in ("minimum shear reinforcement", "minimum shear reo", "minimum lig", "minimum link")
        )
        and "shear" not in active_failures,
        "bending_overdesigned": (
            bending_utilisation is not None
            and float(bending_utilisation) < float(target_low)
            and "bending" not in active_failures
        ),
        "shear_overdesigned": (
            shear_utilisation is not None
            and float(shear_utilisation) < float(target_low)
            and "shear" not in active_failures
        ),
        "bending_within_target_band": (
            bending_utilisation is not None
            and float(target_low) <= float(bending_utilisation) <= float(target_high)
            and "bending" not in active_failures
        ),
        "shear_within_target_band": (
            shear_utilisation is not None
            and float(target_low) <= float(shear_utilisation) <= float(target_high)
            and "shear" not in active_failures
        ),
        "locked_repair_blocked": bool(locked_repair_blocked),
        "legal_repair_exists": bool(repair_payload),
        "repair_required": bool(active_failures & {"bending", "shear", "serviceability"}),
        "exact_stop_proven": bool(exact_text),
        "bending_acceptable": (
            str(bending_status or "").strip().upper() in {"PASS", "OK", "ACCEPTED", "WARN", "NEAR LIMIT"}
            or (
                bending_utilisation is not None
                and float(bending_utilisation) <= float(target_high)
                and "bending" not in active_failures
            )
        ),
        "shear_acceptable": (
            str(shear_status or "").strip().upper() in {"PASS", "OK", "ACCEPTED", "WARN", "NEAR LIMIT"}
            or (
                shear_utilisation is not None
                and float(shear_utilisation) <= float(target_high)
                and "shear" not in active_failures
            )
        ),
        "target_band_terminal_signal": bool(efficient_text),
    }
    evidence = {
        "source": "design_brain.publication.raw_state_flags",
        "base_active_failures": sorted(active_failures),
        "publication_text_signals": text_signals,
        "bending_status": bending_status or "not_proven",
        "shear_status": shear_status or "not_proven",
        "serviceability_status": serviceability_status,
        "bending_utilisation": bending_utilisation,
        "shear_utilisation": shear_utilisation,
        "target_low": target_low,
        "target_high": target_high,
        "geometry_statuses": geometry_statuses,
        "repair_payload_available": bool(repair_payload),
    }
    return raw_flags, evidence


def _family_chooser_output_from_publication(
    payload: dict,
    primary: dict,
    debug: dict,
    result: dict,
    contract: dict,
) -> dict:
    raw_flags, raw_evidence = _raw_state_flags_from_publication(payload, primary, debug, result)
    version = contract.get("version") if isinstance(contract, dict) else None
    classification = classify_family_from_raw_flags(raw_flags, evidence=raw_evidence, contract_version=version)
    conflicts: list[str] = []
    explicit = str(
        payload.get("selected_family_id")
        or primary.get("selected_family_id")
        or debug.get("selected_family_id")
        or result.get("selected_family_id")
        or ""
    ).strip()
    selected = str(classification.get("selected_family") or "").strip()
    if explicit and selected and explicit != selected:
        conflicts.append(f"explicit_selected_family_conflicts_with_chooser:{explicit}!={selected}")
    conflicts.extend(list(classification.get("selection_conflicts") or []))
    bending_status = _status_from_publication(payload, debug, "bending")
    bending_utilisation = _utilisation_from_publication(payload, debug, "bending")
    shear_utilisation = _utilisation_from_publication(payload, debug, "shear")
    geometry_detailing_blocker_active = bool(raw_flags.get("geometry_detailing_fail"))
    if bending_utilisation is None:
        bending_target_band_status = "not_proven"
    elif raw_flags.get("bending_fail"):
        bending_target_band_status = "not_applicable_bending_failure_active"
    elif raw_flags.get("bending_within_target_band"):
        bending_target_band_status = "inside_target_band"
    else:
        bending_target_band_status = "outside_target_band"
    selection_evidence = dict(classification.get("selection_evidence") or {})
    rejected_families = dict(classification.get("rejected_families") or {})
    return {
        "contract_checked": True,
        "contract_file": str(FAMILY_CHOOSER_CONTRACT_PATH),
        "contract_version": version,
        "selected_family": selected,
        "selection_reason": classification.get("selection_reason"),
        "selected_family_reason": classification.get("selected_family_reason"),
        "matched_family_ids": list(classification.get("matched_family_ids") or []),
        "raw_state_flags": dict(classification.get("raw_state_flags") or raw_flags),
        "active_failures": list(classification.get("active_failures") or []),
        "active_overdesigns": list(classification.get("active_overdesigns") or []),
        "active_stops": list(classification.get("active_stops") or []),
        "rejected_families": dict(classification.get("rejected_families") or {}),
        "selection_evidence": {
            **selection_evidence,
            "active_bending_fail": bool(raw_flags.get("bending_fail")),
            "active_shear_fail": bool(raw_flags.get("shear_fail")),
            "active_serviceability_fail": bool(raw_flags.get("serviceability_fail")),
            "bending_status": bending_status or "not_proven",
            "bending_utilisation": bending_utilisation,
            "shear_utilisation": shear_utilisation,
            "serviceability_status": _status_from_publication(payload, debug, "serviceability"),
            "bending_target_band_status": bending_target_band_status,
            "minimum_bending_reinforcement_status": "not_proven",
            "geometry_reduction_status": "not_proven",
            "geometry_detailing_blocker_status": (
                "active" if geometry_detailing_blocker_active else "absent"
            ),
            "why_bending_family_rejected": rejected_families.get("BENDING_FAIL_GOVERNS"),
            "why_min_bending_reo_rejected_or_selected": (
                "not_proven_by_current_publication_diagnostics"
            ),
            "why_geometry_detailing_rejected_or_selected": (
                "geometry/detailing blocker signal active"
                if geometry_detailing_blocker_active
                else "no geometry/detailing blocker signal present"
            ),
            "why_target_band_rejected_or_selected": (
                "rejected because active shear failure exists"
                if raw_flags.get("shear_fail")
                else "not_proven_by_current_publication_diagnostics"
            ),
        },
        "selection_conflicts": conflicts,
        "repair_variables_available": bool(raw_flags.get("legal_repair_exists")),
        "cleanup_variables_available": None,
        "locked_variables": [],
        "classification_passed": bool(classification.get("classification_passed")),
        "family_selection_not_proven": bool(classification.get("family_selection_not_proven")),
    }


def _family_id_from_mechanical_family(family: Any, *, mode: str, active_failures: list[str] | None = None) -> str | None:
    normalised = _normalise_failure_family(family)
    active = set(active_failures or [])
    if mode == "fail":
        if normalised == "combined" or {"bending", "shear"}.issubset(active):
            return "COMBINED_BENDING_SHEAR_FAIL"
        if normalised == "shear":
            return "SHEAR_FAIL_GOVERNS"
        if normalised == "bending":
            return "BENDING_FAIL_GOVERNS"
        if normalised == "serviceability":
            return "SERVICEABILITY_GOVERNS"
    if mode == "overdesign":
        if normalised == "combined":
            return "COMBINED_OVERDESIGN"
        if normalised == "shear":
            return "SHEAR_OVERDESIGN_GOVERNS"
        if normalised == "bending":
            return "BENDING_OVERDESIGN_GOVERNS"
    return None


def _mechanical_family_from_family_id(family_id: Any) -> str | None:
    text = str(family_id or "").strip().upper()
    if text == "COMBINED_BENDING_SHEAR_FAIL":
        return "combined"
    if text == "SHEAR_FAIL_GOVERNS":
        return "shear"
    if text == "BENDING_FAIL_GOVERNS":
        return "bending"
    if text == "SERVICEABILITY_GOVERNS":
        return "serviceability"
    return None


def _selected_family_id_from_publication(payload: dict, primary: dict, debug: dict, result: dict) -> tuple[str | None, str]:
    explicit = str(
        payload.get("selected_family_id")
        or primary.get("selected_family_id")
        or debug.get("selected_family_id")
        or result.get("selected_family_id")
        or ""
    ).strip()
    if explicit:
        return explicit, "explicit"
    active = _active_failures_from_publication_payload(payload, debug, result)
    if {"bending", "shear"}.issubset(set(active)):
        return "COMBINED_BENDING_SHEAR_FAIL", "active_failures"
    if "shear" in active:
        return "SHEAR_FAIL_GOVERNS", "active_failures"
    if "bending" in active:
        return "BENDING_FAIL_GOVERNS", "active_failures"
    if "serviceability" in active:
        return "SERVICEABILITY_GOVERNS", "active_failures"
    return None, "unclassified"


def _candidate_family_id_from_publication(primary: dict, debug: dict) -> str | None:
    contract = button_contract_from_payload(primary, debug)
    raw_family = (
        primary.get("candidate_family_id")
        or contract.get("candidate_family_id")
        or contract.get("family")
        or primary.get("candidate_family")
        or primary.get("family")
        or primary.get("check_key")
        or primary.get("selected_action_family")
    )
    normalised = _normalise_failure_family(raw_family)
    if normalised == "combined":
        return "COMBINED_BENDING_SHEAR_FAIL"
    if normalised == "shear":
        return "SHEAR_FAIL_GOVERNS"
    if normalised == "bending":
        return "BENDING_FAIL_GOVERNS"
    if normalised == "serviceability":
        return "SERVICEABILITY_GOVERNS"
    return None


def _published_family_id_from_publication(
    primary: dict,
    debug: dict,
    result: dict,
    selected_family_id: str | None,
    active_failures: list[str],
) -> str | None:
    explicit = str(
        primary.get("published_family_id")
        or debug.get("published_family_id")
        or result.get("published_family_id")
        or ""
    ).strip()
    if explicit:
        return explicit
    blocked_type = _blocked_publication_type(primary, debug, result)
    if blocked_type:
        text = _publication_text(primary, debug, include_debug=False) or _publication_text(primary, debug)
        if any(token in text for token in ("cleanup", "optimisation", "optimization")):
            if {"bending", "shear"}.issubset(set(active_failures)):
                return "COMBINED_OVERDESIGN"
            if "shear" in active_failures:
                return "SHEAR_OVERDESIGN_GOVERNS"
            if "bending" in active_failures:
                return "BENDING_OVERDESIGN_GOVERNS"
        if "exact" in str(blocked_type).lower():
            return "EXACT_STOP_PROVEN"
        if "design is efficient" in str(blocked_type).lower() or str(blocked_type).upper() == "PASS":
            return "TARGET_BAND_REACHED"
    return selected_family_id


def _cta_family_id_from_publication(
    primary: dict,
    debug: dict,
    selected_family_id: str | None,
    published_family_id: str | None,
) -> str | None:
    explicit = str(primary.get("cta_family_id") or debug.get("cta_family_id") or "").strip()
    if explicit:
        return explicit
    contract = button_contract_from_payload(primary, debug)
    if not contract_enabled(contract):
        return published_family_id or selected_family_id
    text = _publication_text(primary, debug, include_debug=False) or _publication_text(primary, debug)
    if any(token in text for token in ("cleanup", "optimisation", "optimization")):
        mechanical = _normalise_failure_family(contract.get("family") or primary.get("family"))
        if mechanical == "combined":
            return "COMBINED_OVERDESIGN"
        if mechanical == "shear":
            return "SHEAR_OVERDESIGN_GOVERNS"
        if mechanical == "bending":
            return "BENDING_OVERDESIGN_GOVERNS"
    return selected_family_id or published_family_id


def _repair_action_payload_from_publication(primary: dict, debug: dict, active_failures: list[str]) -> dict:
    contract = button_contract_from_payload(primary, debug)
    updates = contract_updates_from_publication(contract, primary)
    action_payload = _as_dict(primary.get("action_payload"))
    resolved = _as_dict(primary.get("resolved_candidate"))
    action_type = str(
        contract.get("action_type")
        or primary.get("action_type")
        or action_payload.get("resolved_candidate_action_type")
        or action_payload.get("action_type")
        or resolved.get("action_type")
        or ""
    ).strip()
    family = _normalise_failure_family(
        contract.get("family")
        or primary.get("family")
        or primary.get("check_key")
        or primary.get("selected_action_family")
        or action_payload.get("family")
        or action_payload.get("resolved_candidate_family_tag")
        or resolved.get("family")
        or resolved.get("recommendation_family_tag")
    )
    if family == "combined":
        family_ok = bool({"bending", "shear"} & set(active_failures))
    else:
        family_ok = bool(family and family in set(active_failures))
    text = _publication_text(primary, debug, include_debug=False) or _publication_text(primary, debug)
    cleanup_text = "cleanup" in text or "optimisation" in text or "optimization" in text
    blocking_reason = str(contract.get("blocking_reason") or primary.get("blocking_reason") or "").strip()
    preview_pass = contract.get("preview_pass", primary.get("preview_pass", True))
    if (
        updates
        and action_type == "apply_resolved_candidate"
        and preview_pass is not False
        and family_ok
        and not cleanup_text
        and not blocking_reason
    ):
        return {
            "contract": dict(contract),
            "updates": dict(updates),
            "action_type": action_type,
            "family": family,
            "action_payload": dict(action_payload),
            "resolved_candidate": dict(resolved),
        }
    return {}


def _family_selection_safe_item(primary: dict, diagnostics: dict) -> dict:
    selected = str(diagnostics.get("selected_family_id") or "UNKNOWN_FAMILY").strip()
    blocked_published = str(diagnostics.get("published_family_id") or "").strip()
    blocked_cta = str(diagnostics.get("cta_family_id") or "").strip()
    blocked_card = str(diagnostics.get("card_family_id") or "").strip()
    item = dict(primary)
    for stale_key in (
        "button_contract",
        "action_payload",
        "resolved_candidate",
        "selected_action_updates",
        "updates",
        "design_guide_terminal_state",
        "terminal_cleanup_state",
        "primary_card_actionable",
    ):
        item.pop(stale_key, None)
    item.update(
        {
            "title_main": "Design Guide family contract violation",
            "title": "Design Guide family contract violation",
            "headline": "Design Guide family contract violation",
            "governing_label": "Family mismatch blocked",
            "summary_line": "Publication blocked by family contract before final render.",
            "family": selected.lower(),
            "check_key": selected.lower(),
            "selected_family_id": selected,
            "selected_family": selected,
            "selection_reason": diagnostics.get("selection_reason"),
            "selected_family_reason": diagnostics.get("selected_family_reason"),
            "published_family_id": selected,
            "cta_family_id": selected,
            "candidate_family_id": str(diagnostics.get("candidate_family_id") or ""),
            "card_family_id": selected,
            "blocked_publication_type": blocked_published or blocked_card or blocked_cta,
            "blocked_published_family_id": blocked_published,
            "blocked_cta_family_id": blocked_cta,
            "blocked_card_family_id": blocked_card,
            "family_selection_source": diagnostics.get("family_selection_source"),
            "family_selection_contract": FAMILY_SELECTION_CONTRACT_ID,
            "family_chooser_contract": FAMILY_CHOOSER_CONTRACT_ID,
            "rejected_families": dict(diagnostics.get("rejected_families") or {}),
            "selection_evidence": dict(diagnostics.get("selection_evidence") or {}),
            "matched_family_ids": list(diagnostics.get("matched_family_ids") or []),
            "raw_state_flags": dict(diagnostics.get("raw_state_flags") or {}),
            "family_match_passed": False,
            "family_match_violation_reason": diagnostics.get("family_match_violation_reason"),
            "status": "FAIL",
            "critical_status": "FAIL",
            "guidance_intent": "required_fix",
            "primary_action": "Publication blocked by family contract.",
            "reasoning": "A wrong-family publication was blocked before the final Design Guide render.",
            "button_contract": {
                "enabled": False,
                "actionable": False,
                "family": selected,
                "action_type": None,
                "updates": {},
                "blocking_reason": "family_selection_contract_mismatch",
            },
        }
    )
    evidence = _as_dict(item.get("candidate_search_evidence"))
    evidence.update(diagnostics)
    item["candidate_search_evidence"] = dict(evidence)
    return item


def _route_shear_fail_family_publication(primary: dict, debug: dict, diagnostics: dict) -> tuple[dict, dict, dict]:
    if str(diagnostics.get("selected_family_id") or diagnostics.get("selected_family") or "").strip() != "SHEAR_FAIL_GOVERNS":
        return primary, debug, diagnostics
    if set(_as_list(diagnostics.get("active_failures"))) != {"shear"}:
        return primary, debug, diagnostics
    try:
        from design_brain.families.base import FamilyStrategyContext
        from design_brain.families.registry import family_strategy_for

        strategy = family_strategy_for("SHEAR_FAIL_GOVERNS")
        if strategy is None or not callable(getattr(strategy, "route_existing_decision", None)):
            diagnostics["family_publication_route_attempted"] = True
            diagnostics["family_publication_route_used"] = False
            diagnostics["family_publication_fallback_reason"] = "shear_fail_family_route_method_missing"
            return primary, debug, diagnostics
        evidence = _as_dict(primary.get("candidate_search_evidence"))
        context = FamilyStrategyContext(
            governing_state="SHEAR_FAIL_GOVERNS",
            payload={"guidance_items": [dict(primary)], "debug_trace": dict(debug)},
            primary=dict(primary),
            summary=_as_dict(debug.get("overview") or debug.get("current_overview")),
            evidence=dict(evidence),
            debug={**dict(debug), "candidate_search_evidence": dict(evidence), "active_failures": ["shear"]},
            classifier={"governing_state": "SHEAR_FAIL_GOVERNS", "active_failures": ["shear"]},
        )
        decision = {
            "card": {
                "intent": "required_fix",
                "family": "shear",
                "check_key": "shear",
                "title": primary.get("title") or primary.get("title_main"),
            },
            "presentation": {},
            "button_contract": _as_dict(primary.get("button_contract") or debug.get("button_contract")),
            "candidate_search_evidence": dict(evidence),
            "debug": dict(debug),
        }
        routed = strategy.route_existing_decision(
            context,
            decision=decision,
            primary_item=dict(primary),
            active_strength_failures={"shear"},
        )
        route_diag = _as_dict(routed.get("diagnostics"))
        diagnostics.update(
            {
                "family_publication_route_attempted": True,
                "family_publication_route_used": bool(routed.get("used")),
                "family_publication_fallback_reason": route_diag.get("fallback_reason"),
                "family_route_owner": route_diag.get("owner"),
            }
        )
        if not routed.get("used"):
            debug["shear_fail_family_publication_route"] = dict(route_diag)
            return primary, debug, diagnostics
        routed_primary = _as_dict(routed.get("primary_item") or primary)
        routed_decision = _as_dict(routed.get("decision"))
        routed_debug = _as_dict(routed_decision.get("debug") or debug)
        routed_debug["shear_fail_family_publication_route"] = dict(route_diag)
        routed_primary.update(
            {
                "selected_family": "SHEAR_FAIL_GOVERNS",
                "selected_family_id": "SHEAR_FAIL_GOVERNS",
                "published_family_id": "SHEAR_FAIL_GOVERNS",
                "cta_family_id": "SHEAR_FAIL_GOVERNS",
                "card_family_id": "SHEAR_FAIL_GOVERNS",
                "family_chooser_contract": FAMILY_CHOOSER_CONTRACT_ID,
                "family_selection_contract": FAMILY_SELECTION_CONTRACT_ID,
                "family_match_passed": True,
                "family_match_violation_reason": None,
                "family_route_owner": route_diag.get("owner"),
            }
        )
        routed_evidence = _as_dict(routed_primary.get("candidate_search_evidence"))
        routed_evidence.update(diagnostics)
        routed_evidence["family_route_owner"] = route_diag.get("owner")
        routed_primary["candidate_search_evidence"] = dict(routed_evidence)
        diagnostics.update(
            {
                "family_match_passed": True,
                "family_match_violation_reason": None,
                "family_route_owner": route_diag.get("owner"),
            }
        )
        return routed_primary, routed_debug, diagnostics
    except Exception as exc:
        diagnostics["family_publication_route_attempted"] = True
        diagnostics["family_publication_route_used"] = False
        diagnostics["family_publication_fallback_reason"] = "adapter_exception"
        diagnostics["family_publication_adapter_error"] = f"{type(exc).__name__}: {exc}"
        debug["shear_fail_family_publication_route"] = dict(diagnostics)
        return primary, debug, diagnostics


def _route_combined_fail_family_publication(primary: dict, debug: dict, diagnostics: dict) -> tuple[dict, dict, dict]:
    if str(diagnostics.get("selected_family_id") or diagnostics.get("selected_family") or "").strip() != "COMBINED_BENDING_SHEAR_FAIL":
        return primary, debug, diagnostics
    active = set(_as_list(diagnostics.get("active_failures")))
    if not active >= {"bending", "shear"}:
        return primary, debug, diagnostics
    try:
        from design_brain.families.base import FamilyStrategyContext
        from design_brain.families.registry import family_strategy_for

        strategy = family_strategy_for("COMBINED_BENDING_SHEAR_FAIL")
        if strategy is None or not callable(getattr(strategy, "route_existing_decision", None)):
            diagnostics["family_publication_route_attempted"] = True
            diagnostics["family_publication_route_used"] = False
            diagnostics["family_publication_fallback_reason"] = "combined_fail_family_route_method_missing"
            return primary, debug, diagnostics
        evidence = _as_dict(primary.get("candidate_search_evidence"))
        context = FamilyStrategyContext(
            governing_state="COMBINED_BENDING_SHEAR_FAIL",
            payload={"guidance_items": [dict(primary)], "debug_trace": dict(debug)},
            primary=dict(primary),
            summary=_as_dict(debug.get("overview") or debug.get("current_overview")),
            evidence=dict(evidence),
            debug={**dict(debug), "candidate_search_evidence": dict(evidence), "active_failures": sorted(active)},
            classifier={"governing_state": "COMBINED_BENDING_SHEAR_FAIL", "active_failures": sorted(active)},
        )
        decision = {
            "card": {
                "intent": "required_fix",
                "family": "combined",
                "check_key": "combined",
                "title": primary.get("title") or primary.get("title_main"),
            },
            "presentation": {},
            "button_contract": _as_dict(primary.get("button_contract") or debug.get("button_contract")),
            "candidate_search_evidence": dict(evidence),
            "debug": dict(debug),
        }
        routed = strategy.route_existing_decision(
            context,
            decision=decision,
            primary_item=dict(primary),
            active_strength_failures={"bending", "shear"},
        )
        route_diag = _as_dict(routed.get("diagnostics"))
        diagnostics.update(
            {
                "family_publication_route_attempted": True,
                "family_publication_route_used": bool(routed.get("used")),
                "family_publication_fallback_reason": route_diag.get("fallback_reason"),
                "family_route_owner": route_diag.get("owner"),
            }
        )
        if not routed.get("used"):
            debug["combined_fail_family_publication_route"] = dict(route_diag)
            return primary, debug, diagnostics
        routed_primary = _as_dict(routed.get("primary_item") or primary)
        routed_decision = _as_dict(routed.get("decision"))
        routed_debug = _as_dict(routed_decision.get("debug") or debug)
        routed_debug["combined_fail_family_publication_route"] = dict(route_diag)
        routed_primary.update(
            {
                "selected_family": "COMBINED_BENDING_SHEAR_FAIL",
                "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                "published_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                "cta_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                "card_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                "family_chooser_contract": FAMILY_CHOOSER_CONTRACT_ID,
                "family_selection_contract": FAMILY_SELECTION_CONTRACT_ID,
                "family_match_passed": True,
                "family_match_violation_reason": None,
                "family_route_owner": route_diag.get("owner"),
            }
        )
        routed_contract = _as_dict(routed_primary.get("button_contract"))
        if routed_contract:
            routed_contract.update(
                {
                    "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "published_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "cta_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "family_match_passed": True,
                }
            )
            routed_primary["button_contract"] = dict(routed_contract)
        routed_evidence = _as_dict(routed_primary.get("candidate_search_evidence"))
        routed_evidence.update(diagnostics)
        routed_evidence.update(
            {
                "published_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                "cta_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                "card_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                "family_match_passed": True,
                "family_match_violation_reason": None,
                "family_route_owner": route_diag.get("owner"),
            }
        )
        routed_primary["candidate_search_evidence"] = dict(routed_evidence)
        diagnostics.update(
            {
                "published_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                "cta_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                "card_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                "family_match_passed": True,
                "family_match_violation_reason": None,
                "family_route_owner": route_diag.get("owner"),
            }
        )
        routed_debug.update(diagnostics)
        routed_debug["primary_button_contract"] = dict(routed_primary.get("button_contract") or {})
        routed_debug["button_contract"] = dict(routed_primary.get("button_contract") or {})
        return routed_primary, routed_debug, diagnostics
    except Exception as exc:
        diagnostics["family_publication_route_attempted"] = True
        diagnostics["family_publication_route_used"] = False
        diagnostics["family_publication_fallback_reason"] = "adapter_exception"
        diagnostics["family_publication_adapter_error"] = f"{type(exc).__name__}: {exc}"
        debug["combined_fail_family_publication_route"] = dict(diagnostics)
        return primary, debug, diagnostics


def enforce_family_selection_publication_contract(payload: dict) -> dict:
    """Stamp and validate selected/published/CTA governing family identity."""
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    items = [dict(item) for item in _as_list(out.get("guidance_items")) if isinstance(item, dict)]
    if not items:
        return out
    debug = _as_dict(out.get("debug_trace"))
    result = _as_dict(out.get("design_brain_result") or debug.get("design_brain_result"))
    primary = dict(items[0])
    contract = _load_family_selection_contract()
    chooser_contract = _load_family_chooser_contract()
    chooser = _family_chooser_output_from_publication(out, primary, debug, result, chooser_contract)
    active_failures = list(chooser.get("active_failures") or _active_failures_from_publication_payload(out, debug, result))
    selected_family_id = str(chooser.get("selected_family") or "").strip() or None
    source = FAMILY_CHOOSER_CONTRACT_ID
    candidate_family_id = _candidate_family_id_from_publication(primary, debug)
    published_family_id = _published_family_id_from_publication(
        primary,
        debug,
        result,
        selected_family_id,
        active_failures,
    )
    cta_family_id = _cta_family_id_from_publication(primary, debug, selected_family_id, published_family_id)
    card_family_id = published_family_id
    if selected_family_id and _publication_has_repair_action(primary, debug, active_failures):
        published_family_id = selected_family_id
        cta_family_id = selected_family_id
        card_family_id = selected_family_id
    violation = ""
    if chooser.get("classification_passed") is False or selected_family_id == FAMILY_SELECTION_CONTRACT_VIOLATION:
        violation = "family_chooser_classification_not_exactly_one_match"
    if selected_family_id and published_family_id and selected_family_id != published_family_id:
        violation = "selected_family_id_does_not_match_published_family_id"
    if not violation and selected_family_id and cta_family_id and selected_family_id != cta_family_id:
        violation = "selected_family_id_does_not_match_cta_family_id"
    forbidden_active = set(active_failures) & {"bending", "shear"}
    forbidden_published = {
        "COMBINED_OVERDESIGN",
        "SHEAR_OVERDESIGN_GOVERNS",
        "BENDING_OVERDESIGN_GOVERNS",
        "TARGET_BAND_REACHED",
        "EXACT_STOP_PROVEN",
    }
    if not violation and forbidden_active and published_family_id in forbidden_published:
        violation = "active_fail_family_published_forbidden_overdesign_or_terminal_family"
    diagnostics = {
        "contract_checked": True,
        "contract_file": str(FAMILY_CHOOSER_CONTRACT_PATH),
        "contract_version": chooser.get("contract_version"),
        "selected_family": selected_family_id,
        "selection_reason": chooser.get("selection_reason"),
        "selected_family_reason": chooser.get("selected_family_reason"),
        "selected_family_id": selected_family_id,
        "published_family_id": published_family_id,
        "cta_family_id": cta_family_id,
        "candidate_family_id": candidate_family_id,
        "card_family_id": card_family_id,
        "family_selection_source": source,
        "family_selection_contract": FAMILY_SELECTION_CONTRACT_ID,
        "family_chooser_contract": FAMILY_CHOOSER_CONTRACT_ID,
        "family_chooser_contract_loaded": bool(chooser_contract),
        "family_selection_contract_loaded": bool(contract),
        "family_match_passed": not bool(violation),
        "family_match_violation_reason": violation or None,
        "active_failures": list(active_failures),
        "active_overdesigns": list(chooser.get("active_overdesigns") or []),
        "active_stops": list(chooser.get("active_stops") or []),
        "matched_family_ids": list(chooser.get("matched_family_ids") or []),
        "raw_state_flags": dict(chooser.get("raw_state_flags") or {}),
        "classification_passed": bool(chooser.get("classification_passed")),
        "family_selection_not_proven": bool(chooser.get("family_selection_not_proven")),
        "rejected_families": dict(chooser.get("rejected_families") or {}),
        "selection_evidence": dict(chooser.get("selection_evidence") or {}),
        "selection_conflicts": list(chooser.get("selection_conflicts") or []),
        "active_bending_fail": "bending" in set(active_failures),
        "active_shear_fail": "shear" in set(active_failures),
        "active_serviceability_fail": "serviceability" in set(active_failures),
        "bending_utilisation": _utilisation_from_publication(out, debug, "bending"),
        "shear_utilisation": _utilisation_from_publication(out, debug, "shear"),
        "serviceability_status": _status_from_publication(out, debug, "serviceability"),
        "repair_variables_available": chooser.get("repair_variables_available"),
        "cleanup_variables_available": chooser.get("cleanup_variables_available"),
        "locked_variables": list(chooser.get("locked_variables") or []),
    }
    if selected_family_id == "COMBINED_BENDING_SHEAR_FAIL":
        primary, debug, diagnostics = _route_combined_fail_family_publication(primary, debug, diagnostics)
        if diagnostics.get("family_publication_route_used"):
            violation = ""
            published_family_id = "COMBINED_BENDING_SHEAR_FAIL"
            cta_family_id = "COMBINED_BENDING_SHEAR_FAIL"
            card_family_id = "COMBINED_BENDING_SHEAR_FAIL"
    if not violation:
        primary, debug, diagnostics = _route_shear_fail_family_publication(primary, debug, diagnostics)
        published_family_id = str(diagnostics.get("published_family_id") or published_family_id or "").strip() or None
        cta_family_id = str(diagnostics.get("cta_family_id") or cta_family_id or "").strip() or None
        card_family_id = str(diagnostics.get("card_family_id") or card_family_id or "").strip() or None
    if violation:
        repair_payload = _repair_action_payload_from_publication(primary, debug, active_failures)
        if repair_payload:
            owner_family = _mechanical_family_from_family_id(selected_family_id) or repair_payload.get("family")
            recovered = dict(primary)
            recovered_contract = dict(repair_payload.get("contract") or {})
            expected_util = recovered_contract.get("expected_util")
            try:
                governing_label = f"Preview utilisation {float(expected_util):.2f}"
            except (TypeError, ValueError):
                governing_label = "Preview utilisation target"
            recovered_contract.update(
                {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": owner_family,
                    "updates": dict(repair_payload.get("updates") or {}),
                    "preview_pass": True,
                    "blocking_reason": None,
                    "selected_family_id": selected_family_id,
                    "published_family_id": selected_family_id,
                    "cta_family_id": selected_family_id,
                    "candidate_family_id": candidate_family_id,
                    "family_selection_contract": FAMILY_SELECTION_CONTRACT_ID,
                    "family_match_passed": True,
                    "family_guard_recovered_to_repair_action": True,
                    "family_guard_blocked_published_family_id": published_family_id,
                    "family_guard_blocked_cta_family_id": cta_family_id,
                }
            )
            recovered.update(
                {
                    "family": owner_family,
                    "check_key": owner_family,
                    "selected_action_family": owner_family,
                    "title_main": "Strengthening required",
                    "title": "Strengthening required",
                    "headline": "Strengthening required",
                    "governing_label": governing_label,
                    "action_type": "apply_resolved_candidate",
                    "updates": dict(repair_payload.get("updates") or {}),
                    "selected_action_updates": dict(repair_payload.get("updates") or {}),
                    "primary_card_actionable": True,
                    "primary_action": recovered.get("primary_action") or "Run one-click auto design",
                    "guidance_intent": "required_fix",
                    "selected_family": selected_family_id,
                    "selection_reason": chooser.get("selection_reason"),
                    "selected_family_reason": chooser.get("selected_family_reason"),
                    "selected_family_id": selected_family_id,
                    "published_family_id": selected_family_id,
                    "cta_family_id": selected_family_id,
                    "candidate_family_id": candidate_family_id,
                    "card_family_id": selected_family_id,
                    "family_selection_source": source,
                    "family_selection_contract": FAMILY_SELECTION_CONTRACT_ID,
                    "family_chooser_contract": FAMILY_CHOOSER_CONTRACT_ID,
                    "rejected_families": dict(chooser.get("rejected_families") or {}),
                    "selection_evidence": dict(chooser.get("selection_evidence") or {}),
                    "matched_family_ids": list(chooser.get("matched_family_ids") or []),
                    "raw_state_flags": dict(chooser.get("raw_state_flags") or {}),
                    "family_match_passed": True,
                    "family_match_violation_reason": None,
                    "button_contract": dict(recovered_contract),
                }
            )
            evidence = _as_dict(recovered.get("candidate_search_evidence"))
            evidence.update(
                {
                    **diagnostics,
                    "published_family_id": selected_family_id,
                    "cta_family_id": selected_family_id,
                    "card_family_id": selected_family_id,
                    "family_match_passed": True,
                    "family_match_violation_reason": None,
                    "family_guard_recovered_to_repair_action": True,
                    "family_guard_blocked_published_family_id": published_family_id,
                    "family_guard_blocked_cta_family_id": cta_family_id,
                    "wrong_family_guard_fallback_rule": "recovered_to_valid_repair_ACTION",
                }
            )
            recovered["candidate_search_evidence"] = dict(evidence)
            debug.update(
                {
                    **diagnostics,
                    "published_family_id": selected_family_id,
                    "cta_family_id": selected_family_id,
                    "card_family_id": selected_family_id,
                    "family_match_passed": True,
                    "family_match_violation_reason": None,
                    "family_guard_recovered_to_repair_action": True,
                    "family_guard_blocked_published_family_id": published_family_id,
                    "family_guard_blocked_cta_family_id": cta_family_id,
                    "primary_button_contract": dict(recovered_contract),
                    "button_contract": dict(recovered_contract),
                }
            )
            out["guidance_items"] = [recovered] + items[1:]
            out["debug_trace"] = debug
            return out
        safe_item = _family_selection_safe_item(primary, diagnostics)
        debug.update(diagnostics)
        out["guidance_items"] = [safe_item] + items[1:]
        out["debug_trace"] = debug
        return out
    primary.update(
        {
            "selected_family_id": selected_family_id,
            "selected_family": selected_family_id,
            "selection_reason": chooser.get("selection_reason"),
            "selected_family_reason": chooser.get("selected_family_reason"),
            "published_family_id": published_family_id,
            "cta_family_id": cta_family_id,
            "candidate_family_id": candidate_family_id,
            "card_family_id": card_family_id,
            "family_selection_source": source,
            "family_selection_contract": FAMILY_SELECTION_CONTRACT_ID,
            "family_chooser_contract": FAMILY_CHOOSER_CONTRACT_ID,
            "rejected_families": dict(chooser.get("rejected_families") or {}),
            "selection_evidence": dict(chooser.get("selection_evidence") or {}),
            "matched_family_ids": list(chooser.get("matched_family_ids") or []),
            "raw_state_flags": dict(chooser.get("raw_state_flags") or {}),
            "family_match_passed": True,
            "family_match_violation_reason": None,
        }
    )
    evidence = _as_dict(primary.get("candidate_search_evidence"))
    evidence.update(diagnostics)
    primary["candidate_search_evidence"] = dict(evidence)
    contract_payload = button_contract_from_payload(primary, debug)
    if contract_payload:
        contract_payload.update(
            {
                "selected_family_id": selected_family_id,
                "published_family_id": published_family_id,
                "cta_family_id": cta_family_id,
                "candidate_family_id": candidate_family_id,
                "family_selection_contract": FAMILY_SELECTION_CONTRACT_ID,
                "family_match_passed": True,
            }
        )
        primary["button_contract"] = dict(contract_payload)
    debug.update(diagnostics)
    debug["primary_button_contract"] = dict(primary.get("button_contract") or debug.get("primary_button_contract") or {})
    debug["button_contract"] = dict(primary.get("button_contract") or debug.get("button_contract") or {})
    out["guidance_items"] = [primary] + items[1:]
    out["debug_trace"] = debug
    return out


def _publication_text(primary: dict, debug: dict, *, include_debug: bool = True) -> str:
    parts = [
        primary.get("title_main"),
        primary.get("title"),
        primary.get("headline"),
        primary.get("governing_label"),
        primary.get("summary_line"),
        primary.get("primary_action"),
        primary.get("secondary_action"),
        primary.get("reasoning"),
        primary.get("subtext"),
        primary.get("guidance_intent"),
        primary.get("design_guide_terminal_state"),
        primary.get("action_type"),
        primary.get("candidate_id"),
        primary.get("source_candidate_id"),
    ]
    if include_debug:
        parts.extend(
            [
                debug.get("selected_title"),
                debug.get("primary_card_title"),
                debug.get("primary_guidance_intent"),
            ]
        )
    return " ".join(str(part or "") for part in parts).strip().lower()


def _publication_has_repair_action(primary: dict, debug: dict, active_failures: list[str]) -> bool:
    return bool(_repair_action_payload_from_publication(primary, debug, active_failures))


def _publication_has_legal_no_repair_proof(primary: dict, debug: dict, result: dict) -> bool:
    evidence = _as_dict(
        primary.get("candidate_search_evidence")
        or _as_dict(primary.get("action_payload")).get("candidate_search_evidence")
        or _as_dict(primary.get("resolved_candidate")).get("candidate_search_evidence")
        or _as_dict(result.get("evidence")).get("candidate_search")
        or debug.get("candidate_search_evidence")
    )
    if _bending_fail_has_family_owned_repair_blocked_proof(primary, debug, result, evidence):
        return True
    text = _publication_text(primary, debug)
    locked = bool(
        evidence.get("locked_no_repair")
        or evidence.get("locked_repair_variables")
        or "locked_no_repair" in text
        or "locked no repair" in text
    )
    exhausted = bool(
        (evidence.get("repair_search_ran") or evidence.get("candidate_search_ran"))
        and (evidence.get("repair_search_exhaustive") or evidence.get("candidate_search_exhaustive"))
        and (
            evidence.get("attempted_candidate_count")
            or evidence.get("candidate_inventory_count")
            or evidence.get("rejected_candidate_count")
        )
        and (
            evidence.get("failed_check_name")
            or evidence.get("reason")
            or evidence.get("engineering_reason")
            or evidence.get("blocked_reason")
        )
    )
    return bool(locked or exhausted)


def _bending_fail_has_family_owned_repair_blocked_proof(
    primary: dict,
    debug: dict,
    result: dict,
    evidence: dict | None = None,
) -> bool:
    evidence_d = _as_dict(evidence)
    proof = _as_dict(
        evidence_d.get("bending_fail_blocked_ownership_proof")
        or _as_dict(evidence_d.get("repair_reason_proof")).get("blocked_ownership_proof")
        or _as_dict(primary.get("repair_reason_proof")).get("blocked_ownership_proof")
        or _as_dict(debug.get("repair_reason_proof")).get("blocked_ownership_proof")
        or _as_dict(result.get("repair_reason_proof")).get("blocked_ownership_proof")
    )
    family_id = str(
        proof.get("family_id")
        or evidence_d.get("family_id")
        or evidence_d.get("governing_family")
        or evidence_d.get("family_name")
        or primary.get("published_family_id")
        or primary.get("candidate_family_id")
        or debug.get("published_family_id")
        or result.get("published_family_id")
        or ""
    ).strip().upper()
    if family_id != "BENDING_FAIL_GOVERNS":
        return False
    repair_blocked = bool(proof.get("repair_blocked") or evidence_d.get("bending_fail_repair_blocked"))
    hard_blocker = bool(proof.get("hard_blocker_proven") or evidence_d.get("bending_fail_hard_blocker_proven"))
    strategy_exhaustion = bool(
        proof.get("contract_strategy_exhaustion_proven")
        or evidence_d.get("bending_fail_contract_strategy_exhaustion_proven")
    )
    cap_only = bool(proof.get("internal_cap_only") or evidence_d.get("bending_fail_internal_cap_only"))
    source = str(proof.get("blocked_reason_source") or evidence_d.get("bending_fail_blocked_reason_source") or "")
    return bool(repair_blocked and (hard_blocker or strategy_exhaustion) and not cap_only and source)


def _blocked_publication_type(primary: dict, debug: dict, result: dict) -> str | None:
    contract = button_contract_from_payload(primary, debug)
    primary_text = _publication_text(primary, debug, include_debug=False)
    text = primary_text or _publication_text(primary, debug)
    intent = str(primary.get("guidance_intent") or debug.get("primary_guidance_intent") or "").strip().lower()
    status = str(primary.get("status") or result.get("status") or "").strip().upper()
    outcome = str(result.get("outcome_id") or "").strip().lower()
    terminal = str(primary.get("design_guide_terminal_state") or result.get("design_guide_terminal_state") or "").strip().lower()
    cta_enabled = contract_enabled(contract)
    if "design is efficient" in text or intent == "already_efficient":
        return "Design is efficient"
    if status == "PASS" or outcome == "passing_exact_stop":
        return "PASS"
    if "exact" in text and ("stop" in text or "proof" in text or terminal == "optimal"):
        return "exact-stop proof"
    if (
        "cleanup" in text
        or "optimisation" in text
        or "optimization" in text
        or intent in {"efficiency_tightening", "optional_cleanup"}
    ):
        return "blocked cleanup" if not cta_enabled or "blocked" in text else "cleanup optimisation"
    return None


def _underdesign_boundary_safe_item(primary: dict, active_failures: list[str], blocked_type: str | None) -> dict:
    if {"bending", "shear"}.issubset(set(active_failures)):
        family = "combined"
        title = "Bending and shear capacity are low"
        reason = "Combined bending and shear failure requires repair or explicit no-repair evidence before cleanup can be published."
    elif "shear" in active_failures:
        family = "shear"
        title = "Shear capacity is low"
        reason = "Shear failure requires repair or explicit no-repair evidence before cleanup can be published."
    elif "bending" in active_failures:
        family = "bending"
        title = "Bending capacity is low"
        reason = "Bending failure requires repair or explicit no-repair evidence before cleanup can be published."
    else:
        family = str(primary.get("family") or primary.get("check_key") or "serviceability")
        title = "Repair required"
        reason = "An active failure requires repair or explicit no-repair evidence before cleanup can be published."
    blocked_label = str(blocked_type or "forbidden publication").strip()
    item = dict(primary)
    for stale_key in (
        "button_contract",
        "action_payload",
        "resolved_candidate",
        "selected_action_updates",
        "updates",
        "design_guide_terminal_state",
        "terminal_cleanup_state",
        "primary_card_actionable",
    ):
        item.pop(stale_key, None)
    item.update(
        {
            "title_main": title,
            "title": title,
            "headline": title,
            "governing_label": "Repair required",
            "summary_line": "Repair or explicit no-repair evidence is required.",
            "family": family,
            "check_key": family,
            "selected_action_family": family,
            "status": "FAIL",
            "critical_status": "FAIL",
            "guidance_intent": "required_fix",
            "final_state_class": "blocked",
            "primary_action": "Repair required",
            "reasoning": f"{reason} The proposed non-repair outcome was blocked by contract.",
            "contract_boundary_blocked_publication": True,
            "contract_boundary_contract": UNDERDESIGN_REPAIR_INVARIANT_CONTRACT_ID,
            "contract_boundary_violation_reason": reason,
            "blocked_publication_type": blocked_label,
            "button_contract": {
                "enabled": False,
                "actionable": False,
                "family": family,
                "action_type": None,
                "updates": {},
                "blocking_reason": "underdesign_repair_invariant_requires_repair_or_no_repair_proof",
            },
        }
    )
    evidence = _as_dict(item.get("candidate_search_evidence"))
    evidence.update(
        {
            "active_failures": list(active_failures),
            "contract_boundary_checked": True,
            "contract_boundary_contract": UNDERDESIGN_REPAIR_INVARIANT_CONTRACT_ID,
            "contract_boundary_passed": False,
            "contract_boundary_violation_reason": reason,
            "blocked_publication_type": blocked_label,
        }
    )
    item["candidate_search_evidence"] = dict(evidence)
    return item


def enforce_underdesign_repair_publication_boundary(payload: dict) -> dict:
    """Validate final visible publication against the underdesign repair invariant.

    This is a pure publication boundary. It does not generate candidates,
    execute buttons, render UI, or change engineering calculations.
    """
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    items = [dict(item) for item in _as_list(out.get("guidance_items")) if isinstance(item, dict)]
    debug = _as_dict(out.get("debug_trace"))
    result = _as_dict(out.get("design_brain_result") or debug.get("design_brain_result"))
    primary = dict(items[0]) if items else {}
    active_failures = _active_failures_from_publication_payload(out, debug, result)
    contract = _load_underdesign_repair_invariant_contract()
    blocked_type = _blocked_publication_type(primary, debug, result) if primary else None
    diagnostic = {
        "contract_boundary_checked": True,
        "contract_boundary_contract": UNDERDESIGN_REPAIR_INVARIANT_CONTRACT_ID,
        "contract_boundary_passed": True,
        "contract_boundary_violation_reason": None,
        "active_failures": list(active_failures),
        "proposed_card_title": str(primary.get("title_main") or primary.get("title") or ""),
        "proposed_cta_label": str(primary.get("primary_action") or ""),
        "blocked_publication_type": blocked_type,
        "contract_loaded": bool(contract),
    }
    if not primary or not (set(active_failures) & {"bending", "shear"}):
        debug.update(diagnostic)
        out["debug_trace"] = debug
        return out
    if _publication_has_repair_action(primary, debug, active_failures):
        diagnostic["allowed_outcome"] = "repair_ACTION"
        repair_item = dict(primary)
        repair_item["governing_label"] = "Repair preview"
        repair_item.setdefault("summary_line", "Run one-click auto design.")
        repair_item["guidance_intent"] = "required_fix"
        repair_item["status"] = repair_item.get("status") or "FAIL"
        evidence = _as_dict(repair_item.get("candidate_search_evidence"))
        evidence.update(
            {
                "active_failures": list(active_failures),
                "contract_boundary_checked": True,
                "contract_boundary_contract": UNDERDESIGN_REPAIR_INVARIANT_CONTRACT_ID,
                "contract_boundary_passed": True,
                "allowed_outcome": "repair_ACTION",
            }
        )
        repair_item["candidate_search_evidence"] = dict(evidence)
        out["guidance_items"] = [repair_item] + items[1:]
        debug.update(diagnostic)
        out["debug_trace"] = debug
        return out
    if _publication_has_legal_no_repair_proof(primary, debug, result):
        diagnostic["allowed_outcome"] = "EXHAUSTED_REPAIR_SEARCH_WITH_PROOF"
        debug.update(diagnostic)
        out["debug_trace"] = debug
        return out
    selected_family_id, selected_family_source = _selected_family_id_from_publication(out, primary, debug, result)
    if active_failures == ["bending"] and selected_family_id == "BENDING_FAIL_GOVERNS":
        diagnostic.update(
            {
                "contract_boundary_passed": False,
                "contract_boundary_violation_reason": (
                    "bending_fail_governs_missing_repair_ACTION_or_family_owned_no_repair_proof"
                ),
                "selected_family_id": selected_family_id,
                "selected_family_source": selected_family_source,
                "family_owned_boundary_passthrough": True,
                "family_owned_boundary_passthrough_reason": (
                    "Publication must not manufacture BENDING_FAIL_GOVERNS repair-blocked legality."
                ),
            }
        )
        debug.update(diagnostic)
        out["debug_trace"] = debug
        return out
    if not blocked_type:
        blocked_type = "missing repair ACTION or legal no-repair proof"
    safe_item = _underdesign_boundary_safe_item(primary, active_failures, blocked_type)
    diagnostic.update(
        {
            "contract_boundary_passed": False,
            "contract_boundary_violation_reason": "active_failure_requires_repair_ACTION_or_legal_no_repair_proof",
            "blocked_publication_type": blocked_type,
            "safe_publication_title": safe_item.get("title_main") or safe_item.get("title"),
        }
    )
    debug.update(diagnostic)
    debug["design_brain_publication_contract_enforced"] = True
    debug["design_brain_publication_contract_enforcement_reason"] = (
        "underdesign_repair_invariant_blocked_invalid_publication"
    )
    out["guidance_items"] = [safe_item] + items[1:]
    out["debug_trace"] = debug
    return out


def outcome_id_for_publication(
    *,
    active_failures: list[str],
    cta_enabled: bool,
    primary: dict,
    summary: dict,
    evidence: dict,
) -> str:
    intent = str(primary.get("guidance_intent") or "").strip().lower()
    status = str(primary.get("status") or primary.get("critical_status") or "").strip().upper()
    terminal = str(primary.get("design_guide_terminal_state") or "").strip().lower()
    if active_failures:
        return "active_required_failure"
    if cta_enabled and (
        intent in {"efficiency_tightening", "optional_cleanup"}
        or int(evidence.get("safe_local_cleanup_count") or 0) > 0
    ):
        return "passing_with_safe_optimisation_available"
    if terminal or intent == "already_efficient" or status == "PASS":
        return "passing_exact_stop"
    if intent == "specific_blocker" or "blocked" in str(primary.get("title_main") or primary.get("title") or "").lower():
        return "blocked_specific_reason"
    if summary.get("any_fail"):
        return "active_required_failure"
    return "unknown"


def card_kind_for_publication(*, cta_enabled: bool, intent: str, status: str | None) -> str | None:
    return "ACTION" if cta_enabled else (
        "PASS" if intent == "already_efficient" or status == "PASS" else (
            "BLOCKED" if intent == "specific_blocker" else None
        )
    )


def _safe_combined_updates_from_result(
    *,
    result: dict,
    proof: dict,
    evidence: dict,
) -> dict:
    target_id = str(proof.get("candidate_id") or "combined_best_safe_shear_plus_bending_cleanup")
    for source in (
        proof.get("updates"),
        evidence.get("selected_candidate_updates"),
        evidence.get("best_safe_candidate_updates"),
        evidence.get("closest_safe_candidate_updates"),
    ):
        updates = _as_dict(source)
        if updates:
            return updates
    for option in _as_list(result.get("optimisation_options")) + _as_list(result.get("repair_options")):
        if not isinstance(option, dict):
            continue
        option_id = str(option.get("candidate_id") or "").strip()
        raw = _as_dict(option.get("raw"))
        raw_id = str(raw.get("candidate_id") or raw.get("id") or "").strip()
        if target_id not in {option_id, raw_id}:
            continue
        for source in (
            option.get("updates"),
            raw.get("updates"),
            raw.get("proposed_updates"),
            raw.get("selected_candidate_updates"),
            raw.get("best_safe_candidate_updates"),
            raw.get("closest_safe_candidate_updates"),
        ):
            updates = _as_dict(source)
            if updates:
                return updates
    for row in candidate_rows_from_evidence(evidence):
        row_id = str(row.get("candidate_id") or row.get("id") or "").strip()
        row_title = str(row.get("title") or row.get("label") or "").strip()
        if target_id not in row_id and target_id not in row_title:
            continue
        candidate = normalise_candidate_row(row, fallback_id=target_id)
        updates = _as_dict(candidate.get("updates"))
        if updates:
            return updates
    return {}


def _safe_combined_active_failure_reason(result: dict, debug: dict) -> str | None:
    active = {
        str(item or "").strip().lower()
        for item in _as_list(result.get("active_failures"))
        if str(item or "").strip()
    }
    statuses = _as_dict(_as_dict(debug.get("overview")).get("statuses"))
    active.update(
        str(family or "").strip().lower()
        for family, status in statuses.items()
        if str(status or "").strip().upper() == "FAIL" and str(family or "").strip()
    )
    active = {("deflection" if item == "serviceability" else item) for item in active}
    if active:
        return "active_required_failure_invalidates_safe_cleanup_candidate"
    return None


def _remove_safe_combined_validation_failure(validation: dict) -> dict:
    out = dict(validation or {})
    out["failures"] = [
        failure
        for failure in _as_list(out.get("failures"))
        if failure != "safe_combined_cleanup_candidate_visible_cta_disabled"
    ]
    out["warnings"] = [
        warning
        for warning in _as_list(out.get("warnings"))
        if warning != "safe_combined_cleanup_candidate_visible_cta_disabled"
    ]
    out["ok"] = not bool(out.get("failures"))
    return out


def enforce_design_brain_publication_contract(payload: dict) -> dict:
    """Reroute only the proven safe-combined-cleanup stale publication state.

    The function is intentionally narrow: it does not search for candidates or
    change engineering semantics. It only publishes an already proven,
    executor-backed, preview-PASS combined cleanup candidate when the final
    visible publication has drifted to a terminal/blocker/no-CTA state.
    """
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    items = [dict(item) for item in _as_list(out.get("guidance_items")) if isinstance(item, dict)]
    if not items:
        return out
    debug = _as_dict(out.get("debug_trace"))
    result = _as_dict(out.get("design_brain_result") or debug.get("design_brain_result"))
    if not result:
        debug["design_brain_publication_contract_enforced"] = False
        debug["design_brain_publication_contract_skip_reason"] = "missing_design_brain_result"
        out["debug_trace"] = debug
        return out
    result_evidence = _as_dict(result.get("evidence"))
    proof = _as_dict(
        debug.get("design_brain_safe_combined_cleanup_proof")
        or result_evidence.get("safe_combined_cleanup")
    )
    evidence = _as_dict(result_evidence.get("candidate_search") or debug.get("candidate_search_evidence"))
    candidate_id = str(proof.get("candidate_id") or "").strip()
    if not candidate_id:
        candidate_id = str(evidence.get("selected_candidate_id") or evidence.get("best_safe_candidate_id") or "").strip()
    target_id = "combined_best_safe_shear_plus_bending_cleanup"
    if target_id not in candidate_id:
        debug["design_brain_publication_contract_enforced"] = False
        debug["design_brain_publication_contract_skip_reason"] = "safe_combined_candidate_not_found"
        out["debug_trace"] = debug
        return out
    updates = _safe_combined_updates_from_result(result=result, proof=proof, evidence=evidence)
    skip_reason = None
    if not proof.get("safe_cleanup_candidate_found"):
        skip_reason = "safe_combined_candidate_not_proven"
    elif proof.get("preview_pass") is not True:
        skip_reason = "safe_combined_candidate_preview_not_pass"
    elif not proof.get("executor_backed"):
        skip_reason = "safe_combined_candidate_not_executor_backed"
    elif not updates:
        skip_reason = "safe_combined_candidate_missing_updates"
    else:
        skip_reason = _safe_combined_active_failure_reason(result, debug)
    if skip_reason:
        proof["publication_contract_skip_reason"] = skip_reason
        proof["publication_contract_enforced"] = False
        validation = _as_dict(result.get("validation") or result_evidence.get("validation"))
        if skip_reason != "safe_combined_candidate_preview_not_pass":
            validation.setdefault("failures", [])
        result["validation"] = validation
        result_evidence["safe_combined_cleanup"] = dict(proof)
        result["evidence"] = dict(result_evidence)
        debug["design_brain_result"] = dict(result)
        debug["design_brain_safe_combined_cleanup_proof"] = dict(proof)
        debug["design_brain_publication_contract_enforced"] = False
        debug["design_brain_publication_contract_skip_reason"] = skip_reason
        out["design_brain_result"] = dict(result)
        out["debug_trace"] = debug
        return out

    primary = dict(items[0])
    contract = button_contract_from_payload(primary, debug)
    current_enabled = contract_enabled(contract)
    title_text = str(primary.get("title_main") or primary.get("title") or "").strip().lower()
    current_kind = str(result.get("card_kind") or "").strip().upper()
    current_outcome = str(result.get("outcome_id") or "").strip()
    stale_terminal_or_blocked = bool(
        not current_enabled
        or current_kind in {"BLOCKED", "PASS"}
        or current_outcome in {"blocked_specific_reason", "passing_exact_stop"}
        or "blocked" in title_text
        or primary.get("design_guide_terminal_state")
    )
    if not stale_terminal_or_blocked:
        proof["publication_contract_enforced"] = False
        proof["publication_contract_skip_reason"] = "publication_already_actionable"
        proof["final_cta_enabled"] = True
        debug["design_brain_safe_combined_cleanup_proof"] = dict(proof)
        out["debug_trace"] = debug
        return out

    expected = proof.get("expected_utilisation") or evidence.get("selected_candidate_util") or evidence.get("best_safe_final_util")
    label = str(proof.get("label") or result.get("selected_candidate_label") or "").strip()
    if not label or "blocked" in label.lower():
        label = str(evidence.get("selected_candidate_title") or "Shear and bending cleanup - one-click optimisation")
    cleaned_evidence = clean_safe_combined_evidence(
        evidence,
        candidate_id=candidate_id,
        updates=updates,
        label=label,
        expected=expected,
    )
    contract = {
        **dict(contract or {}),
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "combined",
        "updates": dict(updates),
        "preview_pass": True,
        "blocking_reason": None,
        "source_candidate_id": candidate_id,
        "candidate_id": candidate_id,
    }
    expected_value = _as_float(expected)
    if expected_value is not None:
        contract["expected_util"] = expected_value
    item = dict(primary)
    for stale_key in (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
        "blocker_attempts_by_family",
        "terminal_state_blocked_by_local_cleanup",
        "design_guide_terminal_state",
        "terminal_cleanup_state",
    ):
        item.pop(stale_key, None)
    item.update(
        {
            "title_main": label,
            "title": label,
            "family": "combined",
            "check_key": "combined",
            "selected_action_family": "combined",
            "status": "EFFICIENCY",
            "guidance_intent": "efficiency_tightening",
            "action_type": "apply_resolved_candidate",
            "primary_card_actionable": True,
            "updates": dict(updates),
            "selected_action_updates": dict(updates),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "button_contract": dict(contract),
            "candidate_search_evidence": dict(cleaned_evidence),
            "primary_action": item.get("primary_action") or "Run one-click auto design",
        }
    )
    if expected_value is not None:
        item["util"] = expected_value
        item["expected_util"] = expected_value
        item["candidate_post_util"] = expected_value
    action_payload = dict(item.get("action_payload") or {})
    action_payload.update(
        {
            "action_type": "apply_resolved_candidate",
            "family": "combined",
            "updates": dict(updates),
            "resolved_candidate_updates": dict(updates),
            "resolved_candidate_action_type": "apply_resolved_candidate",
            "resolved_candidate_family_tag": "combined",
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "candidate_search_evidence": dict(cleaned_evidence),
        }
    )
    if expected_value is not None:
        action_payload["expected_util"] = expected_value
        action_payload["candidate_post_util"] = expected_value
        action_payload["resolved_candidate_post_util"] = expected_value
    item["action_payload"] = dict(action_payload)
    resolved = dict(item.get("resolved_candidate") or {})
    resolved.update(
        {
            "action_type": "apply_resolved_candidate",
            "family": "combined",
            "recommendation_family_tag": "combined",
            "updates": dict(updates),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "candidate_search_evidence": dict(cleaned_evidence),
        }
    )
    if expected_value is not None:
        resolved["expected_util"] = expected_value
        resolved["candidate_post_util"] = expected_value
    item["resolved_candidate"] = dict(resolved)

    proof.update(
        {
            "safe_cleanup_candidate_found": True,
            "candidate_id": candidate_id,
            "candidate_family": "combined",
            "executor_backed": True,
            "preview_pass": True,
            "updates": dict(updates),
            "label": label,
            "expected_utilisation": expected_value,
            "final_published_outcome": "passing_with_safe_optimisation_available",
            "final_cta_enabled": True,
            "publication_contract_enforced": True,
            "publication_contract_enforcement_reason": "safe_executable_combined_cleanup_outranks_stale_blocker",
        }
    )
    cta = _as_dict(result.get("cta"))
    cta.update(
        {
            "intent": "efficiency_tightening",
            "enabled": True,
            "disabled_reason": None,
            "executor_backed": True,
            "action_type": "apply_resolved_candidate",
            "updates": dict(updates),
            "candidate_id": candidate_id,
            "preview_pass": True,
        }
    )
    contract_ids = list(dict.fromkeys(_as_list(result.get("contract_ids")) + [
        "passing_with_safe_optimisation_available",
        "candidate_integrity",
    ]))
    validation = _remove_safe_combined_validation_failure(
        _as_dict(result.get("validation") or result_evidence.get("validation"))
    )
    validation["publication_contract_enforced"] = True
    result.update(
        {
            "outcome_id": "passing_with_safe_optimisation_available",
            "contract_ids": contract_ids,
            "status": "EFFICIENCY",
            "card_kind": "ACTION",
            "is_terminal": False,
            "selected_candidate_id": candidate_id,
            "selected_candidate_label": label,
            "cta": dict(cta),
            "validation": dict(validation),
        }
    )
    result_evidence["candidate_search"] = dict(cleaned_evidence)
    result_evidence["safe_combined_cleanup"] = dict(proof)
    result_evidence["validation"] = dict(validation)
    result["evidence"] = dict(result_evidence)

    debug.update(
        {
            "design_brain_publication_contract_enforced": True,
            "design_brain_publication_contract_enforcement_reason": "safe_executable_combined_cleanup_outranks_stale_blocker",
            "design_brain_result": dict(result),
            "design_brain_result_validation": dict(validation),
            "design_brain_safe_combined_cleanup_proof": dict(proof),
            "candidate_search_evidence": dict(cleaned_evidence),
            "primary_button_contract": dict(contract),
            "displayed_primary_button_contract": dict(contract),
            "button_contract": dict(contract),
            "button_contract_enabled": True,
            "button_contract_updates": dict(updates),
            "button_contract_preview_pass": True,
            "button_contract_blocking_reason": None,
            "selected_title": label,
            "selected_action_type": "apply_resolved_candidate",
            "selected_action_family": "combined",
            "primary_card_title": label,
            "primary_card_intent": "efficiency_tightening",
            "primary_guidance_intent": "efficiency_tightening",
            "design_guide_terminal_state": None,
            "design_guide_terminal_positive": False,
            "design_guide_has_actionable_recommendation": True,
        }
    )
    for stale_key in (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
        "blocker_attempts_by_family",
    ):
        debug.pop(stale_key, None)
    out["guidance_items"] = [item] + items[1:]
    out["design_brain_result"] = dict(result)
    out["debug_trace"] = debug
    return out
