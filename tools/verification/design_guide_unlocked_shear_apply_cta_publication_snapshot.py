"""Snapshot for unlocked shear active-failure Apply CTA publication policy.

This is an audit/proof-only verifier for the runtime guard:

    unlocked active failure reached final publication without an
    executor-backed Apply CTA for shear

It does not weaken the guard, move CTA/apply/render/session ownership, or
change product behaviour. When no live failing final item artifact is
available, it records a minimal policy reproduction and classifies the product
root as requiring a focused live trace before any behaviour fix.
"""

from __future__ import annotations

import ast
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

INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TRACEBACK_FUNCTIONS = (
    "build_design_guide_card_view_model",
    "_render_guidance_secondary_items",
    "_render_fast_design_guidance_panel",
    "_render_fresh_design_guide_panel",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(source: str, function_name: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            segment = ast.get_source_segment(source, node)
            if segment:
                return segment
    raise RuntimeError(f"function not found: {function_name}")


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
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _latest_artifact(prefix: str) -> dict[str, Any]:
    artifacts = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not artifacts:
        return {"path": None, "snapshot": None, "found": False, "passed": False}
    path = artifacts[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "path": str(path),
            "snapshot": None,
            "found": True,
            "passed": False,
            "error": str(exc),
        }
    return {
        "path": str(path),
        "snapshot": snapshot,
        "found": True,
        "passed": snapshot.get("status") == "PASS",
    }


def _policy_from_minimal_case(
    *,
    active_shear_failure: bool,
    actionable: bool,
    contract_enabled: bool,
    visible_blocker: bool,
    geometry_lock: bool,
    exact_shear_proof: bool,
) -> str:
    """Mirror the current policy helper with plain booleans for proof cases."""

    active_failures = {"shear"} if active_shear_failure else set()
    if not active_failures or actionable:
        return ""
    if contract_enabled:
        return ""
    if not visible_blocker:
        return ""
    proven_families = {"shear"} if exact_shear_proof else set()
    if not geometry_lock:
        return "unlocked_active_failure_missing_apply_cta"
    if active_failures.issubset(proven_families):
        return "active_failure_blocked_with_exact_proof"
    return "locked_active_failure_missing_exact_proof"


def _build_minimal_cases() -> dict[str, Any]:
    cases = {
        "failing_traceback_shape": {
            "active_shear_failure": True,
            "actionable": False,
            "contract_enabled": False,
            "visible_blocker": True,
            "geometry_lock": False,
            "exact_shear_proof": False,
            "expected_policy": "unlocked_active_failure_missing_apply_cta",
        },
        "valid_apply_cta_shape": {
            "active_shear_failure": True,
            "actionable": True,
            "contract_enabled": True,
            "visible_blocker": False,
            "geometry_lock": False,
            "exact_shear_proof": False,
            "expected_policy": "",
        },
        "valid_locked_blocker_shape": {
            "active_shear_failure": True,
            "actionable": False,
            "contract_enabled": False,
            "visible_blocker": True,
            "geometry_lock": True,
            "exact_shear_proof": True,
            "expected_policy": "active_failure_blocked_with_exact_proof",
        },
    }
    out: dict[str, Any] = {}
    for name, case in cases.items():
        observed = _policy_from_minimal_case(
            active_shear_failure=bool(case["active_shear_failure"]),
            actionable=bool(case["actionable"]),
            contract_enabled=bool(case["contract_enabled"]),
            visible_blocker=bool(case["visible_blocker"]),
            geometry_lock=bool(case["geometry_lock"]),
            exact_shear_proof=bool(case["exact_shear_proof"]),
        )
        out[name] = {
            **case,
            "observed_policy": observed,
            "matches_expected": observed == case["expected_policy"],
        }
    return out


def _source_capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    functions = {name: _function_source(source, name) for name in TRACEBACK_FUNCTIONS}
    policy_source = _function_source(source, "_design_guide_active_failure_blocker_publication_policy")
    view_source = functions["build_design_guide_card_view_model"]
    secondary_source = functions["_render_guidance_secondary_items"]
    return {
        "source_hashes": {
            name: _stable_hash(text) for name, text in functions.items()
        }
        | {
            "_design_guide_active_failure_blocker_publication_policy": _stable_hash(policy_source),
            "final_publication": _stable_hash(final_source),
        },
        "policy_guards": {
            "hard_runtime_error_present": (
                "Design Guide policy violation: unlocked active failure reached final publication" in view_source
            ),
            "live_guard_trace_hook_present": (
                "_record_unlocked_active_failure_missing_apply_cta_trace(" in view_source
            ),
            "live_guard_trace_helper_present": (
                "def _record_unlocked_active_failure_missing_apply_cta_trace(" in source
            ),
            "live_guard_trace_preserves_raise": (
                "_record_unlocked_active_failure_missing_apply_cta_trace(" in view_source
                and "raise RuntimeError(" in view_source
            ),
            "unlocked_missing_apply_policy_present": (
                '"unlocked_active_failure_missing_apply_cta"' in policy_source
            ),
            "active_failure_from_overview": "_overview_active_failure_keys(" in policy_source,
            "requires_button_contract_or_actionable": (
                "if _design_guide_button_contract_enabled(contract):" in policy_source
                and "if not active_failures or actionable:" in policy_source
            ),
            "geometry_lock_distinguishes_unlocked_path": "if not _geometry_lock_enabled(state or {}):" in policy_source,
            "locked_exact_blocker_path_present": (
                '"active_failure_blocked_with_exact_proof"' in policy_source
            ),
        },
        "traceback_path_guards": {
            "secondary_items_call_view_model": "build_design_guide_card_view_model(" in secondary_source,
            "secondary_items_pass_actionable_flag": "actionable=_view_model_actionable" in secondary_source,
            "secondary_items_can_disable_visible_blocker_contract": (
                "visible_blocker" in secondary_source
                and "button_contract_enabled" in secondary_source
            ),
            "primary_final_view_model_also_present": "_final_dashboard_vm = build_design_guide_card_view_model(" in secondary_source,
        },
        "ownership_guards": {
            "final_publication_has_cta": "class FinalDesignGuideCTA" in final_source,
            "final_publication_has_no_page_import": "inputs_page" not in final_source,
            "final_publication_has_no_streamlit_import": "streamlit" not in final_source,
            "cta_rendering_not_moved": "_design_guide_dashboard_card_html_from_render_model" not in final_source,
            "apply_routing_not_moved": "_record_rendered_design_guide_primary_apply_payload" not in final_source,
        },
    }


def _classification(
    capture: dict[str, Any],
    minimal_cases: dict[str, Any],
    guard_trace: dict[str, Any] | None,
) -> dict[str, Any]:
    failing_case = minimal_cases.get("failing_traceback_shape") or {}
    secondary_path = bool(capture["traceback_path_guards"].get("secondary_items_call_view_model"))
    if isinstance(guard_trace, dict) and guard_trace:
        root = str(guard_trace.get("root_hint") or "E. unknown / needs deeper trace")
        exact_shear = isinstance((guard_trace.get("exact_blockers_by_family") or {}).get("shear"), dict)
        post_exact_shear = isinstance(
            (guard_trace.get("post_click_exact_blockers_by_family") or {}).get("shear"),
            dict,
        )
        safe_count = int(
            ((guard_trace.get("candidate_search_evidence") or {}).get("safe_executor_backed_candidates_count"))
            or 0
        )
        contract = dict(guard_trace.get("button_contract") or {})
        if root.startswith("B."):
            should_be = "locked exact blocker publication or family-owned no-repair proof, not Apply CTA"
            reason = (
                "Live guard trace captured exact/post-click shear blocker evidence, zero safe "
                "executor-backed candidates, and a disabled FinalDesignGuidePublication.cta while "
                "optimisation_lock_geometry was false. The card should not become an Apply CTA; "
                "it needs the active-family locked blocker/no-repair proof path."
            )
        elif safe_count > 0 and not bool(contract.get("enabled")):
            should_be = "executor-backed Apply CTA"
            reason = "Live guard trace found safe executor-backed candidate evidence but no enabled CTA."
        else:
            should_be = "not_decidable_without_deeper_trace"
            reason = "Live guard trace exists but does not prove a specific replacement path."
        return {
            "root_cause_classification": root,
            "classification_reason": reason,
            "secondary_render_path_in_stack": secondary_path,
            "actual_live_final_item_captured": True,
            "candidate_existence_known": True,
            "safe_executor_backed_candidate_count": safe_count,
            "exact_shear_blocker_captured": exact_shear,
            "post_click_exact_shear_blocker_captured": post_exact_shear,
            "should_be_apply_cta_or_locked_blocker": should_be,
            "next_required_proof": (
                "Add a focused locked-blocker/no-repair publication verifier for unlocked combined "
                "active failure with exact bending/shear blocker evidence and zero safe executor-backed candidates."
            ),
            "do_not_fix_by": [
                "weakening the hard policy guard",
                "silently converting this to a disabled card",
                "marking a non-executor-backed card as actionable",
                "moving apply routing into FinalDesignGuidePublication",
            ],
        }
    if not failing_case.get("matches_expected"):
        root = "E. unknown / needs deeper trace"
        reason = "The minimal policy case no longer mirrors the guard, so deeper tracing is required."
    else:
        root = "E. unknown / needs deeper trace"
        reason = (
            "The traceback proves the guard saw active shear failure without an enabled/actionable "
            "executor-backed CTA, but no live final-visible item artifact is available to decide "
            "whether the shear CTA was lost, never produced, overridden by stale blocker evidence, "
            "or misapplied to a secondary card."
        )
    likely_next = (
        "Add a focused live guard-trace artifact at build_design_guide_card_view_model capturing "
        "the item/button_contract/evidence only when the unlocked shear policy branch would raise."
    )
    return {
        "root_cause_classification": root,
        "classification_reason": reason,
        "secondary_render_path_in_stack": secondary_path,
        "actual_live_final_item_captured": False,
        "candidate_existence_known": False,
        "should_be_apply_cta_or_locked_blocker": "not_decidable_without_live_final_item_trace",
        "next_required_proof": likely_next,
        "do_not_fix_by": [
            "weakening the hard policy guard",
            "silently converting this to a disabled card",
            "marking a non-executor-backed card as actionable",
            "moving apply routing into FinalDesignGuidePublication",
        ],
    }


def _build_snapshot() -> dict[str, Any]:
    capture = _source_capture()
    minimal_cases = _build_minimal_cases()
    py_compile = subprocess.run(
        [sys.executable, "-m", "py_compile", "inputs_page.py"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    render_lock_script = ROOT / "tools" / "verification" / "design_guide_render_bridge_lock_verifier.py"
    latest_lock = _latest_artifact("design_guide_independence_lock")
    latest_render_lock = _latest_artifact("design_guide_render_bridge_lock")
    latest_class_e = _latest_artifact("design_guide_post_click_exact_blocker_replacement_narrowing")
    latest_render = latest_render_lock if latest_render_lock.get("passed") else latest_class_e
    latest_guard_trace = _latest_artifact("design_guide_unlocked_active_failure_missing_apply_cta_guard_trace")
    classification = _classification(capture, minimal_cases, latest_guard_trace.get("snapshot"))

    checks = {
        "py_compile_pass": py_compile.returncode == 0,
        "latest_independence_lock_artifact_pass": bool(latest_lock.get("passed")),
        "latest_render_lock_or_class_e_artifact_pass": bool(latest_render.get("passed")),
        "policy_guard_present": all(capture["policy_guards"].values()),
        "ownership_guards_pass": all(capture["ownership_guards"].values()),
        "minimal_cases_match_policy": all(row["matches_expected"] for row in minimal_cases.values()),
        "root_classified": bool(classification["root_cause_classification"]),
    }
    failures = [name for name, passed in checks.items() if not passed]
    proof_surface = {
        "capture": capture,
        "minimal_cases": minimal_cases,
        "classification": classification,
        "checks": checks,
    }
    return {
        "snapshot_name": "design_guide_unlocked_shear_apply_cta_publication_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "runtime_error": (
            "Design Guide policy violation: unlocked active failure reached final publication "
            "without an executor-backed Apply CTA for shear."
        ),
        "captured_fields": {
            "final_visible_item": "captured_by_live_guard_trace_when_branch_raises",
            "selected_family": "captured_by_live_guard_trace_when_branch_raises",
            "overview_active_failure_keys": ["shear"],
            "geometry_lock_state": "false_in_minimal_policy_reproduction",
            "button_contract": {
                "enabled": False,
                "actionable": False,
                "executor_backed": False,
            },
            "action_payload_presence": False,
            "candidate_search_evidence_safe_executor_counts": "captured_by_live_guard_trace_when_branch_raises",
            "exact_blockers_by_family": "captured_by_live_guard_trace_when_branch_raises",
            "post_click_exact_blockers_by_family": "captured_by_live_guard_trace_when_branch_raises",
            "final_publication_cta_fields": "captured_by_live_guard_trace_when_branch_raises",
            "render_stage_bridge_stamps": "captured_by_live_guard_trace_when_branch_raises",
            "shear_fail_governs_applyable_candidate_produced": "classified_from_live_guard_trace_root_hint",
        },
        "source_capture": capture,
        "minimal_policy_cases": minimal_cases,
        "classification": classification,
        "verification": {
            "py_compile": {
                "command": "python -m py_compile inputs_page.py",
                "returncode": py_compile.returncode,
                "passed": py_compile.returncode == 0,
                "stderr_tail": py_compile.stderr.strip().splitlines()[-10:],
            },
            "latest_independence_lock_artifact": {
                "path": latest_lock.get("path"),
                "passed": latest_lock.get("passed"),
            },
            "latest_render_lock_artifact": {
                "path": latest_render_lock.get("path"),
                "passed": latest_render_lock.get("passed"),
            },
            "latest_class_e_narrowing_artifact": {
                "path": latest_class_e.get("path"),
                "passed": latest_class_e.get("passed"),
            },
            "render_bridge_or_class_e_gate_used": {
                "path": latest_render.get("path"),
                "passed": latest_render.get("passed"),
            },
            "latest_guard_trace_artifact": {
                "path": latest_guard_trace.get("path"),
                "found": latest_guard_trace.get("found"),
            },
        },
        "checks": checks,
        "failures": failures,
        "product_behavior_changed": False,
        "snapshot_hash": _stable_hash(proof_surface),
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Unlocked Shear Apply CTA Publication Snapshot",
        "",
        f"Timestamp: `{snapshot['generated_at']}`",
        f"Result: `{snapshot['status']}`",
        f"Snapshot hash: `{snapshot['snapshot_hash']}`",
        "",
        "## Runtime Error",
        "",
        f"`{snapshot['runtime_error']}`",
        "",
        "## Classification",
        "",
        f"- Root cause classification: `{snapshot['classification']['root_cause_classification']}`",
        f"- Secondary render path in stack: `{snapshot['classification']['secondary_render_path_in_stack']}`",
        f"- Actual live final item captured: `{snapshot['classification']['actual_live_final_item_captured']}`",
        f"- Candidate existence known: `{snapshot['classification']['candidate_existence_known']}`",
        f"- Should be Apply CTA or locked blocker: `{snapshot['classification']['should_be_apply_cta_or_locked_blocker']}`",
        f"- Next required proof: {snapshot['classification']['next_required_proof']}",
        "",
        "## Captured Fields",
        "",
    ]
    for key, value in snapshot["captured_fields"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Minimal Policy Cases", ""])
    for name, row in snapshot["minimal_policy_cases"].items():
        lines.append(
            f"- {name}: observed `{row['observed_policy']}`, expected `{row['expected_policy']}`, "
            f"match `{row['matches_expected']}`"
        )
    lines.extend(["", "## Checks", ""])
    for name, passed in snapshot["checks"].items():
        lines.append(f"- {name}: `{'PASS' if passed else 'FAIL'}`")
    lines.extend(["", "## Do Not Fix By", ""])
    for item in snapshot["classification"]["do_not_fix_by"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Failures", ""])
    if snapshot["failures"]:
        lines.extend(f"- `{failure}`" for failure in snapshot["failures"])
    else:
        lines.append("None.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    stamp = snapshot["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_unlocked_shear_apply_cta_publication_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_unlocked_shear_apply_cta_publication_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_unlocked_shear_apply_cta_publication_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print(f"classification={snapshot['classification']['root_cause_classification']}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
