"""Universal verification meta-lock for Design Brain and Design Guide.

This verifier is the final "can we call the app fully verified?" gate.  It is
lightweight by default: it inspects the newest proof artifacts and ties them to
the current source-code hash, but it does not run browser fuzz or live Apply
workflows itself.

Use ``--enforce`` when this script is part of a release/full-verification gate.
Without ``--enforce`` it writes the same artifacts and exits successfully even
when the meta-lock is not yet locked, so it can be used as an audit.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.verification_run_manifest import current_run_artifact

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
RELEASE_MANIFEST = ROOT / "tools" / "verification" / "release_gate_manifest.json"

CODE_HASH_FILES: tuple[str, ...] = (
    "app.py",
    "inputs_page.py",
    "inputs_application/engineering_workspace.py",
    "inputs_application/page_runtime/design_guide.py",
    "inputs_page_modules/guidance_compute.py",
    "inputs_page_modules/design_guide/current_coordinators.py",
    "design_guide_page.py",
)
CODE_HASH_DIRS: tuple[str, ...] = (
    "design_brain",
    "ui",
    "inputs_page_modules",
    "inputs_application",
)

REQUIRED_ARTIFACTS: dict[str, str] = {
    "universal_live_family_lock": "design_brain_universal_live_family_lock",
    "independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
    "zero_authority_inventory_lock": "design_brain_inputs_page_zero_authority_inventory_lock",
    "critical_workflows_lock": "app_stability_critical_workflows_lock",
    "inputs_apply_10x_workflow_lock": "app_stability_inputs_apply_10x_workflow_lock",
    "family_10_fuzz_audit": "family_10_fuzz_audit",
    "browser_live_visual_consistency": "design_guide_browser_live_visual_consistency",
    "browser_live_smoothness_profile": "design_guide_browser_live_smoothness_profile",
    "loading_shell_slot_restoration": "design_guide_loading_shell_slot_restoration",
    "verifier_retirement_deletion_workflow": "verifier_retirement_deletion_workflow",
    "shared_path_release_lock": "design_brain_shared_path_release_lock",
    "browser_visual_layout_lock": "design_guide_browser_visual_layout_lock",
    "safe_optimal_blocker_publication_lock": "design_guide_safe_optimal_blocker_publication_lock",
    "family_smooth_operation_lock": "design_brain_family_smooth_operation_lock",
    "shared_bridge_dependency_binding_lock": "shared_bridge_dependency_binding_lock",
    "legacy_visible_surface_deletion_lock": "design_guide_legacy_visible_surface_deletion_lock",
    "live_bug_registry_contract": "design_guide_live_bug_registry_contract",
}

REGRESSION_FILES: tuple[str, ...] = (
    "tools/verification/check_regression_contracts.py",
    "tools/verification/regression_contract_manifest.json",
    "tools/verification/design_guide_live_bug_regression_registry.json",
    "tools/verification/design_guide_live_bug_registry_contract.py",
    "tools/verification/release_gate_manifest.json",
    "tools/verification/check_release_gate_manifest.py",
    "tools/verification/verifier_retirement_deletion_workflow.py",
    "tools/verification/run_release_gate_manifest.py",
    "tools/verification/design_brain_shared_path_release_lock.py",
    "tools/verification/design_guide_browser_visual_layout_lock.py",
    "tools/verification/design_guide_safe_optimal_blocker_publication_lock.py",
    "tools/verification/design_brain_family_smooth_operation_lock.py",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "UNREADABLE", "error": str(exc)}
    return payload if isinstance(payload, dict) else {"status": "UNREADABLE", "error": "json root is not object"}


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    # Meta-lock inputs are release authority. Never select the newest file
    # from disk; only the active canonical manifest may select them.
    if not os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        return None, {}
    return current_run_artifact(prefix)


def _age_hours(path: Path | None) -> float | None:
    if not path:
        return None
    return round((time.time() - path.stat().st_mtime) / 3600.0, 4)


def _current_run_start() -> float | None:
    manifest_path = str(os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST") or "").strip()
    if not manifest_path:
        return None
    manifest = _read_json(Path(manifest_path))
    started = str(manifest.get("started_at") or "").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(started).timestamp()
    except Exception:
        return None


def _payload_passed(payload: dict[str, Any]) -> bool:
    status = str(payload.get("status") or payload.get("result") or "").strip().upper()
    if status in {"PASS", "PASSED", "LOCKED", "LIVE_EXECUTION_PASS"}:
        return True
    lock_status = str(payload.get("lock_status") or "").strip().upper()
    if lock_status == "LOCKED":
        return True
    completion = str(payload.get("completion_status") or "").strip().upper()
    return completion == "COMPLETE"


def _code_state_hash() -> dict[str, Any]:
    digest = hashlib.sha256()
    files: list[Path] = []
    for relative in CODE_HASH_FILES:
        path = ROOT / relative
        if path.exists() and path.is_file():
            files.append(path)
    for relative in CODE_HASH_DIRS:
        root = ROOT / relative
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
        files.extend(path for path in root.rglob("*.json") if "__pycache__" not in path.parts)
    unique = sorted(set(files), key=lambda path: path.relative_to(ROOT).as_posix())
    for path in unique:
        relative = path.relative_to(ROOT).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return {
        "hash": digest.hexdigest(),
        "file_count": len(unique),
        "scope_files": list(CODE_HASH_FILES),
        "scope_dirs": list(CODE_HASH_DIRS),
    }


def _required_artifact_rows(max_age_hours: float, current_code_hash: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    run_start = _current_run_start()
    for key, prefix in REQUIRED_ARTIFACTS.items():
        path, payload = _latest(prefix)
        age = _age_hours(path)
        stale = age is None or age > max_age_hours
        current_run = bool(path and run_start is not None and path.stat().st_mtime >= run_start)
        if run_start is not None and not current_run:
            stale = True
        row: dict[str, Any] = {
            "key": key,
            "prefix": prefix,
            "path": str(path) if path else None,
            "age_hours": age,
            "status": payload.get("status") or payload.get("result") or payload.get("lock_status") or "MISSING",
            "passed_status": _payload_passed(payload),
            "fresh": not stale,
            "written_in_current_run": current_run if run_start is not None else None,
            "code_state_hash": payload.get("code_state_hash"),
            "code_hash_matches_current": payload.get("code_state_hash") == current_code_hash
            if payload.get("code_state_hash")
            else None,
            "payload": payload,
        }
        rows[key] = row
    return rows


def _universal_family_checks(payload: dict[str, Any], current_code_hash: str) -> dict[str, bool]:
    required_count = len(list(payload.get("families_required") or []))
    bound_count = int(payload.get("current_run_bound_locked_family_count") or 0)
    stale_rows = list(payload.get("stale_or_resumed_locked_families") or [])
    return {
        "universal_lock_status_locked": str(payload.get("universal_lock_status") or "") == "LOCKED",
        "universal_lock_current_code_hash": payload.get("code_state_hash") == current_code_hash,
        "all_locked_family_artifacts_bound_to_universal_run": (
            required_count > 0 and bound_count == required_count and not stale_rows
        ),
        "logical_ladder_proof_complete": not bool(payload.get("families_missing_logical_ladder_proof")),
        "format_text_authority_proof_complete": not bool(payload.get("families_missing_format_authority_proof")),
        "no_missing_or_failed_families": not bool(payload.get("missing_or_failed_families")),
    }


def _regression_gate_present() -> dict[str, Any]:
    rows = []
    for relative in REGRESSION_FILES:
        path = ROOT / relative
        rows.append({"path": relative, "exists": path.exists()})
    manifest = _read_json(RELEASE_MANIFEST)
    gates = [gate for gate in list(manifest.get("release_gates") or []) if isinstance(gate, dict)]
    gate_ids = [str(gate.get("id") or "") for gate in gates]
    manifest_shape_passed = bool(gates) and all(
        bool(gate.get("id")) and bool(gate.get("command")) and bool(gate.get("artifact_prefix"))
        for gate in gates
    ) and len(gate_ids) == len(set(gate_ids))
    return {
        "required_files": rows,
        "manifest_shape_passed": manifest_shape_passed,
        "manifest_gate_count": len(gates),
        "passed": all(row["exists"] for row in rows) and manifest_shape_passed,
    }


def _build(max_age_hours: float) -> dict[str, Any]:
    code_state = _code_state_hash()
    artifact_rows = _required_artifact_rows(max_age_hours, str(code_state["hash"]))
    universal_payload = dict(artifact_rows["universal_live_family_lock"]["payload"])
    universal_checks = _universal_family_checks(universal_payload, str(code_state["hash"]))
    regression_gate = _regression_gate_present()

    freshness_checks = {
        key: bool(row["fresh"])
        for key, row in artifact_rows.items()
    }
    artifact_status_checks = {
        key: bool(row["passed_status"])
        for key, row in artifact_rows.items()
    }
    current_code_checks = {
        "universal_live_family_lock_current_code": bool(
            artifact_rows["universal_live_family_lock"]["code_hash_matches_current"]
        )
    }

    shared_path_checks = {
        "independence_lock_pass": artifact_status_checks["independence_lock"],
        "render_bridge_lock_pass": artifact_status_checks["render_bridge_lock"],
        "compute_resolver_publication_bridge_lock_pass": artifact_status_checks[
            "compute_resolver_publication_bridge_lock"
        ],
        "zero_authority_inventory_lock_pass": artifact_status_checks["zero_authority_inventory_lock"],
        "shared_bridge_dependency_binding_lock_pass": artifact_status_checks[
            "shared_bridge_dependency_binding_lock"
        ],
        "legacy_visible_surface_deletion_lock_pass": artifact_status_checks[
            "legacy_visible_surface_deletion_lock"
        ],
        "shared_path_release_lock_pass": artifact_status_checks["shared_path_release_lock"],
    }
    live_browser_checks = {
        "critical_workflows_lock_pass": artifact_status_checks["critical_workflows_lock"],
        "inputs_apply_10x_workflow_lock_pass": artifact_status_checks["inputs_apply_10x_workflow_lock"],
        "family_10_fuzz_audit_pass": artifact_status_checks["family_10_fuzz_audit"],
    }
    visual_smoothness_checks = {
        "browser_live_visual_consistency_pass": artifact_status_checks["browser_live_visual_consistency"],
        "browser_live_smoothness_profile_pass": artifact_status_checks["browser_live_smoothness_profile"],
        "loading_shell_slot_restoration_pass": artifact_status_checks["loading_shell_slot_restoration"],
        "browser_visual_layout_lock_pass": artifact_status_checks["browser_visual_layout_lock"],
        "safe_optimal_blocker_publication_lock_pass": artifact_status_checks[
            "safe_optimal_blocker_publication_lock"
        ],
        "family_smooth_operation_lock_pass": artifact_status_checks["family_smooth_operation_lock"],
    }

    all_check_groups = {
        "artifact_status_checks": artifact_status_checks,
        "artifact_freshness_checks": freshness_checks,
        "current_code_checks": current_code_checks,
        "universal_family_checks": universal_checks,
        "shared_path_checks": shared_path_checks,
        "live_browser_checks": live_browser_checks,
        "visual_smoothness_checks": visual_smoothness_checks,
        "regression_gate_checks": {
            "regression_contract_gate_present": bool(regression_gate["passed"]),
            "release_gate_manifest_shape_pass": bool(regression_gate["manifest_shape_passed"]),
            "verifier_retirement_deletion_workflow_pass": artifact_status_checks[
                "verifier_retirement_deletion_workflow"
            ],
            "live_bug_registry_contract_pass": artifact_status_checks["live_bug_registry_contract"],
        },
    }
    failed_checks = {
        group: [key for key, passed in checks.items() if not passed]
        for group, checks in all_check_groups.items()
    }
    failed_checks = {group: keys for group, keys in failed_checks.items() if keys}
    meta_locked = not failed_checks

    return {
        "schema": "design_brain.universal_verification_meta_lock.v1",
        "status": "PASS",
        "meta_lock_status": "LOCKED" if meta_locked else "NOT_LOCKED",
        "generated_at": _stamp(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "max_age_hours": max_age_hours,
        "current_code_state_hash": code_state["hash"],
        "current_code_state_hash_scope": {
            "file_count": code_state["file_count"],
            "scope_files": code_state["scope_files"],
            "scope_dirs": code_state["scope_dirs"],
        },
        "check_groups": all_check_groups,
        "failed_checks": failed_checks,
        "required_artifacts": {
            key: {item_key: item_value for item_key, item_value in row.items() if item_key != "payload"}
            for key, row in artifact_rows.items()
        },
        "universal_family_missing_logical_ladder_proof": universal_payload.get(
            "families_missing_logical_ladder_proof",
            [],
        ),
        "universal_family_missing_format_authority_proof": universal_payload.get(
            "families_missing_format_authority_proof",
            [],
        ),
        "regression_gate": regression_gate,
        "fully_verified_app_requires": [
            "latest universal live family lock is LOCKED",
            "latest universal live family lock code_state_hash matches current source",
            "all family ladder/format proofs complete",
            "shared Design Guide publication, render, compute, and zero-authority locks pass",
            "live browser/apply/fuzz proof artifacts pass and are fresh",
            "visual/smoothness proof artifacts pass and are fresh",
            "browser visual/layout release lock passes",
            "safe optimal blocker publication lock turns safe no-action blockers into green optimal cards",
            "family smooth-operation lock proves no per-family card/button/settle churn",
            "release gate manifest checker passes",
            "verifier retirement/deletion workflow has a current PASS artifact",
            "regression intake gate exists before product bugs can be called fixed",
            "active live/browser bug registry has a passing contract artifact",
        ],
        "product_behaviour_changed": False,
    }


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Universal Verification Meta Lock",
        "",
        f"Status: `{payload['status']}`",
        f"Meta lock status: `{payload['meta_lock_status']}`",
        f"Max artifact age hours: `{payload['max_age_hours']}`",
        f"Current code state hash: `{payload['current_code_state_hash']}`",
        "",
        "## Failed Checks",
        "",
    ]
    if payload["failed_checks"]:
        for group, keys in dict(payload["failed_checks"]).items():
            lines.append(f"- `{group}`: `{keys}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Required Artifacts", ""])
    lines.append("| Key | Status | Fresh | Code Hash Matches | Artifact |")
    lines.append("| --- | --- | ---: | ---: | --- |")
    for key, row in dict(payload["required_artifacts"]).items():
        lines.append(
            f"| `{key}` | `{row.get('status')}` | `{row.get('fresh')}` | "
            f"`{row.get('code_hash_matches_current')}` | `{row.get('path')}` |"
        )
    lines.extend(["", "## Universal Family Gaps", ""])
    lines.append(
        f"- Missing logical ladder proof: `{payload['universal_family_missing_logical_ladder_proof']}`"
    )
    lines.append(
        f"- Missing format/text authority proof: `{payload['universal_family_missing_format_authority_proof']}`"
    )
    lines.extend(["", "## Fully Verified Rule", ""])
    for item in payload["fully_verified_app_requires"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Release Command",
            "",
            "```powershell",
            "python tools/verification/run_release_gate_manifest.py",
            "python tools/verification/check_release_gate_manifest.py",
            "python tools/verification/verifier_retirement_deletion_workflow.py",
            "python tools/verification/design_guide_live_bug_registry_contract.py",
            "python tools/verification/design_brain_shared_path_release_lock.py",
            "python tools/verification/design_guide_browser_visual_layout_lock.py",
            "python tools/verification/design_guide_safe_optimal_blocker_publication_lock.py",
            "python tools/verification/design_brain_universal_live_family_lock.py --run-live --port 9301",
            "python tools/verification/design_brain_family_smooth_operation_lock.py",
            "python tools/verification/design_brain_universal_verification_meta_lock.py --enforce",
            "python tools/verification/app_stability_goal_completion_audit.py",
            "```",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-age-hours", type=float, default=24.0)
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Return a failing exit code unless meta_lock_status is LOCKED.",
    )
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build(float(args.max_age_hours))
    stamp = payload["generated_at"]
    json_path = ARTIFACT_DIR / f"design_brain_universal_verification_meta_lock_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_universal_verification_meta_lock_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_markdown(payload, md_path)
    print(f"design_brain_universal_verification_meta_lock {payload['status']}")
    print(f"meta_lock_status={payload['meta_lock_status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if (payload["meta_lock_status"] == "LOCKED" or not args.enforce) else 1


if __name__ == "__main__":
    raise SystemExit(main())
