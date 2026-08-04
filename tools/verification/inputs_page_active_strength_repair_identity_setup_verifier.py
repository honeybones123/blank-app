from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_active_strength_repair_identity_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_active_strength_repair_identity_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    def _case(name: str, *, keys: set, item: dict | None = None, debug: dict | None = None):
        result = inputs_page.render_design_guide_active_strength_repair_identity_setup(
            active_strength_fail_keys_for_card=set(keys),
            guidance_items=[dict(item or {})],
            guidance_debug=dict(debug or {}),
        )
        cases.append({"name": name, "result": result})
        return result

    result = _case("combined_from_bending_and_shear", keys={"bending", "shear"})
    if result != ("combined", "Bending and shear capacity are low", ""):
        failures.append(f"combined_result_mismatch:{result}")

    result = _case("shear_from_shear_key", keys={"shear"})
    if result != ("shear", "Shear capacity is low", ""):
        failures.append(f"shear_result_mismatch:{result}")

    result = _case("bending_default_from_bending_key", keys={"bending"})
    if result != ("bending", "Bending capacity is low", ""):
        failures.append(f"bending_result_mismatch:{result}")

    result = _case(
        "selected_family_id_forces_bending",
        keys={"bending", "shear"},
        item={"selected_family_id": "BENDING_FAIL_GOVERNS"},
    )
    if result != ("bending", "Bending capacity is low", "BENDING_FAIL_GOVERNS"):
        failures.append(f"selected_bending_result_mismatch:{result}")

    result = _case(
        "evidence_selected_family_id_forces_shear",
        keys={"bending", "shear"},
        item={"candidate_search_evidence": {"selected_family_id": "SHEAR_FAIL_GOVERNS"}},
    )
    if result != ("shear", "Shear capacity is low", "SHEAR_FAIL_GOVERNS"):
        failures.append(f"evidence_shear_result_mismatch:{result}")

    result = _case(
        "debug_selected_family_id_fallback",
        keys={"bending", "shear"},
        debug={"selected_family_id": "SHEAR_FAIL_GOVERNS"},
    )
    if result != ("shear", "Shear capacity is low", "SHEAR_FAIL_GOVERNS"):
        failures.append(f"debug_shear_result_mismatch:{result}")

    payload = {
        "verifier": "inputs_page_active_strength_repair_identity_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Active Strength Repair Identity Setup Verifier",
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
