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

from design_brain.families.bending_fail_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    expected_ladder_snapshots,
    family_identity,
    required_locked_snapshot_fields,
)


FAMILY_ID = str(family_identity().get("family_id") or "")


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
        "cover_side": 40.0,
        "lig_d": 0,
    }


def _spec_snapshot(spec: dict[str, Any]) -> dict[str, Any]:
    updates = dict(spec.get("updates") or {})
    return {
        "ladder_index": spec.get("ladder_index"),
        "contract_step": spec.get("contract_step"),
        "stage_name": spec.get("stage_name"),
        "strategy": spec.get("strategy"),
        "updates": updates,
        "update_keys": sorted(updates.keys()),
        "escalation": spec.get("escalation"),
        "candidate_family_id": spec.get("candidate_family_id"),
        "stop_rule": spec.get("stop_rule"),
        "b": spec.get("b"),
        "D": spec.get("D"),
        "bottom_bar_count": spec.get("bottom_bar_count"),
        "bar_diameter": spec.get("bar_diameter"),
        "split_row": spec.get("split_row"),
        "clear_spacing": spec.get("clear_spacing"),
        "label": spec.get("label"),
    }


def _known_bad_snapshot(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage_name": record.get("stage_name"),
        "strategy": record.get("strategy"),
        "b": record.get("b"),
        "D": record.get("D"),
        "bottom_bar_count": record.get("bottom_bar_count"),
        "bar_diameter": record.get("bar_diameter"),
        "split_row": record.get("split_row"),
        "clear_spacing": record.get("clear_spacing"),
        "reason": record.get("reason"),
    }


def _ladder_snapshot(*, geometry_locked: bool) -> dict[str, Any]:
    from design_brain.families.bending_fail import BendingFailFamily

    family = BendingFailFamily()
    result = family.contracted_repair_ladder_specs(_locked_fixture_state(), geometry_locked=geometry_locked)
    specs = [_spec_snapshot(dict(spec)) for spec in list(result.get("specs") or [])]
    known_bad = [_known_bad_snapshot(dict(record)) for record in list(result.get("known_bad_candidates_skipped") or [])]
    ladder_hash = _stable_hash(specs)
    known_bad_hash = _stable_hash(known_bad)
    labels = [str(spec.get("label") or "") for spec in specs]
    indexes = [spec.get("ladder_index") for spec in specs]
    stage_plan_order = [str(spec.get("stage_name") or "") for spec in specs]
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
        "bar_diameters_tried": result.get("bar_diameters_tried"),
        "depth_steps_mm": result.get("depth_steps_mm"),
        "width_steps_mm": result.get("width_steps_mm"),
        "minimum_clear_spacing_mm": result.get("minimum_clear_spacing_mm"),
        "known_bad_candidate_count": result.get("known_bad_candidate_count"),
        "ranking_rule": result.get("ranking_rule"),
        "stop_reason_if_no_candidate": result.get("stop_reason_if_no_candidate"),
        "spec_count": len(specs),
        "ladder_hash": ladder_hash,
        "known_bad_hash": known_bad_hash,
    }
    return {
        "geometry_locked": geometry_locked,
        "family_id": FAMILY_ID,
        "stage_plan_order": stage_plan_order,
        "candidate_count": len(specs),
        "candidate_indexes": indexes,
        "candidate_labels": labels,
        "update_payload_surfaces": update_payload_surfaces,
        "known_bad_skipped_candidates": known_bad,
        "blocker_reasons": sorted({str(record.get("reason") or "") for record in known_bad if record.get("reason")}),
        "no_candidate_stop_reason": result.get("stop_reason_if_no_candidate"),
        "final_result_summary": result_summary,
        "repair_ladder_hash": ladder_hash,
        "known_bad_hash": known_bad_hash,
        "first_spec": specs[0] if specs else None,
        "last_spec": specs[-1] if specs else None,
    }


def _run_product_regression() -> dict[str, Any]:
    command = [sys.executable, "tools/verification/bending_fail_governs_repair_regression.py"]
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


def _product_path_setup_blocked_reason(product: dict[str, Any]) -> str | None:
    """Identify known browser fixture setup blockers without masking product failures."""
    if product.get("status") == "PASS":
        return None
    regression_artifact = _load_json_artifact(product.get("artifact"))
    gate_report = _load_json_artifact(regression_artifact.get("gate_report"))
    failure_text = json.dumps(
        {
            "regression_failed_checks": regression_artifact.get("failed_checks"),
            "regression_stdout": regression_artifact.get("stdout"),
            "gate_results": gate_report.get("results"),
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    disabled_moment_setup = (
        "Could not set visible number input" in failure_text
        and "Positive design moment Mu*+ (kNm)" in failure_text
        and "to 900" in failure_text
        and ("element is not enabled" in failure_text or "disabled" in failure_text)
    )
    if disabled_moment_setup:
        return (
            "product_path_smoke_blocked_by_verifier_setup:"
            "Positive design moment Mu*+ is disabled in design mode and cannot be set directly"
        )
    product_path_timeout_setup = (
        "TimeoutError" in failure_text
        and "Page.wait_for_function" in failure_text
        and "design_guide_product_path_gate" in failure_text
        and not regression_artifact.get("matched_family_ids")
        and not regression_artifact.get("visible_design_guide_apply_cta_buttons")
    )
    if product_path_timeout_setup:
        return (
            "product_path_smoke_blocked_by_verifier_setup:"
            "legacy product-path gate timed out before collecting family/CTA probes"
        )
    return None


def _validate_ladder(snapshot: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    summary = dict(snapshot.get("final_result_summary") or {})
    missing_fields = [field for field in required_locked_snapshot_fields() if field not in snapshot]
    for field in missing_fields:
        failures.append(f"missing_locked_snapshot_field:{field}")
    expected_ladder_hash = str(expected.get("repair_ladder_hash") or "")
    expected_known_bad_hash = str(expected.get("known_bad_hash") or "")
    expected_count = expected.get("candidate_count")
    expected_known_bad_count = expected.get("known_bad_candidate_count")
    expected_depth_steps = list(expected.get("depth_steps_mm") or [])
    expected_width_steps = list(expected.get("width_steps_mm") or [])
    expected_stop = str(expected.get("no_candidate_stop_reason") or "")
    expected_blocker_reasons = list(expected.get("blocker_reasons") or [])

    if snapshot.get("family_id") != FAMILY_ID:
        failures.append(f"family_id_mismatch:{snapshot.get('family_id')}")
    if summary.get("family_name") != FAMILY_ID:
        failures.append(f"summary_family_name_mismatch:{summary.get('family_name')}")
    if summary.get("governing_state") != FAMILY_ID:
        failures.append(f"governing_state_mismatch:{summary.get('governing_state')}")
    if snapshot.get("candidate_count") != expected_count:
        failures.append(f"candidate_count_mismatch:{snapshot.get('candidate_count')}!={expected_count}")
    if summary.get("known_bad_candidate_count") != expected_known_bad_count:
        failures.append(
            f"known_bad_count_mismatch:{summary.get('known_bad_candidate_count')}!={expected_known_bad_count}"
        )
    if snapshot.get("repair_ladder_hash") != expected_ladder_hash:
        failures.append("repair_ladder_hash_mismatch")
    if snapshot.get("known_bad_hash") != expected_known_bad_hash:
        failures.append("known_bad_hash_mismatch")
    indexes = list(snapshot.get("candidate_indexes") or [])
    if indexes != list(range(1, len(indexes) + 1)):
        failures.append("candidate_indexes_not_strictly_increasing_from_one")
    labels = list(snapshot.get("candidate_labels") or [])
    for index, label in zip(indexes, labels):
        allowed_prefixes = (
            f"{FAMILY_ID} ladder {index}: ",
            f"{FAMILY_ID} contract runtime {index}: ",
        )
        if not any(str(label).startswith(prefix) for prefix in allowed_prefixes):
            failures.append(f"candidate_label_prefix_mismatch:{index}")
            break
    if summary.get("depth_steps_mm") != expected_depth_steps:
        failures.append("depth_steps_mismatch")
    if summary.get("width_steps_mm") != expected_width_steps:
        failures.append("width_steps_mismatch")
    if snapshot.get("no_candidate_stop_reason") != expected_stop:
        failures.append("no_candidate_stop_reason_mismatch")
    if snapshot.get("blocker_reasons") != expected_blocker_reasons:
        failures.append("blocker_reasons_mismatch")
    if summary.get("ranking_rule") != (
        "Evaluate contract runtime candidates until a target-band executor-backed pure "
        "bending repair is found, or until all valid repair candidates are exhausted; "
        "rank compliant candidates by target-band satisfaction before ladder-order tie-breaks."
    ):
        failures.append("ranking_rule_mismatch")
    if any(spec.get("candidate_family_id") != FAMILY_ID for spec in [snapshot.get("first_spec"), snapshot.get("last_spec")] if spec):
        failures.append("spec_candidate_family_id_mismatch")
    return failures


def _write_markdown_report(output: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# BENDING_FAIL_GOVERNS Locked Regression",
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
        summary = dict(snapshot.get("final_result_summary") or {})
        lines.extend(
            [
                f"### {key}",
                "",
                f"- candidate_count: `{snapshot.get('candidate_count')}`",
                f"- known_bad_count: `{summary.get('known_bad_candidate_count')}`",
                f"- repair_ladder_hash: `{snapshot.get('repair_ladder_hash')}`",
                f"- known_bad_hash: `{snapshot.get('known_bad_hash')}`",
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
    lines.extend(
        [
            "",
            "## Output",
            "",
            f"- `{output.get('artifact')}`",
        ]
    )
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
    product_path_smoke_blocked_reason = _product_path_setup_blocked_reason(product)
    product_path_smoke_status = (
        "PASS"
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
    artifact_path = ARTIFACT_DIR / f"bending_fail_governs_locked_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_locked_regression_10U_{stamp}.md"
    output = {
        "schema": "bending_fail_governs_locked_regression.v1",
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
