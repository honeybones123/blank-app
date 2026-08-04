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
    register_design_brain_fragment,
    stop_design_brain_polling,
)
from inputs_application.page_runtime import InputsPageRuntime
from inputs_application.region_contexts import (
    InputsDesignBrainRegionContext,
    RevisionIdentity,
)
from inputs_application.summary_calculation_fragment_store import (
    SummaryCalculationFragmentStore,
)
from inputs_application.session_services import InputsSessionServices
from inputs_application.workspace_state_store import InputsWorkspaceStateStore


PageCallable = Callable[..., Any]


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
        "publication_authority_hash": (
            authoritative_result.publication_authority_hash
            if authoritative_result is not None
            else fragment_state.active_publication_authority_hash
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


def prepare_engineering_workspace_transaction(
    *,
    st_module: Any,
    runtime: EngineeringWorkspaceRuntime,
    services: InputsSessionServices,
) -> dict[str, Any]:
    """Commit widget actions and refresh the one authoritative result."""

    workspace_store = InputsWorkspaceStateStore(st_module.session_state)
    reconciled_keys = list(runtime.reconcile_design_actions() or [])
    workspace_store.set_reconciled_keys(reconciled_keys)
    workspace_revision = workspace_store.workspace_revision()
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
            runtime.refresh_engineering_result or runtime.refresh_authoritative_result
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
    }


def render_inputs_summary_fragment_section(
    *,
    st_module: Any,
    runtime: EngineeringWorkspaceRuntime,
    page_context: dict[str, Any],
    services: InputsSessionServices,
) -> Any:
    """Render Summary from the session-owned authoritative transaction."""

    summary_source = runtime.render_summary(
        ss=st_module.session_state,
        sync_callbacks=page_context["sync_callbacks"],
        skip_active_beam_record_write=False,
        mark=page_context["mark"],
        summary_container=st_module.container(),
        render_title=False,
    )
    authoritative_result = services.engineering_results.current()
    SummaryCalculationFragmentStore(st_module.session_state).publish(
        summary_source,
        input_revision=InputsWorkspaceStateStore(
            st_module.session_state
        ).authoritative_revision(),
        engineering_hash=(
            authoritative_result.engineering_hash
            if authoritative_result is not None
            else None
        ),
    )
    return summary_source


def render_inputs_calculation_fragment_section(
    *,
    st_module: Any,
    runtime: EngineeringWorkspaceRuntime,
    page_context: dict[str, Any],
) -> None:
    """Build Calculation state from the session-owned Summary handoff."""

    summary_state = SummaryCalculationFragmentStore(
        st_module.session_state
    ).current()
    if summary_state.source is None:
        return
    current_revision = InputsWorkspaceStateStore(
        st_module.session_state
    ).authoritative_revision()
    if summary_state.input_revision != current_revision:
        return
    runtime.render_calculation(
        summary_source=summary_state.source,
        trace_fn=page_context["pre_widget_trace"],
    )


def render_inputs_controls_fragment_section(
    *,
    st_module: Any,
    runtime: EngineeringWorkspaceRuntime,
    page_context: dict[str, Any],
) -> bool:
    """Render the existing mode and batch controls in their current order."""

    runtime.render_batch(
        ss=st_module.session_state,
        beam_labels=page_context["beam_labels"],
        beam_order=page_context["beam_order"],
        active_beam_id=page_context["active_beam_id"],
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
    design_brain_refresh_required = bool(
        workspace_store.authoritative_result_present()
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
    if (
        fragment_state.status == "refreshing"
        and fragment_state.pending_workspace_revision
        == authoritative_revision
    ):
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
        probe = {
            "fragment_emitted_at_ms": int(time.time() * 1000),
            "workspace_revision": authoritative_revision,
            "authoritative_revision": authoritative_revision,
            "design_brain_job_probe": dict(
                st_module.session_state.get("_inputs_design_brain_job_probe")
                or {}
            ),
            "final_publication_hashes": {
                "publication_hash": final_publication.get("publication_hash"),
                "authority_hash": publication_projection.get("authority_hash"),
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
    skip_active_beam_record_write = runtime.render_widgets(
        ss=st_module.session_state,
        inputs_detailed_mode=inputs_detailed_mode,
        sync_callbacks=page_context["sync_callbacks"],
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
    services = InputsSessionServices.from_mapping(ss)
    workspace_store = InputsWorkspaceStateStore(ss)
    workspace_store.record_fragment_render()
    section_timings_ms: dict[str, float] = {}
    section_started_ns = time.perf_counter_ns()
    workspace_revision = workspace_store.workspace_revision()
    calculation_state = workspace_store.calculation_status()
    calculation_is_current = bool(
        calculation_state.get("status") == "ready"
        and int(calculation_state.get("revision", 0) or 0) == workspace_revision
        and workspace_store.authoritative_result_present()
        and not ss.get(
            "_inputs_authoritative_result_snapshot_update_pending"
        )
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
        )
    section_timings_ms["authoritative_transaction"] = (
        time.perf_counter_ns() - section_started_ns
    ) / 1_000_000
    section_timings_ms["authoritative_transaction_reused"] = float(
        calculation_is_current
    )
    section_started_ns = time.perf_counter_ns()
    render_inputs_summary_fragment_section(
        st_module=st_module,
        runtime=runtime,
        page_context=page_context,
        services=services,
    )
    section_timings_ms["summary"] = (
        time.perf_counter_ns() - section_started_ns
    ) / 1_000_000
    section_started_ns = time.perf_counter_ns()
    render_inputs_calculation_fragment_section(
        st_module=st_module,
        runtime=runtime,
        page_context=page_context,
    )
    section_timings_ms["calculation"] = (
        time.perf_counter_ns() - section_started_ns
    ) / 1_000_000
    section_started_ns = time.perf_counter_ns()
    inputs_detailed_mode = bool(
        st_module.session_state.get("_inputs_detailed_mode", False)
    )
    if include_controls:
        inputs_detailed_mode = render_inputs_controls_fragment_section(
            st_module=st_module,
            runtime=runtime,
            page_context=page_context,
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
                "publication_hash": final_publication.get("publication_hash"),
                "authority_hash": final_publication.get("publication_hash"),
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
            # Verifier-only wall-clock freshness marker.  Streamlit can retain
            # the prior fragment textarea for a short window while the outer
            # post-render probe has already advanced.
            "fragment_emitted_at_ms": int(time.time() * 1000),
            "workspace_revision": ss.get("_inputs_workspace_revision", 0),
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
                    "engineering_calculation_workspace",
                    "engineering_controls_workspace",
                    "design_brain_workspace",
                    "engineering_input_workspace",
                    "diagram_2d",
                    "diagram_3d",
                )
            },
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


def render_engineering_workspace_calculation(
    *,
    st_module: Any,
    runtime: EngineeringWorkspaceRuntime,
    page_context: dict[str, Any],
    workspace_slot: Any = None,
) -> dict[str, Any]:
    ss = st_module.session_state
    workspace_store = InputsWorkspaceStateStore(ss)
    input_revision = workspace_store.workspace_revision()
    # A Streamlit fragment clears its previous elements on every poll.  The
    # engineering transaction may be reused, but the cached Summary and
    # Calculation view models must still be redrawn or the region disappears.
    # render_engineering_workspace performs the revision check and skips the
    # engineering calculation when calculation_state is already current.

    def _render() -> dict[str, Any]:
        return render_engineering_workspace(
            st_module=st_module,
            runtime=runtime,
            page_context=page_context,
            include_design_brain=False,
            include_controls=False,
            include_widgets=False,
        )

    if workspace_slot is None:
        result = _render()
    else:
        workspace_slot.empty()
        with workspace_slot.container():
            result = _render()
    ss["_inputs_calculation_workspace_presented_revision"] = int(
        InputsWorkspaceStateStore(ss).workspace_revision()
    )
    return result


def render_engineering_workspace_controls(
    *,
    st_module: Any,
    runtime: EngineeringWorkspaceRuntime,
    page_context: dict[str, Any],
) -> bool:
    """Render batch and workspace controls without engineering computation."""

    inputs_detailed_mode = render_inputs_controls_fragment_section(
        st_module=st_module,
        runtime=runtime,
        page_context=page_context,
    )
    st_module.session_state["_inputs_detailed_mode"] = bool(inputs_detailed_mode)
    return bool(inputs_detailed_mode)


def render_engineering_workspace_widgets(
    *,
    st_module: Any,
    runtime: EngineeringWorkspaceRuntime,
    page_context: dict[str, Any],
) -> bool:
    """Render mode and engineering widgets in their own stable fragment."""

    inputs_detailed_mode = runtime.render_mode_selector(
        sync_callbacks=page_context["sync_callbacks"],
    )
    st_module.session_state["_inputs_detailed_mode"] = bool(inputs_detailed_mode)
    return render_inputs_widget_fragment_section(
        st_module=st_module,
        runtime=runtime,
        page_context=page_context,
        inputs_detailed_mode=bool(inputs_detailed_mode),
    )


def render_engineering_workspace_design_brain(
    *,
    st_module: Any,
    runtime: EngineeringWorkspaceRuntime,
    page_context: dict[str, Any],
    design_brain_slot: Any = None,
) -> None:
    ss = st_module.session_state
    # The fragment owns its output container.  Passing a shell-owned empty
    # container across this boundary lets sibling fragment reruns erase the
    # Design Guide even though its matching publication is still current.
    if design_brain_slot is None:
        design_brain_slot = st_module.empty()
    workspace_store = InputsWorkspaceStateStore(ss)
    input_revision = workspace_store.workspace_revision()
    register_design_brain_fragment(ss, revision=input_revision)
    services = InputsSessionServices.from_mapping(ss)
    region_context = build_inputs_design_brain_region_context(
        session_state=ss,
        services=services,
        inputs_detailed_mode=bool(
            st_module.session_state.get("_inputs_detailed_mode", False)
        ),
    )
    if region_context is None:
        if (
            workspace_store.authoritative_revision() == input_revision
            and not workspace_store.authoritative_result_present()
        ):
            design_brain_slot.empty()
            stop_design_brain_polling(
                ss,
                reason="no_authoritative_result",
                revision=input_revision,
            )
            return
        if design_brain_slot is not None:
            design_brain_slot.empty()
            with design_brain_slot.container():
                st_module.info("Updating design guidance…")
            ss["_inputs_design_brain_pending_display_revision"] = int(
                input_revision
            )
        return
    publication = services.publications.current()
    # Polling clears this fragment's prior elements.  A ready publication is
    # cheap to reuse, but it must be rendered on every poll to remain visible.
    # The refresh coordinator below is revision-gated and performs no Design
    # Brain work once a matching final publication exists.
    if design_brain_slot is not None:
        design_brain_slot.empty()
    render_inputs_design_guide_fragment_section(
        st_module=st_module,
        runtime=runtime,
        page_context=page_context,
        services=services,
        region_context=region_context,
        design_guide_slot=design_brain_slot,
    )
    publication = services.publications.current()
    if (
        publication.status == "ready"
        and publication.active_workspace_revision == int(input_revision)
    ):
        ss["_inputs_design_brain_presented_revision"] = int(input_revision)
        ss.pop("_inputs_design_brain_pending_display_revision", None)
        stop_design_brain_polling(
            ss,
            reason="matching_publication_ready",
            revision=input_revision,
        )
    elif (
        publication.status in {"failed", "ready_stale"}
        and publication.pending_workspace_revision is None
    ):
        stop_design_brain_polling(
            ss,
            reason=f"publication_{publication.status}",
            revision=input_revision,
        )


__all__ = [
    "EngineeringWorkspaceRuntime",
    "InputsDesignBrainRegionContext",
    "RevisionIdentity",
    "build_inputs_design_brain_region_context",
    "build_engineering_workspace_runtime",
    "prepare_engineering_workspace_transaction",
    "render_engineering_workspace",
    "render_engineering_workspace_calculation",
    "render_engineering_workspace_controls",
    "render_engineering_workspace_design_brain",
    "render_engineering_workspace_widgets",
    "render_inputs_calculation_fragment_section",
    "render_inputs_controls_fragment_section",
    "render_inputs_design_guide_fragment_section",
    "render_inputs_summary_fragment_section",
    "render_inputs_widget_fragment_section",
]
