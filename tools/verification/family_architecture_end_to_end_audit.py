"""End-to-end architecture audit for Design Brain governing families.

Proof-only. This verifier composes existing contract/runtime/live-wiring/
publication/CTA/apply artifacts and reports whether each family has evidence for:

classification -> contract ladder/runtime -> publication -> CTA -> apply effect.

It intentionally does not run broad browser replays or change product behavior.
Use the gaps it reports to choose the next focused verifier/replay.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


@dataclass(frozen=True)
class FamilyConfig:
    family_id: str
    label: str
    contract_pattern: str | None = None
    runtime_pattern: str | None = None
    lock_pattern: str | None = None
    product_path_patterns: tuple[str, ...] = ()
    apply_effect_patterns: tuple[str, ...] = ()


FAMILIES: tuple[FamilyConfig, ...] = (
    FamilyConfig(
        "BENDING_FAIL_GOVERNS",
        "Bending active failure",
        "bending_fail_governs_contract_check_*.json",
        "bending_fail_governs_ladder_runtime_*.json",
        "bending_fail_governs_lock_verifier_*.json",
        ("bending_fail_governs_repair_regression_*.json", "bending_fail_governs_locked_regression_*.json"),
        ("bending_fail_governs_repair_regression_*.json", "bending_fail_governs_live_fuzz_regression_lock_gate_*.json"),
    ),
    FamilyConfig(
        "SHEAR_FAIL_GOVERNS",
        "Shear active failure",
        "shear_fail_governs_contract_check_*.json",
        "shear_fail_governs_ladder_runtime_*.json",
        "shear_fail_governs_lock_verifier_*.json",
        ("shear_fail_governs_locked_regression_*.json", "design_guide_unlocked_shear_apply_cta_publication_*.json"),
        ("design_guide_unlocked_shear_apply_cta_publication_*.json",),
    ),
    FamilyConfig(
        "BENDING_OVERDESIGN_GOVERNS",
        "Bending overdesign",
        "bending_overdesign_governs_contract_check_*.json",
        "bending_overdesign_governs_runtime_*.json",
        "bending_overdesign_governs_lock_verifier_*.json",
        ("design_guide_apply_current_state_safety_*.json",),
        ("design_guide_apply_current_state_safety_*.json",),
    ),
    FamilyConfig(
        "SHEAR_OVERDESIGN_GOVERNS",
        "Shear overdesign",
        "shear_overdesign_governs_contract_check_*.json",
        "shear_overdesign_governs_runtime_*.json",
        "shear_overdesign_governs_lock_verifier_*.json",
        ("design_guide_shear_cleanup_noop_cta_*.json", "design_guide_apply_current_state_safety_*.json"),
        ("design_guide_shear_cleanup_noop_cta_*.json",),
    ),
    FamilyConfig(
        "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
        "Combined bending/shear active failure",
        "bending_and_shear_fail_govern_contract_check_*.json",
        "combined_bending_shear_fail_governs_runtime_*.json",
        "combined_bending_shear_fail_governs_lock_verifier_*.json",
        ("bending_and_shear_fail_govern_locked_regression_*.json", "design_guide_active_fail_blocker_locked_runtime_replay_*.json"),
        ("bending_and_shear_fail_govern_locked_regression_*.json",),
    ),
    FamilyConfig(
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "Bending fail plus shear overdesign",
        "bending_fail_shear_overdesign_governs_contract_check_*.json",
        "bending_fail_shear_overdesign_governs_runtime_*.json",
        "bending_fail_shear_overdesign_governs_lock_verifier_*.json",
        ("design_guide_apply_current_state_safety_*.json",),
        ("design_guide_partial_family_apply_effect_noop_proof_*.json",),
    ),
    FamilyConfig(
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "Shear fail plus bending overdesign",
        "shear_fail_bending_overdesign_governs_contract_check_*.json",
        "shear_fail_bending_overdesign_governs_runtime_*.json",
        "shear_fail_bending_overdesign_governs_lock_verifier_*.json",
        ("design_guide_unlocked_shear_apply_cta_publication_*.json",),
        ("design_guide_partial_family_apply_effect_noop_proof_*.json",),
    ),
    FamilyConfig(
        "COMBINED_OVERDESIGN_GOVERNS",
        "Combined overdesign",
        "combined_overdesign_governs_contract_check_*.json",
        "combined_overdesign_governs_runtime_*.json",
        "combined_overdesign_governs_lock_verifier_*.json",
        ("design_guide_apply_current_state_safety_*.json",),
        ("design_guide_partial_family_apply_effect_noop_proof_*.json",),
    ),
    FamilyConfig(
        "SERVICEABILITY_GOVERNS",
        "Serviceability",
        "serviceability_governs_contract_check_*.json",
        "serviceability_governs_ladder_runtime_*.json",
        "serviceability_governs_lock_verifier_*.json",
        ("compute_serviceability_blocker_snapshot_*.json", "design_guide_serviceability_blocker_runtime_authority_*.json"),
        ("design_guide_partial_family_apply_effect_noop_proof_*.json",),
    ),
)


GLOBAL_GATES: tuple[tuple[str, str], ...] = (
    ("family_classification_contract", "family_classification_contract_check_*.json"),
    ("family_chooser_regression", "family_chooser_classification_regression_*.json"),
    ("family_classification_lock", "family_classification_lock_verifier_*.json"),
    ("locked_family_live_wiring", "locked_family_live_wiring_snapshot_*.json"),
    ("cta_button_contract", "cta_button_contract_check_*.json"),
    ("design_guide_independence_lock", "design_guide_independence_lock_*.json"),
    # The old resolver-bridge gates covered retired page-shell helpers. The
    # current family audit consumes the live publication/renderer evidence and
    # the pure controller compute handoff instead.
    ("design_guide_family_browser_live_visual_consistency", "design_guide_family_browser_live_visual_consistency_*.json"),
    ("design_guide_controller_compute_handoff", "design_guide_controller_compute_handoff_object_*.json"),
    ("design_guide_apply_current_state_safety", "design_guide_apply_current_state_safety_*.json"),
)

FAMILY_CLASSIFICATION_ALIASES: dict[str, tuple[str, ...]] = {
    "COMBINED_BENDING_SHEAR_FAIL_GOVERNS": (
        "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
        "COMBINED_BENDING_SHEAR_FAIL",
        "BENDING_AND_SHEAR_FAIL_GOVERN",
    ),
    "COMBINED_OVERDESIGN_GOVERNS": (
        "COMBINED_OVERDESIGN_GOVERNS",
        "COMBINED_OVERDESIGN",
    ),
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": (
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS",
    ),
}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _module_imports(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(set(imports))


def _status(payload: dict[str, Any]) -> str | None:
    for key in ("status", "result", "lock_status"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            if "PASS" in value.upper() or "COMPLETE" in value.upper() or "LOCKED" in value.upper():
                return "PASS"
            if "FAIL" in value.upper() or "INCOMPLETE" in value.upper():
                return "FAIL"
            if "PARTIAL" in value.upper():
                return "PARTIAL"
            return value
    if payload.get("passed") is True:
        return "PASS"
    if payload.get("passed") is False:
        return "FAIL"
    return None


def _latest_artifact(pattern: str | None) -> dict[str, Any]:
    if not pattern:
        return {"pattern": None, "found": False, "status": "MISSING", "path": None}
    candidates = sorted(ARTIFACT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return {"pattern": pattern, "found": False, "status": "MISSING", "path": None}
    path = candidates[0]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "pattern": pattern,
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "pattern": pattern,
        "found": True,
        "path": str(path),
        "status": _status(payload) or "UNKNOWN",
        "created_at": payload.get("created_at"),
        "payload_keys": sorted(str(k) for k in payload.keys())[:40],
    }


def _latest_any(patterns: tuple[str, ...]) -> list[dict[str, Any]]:
    return [_latest_artifact(pattern) for pattern in patterns]


def _artifact_passed(row: dict[str, Any]) -> bool:
    return str(row.get("status") or "").upper() == "PASS"


def _any_passed(rows: list[dict[str, Any]]) -> bool:
    return any(_artifact_passed(row) for row in rows)


def _apply_effect_evidence_passed(family_id: str, rows: list[dict[str, Any]]) -> bool:
    saw_family_specific_proof = False
    for row in rows:
        if str(row.get("pattern") or "") != "design_guide_partial_family_apply_effect_noop_proof_*.json":
            continue
        saw_family_specific_proof = True
        path_value = row.get("path")
        if not path_value:
            continue
        try:
            payload = json.loads(Path(str(path_value)).read_text(encoding="utf-8"))
        except Exception:
            continue
        family_row = dict((payload.get("families") or {}).get(family_id) or {})
        if bool(family_row.get("counts_as_apply_effect_coverage")):
            return True
    if saw_family_specific_proof:
        return False
    return _any_passed(rows)


def _compile_check() -> dict[str, Any]:
    targets = [
        "tools/verification/family_architecture_end_to_end_audit.py",
        "design_brain/family_chooser.py",
        "design_brain/family_classification_runtime.py",
        "design_brain/final_publication.py",
        "design_brain/publication.py",
        "inputs_page.py",
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", *targets],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    return {
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "returncode": proc.returncode,
        "targets": targets,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def _direct_source_checks() -> dict[str, Any]:
    inputs = _read_text(ROOT / "inputs_page.py")
    app_bridge = _read_text(ROOT / "inputs_page_app_contract_bridge.py")
    design_guide_coordinators = _read_text(ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py")
    final_publication = _read_text(ROOT / "design_brain" / "final_publication.py")
    final_publication_imports = _module_imports(final_publication)
    family_chooser = _read_text(ROOT / "design_brain" / "family_chooser.py")
    runtime = _read_text(ROOT / "design_brain" / "family_classification_runtime.py")
    contract = _read_text(ROOT / "design_brain" / "contracts" / "family_classification_contract.json")
    final_publication_import_roots = {name.split(".", 1)[0] for name in final_publication_imports}
    return {
        "final_publication_is_authority_surface": "FinalDesignGuidePublication" in final_publication,
        "final_publication_no_streamlit_import": "streamlit" not in final_publication_import_roots
        and "st.session_state" not in final_publication,
        "inputs_page_shell_is_live": "def render_inputs_page" in inputs
        and "_render_fast_design_guidance_panel" not in inputs,
        "design_guide_apply_routing_bridge_present": "_queue_primary_design_guide_button_action" in app_bridge
        and "_record_rendered_design_guide_primary_apply_payload" in app_bridge,
        "design_guide_render_coordinator_present": "render_design_guide_final_render_current_coordinator" in design_guide_coordinators
        and "st.markdown" in design_guide_coordinators,
        "family_chooser_contract_runtime_present": "classify_family_from_whole_beam_evidence" in family_chooser
        and "family_classification_contract" in family_chooser,
        "classification_runtime_reads_contract": "load_family_classification_contract" in runtime,
        "classification_contract_mentions_all_configured_families": all(
            any(alias in contract for alias in FAMILY_CLASSIFICATION_ALIASES.get(family.family_id, (family.family_id,)))
            for family in FAMILIES
        ),
    }


def _family_row(config: FamilyConfig) -> dict[str, Any]:
    contract = _latest_artifact(config.contract_pattern)
    runtime = _latest_artifact(config.runtime_pattern)
    lock = _latest_artifact(config.lock_pattern)
    product_paths = _latest_any(config.product_path_patterns)
    apply_effect = _latest_any(config.apply_effect_patterns)
    checks = {
        "contract_passed": _artifact_passed(contract),
        "runtime_or_ladder_passed": _artifact_passed(runtime),
        "lock_passed": _artifact_passed(lock),
        "product_path_evidence_passed": _any_passed(product_paths) if product_paths else False,
        "apply_effect_evidence_passed": _apply_effect_evidence_passed(config.family_id, apply_effect) if apply_effect else False,
    }
    hard_fail = not (checks["contract_passed"] and checks["runtime_or_ladder_passed"] and checks["lock_passed"])
    coverage_gap = not (checks["product_path_evidence_passed"] and checks["apply_effect_evidence_passed"])
    if hard_fail:
        status = "FAIL"
    elif coverage_gap:
        status = "PARTIAL"
    else:
        status = "PASS"
    gaps: list[str] = []
    if not checks["contract_passed"]:
        gaps.append("contract_check_missing_or_not_pass")
    if not checks["runtime_or_ladder_passed"]:
        gaps.append("runtime_or_ladder_snapshot_missing_or_not_pass")
    if not checks["lock_passed"]:
        gaps.append("lock_verifier_missing_or_not_pass")
    if not checks["product_path_evidence_passed"]:
        gaps.append("product_path_publication_evidence_gap")
    if not checks["apply_effect_evidence_passed"]:
        gaps.append("apply_effect_or_noop_effect_evidence_gap")
    return {
        "family_id": config.family_id,
        "label": config.label,
        "status": status,
        "checks": checks,
        "gaps": gaps,
        "contract": contract,
        "runtime": runtime,
        "lock": lock,
        "product_path_evidence": product_paths,
        "apply_effect_evidence": apply_effect,
    }


def _global_rows() -> dict[str, dict[str, Any]]:
    return {name: _latest_artifact(pattern) for name, pattern in GLOBAL_GATES}


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Family Architecture End-to-End Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Created: `{payload['created_at']}`",
        "",
        "## Executive Summary",
        "",
        f"- Families checked: `{len(payload['families'])}`",
        f"- PASS: `{payload['summary']['pass']}`",
        f"- PARTIAL: `{payload['summary']['partial']}`",
        f"- FAIL: `{payload['summary']['fail']}`",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Global Gates",
        "",
        "| Gate | Status | Artifact |",
        "| --- | --- | --- |",
    ]
    for name, row in payload["global_gates"].items():
        lines.append(f"| `{name}` | `{row.get('status')}` | `{row.get('path')}` |")
    lines.extend(
        [
            "",
            "## Family Matrix",
            "",
            "| Family | Status | Contract | Runtime/Ladder | Lock | Product Path | Apply Effect | Gaps |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["families"]:
        product_pass = any(str(item.get("status")) == "PASS" for item in row.get("product_path_evidence") or [])
        apply_pass = bool((row.get("checks") or {}).get("apply_effect_evidence_passed"))
        lines.append(
            "| `{family}` | `{status}` | `{contract}` | `{runtime}` | `{lock}` | `{product}` | `{apply}` | {gaps} |".format(
                family=row["family_id"],
                status=row["status"],
                contract=row["contract"].get("status"),
                runtime=row["runtime"].get("status"),
                lock=row["lock"].get("status"),
                product="PASS" if product_pass else "GAP",
                apply="PASS" if apply_pass else "GAP",
                gaps=", ".join(f"`{gap}`" for gap in row.get("gaps") or []) or "-",
            )
        )
    lines.extend(
        [
            "",
            "## Direct Source Checks",
            "",
            "| Check | Result |",
            "| --- | --- |",
        ]
    )
    for name, value in payload.get("direct_source_checks", {}).items():
        lines.append(f"| `{name}` | `{value}` |")
    lines.extend(["", "## Next Safe Steps", ""])
    for step in payload.get("next_safe_steps") or []:
        lines.append(f"- {step}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    compile_result = _compile_check()
    global_gates = _global_rows()
    direct_source_checks = _direct_source_checks()
    family_rows = [_family_row(config) for config in FAMILIES]
    summary = {
        "pass": sum(1 for row in family_rows if row["status"] == "PASS"),
        "partial": sum(1 for row in family_rows if row["status"] == "PARTIAL"),
        "fail": sum(1 for row in family_rows if row["status"] == "FAIL"),
    }
    global_failures = [
        name
        for name, row in global_gates.items()
        if str(row.get("status") or "").upper() != "PASS"
    ]
    source_failures = [name for name, value in direct_source_checks.items() if value is not True]
    hard_family_failures = [row["family_id"] for row in family_rows if row["status"] == "FAIL"]
    partial_families = [row["family_id"] for row in family_rows if row["status"] == "PARTIAL"]
    if compile_result["status"] != "PASS" or global_failures or source_failures or hard_family_failures:
        status = "FAIL"
    elif partial_families:
        status = "PARTIAL"
    else:
        status = "PASS"
    next_safe_steps = []
    if partial_families:
        next_safe_steps.append(
            "Add focused browser/apply-effect proof for families marked PARTIAL, starting with the families that already have green lock/runtime evidence."
        )
    if global_failures:
        next_safe_steps.append(
            "Refresh or repair failed/missing global gates before trusting broad end-to-end results: "
            + ", ".join(global_failures)
        )
    if not global_failures and not hard_family_failures:
        next_safe_steps.append(
            "Run a targeted live replay matrix only for missing apply-effect coverage; do not rerun broad fuzz until these gaps are closed."
        )
    payload = {
        "schema": "family_architecture_end_to_end_audit.v1",
        "status": status,
        "created_at": stamp,
        "product_behaviour_changed": False,
        "code_changed": False,
        "summary": summary,
        "compile": compile_result,
        "global_gates": global_gates,
        "direct_source_checks": direct_source_checks,
        "families": family_rows,
        "global_failures": global_failures,
        "source_failures": source_failures,
        "hard_family_failures": hard_family_failures,
        "partial_families": partial_families,
        "next_safe_steps": next_safe_steps,
    }
    artifact_path = ARTIFACT_DIR / f"family_architecture_end_to_end_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"family_architecture_end_to_end_audit_{stamp}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(
        json.dumps(
            {
                "status": status,
                "artifact": str(artifact_path),
                "report": str(report_path),
                "pass": summary["pass"],
                "partial": summary["partial"],
                "fail": summary["fail"],
            },
            indent=2,
        )
    )
    return 0 if status in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
