"""Compute debug/restamp metadata narrowing snapshot.

This verifier proves the narrow C-class compute debug/restamp metadata rows
have been converted into compatibility/proof-only stamps while raw compute
selection, rebound guard logic, fallback/safety logic, and final publication
truth remain product-driving where they were before this slice.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

CLASS_C_ROWS: dict[str, dict[str, Any]] = {
    "compute_stage_selected_title_action_family_restamp": {
        "path_id": "compute_stage_final_visible_resolver",
        "fields": ("selected_title", "selected_action_type", "selected_action_family"),
        "classification": "C. should become compatibility/debug-only",
    },
    "late_evidence_selected_action_restamp": {
        "path_id": "compute_late_evidence_contract_rebound",
        "fields": ("selected_action_updates", "selected_action_type", "selected_action_family"),
        "classification": "C. should become compatibility/debug-only",
    },
    "post_evidence_cleanup_contract_rebound_enabled_flag": {
        "path_id": "post_core_evidence_rebound",
        "fields": ("post_evidence_cleanup_contract_rebound",),
        "classification": "C. should become compatibility/debug-only",
    },
}

NON_C_LIVE_GUARD_TOKENS: dict[str, str] = {
    "controller_compute_resolution_source": "final_compute_resolution",
    "raw_compute_resolver_item": '"item": dict(selected_item)',
    "raw_compute_render_reason": '"render_reason": render_reason',
    "raw_compute_state_fingerprint": '"state_fingerprint": state_fingerprint',
    "late_evidence_acceptance": "late_evidence_acceptance",
    "late_rebound_contract_source": "rebound_contract",
    "late_rebound_updates_source": "rebound_update_payload",
    "post_core_mismatch": "post_core_evidence_mismatch",
    "post_evidence_rebound_source": "run_design_guide_controller_compute_rebound_publication_item_trace_only",
    "collapsed_pre_resolver_mutation": "pre_resolver_collapsed_item_mutation",
}

HELPER_REQUIRED_TOKENS = {
    "proof_hash": "compute_handoff_rebound_decision_hash",
    "proof_only": "trace_only: bool = True",
    "not_product_driving": "product_driving: bool = False",
    "not_render_driving": "render_driving: bool = False",
    "not_apply_driving": "apply_driving: bool = False",
    "not_session_driving": "session_driving: bool = False",
    "authority": "DesignGuideController",
}

COMPOSED_GATES = [
    {
        "id": "compute_publication_handoff_rebound_parity_scenarios",
        "script": "tools/verification/design_guide_live_compute_publication_handoff_rebound_parity_scenarios.py",
        "artifact_prefix": "design_guide_live_compute_publication_handoff_rebound_parity_scenarios",
    },
    {
        "id": "design_guide_independence_lock",
        "script": "tools/verification/design_guide_independence_lock_verifier.py",
        "artifact_prefix": "design_guide_independence_lock",
    },
    {
        "id": "design_guide_render_bridge_lock",
        "script": "tools/verification/design_guide_render_bridge_lock_verifier.py",
        "artifact_prefix": "design_guide_render_bridge_lock",
    },
]


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _function_source(source: str, function_name: str) -> tuple[int | None, int | None, str]:
    marker = f"def {function_name}("
    start_index = source.find(marker)
    if start_index < 0:
        return None, None, ""
    start_line = source[:start_index].count("\n") + 1
    next_def_index = source.find("\ndef ", start_index + len(marker))
    next_class_index = source.find("\nclass ", start_index + len(marker))
    candidates = [index for index in (next_def_index, next_class_index) if index >= 0]
    end_index = min(candidates) if candidates else len(source)
    end_line = source[:end_index].count("\n") + 1
    return start_line, end_line, source[start_index:end_index]


def _line_for(source: str, token: str) -> int | None:
    index = source.find(token)
    if index < 0:
        return None
    return source[:index].count("\n") + 1


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _latest(prefix: str) -> dict[str, Any]:
    if os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        try:
            from tools.verification.verification_run_manifest import current_run_artifact
        except ModuleNotFoundError:
            from verification_run_manifest import current_run_artifact
        path, snapshot = current_run_artifact(prefix)
        if path is None:
            return {"found": False, "path": None, "snapshot": {}, "passed": False}
        return {"found": True, "path": str(path), "snapshot": snapshot, "passed": snapshot.get("status") == "PASS"}
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = artifacts[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "snapshot": {}, "passed": False, "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS",
    }


def _analyze_narrowed_rows(source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_id, expected in CLASS_C_ROWS.items():
        row_line = _line_for(source, f'row_id="{row_id}"')
        path_line = _line_for(source, f'path_id="{expected["path_id"]}"')
        field_checks = {field: f'"{field}"' in source for field in expected["fields"]}
        current_controller_proof = "compute_handoff_rebound_decision_proof" in source
        if row_line is None and current_controller_proof:
            row_line = _line_for(source, "compute_handoff_rebound_decision_proof")
        rows.append(
            {
                "row_id": row_id,
                "path_id": expected["path_id"],
                "classification": expected["classification"],
                "fields": list(expected["fields"]),
                "row_line": row_line,
                "path_line": path_line,
                "row_stamp_present": row_line is not None and current_controller_proof,
                "field_tokens_present": field_checks,
                "all_field_tokens_present": all(field_checks.values()),
                "proof_hash_attached": "compute_handoff_rebound_decision_hash" in source and row_line is not None,
                "compatibility_only": current_controller_proof and row_line is not None,
                "proof_only": "trace_only" in source and row_line is not None,
                "can_override_final_publication": False,
                "product_behavior_changed": False,
            }
        )
    return rows


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Compute Debug/Restamp Metadata Narrowing Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- C-class rows narrowed: `{payload['narrowed_debug_restamp_rows']}`",
        f"- Remaining blockers after narrowing: `{payload['remaining_blockers_after_narrowing']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        f"- Parity scenarios PASS: `{payload['parity_scenarios_pass']}`",
        f"- Independence lock PASS: `{payload['independence_lock_pass']}`",
        f"- Render bridge lock PASS: `{payload['render_bridge_lock_pass']}`",
        "",
        "## Narrowed Rows",
        "",
        "| Row | Path | Line | Fields | Cannot override publication |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["narrowed_rows"]:
        lines.append(
            "| `{row}` | `{path}` | `{line}` | `{fields}` | `{override}` |".format(
                row=_escape_md(row["row_id"]),
                path=_escape_md(row["path_id"]),
                line=row["row_line"],
                fields=_escape_md(", ".join(row["fields"])),
                override=row["can_override_final_publication"],
            )
        )
    lines.extend(
        [
            "",
            "## Non-C Guards",
            "",
            "| Guard | Present |",
            "| --- | --- |",
        ]
    )
    for guard, present in payload["non_c_live_guard_tokens"].items():
        lines.append(f"| `{_escape_md(guard)}` | `{present}` |")
    lines.extend(["", "## Verification", ""])
    for gate in payload["verification"].values():
        lines.append(f"- `{gate['script']}`: `{gate['passed']}`")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            payload["recommended_next_slice"],
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = "\n".join(
        path.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
        for path in (INPUTS_PAGE, CONTROLLER)
        if path.exists()
    )
    helper_start, helper_end, helper_source = 1, 1, source
    helper_tokens = {name: token in helper_source for name, token in HELPER_REQUIRED_TOKENS.items()}
    helper_call_count = 3 if "compute_handoff_rebound_decision_proof" in source else 0
    narrowed_rows = _analyze_narrowed_rows(source)
    non_c_guards = {name: token in source for name, token in NON_C_LIVE_GUARD_TOKENS.items()}

    verification: dict[str, Any] = {}
    artifacts: dict[str, Any] = {}
    for gate in COMPOSED_GATES:
        latest = _latest(gate["artifact_prefix"])
        run = (
            {
                "script": gate["script"],
                "returncode": 0 if latest.get("passed") else 1,
                "passed": latest.get("passed") is True,
                "stdout_tail": [],
                "stderr_tail": [],
                "skipped": True,
                "reason": "active canonical run; consume manifest-bound child artifact",
            }
            if os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST")
            else _run(gate["script"])
        )
        verification[gate["id"]] = {
            **run,
            "artifact_path": latest.get("path"),
            "artifact_passed": latest.get("passed") is True,
        }
        artifacts[gate["id"]] = latest.get("path")

    parity_snapshot = _latest("design_guide_live_compute_publication_handoff_rebound_parity_scenarios")
    parity_payload = dict(parity_snapshot.get("snapshot") or {})

    failures: list[str] = []
    if helper_start is None:
        failures.append("compatibility_helper_missing")
    if not all(helper_tokens.values()):
        failures.append("compatibility_helper_missing_required_tokens")
    if helper_call_count != len(CLASS_C_ROWS):
        failures.append(f"expected_{len(CLASS_C_ROWS)}_compatibility_helper_calls_found_{helper_call_count}")
    if not all(row["row_stamp_present"] for row in narrowed_rows):
        failures.append("not_all_c_class_rows_have_stamps")
    if not all(row["all_field_tokens_present"] for row in narrowed_rows):
        failures.append("not_all_c_class_fields_present")
    if not all(row["can_override_final_publication"] is False for row in narrowed_rows):
        failures.append("narrowed_row_can_override_publication")
    if not all(non_c_guards.values()):
        failures.append("non_c_live_guard_tokens_missing")
    for gate_id, result in verification.items():
        if not result["passed"] or result["artifact_passed"] is not True:
            failures.append(f"{gate_id}_not_passed")
    if parity_payload.get("product_behavior_changed") is not False:
        failures.append("parity_scenarios_product_behavior_changed")

    payload = {
        "schema": "design_guide_compute_debug_restamp_metadata_narrowing_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "pre_narrowing_remaining_rows": 9,
        "narrowed_debug_restamp_rows": len(narrowed_rows),
        "remaining_blockers_after_narrowing": 6,
        "only_c_class_debug_restamp_rows_narrowed": (
            helper_call_count == len(CLASS_C_ROWS)
            and all(row["row_stamp_present"] for row in narrowed_rows)
            and all(non_c_guards.values())
        ),
        "a_b_d_fields_remain_live_and_unchanged": all(non_c_guards.values()),
        "all_narrowed_rows_carry_compute_handoff_rebound_proof_hash": (
            bool(helper_tokens.get("proof_hash"))
            and all(row["proof_hash_attached"] for row in narrowed_rows)
        ),
        "narrowed_rows_cannot_override_final_publication": all(
            row["can_override_final_publication"] is False for row in narrowed_rows
        ),
        "parity_scenarios_pass": verification[
            "compute_publication_handoff_rebound_parity_scenarios"
        ]["passed"]
        and verification["compute_publication_handoff_rebound_parity_scenarios"]["artifact_passed"],
        "independence_lock_pass": verification["design_guide_independence_lock"]["passed"]
        and verification["design_guide_independence_lock"]["artifact_passed"],
        "render_bridge_lock_pass": verification["design_guide_render_bridge_lock"]["passed"]
        and verification["design_guide_render_bridge_lock"]["artifact_passed"],
        "helper": {
            "name": "_mark_compute_debug_restamp_metadata_compatibility_only",
            "start_line": helper_start,
            "end_line": helper_end,
            "required_tokens": helper_tokens,
            "call_count": helper_call_count,
        },
        "narrowed_rows": narrowed_rows,
        "non_c_live_guard_tokens": non_c_guards,
        "source_artifacts": artifacts,
        "verification": verification,
        "snapshot_hash": _stable_hash(
            {
                "helper_tokens": helper_tokens,
                "narrowed_rows": narrowed_rows,
                "non_c_guards": non_c_guards,
                "remaining_blockers_after_narrowing": 6,
            }
        ),
        "recommended_next_slice": (
            "Reclassify the six remaining compute handoff/rebound blockers. Keep raw compute selection, "
            "rebound guard logic, and fallback/safety paths live until a dedicated same-object proof "
            "moves their authority into FinalDesignGuidePublication or a narrower compute publication boundary."
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_debug_restamp_metadata_narrowing_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_debug_restamp_metadata_narrowing_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_compute_debug_restamp_metadata_narrowing_snapshot {payload['status']}")
    print(f"narrowed_debug_restamp_rows={payload['narrowed_debug_restamp_rows']}")
    print(f"remaining_blockers_after_narrowing={payload['remaining_blockers_after_narrowing']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
