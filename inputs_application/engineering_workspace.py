"""Typed fragment-owned composition for the interactive Inputs workspace."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import time
from typing import Any, Callable

from application.guidance_result_adapter import (
    guidance_payload_from_authoritative_design_result,
)
from inputs_application.design_guide_fragment_store import (
    DesignGuideFragmentState,
)
from inputs_application.design_brain_polling import (
    DESIGN_BRAIN_POLLING_STATE_KEY,
    register_design_brain_fragment,
    start_design_brain_polling,
    stop_design_brain_polling,
)
from inputs_application.page_runtime import InputsPageRuntime
from inputs_application.region_contexts import (
    InputsCalculationRegionContext,
    InputsControlsRegionContext,
    InputsDesignBrainRegionContext,
    InputsSummaryRegionContext,
    InputsSummaryRegionState,
    RevisionIdentity,
)
from inputs_application.session_services import InputsSessionServices
from inputs_application.summary_contracts import InputsSummaryCalculationSource
from inputs_application.workspace_state_store import InputsWorkspaceStateStore
from inputs_application.design_brain_composition import selected_design_brain_adapter_name
from inputs_application.apply_transaction_store import ApplyTransactionStore
from inputs_application.v2_design_guide_renderer import render_v2_design_guide_card
from inputs_page_modules.fragments import (
    request_inputs_fragment_wake,
    stop_inputs_fragment_polling,
)


PageCallable = Callable[..., Any]

_DESIGN_BRAIN_VISIBLE_REVISION_KEY = "_inputs_design_brain_visible_revision"
_DESIGN_BRAIN_WIDGET_MARKER_REVISION_KEY = (
    "_inputs_design_brain_widget_marker_revision"
)
_DESIGN_BRAIN_WIDGET_MARKER_STATE_KEY = (
    "_inputs_design_brain_widget_marker_state"
)


def _render_design_brain_visibility_marker(
    *,
    st_module: Any,
    workspace_revision: int,
) -> None:
    """Hide an old card while a newer revision is being published.

    The Design Brain is a stopped sibling fragment in its steady state. A
    widget edit can therefore repaint Summary before that sibling gets its
    first wake-up. The marker lets the browser hide the stale card during that
    short hand-off without coupling calculations to Design Brain rendering.
    """

    visible_revision = int(
        st_module.session_state.get(_DESIGN_BRAIN_VISIBLE_REVISION_KEY, 0)
        or 0
    )
    # The current product path owns Design Brain and widgets in the same
    # unified fragment. There is no sibling hand-off window to hide here; the
    # marker's pending CSS only applies to the retired split-fragment route.
    unified_workspace_fragment = (
        str(
            st_module.session_state.get(
                "_inputs_engineering_workspace_fragment_mode"
            )
            or ""
        )
        == "fragment"
    )
    pending = (not unified_workspace_fragment) and (
        visible_revision != int(workspace_revision)
    )
    state = "pending" if pending else "ready"
    st_module.session_state[_DESIGN_BRAIN_WIDGET_MARKER_REVISION_KEY] = int(
        workspace_revision
    )
    st_module.session_state[_DESIGN_BRAIN_WIDGET_MARKER_STATE_KEY] = state
    st_module.markdown(
        f"<div data-testid='inputs-v2-design-brain-visibility' "
        f"data-state='{state}' data-revision='{int(workspace_revision)}' "
        "style='display:none'></div>",
        unsafe_allow_html=True,
    )


@dataclass(frozen=True)
class EngineeringWorkspaceRuntime:
    handle_pending_apply: PageCallable
    reconcile_design_actions: PageCallable
    refresh_authoritative_result: PageCallable
    render_summary: PageCallable
    render_calculation: PageCallable
    render_mode_selector: PageCallable
    render_widgets: PageCallable
    render_batch: PageCallable
    render_design_guide: PageCallable
    render_divider: PageCallable
    refresh_engineering_result: PageCallable | None = None
    refresh_design_brain_result: PageCallable | None = None


def _authoritative_apply_browser_projection(
    authoritative_result: Any | None,
) -> dict[str, Any]:
    """Project the fragment-fresh Apply contract from the immutable result."""

    if authoritative_result is None:
        return {
            "selected_action_updates": {},
            "design_guide_primary_apply_payload": {},
            "design_guide_primary_payload_binding_audit": {},
            "primary_action_type": None,
            "selected_action_type": None,
            "selected_action_family": None,
        }
    apply_payload = dict(authoritative_result.apply_payload or {})
    cta_model = dict(authoritative_result.cta_model or {})
    payload_updates = dict(
        apply_payload.get("updates")
        or apply_payload.get("resolved_candidate_updates")
        or {}
    )
    selected_updates = dict(authoritative_result.selected_updates or {})
    action_type = str(
        apply_payload.get("action_type")
        or apply_payload.get("resolved_candidate_action_type")
        or cta_model.get("action_type")
        or ""
    ).strip() or None
    family = str(
        apply_payload.get("family")
        or authoritative_result.governing_family
        or cta_model.get("family")
        or ""
    ).strip() or None
    candidate_id = (
        apply_payload.get("candidate_id")
        or apply_payload.get("source_candidate_id")
        or cta_model.get("source_candidate_id")
    )
    executable = bool(
        apply_payload
        and payload_updates
        and action_type == "apply_resolved_candidate"
    )
    updates_match = bool(
        executable
        and (not selected_updates or selected_updates == payload_updates)
        and dict(cta_model.get("updates") or payload_updates) == payload_updates
    )
    binding_audit = {
        "visible_primary_candidate_id": candidate_id,
        "button_contract_candidate_id": (
            cta_model.get("source_candidate_id")
            or cta_model.get("candidate_id")
            or candidate_id
        ),
        "queued_apply_candidate_id": None,
        "applied_candidate_id": None,
        "visible_updates": dict(payload_updates),
        "button_contract_updates": dict(cta_model.get("updates") or {}),
        "queued_apply_updates": {},
        "applied_updates": {},
        "payload_binding_match": bool(executable and candidate_id),
        "payload_update_match": updates_match,
        "stale_apply_payload_blocked": False,
        "canonical_primary_payload_exists": bool(apply_payload),
        "legacy_fallback_used": False,
        "winning_button_contract_source": "authoritative_design_result.cta_model",
        "winning_update_payload_source": "authoritative_design_result.apply_payload",
        "winning_action_type_source": "authoritative_design_result.apply_payload",
        "winning_candidate_source": "authoritative_design_result.apply_payload",
        "render_fingerprint": apply_payload.get("render_fingerprint"),
        "state_fingerprint": apply_payload.get("state_fingerprint"),
        "authoritative_publication_hash": (
            authoritative_result.publication_authority_hash
        ),
    }
    return {
        "selected_action_updates": dict(payload_updates),
        "design_guide_primary_apply_payload": dict(apply_payload),
        "design_guide_primary_payload_binding_audit": binding_audit,
        "primary_action_type": action_type,
        "selected_action_type": action_type,
        "selected_action_family": family,
    }


def _fragment_browser_publication_projection(
    *,
    authoritative_result: Any | None,
    fragment_state: DesignGuideFragmentState,
) -> dict[str, Any]:
    """Project publication truth from the result or its fragment-owned copy."""

    authoritative_payload = guidance_payload_from_authoritative_design_result(
        authoritative_result
    )
    if not authoritative_payload:
        authoritative_payload = dict(fragment_state.active_publication or {})
    final_publication = dict(
        authoritative_payload.get("final_design_guide_publication") or {}
    )
    final_verifier = dict(
        authoritative_payload.get("final_publication_verifier_payload") or {}
    )
    display_model = dict(final_publication.get("display") or {})
    terminal_outcome = (
        final_verifier.get("outcome_state")
        or final_publication.get("outcome_state")
        or display_model.get("outcome_state")
        or display_model.get("display_state")
        or display_model.get("status")
        or (
            authoritative_result.family_outcome
            if authoritative_result is not None
            else None
        )
    )
    if terminal_outcome and not final_verifier.get("outcome_state"):
        # The fragment overlay is the fresh browser-verification projection
        # after Apply.  Preserve the canonical terminal state even when an
        # older verifier-payload serializer omitted it.
        final_verifier["outcome_state"] = str(terminal_outcome).strip().upper()
    cta_model = (
        dict(authoritative_result.cta_model or {})
        if authoritative_result is not None
        else dict(final_publication.get("cta") or {})
    )
    selected_family_id = (
        authoritative_result.governing_family
        if authoritative_result is not None
        else (
            final_verifier.get("selected_family_id")
            or final_publication.get("selected_family")
            or final_publication.get("selected_family_id")
        )
    )
    return {
        "authoritative_payload": authoritative_payload,
        "final_publication": final_publication,
        "final_verifier": final_verifier,
        "cta_model": cta_model,
        "selected_family_id": selected_family_id,
        "engineering_hash": (
            authoritative_result.engineering_hash
            if authoritative_result is not None
            else fragment_state.active_engineering_hash
        ),
        # The calculation result and the Design Brain publication are sibling
        # revisions. During the short hand-off window the calculation result
        # can be current while carrying no publication hash; in that case the
        # fragment-owned publication hash is the authoritative source for the
        # browser probe and must not be replaced with ``None``.
        "publication_authority_hash": (
            getattr(authoritative_result, "publication_authority_hash", None)
            or fragment_state.active_publication_authority_hash
            or final_publication.get("publication_hash")
            or final_verifier.get("final_publication_authority_hash")
            or final_verifier.get("publication_hash")
            or authoritative_payload.get("final_publication_authority_hash")
            or authoritative_payload.get("publication_hash")
        ),
    }


def build_engineering_workspace_runtime(
    page_runtime: InputsPageRuntime,
) -> EngineeringWorkspaceRuntime:
    return EngineeringWorkspaceRuntime(
        handle_pending_apply=page_runtime.handle_pending_apply,
        reconcile_design_actions=page_runtime.reconcile_design_actions,
        refresh_authoritative_result=page_runtime.refresh_authoritative_result,
        refresh_engineering_result=page_runtime.refresh_engineering_result,
        refresh_design_brain_result=page_runtime.refresh_design_brain_result,
        render_summary=page_runtime.render_summary_pipeline,
        render_calculation=page_runtime.render_calculation,
        render_mode_selector=page_runtime.render_design_mode_selector,
        render_widgets=page_runtime.render_widget_sections,
        render_batch=page_runtime.render_batch_design_manager,
        render_design_guide=page_runtime.render_design_guide,
        render_divider=page_runtime.render_page_divider,
    )


def build_inputs_design_brain_region_context(
    *,
    session_state: dict[str, Any],
    services: InputsSessionServices,
    inputs_detailed_mode: bool,
) -> InputsDesignBrainRegionContext | None:
    """Bind the Design Brain region to one ready revision/hash pair."""

    workspace_store = InputsWorkspaceStateStore(session_state)
    input_revision = workspace_store.workspace_revision()
    authoritative_result = services.engineering_results.current()
    authoritative_hash = workspace_store.authoritative_hash()
    if (
        workspace_store.authoritative_revision() != input_revision
        or services.engineering_results.source_input_revision() != input_revision
        or not workspace_store.authoritative_result_present()
        or authoritative_result is None
        or authoritative_result.engineering_hash != authoritative_hash
    ):
        return None
    return InputsDesignBrainRegionContext(
        identity=RevisionIdentity(
            input_revision=input_revision,
            engineering_hash=authoritative_result.engineering_hash,
        ),
        beam_id=str(session_state.get("active_beam_id") or ""),
        inputs_detailed_mode=bool(inputs_detailed_mode),
    )


def build_inputs_calculation_region_context(
    *,
    summary_region_context: InputsSummaryRegionContext,
    summary_source: InputsSummaryCalculationSource,
) -> InputsCalculationRegionContext:
    """Bind Calculation directly to the Summary rendered for one identity."""

    if not isinstance(summary_region_context, InputsSummaryRegionContext):
        raise TypeError(
            "summary_region_context must be an InputsSummaryRegionContext"
        )
    if not isinstance(summary_source, InputsSummaryCalculationSource):
        raise TypeError(
            "summary_source must be an InputsSummaryCalculationSource"
        )
    return InputsCalculationRegionContext(
        identity=summary_region_context.identity,
        summary_source=summary_source,
    )


def build_inputs_summary_region_state(
    *,
    session_state: dict[str, Any],
    services: InputsSessionServices,
) -> InputsSummaryRegionState:
    """Resolve Summary readiness without conflating empty, pending, and failed."""

    workspace_store = InputsWorkspaceStateStore(session_state)
    input_revision = workspace_store.workspace_revision()
    authoritative_result = services.engineering_results.current()
    calculation_state = workspace_store.calculation_status()
    calculation_revision = int(calculation_state.get("revision", 0) or 0)
    calculation_status = str(calculation_state.get("status") or "empty")
    if (
        calculation_status == "awaiting_inputs"
        and calculation_revision == input_revision
        and workspace_store.authoritative_revision() == input_revision
        and not workspace_store.authoritative_result_present()
    ):
        return InputsSummaryRegionState(
            input_revision=input_revision,
            status="awaiting_inputs",
        )
    if calculation_status == "failed" and calculation_revision == input_revision:
        return InputsSummaryRegionState(
            input_revision=input_revision,
            status="failed",
            error=str(calculation_state.get("error") or "calculation_failed"),
        )
    if authoritative_result is None:
        return InputsSummaryRegionState(
            input_revision=input_revision,
            status="updating",
        )
    engineering_hash = authoritative_result.engineering_hash
    current_calculations = dict(
        authoritative_result.current_calculations or {}
    )
    resolved_inputs = current_calculations.get("resolved_inputs")
    packs = current_calculations.get("packs")
    if (
        workspace_store.authoritative_revision() != input_revision
        or services.engineering_results.source_input_revision() != input_revision
        or not workspace_store.authoritative_result_present()
        or workspace_store.authoritative_hash() != engineering_hash
        or calculation_state.get("status") != "ready"
        or int(calculation_state.get("revision", 0) or 0) != input_revision
        or calculation_state.get("engineering_hash") != engineering_hash
        or not isinstance(resolved_inputs, dict)
        or not isinstance(packs, dict)
        or any(
            not isinstance(packs.get(family), dict)
            for family in ("bending", "shear", "crack", "deflection")
        )
    ):
        return InputsSummaryRegionState(
            input_revision=input_revision,
            status="updating",
        )
    return InputsSummaryRegionState(
        input_revision=input_revision,
        status="ready",
        context=InputsSummaryRegionContext(
            identity=RevisionIdentity(
                input_revision=input_revision,
                engineering_hash=engineering_hash,
            ),
            resolved_inputs=dict(resolved_inputs),
            packs={
                family: dict(packs[family])
                for family in ("bending", "shear", "crack", "deflection")
            },
            actions_used=dict(current_calculations.get("actions_used") or {}),
        ),
    )


def build_inputs_controls_region_context(
    *,
    page_context: dict[str, Any],
) -> InputsControlsRegionContext:
    """Adapt the setup dictionary once into immutable Controls inputs."""

    beam_labels = dict(page_context.get("beam_labels") or {})
    beam_order = tuple(str(beam_id) for beam_id in page_context.get("beam_order") or ())
    active_beam_id = str(page_context.get("active_beam_id") or "")
    if beam_order and active_beam_id not in beam_order:
        active_beam_id = beam_order[0]
    return InputsControlsRegionContext(
        beam_labels=tuple(
            (str(beam_id), str(label)) for beam_id, label in beam_labels.items()
        ),
        beam_order=beam_order,
        active_beam_id=active_beam_id,
    )


def prepare_engineering_workspace_transaction(
    *,
    st_module: Any,
    runtime: EngineeringWorkspaceRuntime,
    services: InputsSessionServices,
    include_design_brain: bool = False,
) -> dict[str, Any]:
    """Commit widget actions and refresh the one authoritative result.

    The direct Inputs path follows the standalone V2 page: it asks the
    authoritative V2 service for one revision-matched result that contains
    both the engineering packs and Design Brain publication.  The legacy
    sibling-fragment path passes ``False`` and keeps its historical two-stage
    calculation/Design Brain hand-off for rollback and measurement.
    """

    workspace_store = InputsWorkspaceStateStore(st_module.session_state)
    reconciled_keys = list(runtime.reconcile_design_actions() or [])
    workspace_store.set_reconciled_keys(reconciled_keys)
    workspace_revision = workspace_store.workspace_revision()

    # Fragment polling can overlap a just-completed calculation.  Once the
    # committed revision already has a matching authoritative result, this
    # transaction is complete and must be reused.  Re-entering the refresh
    # path here used to make one widget edit look like several calculations
    # and caused the summary/Design Brain siblings to flicker while they
    # repeatedly rebuilt the same revision.
    existing_result = services.engineering_results.current()
    calculation_state = workspace_store.calculation_status()
    if (
        str(calculation_state.get("status") or "") == "ready"
        and int(calculation_state.get("revision", 0) or 0) == workspace_revision
        and workspace_store.authoritative_result_present()
        and workspace_store.authoritative_revision() == workspace_revision
        and existing_result is not None
        and services.engineering_results.source_input_revision()
        == workspace_revision
        and workspace_store.authoritative_hash()
        == existing_result.engineering_hash
    ):
        fragment_state = services.publications.current()
        return {
            "reconciled_design_action_keys": reconciled_keys,
            "engineering_hash": existing_result.engineering_hash,
            "calculation_status": "ready",
            "design_guide_fragment_status": fragment_state.status,
            "design_guide_publication_authority_hash": (
                fragment_state.active_publication_authority_hash
            ),
        }

    workspace_store.begin_calculation(revision=workspace_revision)
    fragment_store = services.publications
    fragment_store.begin_refresh(workspace_revision=workspace_revision)
    compute_counts = dict(
        st_module.session_state.get("_inputs_engineering_compute_count_by_revision")
        or {}
    )
    revision_key = str(int(workspace_revision))
    compute_counts[revision_key] = int(compute_counts.get(revision_key, 0) or 0) + 1
    st_module.session_state[
        "_inputs_engineering_compute_count_by_revision"
    ] = compute_counts
    try:
        engineering_refresh = (
            runtime.refresh_authoritative_result
            if include_design_brain
            else (
                runtime.refresh_engineering_result
                or runtime.refresh_authoritative_result
            )
        )
        authoritative_result = engineering_refresh()
    except Exception as exc:
        workspace_store.fail_calculation(revision=workspace_revision, error=exc)
        fragment_store.fail_refresh(exc)
        raise
    input_transaction = dict(
        st_module.session_state.get(
            "_inputs_engineering_input_transaction_probe"
        )
        or {}
    )
    committed_revision = int(
        services.input_snapshots.current().revision
        or input_transaction.get("revision", workspace_revision)
        or workspace_revision
    )
    if committed_revision != workspace_revision:
        # The committed input transaction is the sole revision authority. This
        # branch handles startup migration and a newer edit observed before the
        # calculation began; it never writes a second revision counter.
        workspace_revision = committed_revision
        workspace_store.begin_calculation(revision=workspace_revision)
        fragment_store.begin_refresh(workspace_revision=workspace_revision)
    if authoritative_result is None:
        # An untouched beam with no actions or explicit design state is not a
        # calculation failure and is not work that polling should retry. Clear
        # all result/publication authorities and publish the explicit idle
        # outcome for this committed input revision.
        services.engineering_results.clear()
        services.recommendations.clear_all()
        fragment_store.clear()
        workspace_store.await_calculation_inputs(revision=workspace_revision)
        workspace_store.publish_authoritative_result(
            revision=workspace_revision,
            result=None,
        )
        return {
            "reconciled_design_action_keys": reconciled_keys,
            "engineering_hash": None,
            "calculation_status": "awaiting_inputs",
            "design_guide_fragment_status": "empty",
            "design_guide_publication_authority_hash": None,
        }
    expected_engineering_hash = input_transaction.get("engineering_hash")
    if (
        authoritative_result is not None
        and expected_engineering_hash
        and authoritative_result.engineering_hash != expected_engineering_hash
    ):
        error = "engineering result does not match committed input revision"
        workspace_store.fail_calculation(revision=workspace_revision, error=error)
        fragment_store.fail_refresh(error)
        raise ValueError(error)
    workspace_store.publish_calculation(
        revision=workspace_revision,
        engineering_hash=(
            authoritative_result.engineering_hash
            if authoritative_result is not None
            else None
        ),
    )
    workspace_store.publish_authoritative_result(
        revision=workspace_revision,
        result=authoritative_result,
    )
    # Calculation readiness is the only trigger that may start Design Brain.
    # The Design Brain fragment can mount before this sibling publishes its
    # first result, so explicitly wake the matching revision once the result
    # is authoritative. This avoids a permanent "Updating design guidance"
    # state without introducing a steady-state polling loop.
    start_design_brain_polling(
        st_module.session_state,
        reason="calculation_revision_ready",
        revision=workspace_revision,
        interval_s=0.1,
    )
    fragment_state = fragment_store.current()
    return {
        "reconciled_design_action_keys": reconciled_keys,
        "engineering_hash": (
            authoritative_result.engineering_hash
            if authoritative_result is not None
            else None
        ),
        "design_guide_fragment_status": fragment_state.status,
        "design_guide_publication_authority_hash": (
            fragment_state.active_publication_authority_hash
        ),
        "calculation_status": "ready",
    }


def render_inputs_summary_fragment_section(
    *,
    st_module: Any,
    runtime: EngineeringWorkspaceRuntime,
    page_context: dict[str, Any],
    region_context: InputsSummaryRegionContext,
) -> Any:
    """Render Summary from one immutable, revision-matched calculation result."""

    summary_source = runtime.render_summary(
        ss=st_module.session_state,
        sync_callbacks=page_context["sync_callbacks"],
        skip_active_beam_record_write=False,
        mark=page_context["mark"],
        summary_container=st_module.container(),
        render_title=False,
        region_context=region_context,
    )
    if not isinstance(summary_source, InputsSummaryCalculationSource):
        raise TypeError(
            "Summary renderer must return an InputsSummaryCalculationSource"
        )
    return summary_source


def render_inputs_calculation_fragment_section(
    *,
    runtime: EngineeringWorkspaceRuntime,
    page_context: dict[str, Any],
    region_context: InputsCalculationRegionContext,
) -> None:
    """Render Calculation only from a current immutable Summary handoff."""

    runtime.render_calculation(
        summary_source=region_context.summary_source,
        trace_fn=page_context["pre_widget_trace"],
    )


def render_inputs_controls_fragment_section(
    *,
    st_module: Any,
    runtime: EngineeringWorkspaceRuntime,
    region_context: InputsControlsRegionContext,
) -> bool:
    """Render the existing mode and batch controls in their current order."""

    runtime.render_batch(
        ss=st_module.session_state,
        beam_labels=region_context.labels_dict(),
        beam_order=list(region_context.beam_order),
        active_beam_id=region_context.active_beam_id,
    )
    return bool(
        st_module.session_state.get(
            "inputs_detailed_mode_toggle",
            st_module.session_state.get("inputs_detailed_mode", False),
        )
    )


def render_inputs_design_guide_fragment_section(
    *,
    st_module: Any,
    runtime: EngineeringWorkspaceRuntime,
    page_context: dict[str, Any],
    services: InputsSessionServices,
    region_context: InputsDesignBrainRegionContext,
    design_guide_slot=None,
) -> None:
    """Render Design Guide only from the current authoritative result."""

    apply_requested = bool(
        st_module.session_state.get("_inputs_action_apply_recommendation")
        or st_module.session_state.get(
            "_inputs_action_apply_recommendation_payload"
        )
    )
    if apply_requested:
        runtime.handle_pending_apply()

    fragment_store = services.publications
    fragment_state = fragment_store.current()
    workspace_store = InputsWorkspaceStateStore(st_module.session_state)
    identity = region_context.identity
    authoritative_revision = identity.input_revision
    if not (
        identity.matches(
            input_revision=workspace_store.workspace_revision(),
            engineering_hash=workspace_store.authoritative_hash(),
        )
        and workspace_store.authoritative_revision() == authoritative_revision
        and services.engineering_results.source_input_revision()
        == authoritative_revision
    ):
        if design_guide_slot is None:
            design_guide_slot = st_module.empty()
        design_guide_slot.empty()
        with design_guide_slot.container():
            st_module.info("Updating design guidance...")
        return
    # The direct V2-shaped transaction already computed the complete result,
    # including its publication.  Do not immediately invoke the Design Brain
    # service a second time just because the UI publication store has not yet
    # been projected for this render.  The projection below publishes that
    # existing revision-matched result.  The fragment fallback still refreshes
    # here because its calculation and Design Brain stages are intentionally
    # separate.
    current_authoritative_result = services.engineering_results.current()
    result_has_matching_publication = bool(
        current_authoritative_result is not None
        and current_authoritative_result.engineering_hash == identity.engineering_hash
        and services.engineering_results.source_input_revision()
        == authoritative_revision
        and current_authoritative_result.final_publication
    )
    design_brain_refresh_required = bool(
        workspace_store.authoritative_result_present()
        and not result_has_matching_publication
        and (
            fragment_state.status == "empty"
            or (
                fragment_state.status == "refreshing"
                and fragment_state.pending_workspace_revision
                == authoritative_revision
            )
        )
    )
    if design_brain_refresh_required:
        design_brain_refresh = (
            runtime.refresh_design_brain_result
            or runtime.refresh_authoritative_result
        )
        refresh_started_ns = time.perf_counter_ns()
        try:
            design_brain_refresh()
        finally:
            st_module.session_state[
                "_inputs_design_brain_refresh_elapsed_ms"
            ] = round(
                (time.perf_counter_ns() - refresh_started_ns) / 1_000_000,
                3,
            )
        fragment_state = fragment_store.current()
    # A direct V2 refresh can start from an empty publication store on a
    # fresh session. In that case the refresh has no pending marker yet, but
    # the returned result is still the matching authoritative publication.
    # Publish it immediately instead of leaving the card in an eternal
    # "Updating design guidance" state. A refreshing store still requires its
    # explicit pending-revision match.
    publication_refresh_revision_matches = bool(
        fragment_state.status == "empty"
        or (
            fragment_state.status == "refreshing"
            and fragment_state.pending_workspace_revision
            == authoritative_revision
        )
    )
    if publication_refresh_revision_matches:
        if workspace_store.authoritative_result_present():
            authoritative_result = services.engineering_results.current()
            expected_hash = identity.engineering_hash
            if (
                authoritative_result is not None
                and authoritative_result.engineering_hash == expected_hash
                and services.engineering_results.source_input_revision()
                == authoritative_revision
                and bool(authoritative_result.final_publication)
            ):
                fragment_state = fragment_store.publish(
                    authoritative_result,
                    workspace_revision=authoritative_revision,
                )
            elif str(
                st_module.session_state.get(
                    "_inputs_design_brain_job_probe", {}
                ).get("status")
                or ""
            ) == "failed":
                fragment_state = fragment_store.fail_refresh(
                    str(
                        st_module.session_state.get(
                            "_inputs_design_brain_job_probe", {}
                        ).get("error")
                        or "design_brain_worker_failed"
                    )
                )
            else:
                fragment_state = fragment_store.current()
        else:
            fragment_state = fragment_store.clear()
    if design_guide_slot is None:
        design_guide_slot = st_module.empty()
    fragment_payload = fragment_state.to_dict()
    fragment_is_current = fragment_store.is_current(
        workspace_revision=authoritative_revision,
        engineering_hash=identity.engineering_hash,
    )
    fragment_payload["is_current"] = fragment_is_current
    fragment_payload["target_workspace_revision"] = authoritative_revision
    if not fragment_is_current:
        design_guide_slot.empty()
        with design_guide_slot.container():
            st_module.info("Updating design guidance...")
        return
    # At this point the card is revision-current and is about to be rendered.
    # Mark it visible before the widget/diagram region emits its compatibility
    # visibility marker; otherwise that older marker treats every unified
    # workspace render as a pending sibling publication and hides the card.
    st_module.session_state[_DESIGN_BRAIN_VISIBLE_REVISION_KEY] = int(
        authoritative_revision
    )
    # The run_every timer schedules its next tick before this fragment body.
    # Cancel it as soon as a revision-matched publication exists, before the
    # comparatively expensive card rendering below can let that scheduled
    # tick become runnable.  The workspace-level stop remains as a fallback
    # for alternate render paths and terminal failure states.
    stop_design_brain_polling(
        st_module.session_state,
        reason="matching_fragment_ready_before_render",
        revision=authoritative_revision,
    )
    stop_inputs_fragment_polling(
        st_module,
        "design_brain_workspace",
        reason="matching_fragment_ready_before_render",
        revision=authoritative_revision,
    )
    if selected_design_brain_adapter_name() == "v2":
        authoritative_result = services.engineering_results.current()
        if authoritative_result is not None:
            revisioned_apply_payload = ApplyTransactionStore(
                st_module.session_state
            ).attach_revision_expectation(
                dict(authoritative_result.apply_payload or {}),
                input_revision=authoritative_revision,
                publication_revision=int(
                    fragment_state.active_workspace_revision
                    if fragment_state.active_workspace_revision is not None
                    else authoritative_revision
                ),
                engineering_hash=identity.engineering_hash,
                publication_authority_hash=str(
                    authoritative_result.publication_authority_hash or ""
                ),
            )
            render_v2_design_guide_card(
                st_module=st_module,
                design_guide_slot=design_guide_slot,
                result=authoritative_result,
                apply_payload=revisioned_apply_payload,
                apply_handler=runtime.handle_pending_apply,
            )
    else:
        runtime.render_design_guide(
            inputs_detailed_mode=region_context.inputs_detailed_mode,
            sync_callbacks=page_context["sync_callbacks"],
            inputs_render_audit=page_context["inputs_render_audit"],
            fast_focus_section=page_context["fast_focus_section"],
            mark=page_context["mark"],
            design_guide_slot=design_guide_slot,
            fragment_state=fragment_payload,
        )
    if str(os.environ.get("CODEX_BROWSER_TEST_MODE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        publication_projection = _fragment_browser_publication_projection(
            authoritative_result=services.engineering_results.current(),
            fragment_state=fragment_state,
        )
        final_publication = dict(
            publication_projection.get("final_publication") or {}
        )
        projected_publication_hash = (
            final_publication.get("publication_hash")
            or dict(publication_projection.get("final_verifier") or {}).get(
                "final_publication_authority_hash"
            )
            or dict(publication_projection.get("final_verifier") or {}).get(
                "publication_hash"
            )
            or publication_projection.get("publication_authority_hash")
        )
        probe = {
            "probe_source": "design_brain_fragment",
            "fragment_emitted_at_ms": int(time.time() * 1000),
            "workspace_revision": authoritative_revision,
            "authoritative_revision": authoritative_revision,
            "design_brain_job_probe": dict(
                st_module.session_state.get("_inputs_design_brain_job_probe")
                or {}
            ),
            "fragment_polling_state": dict(
                st_module.session_state.get(
                    "_inputs_design_brain_workspace_polling_state"
                )
                or {}
            ),
            "final_publication_hashes": {
                "publication_hash": projected_publication_hash,
                "authority_hash": projected_publication_hash,
            },
        }
        poll_count = int(
            st_module.session_state.get("_inputs_design_brain_probe_poll_count", 0)
            or 0
        ) + 1
        st_module.session_state["_inputs_design_brain_probe_poll_count"] = poll_count
        st_module.text_area(
            "Design Brain fragment state",
            value=json.dumps(probe, sort_keys=True, default=str),
            key=f"_inputs_design_brain_fragment_probe_{poll_count}",
            height=80,
            disabled=True,
            label_visibility="collapsed",
        )


def render_inputs_widget_fragment_section(
    *,
    st_module: Any,
    runtime: EngineeringWorkspaceRuntime,
    page_context: dict[str, Any],
    inputs_detailed_mode: bool,
) -> bool:
    """Render widget inputs and their existing nested diagram positions."""

    render_started_ns = time.perf_counter_ns()
    _render_design_brain_visibility_marker(
        st_module=st_module,
        workspace_revision=InputsWorkspaceStateStore(
            st_module.session_state
        ).workspace_revision(),
    )
    # Carry the already-built context through the widget callback bundle.  The
    # widget renderer is legacy-shaped, but the diagram callbacks can now use
    # the explicit committed snapshot instead of rebuilding it from scattered
    # keys.
    sync_callbacks = dict(page_context["sync_callbacks"])
    sync_callbacks["_workspace_context"] = page_context.get("workspace_context")
    skip_active_beam_record_write = runtime.render_widgets(
        ss=st_module.session_state,
        inputs_detailed_mode=inputs_detailed_mode,
        sync_callbacks=sync_callbacks,
        inputs_render_audit=page_context["inputs_render_audit"],
        fast_focus_section=page_context["fast_focus_section"],
        fast_get_param=page_context["fast_get_param"],
        corrected_invalid_shear_state=page_context[
            "corrected_invalid_shear_state"
        ],
        mark=page_context["mark"],
        sub_mark=page_context["sub_mark"],
    )
    st_module.session_state["_inputs_widget_fragment_timings_ms"] = {
        "revision": int(
            InputsWorkspaceStateStore(st_module.session_state).workspace_revision()
        ),
        "total": round(
            (time.perf_counter_ns() - render_started_ns) / 1_000_000,
            3,
        ),
    }
    return bool(skip_active_beam_record_write)


def render_engineering_workspace(
    *,
    st_module: Any,
    runtime: EngineeringWorkspaceRuntime,
    page_context: dict[str, Any],
    include_design_brain: bool = True,
    include_controls: bool = True,
    include_widgets: bool = True,
) -> dict[str, Any]:
    """Render every consumer that must refresh after an engineering edit."""
    ss = st_module.session_state
    workspace_context = page_context.get("workspace_context")
    services = (
        workspace_context.services
        if workspace_context is not None
        else InputsSessionServices.from_mapping(ss)
    )
    workspace_store = InputsWorkspaceStateStore(ss)
    workspace_store.record_fragment_render()
    section_timings_ms: dict[str, float] = {}
    section_started_ns = time.perf_counter_ns()
    workspace_revision = workspace_store.workspace_revision()
    calculation_state = workspace_store.calculation_status()
    authoritative_result = services.engineering_results.current()
    ready_calculation_is_current = bool(
        calculation_state.get("status") == "ready"
        and int(calculation_state.get("revision", 0) or 0) == workspace_revision
        and workspace_store.authoritative_result_present()
        and authoritative_result is not None
        and services.engineering_results.source_input_revision()
        == workspace_revision
        and workspace_store.authoritative_revision() == workspace_revision
        and workspace_store.authoritative_hash()
        == authoritative_result.engineering_hash
        and not ss.get(
            "_inputs_authoritative_result_snapshot_update_pending"
        )
    )
    awaiting_inputs_is_current = bool(
        calculation_state.get("status") == "awaiting_inputs"
        and int(calculation_state.get("revision", 0) or 0) == workspace_revision
        and workspace_store.authoritative_revision() == workspace_revision
        and not workspace_store.authoritative_result_present()
        and authoritative_result is None
        and not ss.get(
            "_inputs_authoritative_result_snapshot_update_pending"
        )
    )
    calculation_is_current = bool(
        ready_calculation_is_current or awaiting_inputs_is_current
    )
    if calculation_is_current:
        fragment_state = services.publications.current()
        transaction = {
            "reconciled_design_action_keys": [],
            "engineering_hash": workspace_store.authoritative_hash(),
            "design_guide_fragment_status": fragment_state.status,
            "design_guide_publication_authority_hash": (
                fragment_state.active_publication_authority_hash
            ),
        }
    else:
        transaction = prepare_engineering_workspace_transaction(
            st_module=st_module,
            runtime=runtime,
            services=services,
            include_design_brain=include_design_brain,
        )
    section_timings_ms["authoritative_transaction"] = (
        time.perf_counter_ns() - section_started_ns
    ) / 1_000_000
    section_timings_ms["authoritative_transaction_reused"] = float(
        calculation_is_current
    )
    section_started_ns = time.perf_counter_ns()
    summary_region_state = build_inputs_summary_region_state(
        session_state=st_module.session_state,
        services=services,
    )
    summary_region_context: InputsSummaryRegionContext | None = None
    summary_source: InputsSummaryCalculationSource | None = None
    if summary_region_state.status == "awaiting_inputs":
        st_module.info("Enter a design action or load to calculate.")
    elif summary_region_state.status == "failed":
        st_module.error("Calculations could not be updated.")
    elif summary_region_state.status == "updating":
        st_module.info("Updating calculations...")
    else:
        summary_region_context = summary_region_state.context
        if summary_region_context is None:
            raise ValueError("ready Summary state is missing its context")
        summary_source = render_inputs_summary_fragment_section(
            st_module=st_module,
            runtime=runtime,
            page_context=page_context,
            region_context=summary_region_context,
        )
    section_timings_ms["summary"] = (
        time.perf_counter_ns() - section_started_ns
    ) / 1_000_000
    section_started_ns = time.perf_counter_ns()
    if summary_region_context is not None and summary_source is not None:
        calculation_region_context = build_inputs_calculation_region_context(
            summary_region_context=summary_region_context,
            summary_source=summary_source,
        )
        render_inputs_calculation_fragment_section(
            runtime=runtime,
            page_context=page_context,
            region_context=calculation_region_context,
        )
    section_timings_ms["calculation"] = (
        time.perf_counter_ns() - section_started_ns
    ) / 1_000_000
    section_started_ns = time.perf_counter_ns()
    inputs_detailed_mode = bool(
        st_module.session_state.get("_inputs_detailed_mode", False)
    )
    if include_controls:
        controls_region_context = build_inputs_controls_region_context(
            page_context=page_context,
        )
        inputs_detailed_mode = render_inputs_controls_fragment_section(
            st_module=st_module,
            runtime=runtime,
            region_context=controls_region_context,
        )
    section_timings_ms["controls_and_batch"] = (
        time.perf_counter_ns() - section_started_ns
    ) / 1_000_000
    section_started_ns = time.perf_counter_ns()
    if include_design_brain:
        design_guide_slot = st_module.empty()
        region_context = build_inputs_design_brain_region_context(
            session_state=st_module.session_state,
            services=services,
            inputs_detailed_mode=inputs_detailed_mode,
        )
        if region_context is None:
            with design_guide_slot.container():
                st_module.info("Updating design guidance...")
        else:
            render_inputs_design_guide_fragment_section(
                st_module=st_module,
                runtime=runtime,
                page_context=page_context,
                services=services,
                region_context=region_context,
                design_guide_slot=design_guide_slot,
            )
        # The widget/diagram renderer still emits the shared visibility marker
        # below. In the unified workspace the Design Brain is rendered in this
        # same fragment, so publish its ready revision before that marker is
        # emitted; otherwise the marker's legacy pending CSS hides the fresh
        # V2 card even though the publication is already current.
        current_publication = services.publications.current()
        if (
            current_publication.status == "ready"
            and current_publication.active_workspace_revision
            == int(workspace_revision)
        ):
            ss[_DESIGN_BRAIN_VISIBLE_REVISION_KEY] = int(workspace_revision)
    st_module.session_state["_inputs_detailed_mode"] = bool(inputs_detailed_mode)
    if include_widgets:
        inputs_detailed_mode = runtime.render_mode_selector(
            sync_callbacks=page_context["sync_callbacks"],
        )
    section_timings_ms["design_guide"] = (
        time.perf_counter_ns() - section_started_ns
    ) / 1_000_000
    section_started_ns = time.perf_counter_ns()
    skip_active_beam_record_write = False
    if include_widgets:
        skip_active_beam_record_write = render_inputs_widget_fragment_section(
            st_module=st_module,
            runtime=runtime,
            page_context=page_context,
            inputs_detailed_mode=inputs_detailed_mode,
        )
    section_timings_ms["widgets_and_nested_diagrams"] = (
        time.perf_counter_ns() - section_started_ns
    ) / 1_000_000
    workspace_store.record_render_completion(
        revision=workspace_store.workspace_revision(),
        section_timings_ms={
            key: round(value, 3) for key, value in section_timings_ms.items()
        },
    )
    if str(os.environ.get("CODEX_BROWSER_TEST_MODE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        authoritative_result = services.engineering_results.current()
        fragment_state = services.publications.current()
        publication_projection = _fragment_browser_publication_projection(
            authoritative_result=authoritative_result,
            fragment_state=fragment_state,
        )
        authoritative_payload = dict(
            publication_projection["authoritative_payload"]
        )
        current_calculations = (
            dict(authoritative_result.current_calculations or {})
            if authoritative_result is not None
            else {}
        )
        resolved_inputs = dict(current_calculations.get("resolved_inputs") or {})
        overview = {
            key: value
            for key, value in current_calculations.items()
            if key != "resolved_inputs"
        }
        guidance_items = list(authoritative_payload.get("guidance_items") or [])
        guidance_debug = dict(authoritative_payload.get("guidance_debug") or {})
        primary_item = (
            dict(guidance_items[0])
            if guidance_items and isinstance(guidance_items[0], dict)
            else {}
        )
        final_publication = dict(
            publication_projection["final_publication"]
        )
        final_verifier = dict(publication_projection["final_verifier"])
        cta_model = dict(publication_projection["cta_model"])
        selected_family_id = publication_projection["selected_family_id"]
        apply_projection = _authoritative_apply_browser_projection(
            authoritative_result
        )
        browser_state_overlay = {
            "fragment_fresh": True,
            "summary_state_probe": dict(resolved_inputs),
            "browser_shared_probe": {
                **dict(resolved_inputs),
                "active_beam_id": ss.get("active_beam_id"),
                "beam_last_hydrated_id": ss.get("beam_last_hydrated_id"),
                # The outer Browser-state probe normally exposes these
                # compatibility aliases.  Mirror them in the verifier-only
                # fragment overlay so freshness checks compare the same
                # contract while the outer app render is intentionally stale.
                "inputs_load_Mstar_pos_proxy": resolved_inputs.get(
                    "load_Mstar_pos_proxy",
                    ss.get("inputs_load_Mstar_pos_proxy"),
                ),
                "inputs_load_Mstar_neg_proxy": resolved_inputs.get(
                    "load_Mstar_neg_proxy",
                    ss.get("inputs_load_Mstar_neg_proxy"),
                ),
                "inputs_load_Vstar_proxy": resolved_inputs.get(
                    "load_Vstar_proxy",
                    ss.get("inputs_load_Vstar_proxy"),
                ),
            },
            "summary_overview_probe": dict(overview),
            "selected_family_id": selected_family_id,
            "design_brain_job_probe": dict(
                ss.get("_inputs_design_brain_job_probe") or {}
            ),
            "design_brain_entered_probe": dict(
                ss.get("_inputs_design_brain_entered_probe") or {}
            ),
            "design_brain_boundary_probe": dict(
                ss.get("_inputs_design_brain_boundary_probe") or {}
            ),
            "primary_button_contract": dict(cta_model),
            "button_contract": dict(cta_model),
            "design_guide_primary_button_contract": dict(cta_model),
            "design_guide_primary_button_contract_enabled": bool(
                cta_model.get("enabled") or cta_model.get("actionable")
            ),
            "design_guide_primary_apply_payload": dict(
                apply_projection.get("design_guide_primary_apply_payload")
                or {}
            ),
            "design_guide_primary_payload_binding_audit": dict(
                apply_projection.get(
                    "design_guide_primary_payload_binding_audit"
                )
                or {}
            ),
            "final_design_guide_publication": dict(final_publication),
            "final_publication_verifier_payload": dict(final_verifier),
            "final_publication_hashes": {
                "publication_hash": (
                    final_publication.get("publication_hash")
                    or final_verifier.get("publication_hash")
                    or final_verifier.get("final_publication_authority_hash")
                ),
                "authority_hash": (
                    final_publication.get("publication_hash")
                    or final_verifier.get("final_publication_authority_hash")
                    or final_verifier.get("publication_hash")
                ),
                "cta_hash": final_verifier.get("final_publication_cta_hash"),
                "display_hash": final_verifier.get(
                    "final_publication_display_hash"
                ),
            },
            "guidance_compute_probe": {
                "item_count": len(guidance_items),
                "primary_title": primary_item.get("title_main")
                or primary_item.get("title"),
                "primary_action_type": primary_item.get("action_type"),
                "primary_status": primary_item.get("status"),
                "primary_updates": dict(
                    apply_projection.get("selected_action_updates") or {}
                ),
                "selected_action_updates": dict(
                    apply_projection.get("selected_action_updates") or {}
                ),
                "selected_action_type": apply_projection.get(
                    "selected_action_type"
                ),
                "selected_action_family": apply_projection.get(
                    "selected_action_family"
                ),
                "design_guide_primary_payload_binding_audit": dict(
                    apply_projection.get(
                        "design_guide_primary_payload_binding_audit"
                    )
                    or {}
                ),
                "overview": dict(guidance_debug.get("overview") or overview),
                "candidate_search_evidence": dict(
                    guidance_debug.get("candidate_search_evidence") or {}
                ),
                "exact_blockers_by_family": dict(
                    guidance_debug.get("exact_blockers_by_family") or {}
                ),
                "post_click_exact_blockers_by_family": dict(
                    guidance_debug.get(
                        "post_click_exact_blockers_by_family"
                    )
                    or {}
                ),
                "family_exact_stop_acceptance_probe": dict(
                    guidance_debug.get(
                        "family_exact_stop_acceptance_probe"
                    )
                    or {}
                ),
                "family_ladder_runtime_result": dict(
                    guidance_debug.get("family_ladder_runtime_result")
                    or {}
                ),
            },
            "design_guide_probe": {
                "final_design_guide_publication": dict(final_publication),
                "final_publication_verifier_payload": dict(final_verifier),
                "selected_family_id": (
                    selected_family_id
                ),
                "exact_blockers_by_family": dict(
                    guidance_debug.get("exact_blockers_by_family") or {}
                ),
                "post_click_exact_blockers_by_family": dict(
                    guidance_debug.get(
                        "post_click_exact_blockers_by_family"
                    )
                    or {}
                ),
                "design_guide_render_eligibility_trace": dict(
                    ss.get("_design_guide_render_eligibility_trace_last") or {}
                ),
            },
            "authoritative_result_probe": {
                "governing_family": (
                    selected_family_id
                ),
                "stored_engineering_hash": (
                    publication_projection["engineering_hash"]
                ),
                "publication_selected_family_id": final_publication.get(
                    "selected_family"
                ),
                "publication_verifier_selected_family_id": final_verifier.get(
                    "selected_family_id"
                ),
                "cta_family_id": cta_model.get("family"),
                "reuse_decision": dict(
                    ss.get("_authoritative_design_result_last_decision") or {}
                ),
            },
            "inputs_route_return_debug": dict(
                ss.get("_inputs_route_return_debug") or {}
            ),
            "solver_result": ss.get("_solver_result"),
            "one_click_feedback": ss.get("_one_click_run_feedback"),
        }
        if authoritative_result is None:
            # The fragment publication remains authoritative, but this render
            # does not own a fresh calculation projection. Do not erase the
            # populated outer Browser-state calculation probes with empties.
            for unavailable_key in (
                "summary_state_probe",
                "browser_shared_probe",
                "summary_overview_probe",
            ):
                browser_state_overlay.pop(unavailable_key, None)
        probe = {
            "probe_source": "design_brain_workspace",
            # Verifier-only wall-clock freshness marker.  Streamlit can retain
            # the prior fragment textarea for a short window while the outer
            # post-render probe has already advanced.
            "fragment_emitted_at_ms": int(time.time() * 1000),
            "workspace_revision": workspace_store.workspace_revision(),
            "authoritative_revision": workspace_store.authoritative_revision(),
            "calculation_status": workspace_store.calculation_status(),
            "result_source_input_revision": services.engineering_results.source_input_revision(),
            "snapshot_update_pending": bool(
                ss.get("_inputs_authoritative_result_snapshot_update_pending")
            ),
            "last_rendered_revision": ss.get(
                "_inputs_workspace_last_rendered_revision",
                0,
            ),
            "engineering_input_transaction": dict(
                ss.get("_inputs_engineering_input_transaction_probe") or {}
            ),
            "engineering_input_transaction_trace": list(
                ss.get("_inputs_engineering_input_transaction_trace_v1") or []
            ),
            "input_commit_timings_ms": dict(
                ss.get("_inputs_last_commit_timings_ms") or {}
            ),
          "widget_fragment_timings_ms": dict(
              ss.get("_inputs_widget_fragment_timings_ms") or {}
          ),
          "widget_section_timings_ms": dict(
              ss.get("_inputs_widget_section_timings_ms") or {}
          ),
          "geometry_section_stage_timings_ms": dict(
              ss.get("_inputs_geometry_section_stage_timings_ms") or {}
          ),
          "diagram_2d_timings_ms": dict(
              ss.get("_inputs_last_2d_diagram_timings_ms") or {}
          ),
          "diagram_2d_source_identity": dict(
              ss.get("_inputs_model_2d_source_identity") or {}
          ),
          "diagram_2d_view_model_trace": dict(
              ss.get("_inputs_diagram_view_model_trace") or {}
          ),
          "diagram_3d_timings_ms": dict(
              ss.get("_inputs_last_3d_diagram_timings_ms") or {}
          ),
          "diagram_3d_source_identity": dict(
              ss.get("_inputs_model_3d_source_identity") or {}
          ),
          "engineering_compute_count_by_revision": dict(
              ss.get("_inputs_engineering_compute_count_by_revision") or {}
          ),
            "committed_engineering_input_baseline": dict(
                ss.get(
                    "_inputs_committed_engineering_baseline_probe"
                )
                or {}
            ),
            "authoritative_apply_command_probe": dict(
                ss.get("_authoritative_apply_command_probe") or {}
            ),
            "typed_inputs_apply_probe": dict(
                ss.get("_typed_inputs_apply_probe") or {}
            ),
            "last_apply_route": dict(
                ss.get("_design_guide_last_apply_route") or {}
            ),
            "workspace_fragment_render_count": workspace_store.fragment_render_count(),
            "page_shell_render_count": ss.get(
                "_inputs_page_shell_render_count",
                0,
            ),
            "fragment_mode": ss.get(
                "_inputs_engineering_workspace_fragment_mode"
            ),
            "fragment_modes": {
                name: ss.get(f"_inputs_{name}_fragment_mode")
                for name in (
                    "engineering_workspace",
                    "engineering_calculation_workspace",
                    "engineering_controls_workspace",
                    "design_brain_workspace",
                    "engineering_input_workspace",
                    "diagram_2d",
                    "diagram_3d",
                )
            },
            "fragment_ids": dict(
                ss.get("_inputs_fragment_ids_v1") or {}
            ),
            "latest_refresh": ss.get("_inputs_workspace_refresh"),
            "event_count": len(
                ss.get("_inputs_workspace_rerun_events") or []
            ),
            "section_timings_ms": workspace_store.section_timings(),
            "authoritative_result_reuse": ss.get(
                "_authoritative_design_result_last_decision"
            ),
            "authoritative_result_lru_size": len(
                ss.get("_authoritative_design_result_lru_v1") or {}
            ),
            "design_guide_stage_timings_ms": ss.get(
                "_inputs_design_guide_stage_timings_ms"
            ),
            "design_brain_refresh_elapsed_ms": ss.get(
                "_inputs_design_brain_refresh_elapsed_ms"
            ),
            "design_guide_active_stage_timings_ms": ss.get(
                "_inputs_design_guide_active_stage_timings_ms"
            ),
            "design_guide_local_cleanup_stage_timings_ms": ss.get(
                "_inputs_design_guide_local_cleanup_stage_timings_ms"
            ),
            "design_guide_direct_target_cache": ss.get(
                "_inputs_design_guide_direct_target_cache"
            ),
            "app_scope_rerun_requested": False,
            "browser_state_overlay": browser_state_overlay,
        }
        probe_json = json.dumps(probe, sort_keys=True, default=str)
        ss["_inputs_workspace_state_probe"] = probe_json
        probe_widget_key = (
            "_inputs_workspace_state_probe_widget_"
            f"{workspace_store.workspace_revision()}_"
            f"{workspace_store.fragment_render_count()}"
        )
        previous_probe_widget_key = ss.get(
            "_inputs_workspace_state_probe_widget_key"
        )
        if (
            previous_probe_widget_key
            and previous_probe_widget_key != probe_widget_key
        ):
            ss.pop(str(previous_probe_widget_key), None)
        ss["_inputs_workspace_state_probe_widget_key"] = probe_widget_key
        st_module.text_area(
            "Inputs workspace state",
            value=probe_json,
            key=probe_widget_key,
            height=80,
            disabled=True,
            label_visibility="collapsed",
        )
    return {
        "inputs_detailed_mode": inputs_detailed_mode,
        "skip_active_beam_record_write": skip_active_beam_record_write,
        "engineering_hash": transaction.get("engineering_hash"),
        "workspace_revision": workspace_store.last_rendered_revision(),
    }


__all__ = [
    "EngineeringWorkspaceRuntime",
    "InputsCalculationRegionContext",
    "InputsControlsRegionContext",
    "InputsDesignBrainRegionContext",
    "InputsSummaryRegionContext",
    "InputsSummaryRegionState",
    "build_inputs_summary_region_state",
    "build_inputs_controls_region_context",
    "RevisionIdentity",
    "build_inputs_calculation_region_context",
    "build_inputs_design_brain_region_context",
    "build_engineering_workspace_runtime",
    "prepare_engineering_workspace_transaction",
    "render_engineering_workspace",
    "render_inputs_calculation_fragment_section",
    "render_inputs_controls_fragment_section",
    "render_inputs_design_guide_fragment_section",
    "render_inputs_summary_fragment_section",
    "render_inputs_widget_fragment_section",
]
