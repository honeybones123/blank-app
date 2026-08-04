"""Audit remaining direct FinalDesignGuidePublication builds in inputs_page.py.

Audit-only. This classifies every remaining direct
`_build_final_design_guide_publication(...)` call after the controller
publication/collapsed bridge cutovers. It does not change behaviour.
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
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


CLASSIFICATION_BY_FUNCTION: dict[str, dict[str, Any]] = {
    "_stamp_final_publication_post_resolver_mutation_proof": {
        "classification": "A. should move behind DesignGuideController proof surface",
        "role": "trace-only post-resolver mutation proof",
        "reason": (
            "Controller already builds post_resolver_mutation_proof; page helper can consume "
            "controller response instead of rebuilding publication directly."
        ),
        "next_step": "Move this helper to controller response first; verify no render/apply/session ownership moves.",
        "priority": 1,
    },
    "_mark_compute_publication_evidence_a_class_compatibility_only": {
        "classification": "B. compatibility/debug-only evidence stamp",
        "role": "compute publication evidence compatibility row",
        "reason": (
            "This is proof/debug compatibility data keyed by publication evidence; it should not "
            "drive product output and can move later after post-resolver proof is controller-backed."
        ),
        "next_step": "Keep for now; later consume controller publication evidence hash.",
        "priority": 3,
    },
    "_stamp_final_publication_resolver_identity_compatibility_proof": {
        "classification": "B. compatibility/debug-only evidence stamp",
        "role": "resolver identity compatibility proof",
        "reason": "Identity rows are already narrowed compatibility proof and cannot override publication.",
        "next_step": "Keep for now; later use controller publication parity payload.",
        "priority": 3,
    },
    "_stamp_final_publication_resolution_metadata_compatibility_proof": {
        "classification": "B. compatibility/debug-only evidence stamp",
        "role": "final visible resolution metadata compatibility proof",
        "reason": "Metadata rows are narrowed compatibility proof and not live publication authority.",
        "next_step": "Keep for now; later use controller post-resolver proof.",
        "priority": 3,
    },
    "_stamp_final_publication_safe_low_util_replacement_compatibility_proof": {
        "classification": "B. compatibility/debug-only evidence stamp",
        "role": "safe-low-util replacement compatibility proof",
        "reason": "Replacement row is proof-only compatibility after prior narrowing.",
        "next_step": "Keep for now; later use controller post-resolver proof.",
        "priority": 3,
    },
    "_stamp_final_publication_combined_cleanup_rescue_compatibility_proof": {
        "classification": "B. compatibility/debug-only evidence stamp",
        "role": "combined cleanup rescue compatibility proof",
        "reason": "Rescue row is proof-only compatibility after prior narrowing.",
        "next_step": "Keep for now; later use controller post-resolver proof.",
        "priority": 3,
    },
    "_stamp_final_publication_post_click_exact_blocker_compatibility_proof": {
        "classification": "B. compatibility/debug-only evidence stamp",
        "role": "post-click exact blocker compatibility proof",
        "reason": "Exact-blocker row is proof-only compatibility after prior narrowing.",
        "next_step": "Keep for now; later use controller post-resolver proof.",
        "priority": 3,
    },
    "_stamp_final_publication_render_item_consumer_proof": {
        "classification": "B. compatibility/debug-only evidence stamp",
        "role": "render item consumer proof",
        "reason": (
            "The helper rebuilds FinalDesignGuidePublication only to stamp render-item "
            "consumer proof into guidance_debug, with explicit non-product, non-render, "
            "non-apply, and non-session-driving markers."
        ),
        "next_step": (
            "Keep for now; later consume controller publication/render-item proof payload "
            "instead of rebuilding publication in inputs_page.py."
        ),
        "priority": 2,
    },
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "passed": proc.returncode == 0,
    }


def _function_source(lines: list[str], node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    end = int(getattr(node, "end_lineno", node.lineno))
    return "\n".join(lines[node.lineno - 1 : end])


def _find_call_records(source: str) -> list[dict[str, Any]]:
    tree = ast.parse(source)
    lines = source.splitlines()
    function_nodes = {
        node: _function_source(lines, node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    records: list[dict[str, Any]] = []
    for fn, body in function_nodes.items():
        for child in ast.walk(fn):
            if isinstance(child, ast.Call):
                callee = child.func
                name = callee.id if isinstance(callee, ast.Name) else None
                if name == "_build_final_design_guide_publication":
                    meta = dict(CLASSIFICATION_BY_FUNCTION.get(fn.name) or {})
                    records.append(
                        {
                            "function": fn.name,
                            "line": int(child.lineno),
                            "classification": meta.get("classification", "C. unknown / needs ownership proof"),
                            "role": meta.get("role", "unknown"),
                            "reason": meta.get("reason", "No classification rule recorded."),
                            "next_step": meta.get("next_step", "Audit manually before moving."),
                            "priority": meta.get("priority", 9),
                            "proof_only_marker_present": "proof_only" in body,
                            "compatibility_only_marker_present": "compatibility_only" in body,
                            "product_driving_false_present": '"product_driving": False' in body
                            or "_product_driving\"] = False" in body
                            or "product_driving\"] = False" in body,
                            "render_driving_false_present": '"render_driving": False' in body
                            or "render_driving\"] = False" in body,
                            "apply_driving_false_present": '"apply_driving": False' in body
                            or "apply_driving\"] = False" in body,
                            "session_driving_false_present": '"session_driving": False' in body
                            or "session_driving\"] = False" in body,
                        }
                    )
    return sorted(records, key=lambda row: (row["priority"], row["line"]))


def _source_checks(source: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "direct_build_count": len(records),
        "unknown_count": sum(1 for row in records if row["classification"].startswith("C.")),
        "live_bridge_direct_builds_removed": all(
            fn not in {row["function"] for row in records}
            for fn in (
                "_collapsed_guidance_item_from_final_publication_authority",
                "_final_visible_resolution_from_final_publication_authority",
            )
        ),
        "controller_authority_present": "_run_design_guide_controller_publication_authority(" in source,
        "cta_apply_render_still_page_owned": all(
            token in source
            for token in (
                "_stamp_final_publication_cta_authority",
                "_record_rendered_design_guide_primary_apply_payload",
                "design_guide_page.render_final_panel",
            )
        ),
    }


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime)
    if not paths:
        return {"found": False, "status": None, "path": None, "passed": False}
    path = paths[-1]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "passed": False, "error": str(exc)}
    status = data.get("status") or data.get("result") or data.get("lock_status")
    return {
        "found": True,
        "status": status,
        "path": str(path),
        "path_name": path.name,
        "passed": status == "PASS" or str(status or "").endswith("locked"),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_remaining_direct_publication_build_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_remaining_direct_publication_build_audit_{stamp}.md"
    lines = [
        "# Design Guide Remaining Direct Publication Build Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Direct build count: `{payload['source_checks']['direct_build_count']}`",
        f"Unknown count: `{payload['source_checks']['unknown_count']}`",
        "",
        "## Classification",
        "",
        "| Function | Line | Classification | Role | Next step |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for row in payload["records"]:
        lines.append(
            f"| `{row['function']}` | {row['line']} | {row['classification']} | {row['role']} | {row['next_step']} |"
        )
    lines.extend(["", "## Recommendation", "", payload["recommendation"], ""])
    if payload["errors"]:
        lines.extend(["## Errors", "", "```json", json.dumps(payload["errors"], indent=2), "```", ""])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    records = _find_call_records(source)
    checks = _source_checks(source, records)
    compile_run = _run([sys.executable, "-m", "py_compile", "inputs_page.py", "design_brain/design_guide_controller.py"])
    lock_artifacts = {
        "controller_publication_authority_cutover": _latest("design_guide_controller_publication_authority_cutover"),
        "controller_collapsed_replacement_authority_cutover": _latest(
            "design_guide_controller_collapsed_replacement_authority_cutover"
        ),
        "design_guide_independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_resolver_publication_bridge_lock": _latest(
            "design_guide_compute_resolver_publication_bridge_lock"
        ),
    }
    errors: list[str] = []
    if not compile_run["passed"]:
        errors.append("py_compile_failed")
    if checks["unknown_count"]:
        errors.append("unknown_direct_publication_builds")
    if not checks["live_bridge_direct_builds_removed"]:
        errors.append("live_bridge_direct_build_still_present")
    if not checks["controller_authority_present"]:
        errors.append("controller_authority_not_present")
    if not checks["cta_apply_render_still_page_owned"]:
        errors.append("page_owned_cta_apply_render_missing")
    if not all(item["passed"] for item in lock_artifacts.values()):
        errors.append("required_lock_artifact_not_green")
    status = "PASS" if not errors else "FAIL"
    priority_one_records = [row for row in records if int(row.get("priority") or 9) == 1]
    if priority_one_records:
        recommendation = (
            "Next narrow move: convert `_stamp_final_publication_post_resolver_mutation_proof(...)` "
            "to consume `DesignGuideController.publication_authority` / controller post-resolver proof. "
            "Leave the six compatibility/debug evidence stamps alone until that proof surface is moved."
        )
    else:
        recommendation = (
            "No priority-1 direct publication builds remain. The remaining direct builds are "
            "compatibility/debug evidence stamps; keep them for now or move them behind a "
            "controller compatibility-proof surface one family of stamps at a time."
        )
    payload = {
        "schema": "design_guide_remaining_direct_publication_build_audit.v1",
        "status": status,
        "created_at": stamp,
        "product_behavior_changed": False,
        "records": records,
        "priority_one_records": priority_one_records,
        "source_checks": checks,
        "compile_run": compile_run,
        "lock_artifacts": lock_artifacts,
        "recommendation": recommendation,
        "errors": errors,
        "audit_hash": _stable_hash({"records": records, "checks": checks, "errors": errors}),
    }
    json_path, md_path = _write(payload)
    print(f"design_guide_remaining_direct_publication_build_audit {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if errors:
        print("errors=" + json.dumps(errors))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
