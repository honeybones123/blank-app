from __future__ import annotations

from inputs_application.design_guide_fragment_store import PublicationStore


def test_design_brain_publication_is_bound_to_pending_revision() -> None:
    state: dict[str, object] = {}
    store = PublicationStore(state)
    store.begin_refresh(workspace_revision=42)

    from application.contracts.design_brain import AuthoritativeDesignResult

    typed = AuthoritativeDesignResult(
        engineering_hash="engineering-42",
        publication_authority_hash="publication-42",
        final_publication={"revision": 42},
    )
    ready = store.publish(typed, workspace_revision=42)
    assert ready.active_workspace_revision == 42
    assert store.is_current(
        workspace_revision=42,
        engineering_hash="engineering-42",
    )
    assert not store.is_current(
        workspace_revision=43,
        engineering_hash="engineering-42",
    )


def test_new_revision_keeps_old_publication_hidden_while_refreshing() -> None:
    state: dict[str, object] = {}
    store = PublicationStore(state)
    from application.contracts.design_brain import AuthoritativeDesignResult

    first = AuthoritativeDesignResult(
        engineering_hash="engineering-41",
        publication_authority_hash="publication-41",
        final_publication={"revision": 41},
    )
    store.begin_refresh(workspace_revision=41)
    store.publish(first, workspace_revision=41)

    pending = store.begin_refresh(workspace_revision=42)
    assert pending.status == "refreshing"
    assert pending.pending_workspace_revision == 42
    assert pending.active_workspace_revision == 41
    assert not store.is_current(
        workspace_revision=42,
        engineering_hash="engineering-42",
    )
