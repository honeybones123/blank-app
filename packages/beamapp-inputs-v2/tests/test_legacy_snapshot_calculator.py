from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.engineering.engineering_calculator import EngineeringCalculator


def test_copied_engineering_snapshot_is_revision_tagged() -> None:
    inputs = BeamInputs().validated()
    result = EngineeringCalculator().calculate(inputs)
    assert result.status == "production-shadow"
    assert result.source_revision == inputs.revision
    assert result.source_hash == inputs.content_hash
    assert {"bending", "shear", "creep_shrinkage"} <= result.families.keys()


def test_copied_engineering_snapshot_changes_with_actions() -> None:
    inputs = BeamInputs().validated()
    changed = inputs.next_revision(
        width_mm=inputs.width_mm, depth_mm=inputs.depth_mm, bottom=inputs.bottom,
        actions=inputs.actions.__class__(bending_moment_knm=180.0),
    )
    result = EngineeringCalculator().calculate(changed)
    assert result.families["bending"]["M_star_kNm"] == 180.0
