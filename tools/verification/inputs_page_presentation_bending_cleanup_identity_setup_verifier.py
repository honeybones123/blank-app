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
    json_path = ARTIFACT_DIR / f"inputs_page_presentation_bending_cleanup_identity_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_presentation_bending_cleanup_identity_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    primary_item = {"title": "Original primary", "nested": {"kept": True}}
    result = inputs_page.render_design_guide_presentation_bending_cleanup_identity_setup(
        guidance_items=[primary_item],
        presentation_bending_evidence={
            "target_band_candidate_count": 2,
            "best_target_band_candidate_id": "target-band-1",
            "selected_candidate_id": "selected-1",
            "closest_safe_candidate_id": "closest-1",
        },
    )
    cases.append({"name": "target_band_candidate_identity", "result": result})
    item, title, candidate_id, family, subfamilies = result
    if item != primary_item or item is primary_item:
        failures.append(f"target_band_item_copy_mismatch:{result}")
    if title != "Bending cleanup - further reduction reaches target range":
        failures.append(f"target_band_title_mismatch:{result}")
    if candidate_id != "target-band-1":
        failures.append(f"target_band_candidate_id_mismatch:{result}")
    if family != "bending" or subfamilies != ["bottom_reinforcement"]:
        failures.append(f"target_band_family_mismatch:{result}")

    result = inputs_page.render_design_guide_presentation_bending_cleanup_identity_setup(
        guidance_items=[{"title": "Original primary"}],
        presentation_bending_evidence={
            "target_band_candidate_count": 0,
            "best_target_band_candidate_id": "ignored-target-band",
            "selected_candidate_id": "selected-2",
            "closest_safe_candidate_id": "closest-2",
        },
    )
    cases.append({"name": "selected_candidate_identity_fallback", "result": result})
    if result[1] != "Bending cleanup - best safe one-click reduction":
        failures.append(f"selected_title_mismatch:{result}")
    if result[2] != "selected-2":
        failures.append(f"selected_candidate_id_mismatch:{result}")

    result = inputs_page.render_design_guide_presentation_bending_cleanup_identity_setup(
        guidance_items=[{"title": "Original primary"}],
        presentation_bending_evidence={
            "target_band_candidate_count": 0,
            "closest_safe_candidate_id": "closest-3",
        },
    )
    cases.append({"name": "closest_safe_candidate_identity_fallback", "result": result})
    if result[2] != "closest-3":
        failures.append(f"closest_candidate_id_mismatch:{result}")

    result = inputs_page.render_design_guide_presentation_bending_cleanup_identity_setup(
        guidance_items=[{"title": "Original primary"}],
        presentation_bending_evidence={"target_band_candidate_count": 0},
    )
    cases.append({"name": "default_candidate_identity_fallback", "result": result})
    if result[2] != "bending_only_cleanup_candidate":
        failures.append(f"default_candidate_id_mismatch:{result}")

    payload_out = {
        "verifier": "inputs_page_presentation_bending_cleanup_identity_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Presentation Bending Cleanup Identity Setup Verifier",
                "",
                f"Status: `{payload_out['status']}`",
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
    print(payload_out["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
