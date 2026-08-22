from __future__ import annotations

import inspect
from types import SimpleNamespace

from inputs_application.page_runtime import batch as batch_runtime
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
    source = inspect.getsource(batch_runtime.render_inputs_batch_design_manager_coordinator)

    assert "add_beam=add_batch_project_beam" in source
    assert "duplicate_beam=duplicate_batch_project_beam" in source
    assert "delete_beam=delete_batch_project_beam" in source


def test_batch_context_reads_live_project_identity_after_local_rerun(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(
        batch_runtime,
        "render_batch_design_page",
        lambda context: captured.append(context),
    )
    state = {
        "active_beam_id": "beam_2",
        "beam_order": ["beam_1", "beam_2"],
        "beam_records": {
            "beam_1": {"beam_label": "Beam 1"},
            "beam_2": {"beam_label": "Beam 2"},
        },
    }

    batch_runtime.render_inputs_batch_design_manager_coordinator(
        ss=state,
        beam_labels={"beam_1": "Beam 1"},
        beam_order=["beam_1"],
        active_beam_id="beam_1",
    )

    assert len(captured) == 1
    context = captured[0]
    assert context.beam_order == ["beam_1", "beam_2"]
    assert context.active_beam_id == "beam_2"
    assert context.beam_labels["beam_2"] == "Beam 2"


def test_beam_selector_arms_atomic_gate_before_inputs_refresh(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    state: dict[str, object] = {
        batch_page.ACTIVE_BEAM_SELECTOR_KEY: "beam_2",
        "active_beam_id": "beam_1",
    }
    monkeypatch.setattr(batch_page, "st", SimpleNamespace(session_state=state))
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
