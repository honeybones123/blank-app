from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _function_body(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.index(marker)
    next_def = source.find("\ndef ", start + len(marker))
    next_marker = source.find("\n# ------------------------------------------------------------", start + len(marker))
    candidates = [idx for idx in (next_def, next_marker) if idx != -1]
    end = min(candidates) if candidates else len(source)
    return source[start:end]


def run_snapshot() -> dict:
    files = {
        "models": "inputs_page_modules/diagrams/models.py",
        "builders": "inputs_page_modules/diagrams/builders.py",
        "contracts": "inputs_page_modules/diagrams/contracts.py",
        "page": "inputs_page.py",
    }
    source = {key: _read(path) for key, path in files.items()}
    module_source = source["models"] + source["builders"] + source["contracts"]
    beam_body = _function_body(source["page"], "make_beam_3d_figure")
    checks = {
        "models_define_source_snapshot": "class InputsDiagramSourceSnapshot" in source["models"],
        "models_define_section_2d_vm": "class Section2DFigureRequestViewModel" in source["models"],
        "models_define_beam_3d_vm": "class Beam3DFigureRequestViewModel" in source["models"],
        "builders_define_section_builder": "def build_section_2d_request_view_model(" in source["builders"],
        "builders_define_beam_builder": "def build_beam_3d_request_view_model(" in source["builders"],
        "contracts_define_hash_fields": "SECTION_2D_HASH_FIELDS" in source["contracts"] and "BEAM_3D_HASH_FIELDS" in source["contracts"],
        "diagram_module_no_streamlit_import": not re.search(r"(?m)^\s*(import|from)\s+streamlit\b", module_source),
        "diagram_module_no_inputs_page_import": not re.search(r"(?m)^\s*(import|from)\s+inputs_page\b", module_source),
        "page_renderers_still_present": "def _render_section_2d_diagram_block" in source["page"] and "def _render_3d_diagram_block" in source["page"],
        "page_trace_wiring_present": "build_inputs_diagram_view_model(source)" in source["page"],
        "page_trace_marked_not_live_cutover": "live_cutover=False" in source["page"],
        "current_figure_paths_still_authoritative": "fig_sec = make_summary_cross_section_figure()" in source["page"] and "fig3d = make_beam_3d_figure()" in source["page"],
        "page_delegates_2d_request_defaults": "section_vm = view_model.section_2d" in source["page"] and "fallback_cover_side=float(section_vm.fallback_cover_side)" in source["page"],
        "page_delegates_3d_request_to_view_model": "beam_vm = view_model.beam_3d" in source["page"] and "shape_name=beam_vm.shape_name" in source["page"],
        "old_3d_request_tail_deleted": "shape_name = str(layout.get(\"shape_name\"" not in beam_body,
    }
    failures = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    return {
        "status": status,
        "decision": "DIAGRAM_REQUEST_CONSTRUCTION_DELEGATED" if status == "PASS" else "DIAGRAM_EXTRACTION_OWNERSHIP_AMBIGUOUS",
        "checks": checks,
        "failures": failures,
        "product_behavior_changed": False,
        "live_cutover_performed": False,
    }


def write_artifacts(snapshot: dict) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_diagram_state_extraction_{ts}.json"
    md_path = AUDIT_DIR / f"inputs_diagram_state_extraction_{ts}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Inputs Diagram State Extraction Snapshot",
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
    print(f"inputs_diagram_state_extraction_snapshot {snapshot['status']}")
    print(f"decision={snapshot['decision']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
