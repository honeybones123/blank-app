from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.families.bending_and_shear_fail_govern.contract import (  # noqa: E402
    CONTRACT_PATH,
    expected_ladder_snapshots,
    family_identity,
    required_locked_snapshot_fields,
)


IDENTITY = family_identity()
FAMILY_ID = str(IDENTITY.get("family_id") or "")
RUNTIME_FAMILY_ID = str(IDENTITY.get("runtime_family_id") or "")


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _locked_fixture_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 350.0,
        "bot1_count": 2,
        "db_bot_1": 10,
        "bot_row_1_bars": 2,
        "bot_row_1_dia": 10,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200.0,
    }


def _spec_snapshot(spec: dict[str, Any]) -> dict[str, Any]:
    updates = dict(spec.get("updates") or {})
    return {
        "ladder_index": spec.get("ladder_index"),
        "contract_step": spec.get("contract_step"),
        "strategy": spec.get("strategy"),
        "updates": updates,
        "update_keys": sorted(updates.keys()),
        "stop_rule": spec.get("stop_rule"),
        "candidate_family_id": spec.get("candidate_family_id"),
        "label": spec.get("label"),
    }


def _ladder_snapshot(*, geometry_locked: bool) -> dict[str, Any]:
    from design_brain.families.combined_bending_shear_fail import CombinedBendingShearFailFamily

    family = CombinedBendingShearFailFamily()
    result = family.contracted_repair_ladder_specs(_locked_fixture_state(), geometry_locked=geometry_locked)
    specs = [_spec_snapshot(dict(spec)) for spec in list(result.get("specs") or [])]
    ladder_hash = _stable_hash(specs)
    indexes = [spec.get("ladder_index") for spec in specs]
    labels = [str(spec.get("label") or "") for spec in specs]
    stage_plan_order = [spec.get("contract_step") for spec in specs]
    update_payload_surfaces = [
        {
            "ladder_index": spec.get("ladder_index"),
            "update_keys": spec.get("update_keys"),
            "updates": spec.get("updates"),
        }
        for spec in specs
    ]
    result_summary = {
        "family_name": result.get("family_name"),
        "governing_state": result.get("governing_state"),
        "candidate_strategy": result.get("candidate_strategy"),
        "ranking_strategy": result.get("ranking_strategy"),
        "depth_steps_mm": result.get("depth_steps_mm"),
        "width_steps_mm": result.get("width_steps_mm"),
        "bottom_repair_count": result.get("bottom_repair_count"),
        "bottom_repair_dia": result.get("bottom_repair_dia"),
        "lig_diameters_tried": result.get("lig_diameters_tried"),
        "spacing_values_tried": result.get("spacing_values_tried"),
        "stop_rule": result.get("stop_rule"),
        "fallback_rule": result.get("fallback_rule"),
        "spec_count": len(specs),
        "ladder_hash": ladder_hash,
    }
    return {
        "geometry_locked": geometry_locked,
        "family_id": FAMILY_ID,
        "runtime_family_id": RUNTIME_FAMILY_ID,
        "stage_plan_order": stage_plan_order,
        "candidate_count": len(specs),
        "candidate_indexes": indexes,
        "candidate_labels": labels,
        "update_payload_surfaces": update_payload_surfaces,
        "depth_steps_mm": result.get("depth_steps_mm"),
        "width_steps_mm": result.get("width_steps_mm"),
        "bottom_repair_count": result.get("bottom_repair_count"),
        "bottom_repair_dia": result.get("bottom_repair_dia"),
        "lig_diameters_tried": result.get("lig_diameters_tried"),
        "spacing_values_tried": result.get("spacing_values_tried"),
        "stop_rule": result.get("stop_rule"),
        "fallback_rule": result.get("fallback_rule"),
        "final_result_summary": result_summary,
        "repair_ladder_hash": ladder_hash,
        "first_spec": specs[0] if specs else None,
        "last_spec": specs[-1] if specs else None,
    }


def _run_product_regression() -> dict[str, Any]:
    command = [sys.executable, "tools/verification/combined_bending_shear_fail_repair_regression.py"]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    artifact = None
    for line in str(completed.stdout or "").splitlines():
        text = line.strip()
        if text.startswith("PASS:") or text.startswith("FAIL:"):
            artifact = text.split(":", 1)[1].strip()
            break
    return {
        "command": command,
        "returncode": completed.returncode,
        "artifact": artifact,
        "stdout": completed.stdout,
        "stderr_tail": completed.stderr[-4000:],
        "status": "PASS" if completed.returncode == 0 else "FAIL",
    }


def _validate_ladder(snapshot: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    missing_fields = [field for field in required_locked_snapshot_fields() if field not in snapshot]
    for field in missing_fields:
        failures.append(f"missing_locked_snapshot_field:{field}")
    summary = dict(snapshot.get("final_result_summary") or {})
    if snapshot.get("family_id") != FAMILY_ID:
        failures.append(f"family_id_mismatch:{snapshot.get('family_id')}")
    if snapshot.get("runtime_family_id") != RUNTIME_FAMILY_ID:
        failures.append(f"runtime_family_id_mismatch:{snapshot.get('runtime_family_id')}")
    if summary.get("family_name") != RUNTIME_FAMILY_ID:
        failures.append(f"summary_family_name_mismatch:{summary.get('family_name')}")
    if summary.get("governing_state") != RUNTIME_FAMILY_ID:
        failures.append(f"governing_state_mismatch:{summary.get('governing_state')}")
    for key in (
        "candidate_count",
        "repair_ladder_hash",
        "stage_plan_order",
        "depth_steps_mm",
        "width_steps_mm",
        "bottom_repair_count",
        "bottom_repair_dia",
        "lig_diameters_tried",
        "spacing_values_tried",
        "stop_rule",
        "fallback_rule",
    ):
        if snapshot.get(key) != expected.get(key):
            failures.append(f"{key}_mismatch")
    indexes = list(snapshot.get("candidate_indexes") or [])
    if indexes != list(range(1, len(indexes) + 1)):
        failures.append("candidate_indexes_not_strictly_increasing_from_one")
    labels = list(snapshot.get("candidate_labels") or [])
    for index, label in zip(indexes, labels):
        expected_prefix = f"{RUNTIME_FAMILY_ID} ladder {index}: "
        if not str(label).startswith(expected_prefix):
            failures.append(f"candidate_label_prefix_mismatch:{index}")
            break
    for spec in [snapshot.get("first_spec"), snapshot.get("last_spec")]:
        if spec and dict(spec).get("candidate_family_id") != RUNTIME_FAMILY_ID:
            failures.append("spec_candidate_family_id_mismatch")
            break
    return failures


def _write_markdown_report(output: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# BENDING_AND_SHEAR_FAIL_GOVERN Locked Regression",
        "",
        f"Status: {output.get('status')}",
        "",
        "## Lock Decision",
        "",
        f"- ready_to_mark_locked_next: `{output.get('ready_to_mark_locked_next')}`",
        f"- family_marked_locked_now: `{output.get('family_marked_locked_now')}`",
        "",
        "## Direct Ladder Snapshots",
        "",
    ]
    for key in output.get("required_snapshots") or []:
        snapshot = dict(output.get("direct_ladder_snapshots", {}).get(key) or {})
        lines.extend(
            [
                f"### {key}",
                "",
                f"- candidate_count: `{snapshot.get('candidate_count')}`",
                f"- repair_ladder_hash: `{snapshot.get('repair_ladder_hash')}`",
                f"- stage_plan_order: `{snapshot.get('stage_plan_order')}`",
                f"- stop_rule: `{snapshot.get('stop_rule')}`",
                "",
            ]
        )
    product = dict(output.get("product_path_confirmation") or {})
    lines.extend(
        [
            "## Product Path Confirmation",
            "",
            f"- status: `{product.get('status')}`",
            f"- artifact: `{product.get('artifact')}`",
            "",
            "## Failures",
            "",
        ]
    )
    lines.extend([f"- {failure}" for failure in output.get("failures") or []] or ["- none"])
    lines.extend(["", "## Output", "", f"- `{output.get('artifact')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    expected = expected_ladder_snapshots()
    direct_snapshots = {
        "geometry_unlocked_ladder": _ladder_snapshot(geometry_locked=False),
        "geometry_locked_ladder": _ladder_snapshot(geometry_locked=True),
    }
    failures: list[str] = []
    for name, snapshot in direct_snapshots.items():
        failures.extend(f"{name}:{failure}" for failure in _validate_ladder(snapshot, dict(expected.get(name) or {})))
    product_confirmation = _run_product_regression()
    if product_confirmation.get("status") != "PASS":
        failures.append("combined_product_path_regression_failed")
    status = "PASS" if not failures else "FAIL"
    output = {
        "schema": "bending_and_shear_fail_govern_locked_regression.v1",
        "status": status,
        "contract_path": str(CONTRACT_PATH),
        "family_id": FAMILY_ID,
        "runtime_family_id": RUNTIME_FAMILY_ID,
        "required_snapshot_fields": list(required_locked_snapshot_fields()),
        "required_snapshots": list(expected.keys()),
        "direct_ladder_snapshots": direct_snapshots,
        "product_path_confirmation": product_confirmation,
        "ready_to_mark_locked_next": status == "PASS",
        "family_marked_locked_now": False,
        "failures": failures,
    }
    artifact_path = ARTIFACT_DIR / f"bending_and_shear_fail_govern_locked_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_and_shear_fail_govern_locked_regression_{stamp}.md"
    output["artifact"] = str(artifact_path)
    output["report"] = str(report_path)
    artifact_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown_report(output, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
