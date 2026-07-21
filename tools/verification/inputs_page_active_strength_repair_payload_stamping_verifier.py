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
    json_path = ARTIFACT_DIR / f"inputs_page_active_strength_repair_payload_stamping_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_active_strength_repair_payload_stamping_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    merged_cleanup = {"evidence": {"merged": True, "candidate": "shear-cleanup"}}
    item, payload, resolved = inputs_page.render_design_guide_active_strength_repair_payload_stamping(
        active_repair_item={
            "action_payload": {"old": True},
            "resolved_candidate": {"old_resolved": True},
        },
        active_repair_contract={"enabled": True, "updates": {"depth": 475}},
        active_repair_family="combined",
        active_repair_title="Bending and shear capacity are low",
        active_repair_updates={"depth": 475, "links": "T10"},
        active_repair_expected_util=0.91,
        active_repair_merged_shear_cleanup=merged_cleanup,
    )
    cases.append({"name": "stamps_payload_resolved_and_contract", "item": item, "payload": payload, "resolved": resolved})
    if item.get("button_contract") != {"enabled": True, "updates": {"depth": 475}}:
        failures.append(f"button_contract_not_stamped:{item}")
    for container_name, container in (("payload", payload), ("resolved", resolved)):
        if container.get("family") != "combined":
            failures.append(f"{container_name}_family_mismatch:{container}")
        if container.get("updates") != {"depth": 475, "links": "T10"}:
            failures.append(f"{container_name}_updates_mismatch:{container}")
        if container.get("active_repair_includes_residual_shear_cleanup") is not True:
            failures.append(f"{container_name}_merged_flag_missing:{container}")
        if container.get("residual_shear_cleanup_evidence") != merged_cleanup["evidence"]:
            failures.append(f"{container_name}_merged_evidence_mismatch:{container}")
        if container.get("candidate_post_util") != 0.91 or container.get("expected_util") != 0.91:
            failures.append(f"{container_name}_util_mismatch:{container}")
    if payload.get("resolved_candidate_updates") != {"depth": 475, "links": "T10"}:
        failures.append(f"payload_resolved_updates_mismatch:{payload}")
    if resolved.get("label") != "Bending and shear capacity are low":
        failures.append(f"resolved_label_mismatch:{resolved}")

    item, payload, resolved = inputs_page.render_design_guide_active_strength_repair_payload_stamping(
        active_repair_item={"title": "No payloads"},
        active_repair_contract={},
        active_repair_family="bending",
        active_repair_title="Bending capacity is low",
        active_repair_updates={},
        active_repair_expected_util=None,
        active_repair_merged_shear_cleanup={},
    )
    cases.append({"name": "empty_payloads_stay_empty", "item": item, "payload": payload, "resolved": resolved})
    if payload != {} or resolved != {}:
        failures.append(f"empty_payloads_not_empty:{payload}:{resolved}")
    if "button_contract" in item:
        failures.append(f"empty_contract_stamped_unexpectedly:{item}")

    item, payload, resolved = inputs_page.render_design_guide_active_strength_repair_payload_stamping(
        active_repair_item={
            "action_payload": {"old": True},
            "resolved_candidate": {"old_resolved": True},
        },
        active_repair_contract={},
        active_repair_family="shear",
        active_repair_title="Shear capacity is low",
        active_repair_updates={},
        active_repair_expected_util=0.77,
        active_repair_merged_shear_cleanup={},
    )
    cases.append({"name": "util_only_without_updates", "item": item, "payload": payload, "resolved": resolved})
    if payload.get("family") != "shear" or resolved.get("family") != "shear":
        failures.append(f"util_only_family_mismatch:{payload}:{resolved}")
    if "updates" in payload or "updates" in resolved:
        failures.append(f"util_only_updates_unexpected:{payload}:{resolved}")
    if payload.get("expected_util") != 0.77 or resolved.get("expected_util") != 0.77:
        failures.append(f"util_only_expected_mismatch:{payload}:{resolved}")

    payload_out = {
        "verifier": "inputs_page_active_strength_repair_payload_stamping_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Active Strength Repair Payload Stamping Verifier",
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
