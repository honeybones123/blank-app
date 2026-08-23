from __future__ import annotations

import inspect
from types import SimpleNamespace

import pandas as pd

from inputs_application.page_runtime import batch as batch_runtime
from batch_design.models import BatchDesignResult
from batch_design.store import BatchDesignWorkflowState
from batch_design.ui import page as batch_page


def _record_commit_boundary(monkeypatch, events: list[tuple[str, str]]) -> None:
    class _Results:
        def clear_current(self) -> None:
            events.append(("clear", "result"))

    class _Publications:
        def clear(self) -> None:
            events.append(("clear", "publication"))

    class _Services:
        engineering_results = _Results()
        publications = _Publications()

    monkeypatch.setattr(
        "inputs_application.session_services.InputsSessionServices.from_mapping",
        lambda state: _Services(),
    )
    monkeypatch.setattr(
        batch_runtime,
        "_apply_canonical_convenience_resync",
        lambda *, source: events.append(("resync", source)),
    )
    monkeypatch.setattr(
        batch_runtime,
        "_request_inputs_engineering_commit",
        lambda source: events.append(("commit", source)),
    )


def test_add_project_beam_publishes_initial_authoritative_revision(monkeypatch) -> None:
    events: list[tuple[str, str]] = []
    monkeypatch.setattr(batch_runtime, "add_new_beam_record", lambda: "beam_2")
    _record_commit_boundary(monkeypatch, events)

    assert batch_runtime.add_batch_project_beam() == "beam_2"
    assert events == [
        ("clear", "result"),
        ("clear", "publication"),
        ("resync", "inputs_batch_design_add_beam"),
        ("commit", "inputs_batch_design_add_beam"),
    ]


def test_duplicate_project_beam_publishes_duplicated_revision(monkeypatch) -> None:
    events: list[tuple[str, str]] = []
    monkeypatch.setattr(
        batch_runtime,
        "duplicate_active_beam_record",
        lambda: "beam_2",
    )
    _record_commit_boundary(monkeypatch, events)

    assert batch_runtime.duplicate_batch_project_beam() == "beam_2"
    assert events == [
        ("clear", "result"),
        ("clear", "publication"),
        ("resync", "inputs_batch_design_duplicate_beam"),
        ("commit", "inputs_batch_design_duplicate_beam"),
    ]


def test_delete_project_beam_only_publishes_when_active_beam_changes(monkeypatch) -> None:
    events: list[tuple[str, str]] = []
    _record_commit_boundary(monkeypatch, events)
    monkeypatch.setattr(batch_runtime, "delete_beam_record", lambda beam_id: False)

    assert batch_runtime.delete_batch_project_beam("beam_2") is False
    assert events == []

    monkeypatch.setattr(batch_runtime, "delete_beam_record", lambda beam_id: True)
    assert batch_runtime.delete_batch_project_beam("beam_2") is True
    assert events == [
        ("clear", "result"),
        ("clear", "publication"),
        ("resync", "inputs_batch_design_delete_beam"),
        ("commit", "inputs_batch_design_delete_beam"),
    ]


def test_batch_page_wires_identity_mutations_to_revisioned_coordinators() -> None:
    source = inspect.getsource(
        batch_runtime._build_inputs_batch_design_page_context
    )

    assert "add_beam=add_batch_project_beam" in source
    assert "duplicate_beam=duplicate_batch_project_beam" in source
    assert "delete_beam=delete_batch_project_beam" in source


def test_batch_context_reads_live_project_identity_after_local_rerun(monkeypatch) -> None:
    state = {
        "active_beam_id": "beam_2",
        "beam_order": ["beam_1", "beam_2"],
        "beam_records": {
            "beam_1": {"beam_label": "Beam 1"},
            "beam_2": {"beam_label": "Beam 2"},
        },
    }

    context = batch_runtime._build_inputs_batch_design_page_context(
        ss=state,
        beam_labels={"beam_1": "Beam 1"},
        beam_order=["beam_1"],
        active_beam_id="beam_1",
    )

    assert context.beam_order == ["beam_1", "beam_2"]
    assert context.active_beam_id == "beam_2"
    assert context.beam_labels["beam_2"] == "Beam 2"


def test_beam_selector_arms_atomic_gate_before_inputs_refresh(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    state: dict[str, object] = {
        batch_page.ACTIVE_BEAM_SELECTOR_KEY: "beam_2",
        "active_beam_id": "beam_1",
    }
    monkeypatch.setattr(
        batch_page,
        "st",
        SimpleNamespace(
            session_state=state,
        ),
    )
    context = SimpleNamespace(
        set_active_beam=lambda beam_id: events.append(("set", beam_id)) or True,
        force_refresh=lambda reason: events.append(
            ("refresh_guard", state.get("_inputs_atomic_revision_guard_pending"))
        ),
        log_rerun=lambda reason: events.append(("log", reason)),
    )

    batch_page._activate_selected_project_beam(context)

    assert events == [
        ("set", "beam_2"),
        ("refresh_guard", True),
        ("log", "beam_selector_change"),
    ]


def test_batch_page_uses_one_fragment_owner(monkeypatch) -> None:
    captured = {}

    def fake_run_inputs_fragment(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(batch_runtime, "run_inputs_fragment", fake_run_inputs_fragment)

    ctx = SimpleNamespace()
    batch_runtime._render_inputs_batch_design_page_coordinator(ctx)

    assert captured["fragment_name"] == "batch_design_shell"
    assert captured["render_fn"] is batch_runtime._render_inputs_batch_design_page_fragment
    assert captured["kwargs"] == {"ctx": ctx}
    assert captured["force_fragment"] is True


def test_batch_manager_puts_shell_controls_and_workspace_in_one_fragment(
    monkeypatch,
) -> None:
    captured = []
    context = SimpleNamespace()
    monkeypatch.setattr(
        batch_runtime,
        "_build_inputs_batch_design_page_context",
        lambda **kwargs: context,
    )
    monkeypatch.setattr(
        batch_runtime,
        "_render_inputs_batch_design_page_coordinator",
        lambda ctx: captured.append(ctx),
    )

    batch_runtime.render_inputs_batch_design_manager_coordinator(
        ss={},
        beam_labels={},
        beam_order=[],
        active_beam_id="",
    )

    assert captured == [context]


def test_batch_identity_command_is_consumed_once_before_render(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    state = {
        batch_page.PROJECT_BEAM_IDENTITY_REQUEST_KEY: "duplicate",
        "active_beam_id": "beam_1",
        "beam_order": ["beam_1"],
        "beam_records": {"beam_1": {"beam_label": "Beam 1"}},
    }
    monkeypatch.setattr(
        batch_page,
        "st",
        SimpleNamespace(session_state=state),
    )
    monkeypatch.setattr(
        batch_page,
        "_rerun_inputs_page",
        lambda: events.append(("rerun", "app")),
    )
    context = SimpleNamespace(
        session_state=state,
        beam_order=["beam_1"],
        active_beam_id="beam_1",
        beam_labels={"beam_1": "Beam 1"},
        add_beam=lambda: events.append(("add", None)),
        duplicate_beam=lambda: events.append(("duplicate", None)),
        delete_beam=lambda beam_id: events.append(("delete", beam_id)),
        reset_workspace=lambda: events.append(("reset", None)),
        apply_resync=lambda **kwargs: events.append(("resync", kwargs)),
        force_refresh=lambda reason: events.append(("refresh", reason)),
        log_rerun=lambda reason: events.append(("log", reason)),
    )

    batch_page._consume_project_beam_identity_request(context)
    batch_page._consume_project_beam_identity_request(context)

    assert events == [
        ("duplicate", None),
        ("refresh", "duplicate_beam"),
        ("log", "duplicate_beam"),
        ("rerun", "app"),
    ]
    assert state[batch_page.WORKSPACE_OPEN_KEY] is True
    assert state["_batch_design_project_beam_editor_epoch"] == 1


def test_batch_fragment_uses_live_identity_after_a_beam_mutation() -> None:
    state = {
        "active_beam_id": "beam_2",
        "beam_order": ["beam_1", "beam_2"],
        "beam_records": {
            "beam_1": {"beam_label": "Beam 1"},
            "beam_2": {"beam_label": "Beam 2"},
        },
    }
    stale_context = SimpleNamespace(
        session_state=state,
        beam_order=["beam_1"],
        active_beam_id="beam_1",
        beam_labels={"beam_1": "Beam 1"},
    )

    order, active, labels = batch_page._live_project_beam_identity(stale_context)

    assert order == ["beam_1", "beam_2"]
    assert active == "beam_2"
    assert labels["beam_2"] == "Beam 2"


def test_auto_assign_command_uses_durable_one_shot_request(monkeypatch) -> None:
    events: list[str] = []

    class _Column:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    class _FakeStreamlit:
        def __init__(self) -> None:
            self.session_state = {}
            self.auto_click_available = True

        def columns(self, *args, **kwargs):
            return [_Column(), _Column()]

        def button(self, label, **kwargs):
            if (
                label == batch_page.WORKFLOW_MODE_AUTO_ASSIGN
                and self.auto_click_available
            ):
                self.auto_click_available = False
                kwargs["on_click"]()
            return False

    fake_st = _FakeStreamlit()
    monkeypatch.setattr(batch_page, "st", fake_st)
    monkeypatch.setattr(
        batch_page,
        "_run_auto_assign_now",
        lambda workflow, ctx: events.append("auto_assign"),
    )

    batch_page._render_workflow_mode_selector(SimpleNamespace(), SimpleNamespace())
    batch_page._render_workflow_mode_selector(SimpleNamespace(), SimpleNamespace())

    assert events == ["auto_assign"]
    assert fake_st.session_state[batch_page.WORKFLOW_MODE_KEY] == (
        batch_page.WORKFLOW_MODE_AUTO_ASSIGN
    )
    assert batch_page.AUTO_ASSIGN_REQUEST_KEY not in fake_st.session_state


def test_auto_assign_uses_three_selected_sources_for_twelve_targets(monkeypatch) -> None:
    rows = []
    beam_records = {}
    for index in range(1, 16):
        beam_id = f"beam_{index}"
        rows.append(
            {
                "beam_id": beam_id,
                "beam_label": f"Beam {index}",
                "use_for_auto_design": index <= 3,
                "sec_shape": "RECT",
                "b": 250.0,
                "D": 300.0,
                "L": 6000.0,
                "mz_star": 100.0 + index,
            }
        )
        beam_records[beam_id] = {
            "beam_label": f"Beam {index}",
            "params": {"source_rank": index},
        }
    schedule = pd.DataFrame(rows)
    state = {
        batch_page.PROJECT_BEAM_TABLE_FRAME_KEY: schedule,
        "beam_records": beam_records,
    }
    calls: list[tuple[str, int]] = []
    published: list[BatchDesignResult] = []
    reruns: list[str] = []

    class _Adapter:
        def run_case(
            self,
            case,
            *,
            assumptions,
            base_state,
            request_kind,
        ):
            source_rank = int(base_state["source_rank"])
            calls.append((str(case.member_id), source_rank))
            utilisation = {1: 0.55, 2: 0.82, 3: 0.95}[source_rank]
            return BatchDesignResult(
                member_id=str(case.member_id),
                input_case=case,
                passed=True,
                selected_section="250 x 300 RECT",
                utilisation=utilisation,
            )

    fake_st = SimpleNamespace(
        session_state=state,
        warning=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(batch_page, "st", fake_st)
    monkeypatch.setattr(
        batch_page,
        "_rerun_inputs_page",
        lambda: reruns.append("app"),
    )
    workflow = BatchDesignWorkflowState()
    context = SimpleNamespace(
        build_schedule_editor_df=lambda: schedule,
        design_brain_adapter=_Adapter(),
        publish_batch_design_results=(
            lambda results: published.extend(results)
            or {str(result.member_id) for result in results}
        ),
    )

    batch_page._run_auto_assign_now(workflow, context)

    assert len(calls) == 36
    assert len(published) == 12
    assert {result.member_id for result in published} == {
        f"beam_{index}" for index in range(4, 16)
    }
    assert all(
        result.raw_result["auto_design_source_beam_id"] == "beam_3"
        for result in published
    )
    assert len(workflow.assignment_results) == 12
    assert all(result.passed for result in workflow.assignment_results)
    assert reruns == ["app"]
