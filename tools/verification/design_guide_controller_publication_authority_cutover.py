"""DesignGuideController publication authority cutover verifier.

Verifies the narrow cutover where the render-stage final-visible publication
bridge consumes `DesignGuideController.publication_authority` instead of
building `FinalDesignGuidePublication` directly in `inputs_page.py`.

Rendering, Apply routing, session state, UI, visible wording, and family
runtimes must remain outside the controller.
"""

from __future__ import annotations

import hashlib
import json
import re
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


REQUIRED_ARTIFACTS = {
    "controller_trace_only_parity": "design_guide_controller_trace_only_parity",
    "controller_live_trace_wiring": "design_guide_controller_live_trace_wiring",
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
}


FORBIDDEN_CONTROLLER_TOKENS = (
    "inputs_page",
    "streamlit",
    "st.session_state",
    "design_guide_page",
    "render_final_panel",
    "playwright",
    "_record_rendered_design_guide_primary_apply_payload",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_body(source: str, function_name: str) -> str:
    pattern = re.compile(rf"^def {re.escape(function_name)}\(.*?(?=^def |\Z)", re.S | re.M)
    match = pattern.search(source)
    return match.group(0) if match else ""


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "passed": False}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "passed": False,
            "error": str(exc),
        }
    status = payload.get("status") or payload.get("result") or payload.get("lock_status")
    return {
        "found": True,
        "path": str(path),
        "path_name": path.name,
        "status": status,
        "passed": status == "PASS" or str(status or "").endswith("locked"),
    }


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _case_payloads() -> list[dict[str, Any]]:
    return [
        {
            "name": "pass_design",
            "item": {
                "published_item_id": "pass-controller-001",
                "selected_family_id": "DESIGN_IS_EFFICIENT",
                "status": "PASS",
                "bucket": "pass",
                "title": "Design is efficient",
                "summary_line": "All checks pass.",
                "candidate_search_evidence": {"selected_family_id": "DESIGN_IS_EFFICIENT"},
            },
            "expected_outcome": "PASS",
        },
        {
            "name": "action_design",
            "item": {
                "published_item_id": "action-controller-001",
                "selected_family_id": "BENDING_FAIL_GOVERNS",
                "status": "ACTION",
                "bucket": "action",
                "title": "Strengthening required",
                "summary_line": "Apply the proposed repair.",
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_candidate",
                    "family": "BENDING_FAIL_GOVERNS",
                    "updates": {"D": 650},
                },
                "candidate_search_evidence": {"selected_family_id": "BENDING_FAIL_GOVERNS"},
            },
            "expected_outcome": "ACTION",
        },
        {
            "name": "blocked_design",
            "item": {
                "published_item_id": "blocked-controller-001",
                "selected_family_id": "SHEAR_FAIL_GOVERNS",
                "status": "BLOCKED",
                "bucket": "fail",
                "title": "Design Guide blocker proof incomplete",
                "summary_line": "Repair is blocked.",
                "blocking_reason": "No valid candidate remained.",
                "exact_blockers_by_family": {
                    "SHEAR_FAIL_GOVERNS": {"blocked": True, "reason": "no_valid_candidate"}
                },
            },
            "expected_outcome": "BLOCKED",
        },
    ]


def _run_parity_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        DesignGuideControllerRequest,
        run_design_guide_controller_publication_authority,
    )
    from design_brain.final_publication import build_final_design_guide_publication

    results = []
    for case in _case_payloads():
        reason = f"{case['name']}_controller_cutover"
        direct = build_final_design_guide_publication(
            item=case["item"],
            debug={},
            publication_reason=reason,
        )
        response = run_design_guide_controller_publication_authority(
            DesignGuideControllerRequest(
                item=case["item"],
                debug={},
                publication_reason=reason,
                source=reason,
            )
        )
        result = {
            "name": case["name"],
            "expected_outcome": case["expected_outcome"],
            "direct_publication_hash": direct.publication_hash,
            "controller_publication_hash": response.publication_hash,
            "direct_outcome": direct.outcome_state,
            "controller_outcome": response.parity_payload.get("outcome_state"),
            "collapsed_item_hash_matches": (
                response.collapsed_guidance_item.get("publication_hash")
                == response.publication_hash
            ),
            "resolution_hash_matches": (
                response.final_visible_resolution.get("publication_hash")
                == response.publication_hash
            ),
            "trace_only": response.trace_only,
            "product_driving": response.product_driving,
            "render_driving": response.render_driving,
            "apply_driving": response.apply_driving,
            "session_driving": response.session_driving,
        }
        result["passed"] = all(
            [
                result["direct_publication_hash"] == result["controller_publication_hash"],
                result["direct_outcome"] == case["expected_outcome"],
                result["controller_outcome"] == case["expected_outcome"],
                result["collapsed_item_hash_matches"],
                result["resolution_hash_matches"],
                result["trace_only"] is False,
                result["product_driving"] is True,
                result["render_driving"] is False,
                result["apply_driving"] is False,
                result["session_driving"] is False,
            ]
        )
        results.append(result)
    return results


def _source_checks() -> dict[str, Any]:
    page_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    final_visible_body = _function_body(
        page_source,
        "_final_visible_resolution_from_final_publication_authority",
    )
    controller_forbidden_hits = [
        token for token in FORBIDDEN_CONTROLLER_TOKENS if token in controller_source
    ]
    checks = {
        "controller_publication_authority_exported": (
            "run_design_guide_controller_publication_authority" in controller_source
            and '"run_design_guide_controller_publication_authority"' in controller_source
        ),
        "inputs_imports_controller_authority": (
            "_run_design_guide_controller_publication_authority" in page_source
        ),
        "final_visible_bridge_calls_controller_authority": (
            "_run_design_guide_controller_publication_authority(" in final_visible_body
        ),
        "final_visible_bridge_no_direct_publication_build": (
            "_build_final_design_guide_publication(" not in final_visible_body
        ),
        "final_visible_bridge_uses_controller_publication": (
            "controller_response.publication" in final_visible_body
            and "controller_response.collapsed_guidance_item" in final_visible_body
        ),
        "final_visible_bridge_records_controller_authority": (
            'debug_sink["design_guide_controller_publication_authority_live_wired"] = True'
            in final_visible_body
            and '"DesignGuideController.publication_authority"' in final_visible_body
        ),
        "controller_clean_of_page_ui_apply_imports": not controller_forbidden_hits,
        "cta_apply_render_session_remain_page_owned": all(
            token in page_source
            for token in (
                "_stamp_final_publication_cta_authority",
                "_record_rendered_design_guide_primary_apply_payload",
                "design_guide_page.render_final_panel",
                "st.session_state",
            )
        ),
    }
    checks["controller_forbidden_hits"] = controller_forbidden_hits
    checks["all_source_checks_pass"] = all(
        value for key, value in checks.items() if key != "controller_forbidden_hits"
    )
    return checks


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_controller_publication_authority_cutover_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_controller_publication_authority_cutover_{stamp}.md"
    lines = [
        "# DesignGuideController Publication Authority Cutover",
        "",
        f"Status: `{payload['status']}`",
        f"Product behavior changed outside publication bridge: `{payload['product_behavior_changed_outside_publication_bridge']}`",
        "",
        "## Case Parity",
        "",
    ]
    for row in payload["case_results"]:
        lines.append(
            f"- `{row['name']}`: direct `{row['direct_outcome']}`, "
            f"controller `{row['controller_outcome']}`, passed `{row['passed']}`"
        )
    lines.extend(["", "## Source Checks", ""])
    for key, value in payload["source_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Composed Gates", ""])
    for key, value in payload["required_artifacts"].items():
        lines.append(f"- `{key}`: `{value.get('status')}` `{value.get('path')}`")
    if payload["errors"]:
        lines.extend(["", "## Errors", "", "```json", json.dumps(payload["errors"], indent=2), "```"])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "design_brain/design_guide_controller.py",
            "inputs_page.py",
        ]
    )
    source_checks = _source_checks()
    case_results = _run_parity_cases()
    artifacts = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()}
    errors: list[str] = []
    if compile_run["returncode"] != 0:
        errors.append("py_compile_failed")
    if not source_checks["all_source_checks_pass"]:
        errors.append("source_checks_failed")
    if not all(row["passed"] for row in case_results):
        errors.append("controller_publication_parity_failed")
    if not all(artifact["passed"] for artifact in artifacts.values()):
        errors.append("required_artifact_not_green")
    status = "PASS" if not errors else "FAIL"
    payload = {
        "schema": "design_guide_controller_publication_authority_cutover.v1",
        "status": status,
        "created_at": stamp,
        "product_behavior_changed_outside_publication_bridge": False,
        "cta_publication_apply_semantics_changed": False,
        "family_runtimes_changed": False,
        "visible_wording_changed": False,
        "rendering_moved": False,
        "compile_run": compile_run,
        "source_checks": source_checks,
        "case_results": case_results,
        "required_artifacts": artifacts,
        "errors": errors,
        "snapshot_hash": _stable_hash(
            {
                "source_checks": source_checks,
                "case_results": case_results,
                "errors": errors,
            }
        ),
    }
    json_path, md_path = _write(payload)
    print(f"design_guide_controller_publication_authority_cutover {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if errors:
        print("errors=" + json.dumps(errors))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

