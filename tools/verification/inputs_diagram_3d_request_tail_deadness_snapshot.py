from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _function_body(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.index(marker)
    next_def = source.find("\ndef ", start + len(marker))
    next_marker = source.find("\n# ------------------------------------------------------------", start + len(marker))
    candidates = [idx for idx in (next_def, next_marker) if idx != -1]
    end = min(candidates) if candidates else len(source)
    return source[start:end]


def run_snapshot() -> dict:
    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    body = _function_body(source, "make_beam_3d_figure")
    checks = {
        "uses_extracted_diagram_source_snapshot": "_build_inputs_diagram_source_snapshot(layout)" in body,
        "uses_extracted_diagram_view_model": "view_model = build_inputs_diagram_view_model(source)" in body,
        "uses_beam_view_model": "beam_vm = view_model.beam_3d" in body,
        "returns_from_beam_view_model": "shape_name=beam_vm.shape_name" in body and "resolved_bars=list(beam_vm.resolved_bars or ())" in body,
        "old_shape_name_default_removed": "shape_name = str(layout.get(\"shape_name\"" not in body,
        "old_local_ligature_resolution_removed": "shared_state = _shared_state_snapshot()" not in body,
        "old_local_outline_resolution_removed": "pts, b_box, D = _get_outline_points_and_bbox()" not in body,
        "old_resolved_bars_call_removed": "resolve_longitudinal_bars_from_layout(" not in body,
        "single_figure_return": body.count("return build_inputs_beam_3d_figure(") == 1,
    }
    failures = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    return {
        "status": status,
        "decision": "INPUTS_3D_PAGE_REQUEST_TAIL_DELETED" if status == "PASS" else "INPUTS_3D_PAGE_REQUEST_TAIL_STILL_PRESENT",
        "checks": checks,
        "failures": failures,
        "product_behavior_changed": False,
        "visible_behavior_changed": False,
    }


def write_artifacts(snapshot: dict) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_diagram_3d_request_tail_deadness_{ts}.json"
    md_path = AUDIT_DIR / f"inputs_diagram_3d_request_tail_deadness_{ts}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Inputs Diagram 3D Request Tail Deadness Snapshot",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- `{name}`: `{value}`" for name, value in snapshot["checks"].items())
    lines.extend(["", "## Failures"])
    lines.extend(f"- `{failure}`" for failure in snapshot["failures"]) if snapshot["failures"] else lines.append("- None")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    snapshot = run_snapshot()
    json_path, md_path = write_artifacts(snapshot)
    print(f"inputs_diagram_3d_request_tail_deadness_snapshot {snapshot['status']}")
    print(f"decision={snapshot['decision']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

