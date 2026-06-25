from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PACKAGE_INIT = ROOT / "design_brain" / "families" / "bending_and_shear_fail_govern" / "__init__.py"


def _source_contains(path: Path, needle: str) -> bool:
    return needle in path.read_text(encoding="utf-8", errors="replace")


def _line_hits(path: Path, needle: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if needle in line:
            hits.append({"line": idx, "text": line.strip()[:240]})
    return hits


def main() -> int:
    failures: list[str] = []
    if not PACKAGE_INIT.exists():
        failures.append("missing_bending_and_shear_fail_govern_package_init")

    source = PACKAGE_INIT.read_text(encoding="utf-8", errors="replace") if PACKAGE_INIT.exists() else ""
    if "inputs_page" in source:
        failures.append("bending_and_shear_fail_govern_imports_inputs_page")
    if "def evaluate_bending_and_shear_fail_govern" not in source:
        failures.append("missing_evaluate_bending_and_shear_fail_govern")

    engine_hits = _line_hits(ROOT / "design_brain" / "engine.py", "evaluate_bending_and_shear_fail_govern")
    inputs_hits = _line_hits(ROOT / "inputs_page.py", "evaluate_bending_and_shear_fail_govern")
    if engine_hits:
        failures.append("engine_calls_new_bending_and_shear_fail_govern_api")
    if inputs_hits:
        failures.append("inputs_page_calls_new_bending_and_shear_fail_govern_api")

    result_summary: dict[str, Any] = {}
    if not failures:
        from design_brain.families.bending_and_shear_fail_govern import evaluate_bending_and_shear_fail_govern
        from design_brain.shared.schemas import FamilyResult

        result = evaluate_bending_and_shear_fail_govern(
            {
                "summary": {
                    "statuses": {"shear": "FAIL", "bending": "FAIL"},
                    "utils": {"shear": 1.18, "bending": 1.12},
                },
                "evidence": {
                    "active_failures": ["bending", "shear"],
                    "candidate_rows": [],
                },
                "primary": {
                    "title": "Combined repair required",
                    "status": "FAIL",
                    "button_contract": {
                        "action_type": "apply_resolved_candidate",
                        "updates": {"D": 420.0, "s_lig": 125.0},
                    },
                },
            }
        )
        if not isinstance(result, FamilyResult):
            failures.append("api_did_not_return_family_result")
        result_summary = {
            "family_id": getattr(result, "family_id", None),
            "is_applicable": getattr(result, "is_applicable", None),
            "status": getattr(result, "status", None),
            "evidence_keys": sorted((getattr(result, "evidence", {}) or {}).keys()),
            "publication_keys": sorted((getattr(result, "publication", {}) or {}).keys()),
            "cta_contract_keys": sorted((getattr(result, "cta_contract", {}) or {}).keys()),
            "legacy_runtime_family_id": (getattr(result, "lock_proof", {}) or {}).get("legacy_runtime_family_id"),
            "product_routing_enabled": bool((getattr(result, "lock_proof", {}) or {}).get("product_routing_enabled")),
            "compatibility_api": bool((getattr(result, "lock_proof", {}) or {}).get("compatibility_api")),
        }
        if result_summary.get("family_id") != "BENDING_AND_SHEAR_FAIL_GOVERN":
            failures.append("family_id_mismatch")
        if result_summary.get("is_applicable") is not True:
            failures.append("synthetic_combined_fail_context_not_applicable")
        if result_summary.get("legacy_runtime_family_id") != "COMBINED_BENDING_SHEAR_FAIL":
            failures.append("legacy_runtime_family_id_mismatch")
        if result_summary.get("product_routing_enabled") is not False:
            failures.append("api_claims_product_routing_enabled")

    status = "PASS" if not failures else "FAIL"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    output = {
        "schema": "design_brain_bending_and_shear_fail_govern_api_check.v1",
        "status": status,
        "package": str(PACKAGE_INIT.relative_to(ROOT)),
        "imports_inputs_page": _source_contains(PACKAGE_INIT, "inputs_page") if PACKAGE_INIT.exists() else None,
        "engine_call_hits": engine_hits,
        "inputs_page_call_hits": inputs_hits,
        "api_result_summary": result_summary,
        "failures": failures,
    }
    output_path = ARTIFACT_DIR / f"design_brain_bending_and_shear_fail_govern_api_check_{stamp}.json"
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    report_path = AUDIT_DIR / f"design_brain_bending_and_shear_fail_govern_api_check_{stamp}.md"
    report_lines = [
        "# Design Brain BENDING_AND_SHEAR_FAIL_GOVERN API Check",
        "",
        f"Status: {status}",
        "",
        "## Result Summary",
        "",
        f"- family_id: `{result_summary.get('family_id')}`",
        f"- is_applicable: `{result_summary.get('is_applicable')}`",
        f"- legacy_runtime_family_id: `{result_summary.get('legacy_runtime_family_id')}`",
        f"- product_routing_enabled: `{result_summary.get('product_routing_enabled')}`",
        f"- compatibility_api: `{result_summary.get('compatibility_api')}`",
        "",
        "## Failures",
        "",
    ]
    report_lines.extend([f"- {failure}" for failure in failures] or ["- none"])
    report_lines.extend(["", "## Output", "", f"- `{output_path}`"])
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"{status}: {output_path}")
    print(f"REPORT: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
