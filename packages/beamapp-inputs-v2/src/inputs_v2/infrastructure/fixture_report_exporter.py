"""Deterministic report exporter used until the production adapter is approved."""

from __future__ import annotations

import csv
import io

from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.domain.reporting import ReportArtifact, ReportRequest


class FixtureReportExporter:
    def export(self, request: ReportRequest, inputs: BeamInputs, result: EngineeringResult) -> ReportArtifact:
        if request.source_revision != inputs.revision or request.source_hash != inputs.content_hash:
            raise ValueError("report request is stale")
        if request.format == "pdf":
            body = _make_pdf(
                f"Beam {request.beam_id} | revision {inputs.revision} | hash {inputs.content_hash} | result {result.summary}"
            )
        elif request.format == "csv":
            stream = io.StringIO(newline="")
            writer = csv.writer(stream)
            writer.writerow(("beam_id", "revision", "input_hash", "result"))
            writer.writerow((request.beam_id, inputs.revision, inputs.content_hash, result.summary))
            body = stream.getvalue().encode("utf-8")
        else:
            body = (
                f"Beam {request.beam_id}\n"
                f"revision={inputs.revision}\n"
                f"input_hash={inputs.content_hash}\n"
                f"result={result.summary}\n"
            ).encode("utf-8")
        extension = request.format
        media_type = {"html": "text/html", "pdf": "application/pdf", "csv": "text/csv"}[extension]
        return ReportArtifact(request, media_type, f"{request.beam_id}-r{inputs.revision}.{extension}", body)


def _make_pdf(text: str) -> bytes:
    """Create a tiny deterministic one-page PDF for isolated lab evidence."""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 11 Tf 50 760 Td ({escaped}) Tj ET".encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects)+1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    output.extend(b"".join(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:]))
    output.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(output)
