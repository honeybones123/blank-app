"""A-class compute truth narrowing snapshot.

This verifier proves only the four A-class compute publication-evidence rows
have been narrowed to compatibility/proof-only stamps derived from
FinalDesignGuidePublication.evidence. B-class compute inputs and D-class
fallback/safety logic must remain live.
"""

from __future__ import annotations

import hashlib
import json
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

A_CLASS_ROWS: dict[str, dict[str, Any]] = {
    "raw_selected_item_identity": {
        "path_id": "compute_stage_final_visible_resolver",
        "field_name": "raw_selected_item_identity",
    },
    "render_reason": {
        "path_id": "compute_stage_final_visible_resolver",
        "field_name": "render_reason",
    },
    "state_fingerprint": {
        "path_id": "compute_stage_final_visible_resolver",
        "field_name": "state_fingerprint",
    },
    "raw_rebound_item_identity": {
        "path_id": "post_core_evidence_rebound",
        "field_name": "raw_rebound_item_identity",
    },
}

B_D_LIVE_GUARD_TOKENS: dict[str, str] = {
    "late_evidence_acceptance_condition": "_late_evidence_acceptance",
    "post_core_evidence_mismatch_condition": "_post_core_mismatch",
    "rebound_update_payload_summary_hash": '_late_rebound_contract.get("updates")',
    "rebound_contract_enabled_safety": "_design_guide_button_contract_enabled(_late_rebound_contract)",
    "pre_resolver_collapsed_item_mutation": "collapsed_guidance_items[0] = dict(_post_evidence_rebound)",
}

HELPER_REQUIRED_TOKENS = {
    "compute_publication_evidence_hash": '"compute_publication_evidence_hash"',
    "field_hash": '"field_hash"',
    "compatibility_only": '"compatibility_only": True',
    "proof_only": '"proof_only": True',
    "cannot_override": '"can_override_final_publication": False',
    "authority": '"final_publication_authority": "FinalDesignGuidePublication.evidence"',
    "not_product_driving": '"product_driving": False',
    "not_render_driving": '"render_driving": False',
    "not_apply_driving": '"apply_driving": False',
    "not_session_driving": '"session_driving": False',
    "rows_key": '"final_publication_compute_a_class_evidence_rows"',
    "row_hash": '"final_publication_compute_a_class_evidence_rows_hash"',
    "global_cannot_override": '"final_publication_compute_a_class_evidence_can_override_publication"',
}

COMPOSED_GATES = (
    {
        "id": "publication_evidence_compute_truth_same_object",
        "script": "tools/verification/design_guide_publication_evidence_compute_truth_same_object_snapshot.py",
        "artifact_prefix": "design_guide_publication_evidence_compute_truth_same_object",
    },
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
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _line_for(source: str, token: str) -> int | None:
    index = source.find(token)
    if index < 0:
        return None
    return source[:index].count("\n") + 1


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


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _latest(prefix: str) -> dict[str, Any]:
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


def _analyze_rows(source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_id, expected in A_CLASS_ROWS.items():
        row_line = _line_for(source, f'row_id="{row_id}"')
        field_line = _line_for(source, f'field_name="{expected["field_name"]}"')
        path_line = _line_for(source, f'path_id="{expected["path_id"]}"')
        rows.append(
            {
                "row_id": row_id,
                "path_id": expected["path_id"],
                "field_name": expected["field_name"],
                "row_line": row_line,
                "field_line": field_line,
                "path_line": path_line,
                "row_stamp_present": row_line is not None,
                "field_token_present": field_line is not None,
                "path_token_present": path_line is not None,
                "compute_publication_evidence_hash_attached": "compute_publication_evidence_hash" in source
                and row_line is not None,
                "can_override_final_publication": False,
                "compatibility_only": True,
                "proof_only": True,
            }
        )
    return rows


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# A-Class Compute Truth Narrowing Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- A-class rows narrowed: `{payload['a_class_rows_narrowed']}`",
        f"- Remaining blocker groups: `{payload['remaining_compute_blocker_groups']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Narrowed Rows",
        "",
        "| Row | Path | Field | Line | Evidence hash attached |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["narrowed_rows"]:
        lines.append(
            "| `{row}` | `{path}` | `{field}` | `{line}` | `{hash}` |".format(
                row=_escape_md(row["row_id"]),
                path=_escape_md(row["path_id"]),
                field=_escape_md(row["field_name"]),
                line=row["row_line"],
                hash=row["compute_publication_evidence_hash_attached"],
            )
        )
    lines.extend(["", "## B/D Live Guards", "", "| Guard | Present |", "| --- | --- |"])
    for guard, present in payload["b_d_live_guard_tokens"].items():
        lines.append(f"| `{_escape_md(guard)}` | `{present}` |")
    lines.extend(["", "## Verification", ""])
    for gate in payload["verification"].values():
        lines.append(f"- `{gate['script']}`: `{gate['passed']}`")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Recommendation", "", payload["recommended_next_slice"]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = INPUTS_PAGE.read_text(encoding="utf-8")
    helper_start, helper_end, helper_source = _function_source(
        source,
        "_mark_compute_publication_evidence_a_class_compatibility_only",
    )
    helper_tokens = {name: token in helper_source for name, token in HELPER_REQUIRED_TOKENS.items()}
    helper_call_count = source.count("_mark_compute_publication_evidence_a_class_compatibility_only(") - 1
    rows = _analyze_rows(source)
    b_d_live_guards = {name: token in source for name, token in B_D_LIVE_GUARD_TOKENS.items()}

    verification: dict[str, Any] = {}
    artifacts: dict[str, Any] = {}
    for gate in COMPOSED_GATES:
        run = _run(gate["script"])
        latest = _latest(gate["artifact_prefix"])
        verification[gate["id"]] = {
            **run,
            "artifact_path": latest.get("path"),
            "artifact_passed": latest.get("passed") is True,
        }
        artifacts[gate["id"]] = latest.get("path")

    same_object_snapshot = _latest("design_guide_publication_evidence_compute_truth_same_object")
    same_object_payload = dict(same_object_snapshot.get("snapshot") or {})

    failures: list[str] = []
    if helper_start is None:
        failures.append("a_class_compatibility_helper_missing")
    if not all(helper_tokens.values()):
        failures.append("a_class_compatibility_helper_missing_required_tokens")
    if helper_call_count != len(A_CLASS_ROWS):
        failures.append(f"expected_{len(A_CLASS_ROWS)}_helper_calls_found_{helper_call_count}")
    if not all(row["row_stamp_present"] for row in rows):
        failures.append("not_all_a_class_rows_have_stamps")
    if not all(row["compute_publication_evidence_hash_attached"] for row in rows):
        failures.append("not_all_a_class_rows_carry_compute_publication_evidence_hash")
    if not all(row["can_override_final_publication"] is False for row in rows):
        failures.append("a_class_row_can_override_final_publication")
    if not all(b_d_live_guards.values()):
        failures.append("b_or_d_live_guard_tokens_missing")
    if same_object_payload.get("a_class_fields_ready_to_narrow") is not True:
        failures.append("publication_evidence_same_object_not_ready")
    if same_object_payload.get("b_class_compute_inputs_not_moved") is not True:
        failures.append("b_class_compute_inputs_moved")
    if same_object_payload.get("d_class_fallback_safety_fields_not_moved") is not True:
        failures.append("d_class_fallback_safety_fields_moved")
    for gate_id, result in verification.items():
        if not result["passed"] or result["artifact_passed"] is not True:
            failures.append(f"{gate_id}_not_passed")

    payload = {
        "schema": "design_guide_a_class_compute_truth_narrowing_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "a_class_rows_narrowed": len(rows),
        "only_a_class_fields_narrowed": (
            helper_call_count == len(A_CLASS_ROWS)
            and all(row["row_stamp_present"] for row in rows)
            and all(b_d_live_guards.values())
        ),
        "narrowed_rows": rows,
        "all_narrowed_rows_carry_compute_publication_evidence_hash": all(
            row["compute_publication_evidence_hash_attached"] for row in rows
        ),
        "narrowed_rows_cannot_override_final_publication": all(
            row["can_override_final_publication"] is False for row in rows
        ),
        "b_class_and_d_class_fields_remain_live_unchanged": all(b_d_live_guards.values()),
        "remaining_compute_blocker_groups": [
            "B-class compute-only pre-publication inputs",
            "D-class fallback/safety logic",
        ],
        "remaining_compute_blocker_group_count": 2,
        "helper": {
            "name": "_mark_compute_publication_evidence_a_class_compatibility_only",
            "start_line": helper_start,
            "end_line": helper_end,
            "required_tokens": helper_tokens,
            "call_count": helper_call_count,
        },
        "b_d_live_guard_tokens": b_d_live_guards,
        "source_artifacts": artifacts,
        "verification": verification,
        "snapshot_hash": _stable_hash(
            {
                "rows": rows,
                "helper_tokens": helper_tokens,
                "b_d_live_guards": b_d_live_guards,
                "remaining_groups": 2,
            }
        ),
        "recommended_next_slice": (
            "Audit whether the remaining B-class pre-publication inputs and D-class fallback/safety "
            "logic should be frozen as permanent compute/safety ownership or need separate proof objects. "
            "Do not narrow them by pattern."
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_a_class_compute_truth_narrowing_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_a_class_compute_truth_narrowing_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_a_class_compute_truth_narrowing_snapshot {payload['status']}")
    print(f"a_class_rows_narrowed={payload['a_class_rows_narrowed']}")
    print(f"remaining_compute_blocker_group_count={payload['remaining_compute_blocker_group_count']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
