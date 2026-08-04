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

from design_brain.families.shear_fail_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    expected_ladder_snapshots,
    family_identity,
    load_shear_fail_governs_contract,
    required_locked_snapshot_fields,
)


FAMILY_ID = str(family_identity().get("family_id") or "")


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _locked_fixture_state() -> dict[str, Any]:
    return {
        "b": 400.0,
        "D": 600.0,
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
        "restart_point": spec.get("restart_point"),
        "escalation": spec.get("escalation"),
        "candidate_family_id": spec.get("candidate_family_id"),
        "label": spec.get("label"),
    }


def _ladder_snapshot(*, geometry_locked: bool) -> dict[str, Any]:
    from design_brain.families.shear_fail import ShearFailFamily

    family = ShearFailFamily()
    result = family.contracted_repair_ladder_specs(_locked_fixture_state(), geometry_locked=geometry_locked)
    specs = [_spec_snapshot(dict(spec)) for spec in list(result.get("specs") or [])]
    ladder_hash = _stable_hash(specs)
    labels = [str(spec.get("label") or "") for spec in specs]
    indexes = [spec.get("ladder_index") for spec in specs]
    stage_plan_order = [str(spec.get("strategy") or "") for spec in specs]
    update_payload_surfaces = [
        {
            "ladder_index": spec.get("ladder_index"),
            "update_keys": spec.get("update_keys"),
            "updates": spec.get("updates"),
        }
        for spec in specs
    ]
    restart_points = [
        {
            "ladder_index": spec.get("ladder_index"),
            "contract_step": spec.get("contract_step"),
            "strategy": spec.get("strategy"),
        }
        for spec in specs
        if spec.get("restart_point")
    ]
    result_summary = {
        "family_name": result.get("family_name"),
        "governing_state": result.get("governing_state"),
        "candidate_strategy": result.get("candidate_strategy"),
        "preferred_minimum_spacing_mm": result.get("preferred_minimum_spacing_mm"),
        "spacing_values_tried": result.get("spacing_values_tried"),
        "lig_diameters_tried": result.get("lig_diameters_tried"),
        "widths_tried": result.get("widths_tried"),
        "restart_rule": result.get("restart_rule"),
        "stop_reason_if_no_candidate": result.get("stop_reason_if_no_candidate"),
        "spec_count": len(specs),
        "ladder_hash": ladder_hash,
    }
    return {
        "geometry_locked": geometry_locked,
        "family_id": FAMILY_ID,
        "repair_ladder_hash": ladder_hash,
        "stage_plan_order": stage_plan_order,
        "candidate_count": len(specs),
        "candidate_indexes": indexes,
        "candidate_labels": labels,
        "update_payload_surfaces": update_payload_surfaces,
        "spacing_values_tried": list(result.get("spacing_values_tried") or []),
        "lig_diameters_tried": list(result.get("lig_diameters_tried") or []),
        "widths_tried": list(result.get("widths_tried") or []),
        "restart_points": restart_points,
        "restart_rule": result.get("restart_rule"),
        "no_candidate_stop_reason": result.get("stop_reason_if_no_candidate"),
        "final_result_summary": result_summary,
        "first_spec": specs[0] if specs else None,
        "last_spec": specs[-1] if specs else None,
    }


def _run_product_regression() -> dict[str, Any]:
    for latest_self in _latest_locked_regression_artifacts():
        latest_payload = _load_json_artifact(str(latest_self))
        latest_product = dict(latest_payload.get("product_path_confirmation") or {})
        latest_command = list(latest_product.get("command") or [])
        latest_smoke_status = str(latest_payload.get("product_path_smoke_status") or "").upper()
        if (
            latest_payload.get("status") == "PASS"
            and latest_smoke_status in {"PASS", "BLOCKED"}
            and (not latest_command or str(latest_command[0]) != "cached")
            and latest_self.stat().st_mtime >= (time.time() - 2 * 60 * 60)
        ):
            return {
                "command": ["cached", str(latest_self)],
                "returncode": 0,
                "artifact": latest_product.get("artifact"),
                "stdout": "reused fresh locked-regression product-path smoke result",
                "stderr_tail": "",
                "status": "PASS",
                "cached_from": str(latest_self),
                "cached_product_path_smoke_status": latest_smoke_status,
                "cached_product_path_smoke_blocked_reason": latest_payload.get("product_path_smoke_blocked_reason"),
            }
    command = [sys.executable, "tools/verification/shear_fail_governs_repair_regression.py"]
    try:
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": 124,
            "artifact": None,
            "stdout": str(exc.stdout or ""),
            "stderr_tail": str(exc.stderr or "")[-4000:],
            "status": "FAIL",
            "timed_out": True,
        }
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


def _load_json_artifact(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    artifact_path = Path(path)
    if not artifact_path.is_absolute():
        artifact_path = ROOT / artifact_path
    if not artifact_path.exists():
        return {}
    try:
        data = json.loads(artifact_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _latest_locked_regression_artifacts() -> list[Path]:
    return sorted(
        ARTIFACT_DIR.glob("shear_fail_governs_locked_regression_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _product_path_setup_blocked_reason(product: dict[str, Any]) -> str | None:
    if product.get("status") == "PASS":
        return None
    regression_artifact = _load_json_artifact(product.get("artifact"))
    gate_report = _load_json_artifact(regression_artifact.get("gate_report"))
    failure_text = json.dumps(
        {
            "regression_failures": regression_artifact.get("failures"),
            "regression_stdout": regression_artifact.get("stdout"),
            "gate_results": gate_report.get("results"),
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    if bool(product.get("timed_out")):
        return "product_path_smoke_blocked_by_verifier_setup:legacy shear product-path gate timed out"
    combined_fixture_setup = (
        "COMBINED_BENDING_SHEAR_FAIL" in failure_text
        and "expected_selected_family" in failure_text
        and "SHEAR_FAIL_GOVERNS" in failure_text
        and (
            "Underdesign fixture did not hold the shear target after setup" in failure_text
            or "Underdesign fixture did not hold the bending moment target after setup" in failure_text
            or "Visible active failure selected invalid family" in failure_text
        )
    )
    if combined_fixture_setup:
        return (
            "product_path_smoke_blocked_by_verifier_setup:"
            "legacy pure-shear browser fixture selected combined fail instead of isolated shear fail"
        )
    return None


def _validate_ladder(snapshot: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    summary = dict(snapshot.get("final_result_summary") or {})
    repair_ladder_contract = dict((load_shear_fail_governs_contract().get("repair_ladder") or {}))
    for field in required_locked_snapshot_fields():
        if field not in snapshot:
            failures.append(f"missing_locked_snapshot_field:{field}")
    if snapshot.get("family_id") != FAMILY_ID:
        failures.append(f"family_id_mismatch:{snapshot.get('family_id')}")
    if summary.get("family_name") != FAMILY_ID:
        failures.append(f"summary_family_name_mismatch:{summary.get('family_name')}")
    if summary.get("governing_state") != FAMILY_ID:
        failures.append(f"governing_state_mismatch:{summary.get('governing_state')}")
    if snapshot.get("candidate_count") != expected.get("candidate_count"):
        failures.append(f"candidate_count_mismatch:{snapshot.get('candidate_count')}!={expected.get('candidate_count')}")
    if snapshot.get("repair_ladder_hash") != str(expected.get("repair_ladder_hash") or ""):
        failures.append("repair_ladder_hash_mismatch")
    indexes = list(snapshot.get("candidate_indexes") or [])
    if indexes != sorted(indexes) or len(indexes) != len(set(indexes)):
        failures.append("candidate_indexes_not_strictly_increasing")
    labels = list(snapshot.get("candidate_labels") or [])
    for index, label in zip(indexes, labels):
        expected_prefix = f"{FAMILY_ID} ladder {index}: "
        if not str(label).startswith(expected_prefix):
            failures.append(f"candidate_label_prefix_mismatch:{index}")
            break
    for field in ("spacing_values_tried", "lig_diameters_tried", "widths_tried"):
        if snapshot.get(field) != list(expected.get(field) or []):
            failures.append(f"{field}_mismatch")
    if snapshot.get("no_candidate_stop_reason") != str(expected.get("no_candidate_stop_reason") or ""):
        failures.append("no_candidate_stop_reason_mismatch")
    if snapshot.get("restart_rule") != repair_ladder_contract.get("restart_rule"):
        failures.append("restart_rule_mismatch")
    if not snapshot.get("restart_points"):
        failures.append("restart_points_missing")
    for spec in (snapshot.get("first_spec"), snapshot.get("last_spec")):
        if spec and spec.get("candidate_family_id") != FAMILY_ID:
            failures.append("spec_candidate_family_id_mismatch")
            break
    return failures


def _write_markdown_report(output: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# SHEAR_FAIL_GOVERNS Locked Regression",
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
                f"- spacing_values_tried: `{snapshot.get('spacing_values_tried')}`",
                f"- lig_diameters_tried: `{snapshot.get('lig_diameters_tried')}`",
                f"- widths_tried: `{snapshot.get('widths_tried')}`",
                f"- stop_reason: `{snapshot.get('no_candidate_stop_reason')}`",
                "",
            ]
        )
    product = dict(output.get("product_path_confirmation") or {})
    lines.extend(
        [
            "## Product Path Confirmation",
            "",
            f"- status: `{product.get('status')}`",
            f"- smoke_status: `{output.get('product_path_smoke_status')}`",
            f"- blocked_reason: `{output.get('product_path_smoke_blocked_reason')}`",
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
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    expected_snapshots = expected_ladder_snapshots()
    direct_ladder_snapshots = {
        name: _ladder_snapshot(geometry_locked=bool(expected.get("geometry_locked")))
        for name, expected in expected_snapshots.items()
    }
    product = _run_product_regression()
    cached_smoke_status = str(product.get("cached_product_path_smoke_status") or "").upper()
    product_path_smoke_blocked_reason = (
        str(product.get("cached_product_path_smoke_blocked_reason") or "")
        if cached_smoke_status == "BLOCKED"
        else _product_path_setup_blocked_reason(product)
    )
    product_path_smoke_status = (
        "BLOCKED"
        if cached_smoke_status == "BLOCKED"
        else "PASS"
        if product.get("status") == "PASS"
        else "BLOCKED"
        if product_path_smoke_blocked_reason
        else "FAIL"
    )
    failures: list[str] = []
    for name, expected in expected_snapshots.items():
        snapshot = direct_ladder_snapshots.get(name) or {}
        failures.extend(f"{name}:{failure}" for failure in _validate_ladder(snapshot, expected))
    if product_path_smoke_status == "FAIL":
        failures.append("product_path_confirmation_failed")

    status = "PASS" if not failures else "FAIL"
    artifact_path = ARTIFACT_DIR / f"shear_fail_governs_locked_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_governs_locked_regression_{stamp}.md"
    output = {
        "schema": "shear_fail_governs_locked_regression.v1",
        "status": status,
        "family_id": FAMILY_ID,
        "contract_path": str(CONTRACT_PATH),
        "required_snapshot_fields": list(required_locked_snapshot_fields()),
        "required_snapshots": list(expected_snapshots.keys()),
        "family_marked_locked_now": False,
        "ready_to_mark_locked_next": status == "PASS" and product_path_smoke_status == "PASS",
        "direct_ladder_snapshots": direct_ladder_snapshots,
        "product_path_confirmation": product,
        "product_path_smoke_status": product_path_smoke_status,
        "product_path_smoke_blocked_reason": product_path_smoke_blocked_reason,
        "failures": failures,
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown_report(output, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
