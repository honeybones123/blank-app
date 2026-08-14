from __future__ import annotations

from types import SimpleNamespace

from inputs_application.design_guide_fragment_store import PublicationStore
from inputs_application.engineering_input_store import TRANSACTION_META_KEY
from inputs_application.engineering_workspace import (
    prepare_engineering_workspace_transaction,
)
from inputs_application.session_services import InputsSessionServices


class _RuntimeThatMustNotRefresh:
    def reconcile_design_actions(self):
        return []

    def refresh_authoritative_result(self):  # pragma: no cover - failure guard
        raise AssertionError("a superseded fragment must not calculate")

    refresh_engineering_result = refresh_authoritative_result


def test_older_fragment_does_not_replace_a_newer_pending_revision() -> None:
    state = {
        TRANSACTION_META_KEY: {"revision": 1},
        "active_beam_id": "beam-1",
    }
    services = InputsSessionServices.from_mapping(state)
    services.publications.begin_refresh(workspace_revision=2)
    pending_before = services.publications.current()

    transaction = prepare_engineering_workspace_transaction(
        st_module=SimpleNamespace(session_state=state),
        runtime=_RuntimeThatMustNotRefresh(),
        services=services,
        include_design_brain=True,
    )

    assert transaction["calculation_status"] == "superseded"
    assert services.publications.current() == pending_before
    assert services.publications.current().pending_workspace_revision == 2


def test_store_still_rejects_direct_superseded_refreshes() -> None:
    state = {}
    store = PublicationStore(state)
    store.begin_refresh(workspace_revision=2)

    try:
        store.begin_refresh(workspace_revision=1)
    except ValueError as exc:
        assert str(exc) == "cannot refresh a superseded Design Guide revision"
    else:  # pragma: no cover - contract guard
        raise AssertionError("the store must retain its fail-closed boundary")


def test_in_flight_refresh_can_retarget_to_its_committed_revision() -> None:
    state = {}
    store = PublicationStore(state)
    store.begin_refresh(workspace_revision=4)

    retargeted = store.retarget_refresh(
        expected_workspace_revision=4,
        committed_workspace_revision=5,
    )

    assert retargeted.status == "refreshing"
    assert retargeted.pending_workspace_revision == 5


def test_stale_refresh_cannot_retarget_a_newer_pending_revision() -> None:
    state = {}
    store = PublicationStore(state)
    store.begin_refresh(workspace_revision=5)

    try:
        store.retarget_refresh(
            expected_workspace_revision=4,
            committed_workspace_revision=6,
        )
    except ValueError as exc:
        assert str(exc) == "cannot retarget a superseded Design Guide refresh"
    else:  # pragma: no cover - contract guard
        raise AssertionError("a stale transaction must not retarget publication")
