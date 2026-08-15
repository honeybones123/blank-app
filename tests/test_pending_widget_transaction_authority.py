from inputs_application.page_runtime.setup import (
    _pending_revision_matches_committed_snapshot,
)


def test_matching_widget_revision_is_already_authoritative() -> None:
    assert _pending_revision_matches_committed_snapshot(
        pending_revision=7,
        committed_revision=7,
    )


def test_missing_or_stale_pending_revision_requires_normal_reconciliation() -> None:
    assert not _pending_revision_matches_committed_snapshot(
        pending_revision=0,
        committed_revision=7,
    )
    assert not _pending_revision_matches_committed_snapshot(
        pending_revision=6,
        committed_revision=7,
    )
