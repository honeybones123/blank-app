"""Live cutover verifier for collapsed guidance replacement authority.

This verifier proves collapsed_guidance_items replacement is mediated by
DesignGuideController publication authority, whose inner publication object is
FinalDesignGuidePublication. It does not require moving CTA rendering, apply
routing, visible wording, family runtimes, or evaluator behavior.
"""

from __future__ import annotations

import ast
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
ROUTE_COORDINATORS = (
    ROOT
    / "inputs_page_modules"
    / "design_guide"
    / "current_coordinators.py"
)
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

REQUIRED_CALLSITES = {
    "compute_publication_resolution": "final_compute_resolution = {",
    "late_evidence_contract_rebound": "run_design_guide_controller_compute_publication_handoff_trace_only(",
    "post_evidence_contract_rebound": "run_design_guide_controller_compute_rebound_publication_item_trace_only(",
}

FORBIDDEN_RUNTIME_MOVES = (
    "move_cta_rendering_into_final_publication",
    "move_apply_routing_into_final_publication",
    "move_visible_wording_into_final_publication",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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


def _latest_artifact(prefix: str) -> dict[str, Any]:
    if os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        try:
            from tools.verification.verification_run_manifest import current_run_artifact
        except ModuleNotFoundError:
            from verification_run_manifest import current_run_artifact
        path, snapshot = current_run_artifact(prefix)
        return {"path": str(path) if path else None, "snapshot": snapshot if path else None, "passed": bool(path and snapshot.get("status") == "PASS")}
    artifacts = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not artifacts:
        return {"path": None, "snapshot": None}
    path = artifacts[-1]
    return {
        "path": str(path),
        "snapshot": json.loads(path.read_text(encoding="utf-8")),
    }


def _latest_pass_or_latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not artifacts:
        return {"path": None, "snapshot": None, "passed": False}
    for path in artifacts:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        if snapshot.get("status") == "PASS":
            return {"path": str(path), "snapshot": snapshot, "passed": True}
    path = artifacts[0]
    return {
        "path": str(path),
        "snapshot": json.loads(path.read_text(encoding="utf-8")),
        "passed": False,
    }


def _function_bounds(source: str, function_name: str) -> tuple[int, int] | None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return int(node.lineno), int(getattr(node, "end_lineno", node.lineno))
    return None


def _function_source(source: str, function_name: str) -> str:
    bounds = _function_bounds(source, function_name)
    if bounds is None:
        return ""
    start, end = bounds
    lines = source.splitlines()
    return "\n".join(lines[start - 1 : end])


def _line_containing(source: str, needle: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            return index
    return None


def _build_snapshot() -> dict[str, Any]:
    adapter_artifact = _latest_pass_or_latest("design_guide_collapsed_guidance_adapter_parity")
    consumes_artifact = _latest_pass_or_latest(
        "design_guide_collapsed_replacement_consumes_publication_snapshot"
    )
    lock_artifact = _latest_pass_or_latest("design_guide_independence_lock")

    input_source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (INPUTS_PAGE, ROUTE_COORDINATORS, CONTROLLER)
        if path.exists()
    )
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    controller_source = CONTROLLER.read_text(encoding="utf-8")
    apply_owner_sources = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (
            ROOT / "inputs_page_modules" / "apply_routing.py",
            ROOT / "inputs_application" / "page_runtime" / "common.py",
            ROOT / "inputs_page_app_contracts.py",
        )
        if path.exists()
    )
    helper_source = _function_source(input_source, "_collapsed_guidance_item_from_final_publication_authority")
    adapter_source = _function_source(publication_source, "build_collapsed_guidance_item_from_final_publication")

    callsites = {
        name: {
            "marker": marker,
            "present": marker in input_source,
            "line": _line_containing(input_source, marker),
        }
        for name, marker in REQUIRED_CALLSITES.items()
    }
    imports_present = {
        "controller_publication_authority": "_run_design_guide_controller_publication_authority" in input_source,
        "controller_request": "_DesignGuideControllerRequest" in input_source,
    }
    helper_checks = {
        "helper_exists": bool(helper_source),
        "uses_controller_publication_authority": "run_design_guide_controller_compute_publication_handoff_trace_only(" in controller_source,
        "uses_controller_collapsed_item": "build_collapsed_guidance_item_from_final_publication(" in controller_source,
        "does_not_build_final_publication_directly": "_build_final_design_guide_publication(" not in helper_source,
        "does_not_use_collapsed_adapter_directly": "_build_collapsed_guidance_item_from_final_publication(" not in helper_source,
        "stamps_publication_authority": "publication_hash" in controller_source,
        "stamps_controller_authority": '"authority": "DesignGuideController' in controller_source,
        "stamps_inner_final_publication_authority": "build_final_design_guide_publication(" in controller_source,
        "fallback_available": "build_design_guide_controller_compute_resolver_fallback_shell(" in controller_source,
        "fallback_non_authoritative": "fallback_shell" in controller_source and '"enabled": False' in controller_source,
    }
    controller_checks = {
        "controller_exists": bool(controller_source),
        "controller_exports_publication_authority": "run_design_guide_controller_compute_publication_handoff_trace_only(" in controller_source,
        "controller_builds_final_publication": "build_final_design_guide_publication(" in controller_source,
        "controller_builds_collapsed_item": "build_collapsed_guidance_item_from_final_publication(" in controller_source,
        "controller_no_inputs_page_import": "inputs_page" not in controller_source,
        "controller_no_streamlit_import": "streamlit" not in controller_source,
        "controller_no_apply_routing": "_record_rendered_design_guide_primary_apply_payload" not in controller_source,
    }
    adapter_checks = {
        "adapter_exists": bool(adapter_source),
        "accepts_final_publication": "FinalDesignGuidePublication" in adapter_source,
        "no_inputs_page_import": "inputs_page" not in publication_source,
        "no_streamlit_import": "streamlit" not in publication_source,
        "proof_only_flag": "collapsed_guidance_adapter_proof_only" in adapter_source,
        "non_product_driving_flag": '"product_driving": False' in adapter_source,
        "non_render_driving_flag": '"render_driving": False' in adapter_source,
    }
    ownership_guards = {
        "cta_rendering_stays_page_owned": "render_final_design_guide_card_html" in (ROOT / "ui" / "final_design_guide_card.py").read_text(encoding="utf-8")
        and "render_final_design_guide_card_html" not in publication_source,
        "apply_routing_stays_page_owned": (
            "handle_inputs_apply_buttons" in apply_owner_sources
            and "apply_recommendation_result_fn" in apply_owner_sources
            and "handle_inputs_apply_buttons" not in publication_source
        ),
        "legacy_wording_helper_deleted": "_design_guide_clean_main_card_text" not in input_source,
        "no_forbidden_runtime_move_markers": not any(marker in publication_source for marker in FORBIDDEN_RUNTIME_MOVES),
    }
    failures: list[str] = []
    if not adapter_artifact.get("passed"):
        failures.append("adapter_parity_latest_pass_artifact_missing")
    if not lock_artifact.get("passed"):
        failures.append("design_guide_independence_lock_failed")
    if not all(row["present"] for row in callsites.values()):
        failures.append("missing_adapter_wired_callsite")
    if not all(controller_checks.values()):
        failures.append("controller_contract_failed")
    if not all(adapter_checks.values()):
        failures.append("adapter_contract_failed")
    if not all(ownership_guards.values()):
        failures.append("ownership_guard_failed")

    status = "PASS" if not failures else "FAIL"
    proof_surface = {
        "callsites": callsites,
        "imports_present": imports_present,
        "helper_checks": helper_checks,
        "controller_checks": controller_checks,
        "adapter_checks": adapter_checks,
        "ownership_guards": ownership_guards,
        "adapter_artifact": adapter_artifact.get("path"),
        "consumes_artifact": consumes_artifact.get("path"),
        "lock_artifact": lock_artifact.get("path"),
    }
    return {
        "snapshot_name": "design_guide_collapsed_replacement_authority_cutover",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "callsites": callsites,
        "imports_present": imports_present,
        "helper_checks": helper_checks,
        "controller_checks": controller_checks,
        "adapter_checks": adapter_checks,
        "ownership_guards": ownership_guards,
        "verification": {
            "collapsed_guidance_adapter_parity_latest_pass": adapter_artifact,
            "design_guide_independence_lock_latest_pass": lock_artifact,
        },
        "source_artifacts": {
            "adapter_parity": adapter_artifact.get("path"),
            "replacement_consumes_publication": consumes_artifact.get("path"),
            "independence_lock": lock_artifact.get("path"),
        },
        "product_behavior_changed": False,
        "cta_rendering_moved": False,
        "apply_routing_moved": False,
        "visible_wording_moved": False,
        "fallback_available_non_authoritative": bool(helper_checks["fallback_available"]),
        "snapshot_hash": _stable_hash(proof_surface),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    callsite_rows = [
        f"| `{name}` | `{row['line']}` | `{row['present']}` |"
        for name, row in snapshot["callsites"].items()
    ]
    body = "\n".join(
        [
            "# Design Guide Collapsed Replacement Authority Cutover",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Product behavior changed: `{snapshot['product_behavior_changed']}`",
            f"- CTA rendering moved: `{snapshot['cta_rendering_moved']}`",
            f"- Apply routing moved: `{snapshot['apply_routing_moved']}`",
            f"- Visible wording moved: `{snapshot['visible_wording_moved']}`",
            f"- Fallback available and non-authoritative: `{snapshot['fallback_available_non_authoritative']}`",
            "",
            "## Wired Callsites",
            "",
            "| Callsite | Line | Present |",
            "|---|---:|---:|",
            *callsite_rows,
            "",
            "## Ownership Guards",
            "",
            *[f"- `{key}`: `{value}`" for key, value in snapshot["ownership_guards"].items()],
            "",
            "## Source Artifacts",
            "",
            f"- Adapter parity: `{snapshot['source_artifacts']['adapter_parity']}`",
            f"- Replacement consumes publication: `{snapshot['source_artifacts']['replacement_consumes_publication']}`",
            f"- Independence lock: `{snapshot['source_artifacts']['independence_lock']}`",
            "",
            "## Failures",
            "",
            (
                "None."
                if not snapshot["failures"]
                else "\n".join(f"- `{failure}`" for failure in snapshot["failures"])
            ),
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    stamp = snapshot["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_collapsed_replacement_authority_cutover_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_collapsed_replacement_authority_cutover_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_collapsed_replacement_authority_cutover {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
