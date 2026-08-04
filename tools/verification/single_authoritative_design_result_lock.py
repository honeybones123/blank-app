from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
AUTHORITY = ROOT / "design_brain" / "authority.py"
DESIGN_BRAIN_INIT = ROOT / "design_brain" / "__init__.py"
INPUTS = ROOT / "inputs_page.py"
APP = ROOT / "app.py"
DESIGN_GUIDE_MODULES = ROOT / "inputs_page_modules" / "design_guide"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _compile(paths: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", *paths],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    return {
        "command": "python -m py_compile " + " ".join(paths),
        "returncode": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _dataclass_frozen(tree: ast.AST, name: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != name:
            continue
        for decorator in node.decorator_list:
            call = decorator if isinstance(decorator, ast.Call) else None
            if call is None:
                continue
            func_name = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
            if func_name != "dataclass":
                continue
            for keyword in call.keywords:
                if keyword.arg == "frozen" and isinstance(keyword.value, ast.Constant):
                    return keyword.value.value is True
        return False
    return False


def _candidate_writers(pattern: str) -> list[str]:
    matches: list[str] = []
    paths = [APP, INPUTS, *sorted(DESIGN_GUIDE_MODULES.rglob("*.py"))]
    for path in paths:
        if not path.exists():
            continue
        for lineno, line in enumerate(_read(path).splitlines(), start=1):
            if pattern not in line or not ("=" in line or ".update(" in line or ".pop(" in line):
                continue
            stripped = line.strip()
            # Local reads and diagnostic projections are consumers of the
            # authoritative result, not alternate owners of publication or
            # Apply identity. Keep the scan focused on live state writers.
            if ".get(" in stripped and "st.session_state" not in stripped:
                continue
            if "_error" in stripped or "authoritative_" in stripped:
                continue
            if "build_final_design_guide_primary_apply_payload_projection" in stripped:
                continue
            if pattern == "design_guide_primary_apply_payload" and "_target[" in stripped:
                continue
            matches.append(f"{path.relative_to(ROOT)}:{lineno}:{stripped}")
    return matches


def _authority_model_checks() -> dict[str, Any]:
    from design_brain.authority import (
        AuthoritativeDesignResult,
        EngineeringInputSnapshot,
        UI_ONLY_EXCLUDED_FIELDS,
        build_authoritative_design_result,
    )

    tree = ast.parse(_read(AUTHORITY))
    snapshot_fields = {field.name for field in fields(EngineeringInputSnapshot)}
    result_fields = {field.name for field in fields(AuthoritativeDesignResult)}
    ui_excluded = set(UI_ONLY_EXCLUDED_FIELDS)

    snapshot_a = EngineeringInputSnapshot(
        geometry={"D": 300, "b": 250},
        materials={"fc": 32},
        reinforcement={"bot": {"count": 3, "dia": 16}},
        design_actions={"Mu": 600, "Vu": 600},
        design_settings={"mode": "fast"},
        locked_variables={"D": False},
        unlocked_variables={"bot": True},
        contract_versions={"combined": "v1"},
        calculation_versions={"beam": "v1"},
    )
    snapshot_b = EngineeringInputSnapshot(
        geometry={"b": 250, "D": 300},
        materials={"fc": 32},
        reinforcement={"bot": {"dia": 16, "count": 3}},
        design_actions={"Vu": 600, "Mu": 600},
        design_settings={"mode": "fast"},
        locked_variables={"D": False},
        unlocked_variables={"bot": True},
        contract_versions={"combined": "v1"},
        calculation_versions={"beam": "v1"},
    )
    snapshot_c = EngineeringInputSnapshot(
        geometry={"D": 320, "b": 250},
        materials={"fc": 32},
        reinforcement={"bot": {"count": 3, "dia": 16}},
        design_actions={"Mu": 600, "Vu": 600},
        design_settings={"mode": "fast"},
        locked_variables={"D": False},
        unlocked_variables={"bot": True},
        contract_versions={"combined": "v1"},
        calculation_versions={"beam": "v1"},
    )

    base_result = build_authoritative_design_result(
        engineering_snapshot=snapshot_a,
        current_calculations={"bending_util": 7.96, "shear_util": 7.96},
        governing_family="BENDING_AND_SHEAR_FAIL_GOVERN",
        family_contract_version="v1",
        family_outcome="BLOCKED",
        selected_candidate_absence={"reason": "no_safe_executable_candidate"},
        selected_updates={},
        candidate_acceptance_proof={"accepted": False},
        blocker_or_exhaustion_proof={"complete_family_proof": True, "safe_candidate_count": 0},
        final_publication={"outcome_state": "BLOCKED", "candidate_id": None},
        display_model={"badge": "BLOCKED", "title": "Bending and shear repair blocked"},
        cta_model={"enabled": False, "disabled_reason": "candidate_preview_has_fail_status"},
        apply_payload={},
    )
    reordered_result = build_authoritative_design_result(
        engineering_snapshot=snapshot_b,
        current_calculations={"shear_util": 7.96, "bending_util": 7.96},
        governing_family="BENDING_AND_SHEAR_FAIL_GOVERN",
        family_contract_version="v1",
        family_outcome="BLOCKED",
        selected_candidate_absence={"reason": "no_safe_executable_candidate"},
        selected_updates={},
        candidate_acceptance_proof={"accepted": False},
        blocker_or_exhaustion_proof={"safe_candidate_count": 0, "complete_family_proof": True},
        final_publication={"candidate_id": None, "outcome_state": "BLOCKED"},
        display_model={"title": "Bending and shear repair blocked", "badge": "BLOCKED"},
        cta_model={"disabled_reason": "candidate_preview_has_fail_status", "enabled": False},
        apply_payload={},
    )
    cta_changed = build_authoritative_design_result(
        engineering_snapshot=snapshot_a,
        current_calculations={"bending_util": 7.96, "shear_util": 7.96},
        governing_family="BENDING_AND_SHEAR_FAIL_GOVERN",
        family_contract_version="v1",
        family_outcome="ACTION",
        selected_candidate={"candidate_id": "unsafe-preview"},
        selected_updates={"D": 400},
        candidate_acceptance_proof={"accepted": True},
        blocker_or_exhaustion_proof={},
        final_publication={"outcome_state": "ACTION", "candidate_id": "unsafe-preview"},
        display_model={"badge": "NEXT", "title": "Bending and shear capacity are low"},
        cta_model={"enabled": True, "label": "Run one-click auto design"},
        apply_payload={"candidate_id": "unsafe-preview", "updates": {"D": 400}},
    )

    return {
        "engineering_input_snapshot_is_dataclass": is_dataclass(EngineeringInputSnapshot),
        "engineering_input_snapshot_is_frozen": _dataclass_frozen(tree, "EngineeringInputSnapshot"),
        "authoritative_design_result_is_dataclass": is_dataclass(AuthoritativeDesignResult),
        "authoritative_design_result_is_frozen": _dataclass_frozen(tree, "AuthoritativeDesignResult"),
        "engineering_snapshot_has_required_fields": {
            "pass": {
                "geometry",
                "materials",
                "reinforcement",
                "design_actions",
                "design_settings",
                "locked_variables",
                "unlocked_variables",
                "contract_versions",
                "calculation_versions",
            }.issubset(snapshot_fields),
            "fields": sorted(snapshot_fields),
        },
        "engineering_snapshot_excludes_ui_only_fields": {
            "pass": not bool(snapshot_fields & ui_excluded),
            "forbidden_present": sorted(snapshot_fields & ui_excluded),
        },
        "authoritative_result_has_required_fields": {
            "pass": {
                "engineering_hash",
                "current_calculations",
                "governing_family",
                "family_contract_version",
                "family_outcome",
                "selected_candidate",
                "selected_candidate_absence",
                "selected_updates",
                "candidate_evaluation",
                "candidate_acceptance_proof",
                "blocker_or_exhaustion_proof",
                "final_publication",
                "display_model",
                "cta_model",
                "apply_payload",
                "publication_authority_hash",
            }.issubset(result_fields),
            "fields": sorted(result_fields),
        },
        "engineering_hash_is_order_stable": snapshot_a.engineering_hash == snapshot_b.engineering_hash,
        "engineering_hash_changes_on_engineering_input": snapshot_a.engineering_hash != snapshot_c.engineering_hash,
        "publication_authority_hash_is_order_stable": (
            base_result.publication_authority_hash == reordered_result.publication_authority_hash
        ),
        "publication_authority_hash_changes_on_visible_cta_apply_result": (
            base_result.publication_authority_hash != cta_changed.publication_authority_hash
        ),
        "publication_authority_hash_present": bool(base_result.publication_authority_hash),
        "design_brain_public_exports_present": all(
            name in _read(DESIGN_BRAIN_INIT)
            for name in (
                "EngineeringInputSnapshot",
                "AuthoritativeDesignResult",
                "build_authoritative_design_result",
            )
        ),
    }


def _all_required_checks_pass(checks: dict[str, Any]) -> bool:
    for value in checks.values():
        if isinstance(value, dict) and "pass" in value:
            if value["pass"] is not True:
                return False
        elif value is not True:
            return False
    return True


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Single Authoritative Design Result Lock",
        "",
        f"Status: `{snapshot['status']}`",
        f"Model lock: `{snapshot['model_lock']}`",
        f"Live owner cutover: `{snapshot['live_owner_cutover']}`",
        "",
        "## Scope",
        "",
        "This is the Phase 1 authority lock. It proves the immutable authority models and deterministic hash behaviour now, and records live cutover gaps separately.",
        "",
        "## Model Checks",
        "",
    ]
    for key, value in snapshot["checks"].items():
        if isinstance(value, dict) and "pass" in value:
            lines.append(f"- `{key}`: `{value['pass']}`")
        else:
            lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Live Cutover Gaps", ""])
    if snapshot["live_cutover_gaps"]:
        lines.extend(f"- {gap}" for gap in snapshot["live_cutover_gaps"])
    else:
        lines.append("- none")
    lines.extend(["", "## Candidate Legacy Authority Writers", ""])
    for key, rows in snapshot["candidate_legacy_authority_writers"].items():
        lines.append(f"- `{key}`: `{len(rows)}`")
        for row in rows[:20]:
            lines.append(f"  - `{row}`")
        if len(rows) > 20:
            lines.append(f"  - ... `{len(rows) - 20}` more")
    lines.append(f"\nJSON: `{snapshot['artifact']}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    compile_result = _compile(
        [
            "design_brain/authority.py",
            "design_brain/__init__.py",
            "tools/verification/single_authoritative_design_result_lock.py",
        ]
    )
    checks = _authority_model_checks()
    candidate_writers = {
        "final_publication_verifier_payload": _candidate_writers("final_publication_verifier_payload"),
        "design_guide_primary_apply_payload": _candidate_writers("design_guide_primary_apply_payload"),
        "final_publication_hashes": _candidate_writers("final_publication_hashes"),
    }
    live_cutover_gaps: list[str] = []
    if candidate_writers["final_publication_verifier_payload"]:
        live_cutover_gaps.append(
            "legacy final_publication_verifier_payload writers still exist; cutover must prove they mirror AuthoritativeDesignResult"
        )
    if candidate_writers["design_guide_primary_apply_payload"]:
        live_cutover_gaps.append(
            "legacy primary Apply payload writers still exist; cutover must prove they share AuthoritativeDesignResult publication_authority_hash"
        )
    if candidate_writers["final_publication_hashes"]:
        live_cutover_gaps.append(
            "legacy final_publication_hashes projection writers still exist; cutover must prove no second publication identity can drive visible state"
        )

    model_lock = "LOCKED" if compile_result["status"] == "PASS" and _all_required_checks_pass(checks) else "FAIL"
    live_owner_cutover = "PENDING" if live_cutover_gaps else "LOCKED"
    status = "LOCKED" if model_lock == "LOCKED" and live_owner_cutover == "LOCKED" else "MODEL_LOCKED_LIVE_CUTOVER_PENDING"
    if model_lock != "LOCKED":
        status = "FAIL"

    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"single_authoritative_design_result_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"single_authoritative_design_result_lock_{stamp}.md"
    snapshot = {
        "schema": "single_authoritative_design_result_lock.v1",
        "status": status,
        "lock_status": status,
        "model_lock": model_lock,
        "live_owner_cutover": live_owner_cutover,
        "compile": compile_result,
        "checks": checks,
        "live_cutover_gaps": live_cutover_gaps,
        "candidate_legacy_authority_writers": candidate_writers,
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    if live_cutover_gaps:
        print("live_cutover_gaps=" + "; ".join(live_cutover_gaps))
    return 0 if model_lock == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
