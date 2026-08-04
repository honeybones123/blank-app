from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_pre_presentation_bending_cleanup_context_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_presentation_bending_cleanup_context_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_parse = inputs_page._parse_util_value
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _parse(value):
        if value is None:
            return None
        return float(value)

    def _run_case(name: str, *, primary: dict, overview: dict, debug: dict):
        try:
            inputs_page._parse_util_value = _parse
            result = inputs_page.render_design_guide_pre_presentation_bending_cleanup_context(
                guidance_items=[primary],
                dg_overview=dict(overview),
                guidance_debug=dict(debug),
            )
        finally:
            inputs_page._parse_util_value = original_parse
        cases.append({"name": name, "result": result})
        return result

    primary = {
        "candidate_search_evidence": {
            "target_band_candidate_count": 2,
            "best_target_band_candidate_updates": {"bottom_bars": 3},
            "best_target_band_candidate_util": 0.91,
            "selected_candidate_updates": {"bottom_bars": 4},
            "selected_candidate_util": 0.8,
        }
    }
    result = _run_case(
        "primary_evidence_prefers_target_band_candidate",
        primary=primary,
        overview={"utils": {"bending": 0.42, "shear": 1.1}},
        debug={},
    )
    if result[0] != primary:
        failures.append(f"primary_identity_mismatch:{result[0]}")
    if result[1] != {"utils": {"bending": 0.42, "shear": 1.1}}:
        failures.append(f"overview_mismatch:{result[1]}")
    if result[2] != {"bending": 0.42, "shear": 1.1}:
        failures.append(f"utils_mismatch:{result[2]}")
    if result[3] != 0.42:
        failures.append(f"bending_util_mismatch:{result[3]}")
    if result[5] != {"bottom_bars": 3}:
        failures.append(f"target_band_updates_mismatch:{result[5]}")
    if result[6] != 0.91:
        failures.append(f"target_band_util_mismatch:{result[6]}")

    payload_evidence = {
        "selected_candidate_updates": {"width": 350},
        "selected_candidate_util": 0.76,
    }
    result = _run_case(
        "action_payload_evidence_selected_candidate",
        primary={"action_payload": {"candidate_search_evidence": payload_evidence}},
        overview={"utils": {"bending": 0.5}},
        debug={},
    )
    if result[4] != payload_evidence:
        failures.append(f"payload_evidence_mismatch:{result[4]}")
    if result[5] != {"width": 350} or result[6] != 0.76:
        failures.append(f"selected_candidate_projection_mismatch:{result[5:7]}")

    debug_evidence = {
        "closest_safe_candidate_updates": {"depth": 450},
        "closest_safe_candidate_util": 0.69,
    }
    result = _run_case(
        "debug_evidence_closest_safe_fallback",
        primary={},
        overview={"utils": {"bending": 0.8}},
        debug={
            "overview": {"utils": {"bending": 0.31}},
            "candidate_search_evidence": debug_evidence,
        },
    )
    if result[1] != {"utils": {"bending": 0.31}}:
        failures.append(f"debug_overview_precedence_mismatch:{result[1]}")
    if result[3] != 0.31:
        failures.append(f"debug_bending_util_mismatch:{result[3]}")
    if result[4] != debug_evidence:
        failures.append(f"debug_evidence_mismatch:{result[4]}")
    if result[5] != {"depth": 450} or result[6] != 0.69:
        failures.append(f"closest_safe_projection_mismatch:{result[5:7]}")

    payload = {
        "verifier": "inputs_page_pre_presentation_bending_cleanup_context_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre Presentation Bending Cleanup Context Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`" for case in cases),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
