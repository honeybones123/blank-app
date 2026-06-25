"""Snapshot for active-failure exact-blocker publication policy.

This verifier proves a non-actionable active bending/shear failure may only
reach final publication without an Apply CTA when exact blocker evidence is
backed by locked runtime proof for unlocked geometry, or when geometry is locked
and exact blocker evidence is present. Missing proof must not become a terminal
blocked card.
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
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(source: str, function_name: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            segment = ast.get_source_segment(source, node)
            if segment:
                return segment
    raise RuntimeError(f"function not found: {function_name}")


def _run_compile() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", "inputs_page.py"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": "python -m py_compile inputs_page.py",
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout": proc.stdout.strip().splitlines()[-5:],
        "stderr": proc.stderr.strip().splitlines()[-5:],
    }


def _build_snapshot() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    policy_source = _function_source(
        source,
        "_design_guide_active_failure_blocker_publication_policy",
    )
    view_model_source = _function_source(source, "build_design_guide_card_view_model")
    dashboard_title_source = _function_source(source, "_design_guide_dashboard_title")

    exact_proof_return = 'return "active_failure_blocked_with_exact_proof"'
    geometry_lock_check = "if not _geometry_lock_enabled(state or {}):"
    missing_exact_return = 'return "locked_active_failure_missing_exact_proof"'
    no_cta_return = 'return "unlocked_active_failure_missing_apply_cta"'
    missing_runtime_return = 'return "unlocked_active_failure_missing_runtime_proof"'
    no_cta_raise = (
        'if _active_failure_blocker_policy == "unlocked_active_failure_missing_apply_cta":'
    )

    exact_proof_index = policy_source.find(exact_proof_return)
    geometry_lock_index = policy_source.find(geometry_lock_check)
    missing_exact_index = policy_source.find(missing_exact_return)
    no_cta_index = policy_source.find(no_cta_return)
    missing_runtime_index = policy_source.find(missing_runtime_return)

    checks = {
        "exact_proof_policy_exists": exact_proof_index >= 0,
        "exact_proof_precedes_geometry_lock": (
            exact_proof_index >= 0
            and geometry_lock_index >= 0
            and exact_proof_index < geometry_lock_index
        ),
        "missing_exact_proof_still_guarded": missing_exact_index >= 0,
        "unlocked_exact_proof_requires_runtime_proof": (
            "_active_failure_blocker_has_locked_runtime_proof(" in policy_source
            and "runtime_blocker_proven" in policy_source
            and missing_runtime_index >= 0
        ),
        "unlocked_missing_runtime_proof_goes_to_incomplete_card": (
            '"unlocked_active_failure_missing_runtime_proof"' in view_model_source
        ),
        "unlocked_missing_runtime_proof_title_stays_incomplete": (
            '"unlocked_active_failure_missing_runtime_proof"' in dashboard_title_source
            and "Design Guide blocker proof incomplete" in dashboard_title_source
        ),
        "unlocked_missing_cta_still_hard_fails": (
            no_cta_index >= 0 and no_cta_raise in view_model_source
        ),
        "exact_rows_use_visible_failure_proof": (
            "_exact_blocker_row_has_visible_failure_proof(" in policy_source
        ),
        "all_active_families_must_be_proven": (
            "active_failures.issubset(proven_families)" in policy_source
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    compile_result = _run_compile()
    if not compile_result["passed"]:
        failures.append("py_compile_failed")

    behavior_matrix = [
        {
            "case": "active_shear_failure_legacy_exact_blocker_unlocked_no_runtime_proof",
            "expected_policy": "unlocked_active_failure_missing_runtime_proof",
            "final_publication_allowed": "proof_incomplete_card_only",
        },
        {
            "case": "active_shear_failure_runtime_exact_blocker_proven_no_cta",
            "expected_policy": "active_failure_blocked_with_exact_proof",
            "final_publication_allowed": True,
        },
        {
            "case": "active_shear_failure_no_exact_blocker_no_cta_unlocked",
            "expected_policy": "unlocked_active_failure_missing_apply_cta",
            "final_publication_allowed": False,
        },
        {
            "case": "active_shear_failure_missing_exact_blocker_geometry_locked",
            "expected_policy": "locked_active_failure_missing_exact_proof",
            "final_publication_allowed": "error_card_only",
        },
        {
            "case": "active_bending_and_shear_failure_partial_exact_proof",
            "expected_policy": "unlocked_active_failure_missing_apply_cta",
            "final_publication_allowed": False,
        },
    ]

    snapshot = {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "compile": compile_result,
        "behavior_matrix": behavior_matrix,
        "source_hashes": {
            "policy_function": _stable_hash(policy_source),
            "view_model_function": _stable_hash(view_model_source),
            "dashboard_title_function": _stable_hash(dashboard_title_source),
        },
    }
    snapshot["snapshot_hash"] = _stable_hash(
        {
            "checks": checks,
            "behavior_matrix": behavior_matrix,
            "source_hashes": snapshot["source_hashes"],
        }
    )
    return snapshot


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_active_failure_exact_blocker_policy_{timestamp}.json"
    md_path = AUDIT_DIR / f"design_guide_active_failure_exact_blocker_policy_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Design Guide Active Failure Exact Blocker Policy",
        "",
        f"Status: `{snapshot['status']}`",
        f"Snapshot hash: `{snapshot['snapshot_hash']}`",
        "",
        "## Checks",
    ]
    for name, passed in snapshot["checks"].items():
        lines.append(f"- {name}: {'PASS' if passed else 'FAIL'}")
    lines.extend(["", "## Behaviour Matrix"])
    for row in snapshot["behavior_matrix"]:
        lines.append(
            "- "
            f"{row['case']}: expected `{row['expected_policy']}`, "
            f"final publication allowed `{row['final_publication_allowed']}`"
        )
    if snapshot["failures"]:
        lines.extend(["", "## Failures"])
        lines.extend(f"- {failure}" for failure in snapshot["failures"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    snapshot = _build_snapshot()
    json_path, md_path = _write_artifacts(snapshot)
    print(f"status={snapshot['status']}")
    print(f"snapshot_hash={snapshot['snapshot_hash']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
