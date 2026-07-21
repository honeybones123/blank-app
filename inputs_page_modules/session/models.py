from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InputsSessionEntry:
    key: str
    value: Any


@dataclass(frozen=True)
class InputsSessionSourceSnapshot:
    entries: tuple[InputsSessionEntry, ...]
    display_hash: str


@dataclass(frozen=True)
class InputsSummarySourceShapingSnapshot:
    working_state: dict[str, Any]
    overlay_applied: dict[str, dict[str, Any]]
    shared_only_mode: bool
    shared_only_reason: str
    display_hash: str


@dataclass(frozen=True)
class InputsDesignActionResultOverlaySnapshot:
    working_state: dict[str, Any]
    result_overlay: dict[str, dict[str, Any]]
    overlay_applied: dict[str, dict[str, Any]]
    display_hash: str


@dataclass(frozen=True)
class InputsSummaryDebugPayloadSnapshot:
    debug_payload: dict[str, Any]
    compact_diffs: dict[str, dict[str, Any]]
    display_hash: str


@dataclass(frozen=True)
class InputsSummaryStateModeMarkerSnapshot:
    marker_payload: dict[str, Any]
    display_hash: str


@dataclass(frozen=True)
class InputsShearWidgetMirrorOverlayPlan:
    working_state: dict[str, Any]
    overlay_applied: dict[str, dict[str, Any]]
    debug_payload: dict[str, Any]
    display_hash: str


@dataclass(frozen=True)
class InputsModelReoWidgetMirrorOverlayPlan:
    working_state: dict[str, Any]
    overlay_keys: tuple[str, ...]
    debug_payload: dict[str, Any]
    suppressed: bool
    display_hash: str


@dataclass(frozen=True)
class InputsModelStateDebugPayloadSnapshot:
    debug_payload: dict[str, Any]
    display_hash: str


@dataclass(frozen=True)
class InputsSummarySharedOnlyDecision:
    shared_only_mode: bool
    reason: str
    display_hash: str


@dataclass(frozen=True)
class InputsNormalizedShearTruthOverlaySnapshot:
    merged_state: dict[str, Any]
    session_overlay: dict[str, Any]
    normalized_overlay: dict[str, Any]
    display_hash: str


@dataclass(frozen=True)
class InputsSamePageRerunNonLandingDecision:
    should_suppress_landing: bool
    reason: str
    display_hash: str


@dataclass(frozen=True)
class InputsHasDesignActionsOrLoadsDecision:
    has_design_actions_or_loads: bool
    nonzero_keys: tuple[str, ...]
    display_hash: str


@dataclass(frozen=True)
class InputsLandingDashboardVisibilityDecision:
    show_landing_dashboard: bool
    no_design_actions: bool
    no_loads: bool
    reason: str
    display_hash: str


@dataclass(frozen=True)
class InputsLandingContextSnapshot:
    context: str
    display_hash: str


@dataclass(frozen=True)
class InputsBrowserRecipeActionAppliedDecision:
    action_already_applied: bool
    reason: str
    display_hash: str


@dataclass(frozen=True)
class InputsAutoDesignInvokeDebugSnapshot:
    debug_payload: dict[str, Any]
    display_hash: str


@dataclass(frozen=True)
class InputsRerunTriggerRecordPlan:
    trigger_payload: dict[str, Any]
    stored_triggers: list[dict[str, Any]]
    log_payload: dict[str, Any]
    ssl_trigger_reason: str
    display_hash: str


@dataclass(frozen=True)
class InputsCandidateSearchReuseStaleApplyDecision:
    stale: bool
    reason: str | None
    display_hash: str


@dataclass(frozen=True)
class InputsCandidateSearchReuseDisabledDecision:
    disabled: bool
    reason: str | None
    display_hash: str


@dataclass(frozen=True)
class InputsCandidateSearchReuseLookupResult:
    payload: dict[str, Any] | None
    cache_hit: bool
    decision: str
    reason: str
    display_hash: str


@dataclass(frozen=True)
class InputsCandidateSearchReuseStorePlan:
    cache: dict[str, Any]
    stored: bool
    key_hash: str
    display_hash: str


@dataclass(frozen=True)
class InputsTracerOneClickActionSourceSummary:
    summary_payload: dict[str, Any]
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideApplyTraceRunEndMetaPlan:
    run_id: str
    meta: dict[str, Any]
    recovered: bool
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideApplyTraceRunEndOutcome:
    final_util: Any
    statuses: dict[str, Any]
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideTracerVerboseLogDecision:
    verbose_log: bool
    reason: str
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideRuntimeTraceSessionSnapshot:
    snapshot: dict[str, Any]
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideRuntimeTraceSessionDiff:
    diff: dict[str, Any]
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideLiveBreadcrumbPayload:
    payload: dict[str, Any]
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideSettleGateDelayDecision:
    delay_ms: int
    reason: str
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideSettleGateEnabledDecision:
    enabled: bool
    reason: str
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideTransientUiClearPlan:
    transient_keys: tuple[str, ...]
    always_clear_keys: tuple[str, ...]
    history_keys: tuple[str, ...]
    all_keys: tuple[str, ...]
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideDirtyMarkPlan:
    refresh_key: str
    refresh_value: bool
    clear_history: bool
    preserve_apply_banner: bool
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideCachedPublicationAvailabilityDecision:
    available: bool
    source: str
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideCachedDebugTrustDecision:
    trustworthy: bool
    reason: str
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideSettleGateDefaultState:
    gate_state: dict[str, Any]
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideSettleGateFingerprintUpdate:
    gate_state: dict[str, Any]
    previous_fingerprint: str
    current_fingerprint: str
    fingerprint_changed: bool
    invalidated_previous_fingerprint: bool
    fingerprint_changes_seen: int
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideSettleGateStabilityDecision:
    gate_state: dict[str, Any]
    decision: dict[str, Any]
    stable: bool
    elapsed_ms: float
    panel_pass_count: int
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideSettleGateWaitingMark:
    gate_state: dict[str, Any]
    decision: dict[str, Any]
    skipped_expensive_publication_count: int
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideSettleGateExpensiveAllowedMark:
    gate_state: dict[str, Any]
    decision: dict[str, Any]
    expensive_publication_count: int
    first_stable_publication_timestamp: str | None
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideSettleGateSnapshotHitDecision:
    snapshot_hit: bool
    source: str
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideGuidanceCacheResult:
    items: list[dict[str, Any]]
    debug: dict[str, Any]
    cache_hit: bool
    source: str
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideGuidanceCacheWritePlan:
    fingerprint: Any
    guidance_items: list[dict[str, Any]]
    cache_debug: dict[str, Any]
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideStepHistoryResetPlan:
    current_anchor: tuple[Any, ...]
    reset_history: bool
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideStepHistoryDebugSummary:
    payload: dict[str, Any]
    display_hash: str


@dataclass(frozen=True)
class InputsDesignGuideApplyStepHistoryEntryPlan:
    entry: dict[str, Any]
    set_first_target_band_step: bool
    first_target_band_step_after_apply: int | None
    display_hash: str
