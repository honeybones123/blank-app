from inputs_v2.application.design_brain_service import DesignBrainService
from inputs_v2.domain.beam_inputs import ActionInputs, BeamInputs


def test_proportion_pipeline_is_bounded_and_preserves_source_identity() -> None:
    current = BeamInputs(
        actions=ActionInputs(bending_moment_knm=300.0)
    ).validated()
    service = DesignBrainService()
    preview = service.preview(current)
    metrics = service.last_search_metrics
    assert metrics["proportion_triggered"] is True
    assert metrics["additional_evaluations"] <= 24
    assert preview.candidate.source_revision == current.revision
    assert preview.candidate.source_hash == current.content_hash
    assert preview.after.source_revision == current.revision + 1
    assert preview.after.source_hash != current.content_hash


def test_geometry_locks_disable_proportion_balancing() -> None:
    current = BeamInputs(
        width_locked=True,
        depth_locked=True,
        actions=ActionInputs(bending_moment_knm=150.0),
    ).validated()
    service = DesignBrainService()
    service.preview(current)
    assert service.last_search_metrics["proportion_triggered"] is False
    assert service.last_search_metrics["additional_evaluations"] == 0
