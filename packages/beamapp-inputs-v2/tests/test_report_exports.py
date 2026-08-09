from inputs_v2.application.report_exports import request_for_current
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.engineering_port.fixture_calculator import FixtureCalculator
from inputs_v2.infrastructure.fixture_report_exporter import FixtureReportExporter


def test_report_export_is_revision_tagged_and_typed() -> None:
    inputs = BeamInputs().validated()
    result = FixtureCalculator().calculate(inputs)
    request = request_for_current("A", inputs, "pdf")
    artifact = FixtureReportExporter().export(request, inputs, result)
    assert artifact.filename == "A-r0.pdf"
    assert artifact.media_type == "application/pdf"
    assert artifact.content.startswith(b"%PDF-1.4")
    assert str(inputs.content_hash).encode() in artifact.content


def test_report_export_rejects_stale_request() -> None:
    inputs = BeamInputs().validated()
    result = FixtureCalculator().calculate(inputs)
    request = request_for_current("A", inputs, "html")
    newer = BeamInputs(revision=1).validated()
    try:
        FixtureReportExporter().export(request, newer, result)
    except ValueError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("stale report request was accepted")


def test_csv_report_is_structured_and_revision_tagged() -> None:
    inputs = BeamInputs().validated()
    result = FixtureCalculator().calculate(inputs)
    artifact = FixtureReportExporter().export(request_for_current("A", inputs, "csv"), inputs, result)
    rows = list(csv.DictReader(io.StringIO(artifact.content.decode("utf-8"))))
    assert rows[0]["beam_id"] == "A"
    assert rows[0]["revision"] == "0"
    assert rows[0]["input_hash"] == inputs.content_hash
import csv
import io
