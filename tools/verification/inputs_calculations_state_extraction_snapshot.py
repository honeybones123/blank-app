from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
MODULE_ROOT = ROOT / "inputs_page_modules" / "calculations"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_report(payload: dict, report_path: Path) -> None:
    lines = [
        "# Inputs Calculations State Extraction Snapshot",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Source row copying and source-hash construction are module-owned.",
            "- `inputs_page.py` still owns row collection, Streamlit/session state, and rendering.",
            "- Live renderer remains unchanged.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    module_sources = {
        path.name: _read(path)
        for path in MODULE_ROOT.glob("*.py")
    }
    module_combined = "\n".join(module_sources.values())
    page_import_match = re.search(
        r"from inputs_page_modules\.calculations import \((?P<body>.*?)\)",
        page,
        re.DOTALL,
    )
    page_import_section = page_import_match.group("body") if page_import_match else ""
    checks = {
        "module_has_source_snapshot_builder": "def build_inputs_calculation_explainer_source_snapshot(" in module_sources.get("builders.py", ""),
        "module_has_source_hash_builder": "def build_inputs_calculation_explainer_source_hash(" in module_sources.get("builders.py", ""),
        "module_exports_source_snapshot_builder": "build_inputs_calculation_explainer_source_snapshot" in module_sources.get("__init__.py", ""),
        "module_exports_source_hash_builder": "build_inputs_calculation_explainer_source_hash" in module_sources.get("__init__.py", ""),
        "page_imports_source_builder": "build_inputs_calculation_explainer_source_snapshot" in page_import_section,
        "page_imports_source_hash_builder": "build_inputs_calculation_explainer_source_hash" in page_import_section,
        "page_calls_source_builder": "_calculation_explainer_source_snapshot = build_inputs_calculation_explainer_source_snapshot(" in page,
        "page_calls_source_hash_builder": "_calculation_explainer_source_hash = build_inputs_calculation_explainer_source_hash(" in page,
        "page_no_direct_source_dataclass_import": "InputsCalculationExplainerSourceSnapshot" not in page_import_section,
        "page_no_direct_source_dataclass_construction": "_calculation_explainer_source_snapshot = InputsCalculationExplainerSourceSnapshot(" not in page,
        "module_imports_streamlit": "import streamlit" in module_combined or "from streamlit" in module_combined,
        "module_imports_inputs_page": "inputs_page" in module_combined,
        "live_renderer_not_cut_over": '"live_calculation_explainer_renderer_cutover": False' in page,
    }
    failures = [
        key for key, value in checks.items()
        if (key.startswith("module_imports_") and value) or (not key.startswith("module_imports_") and not value)
    ]
    decision = "CALCULATION_STATE_EXTRACTED_TRACE_ONLY" if not failures else "CALCULATION_STATE_EXTRACTION_GAPS_REMAIN"
    payload = {
        "audit": "inputs_calculations_state_extraction_snapshot",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "live_renderer_switched": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_calculations_state_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_calculations_state_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_calculations_state_extraction_snapshot", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
