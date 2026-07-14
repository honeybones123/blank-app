"""Verify combined cleanup rescue compatibility proof consumes DesignGuideController."""

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
HELPER_NAME = "_stamp_final_publication_combined_cleanup_rescue_compatibility_proof"


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


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : int(getattr(node, "end_lineno", node.lineno))])
    return ""


def _direct_publication_build_count(source: str) -> int:
    tree = ast.parse(source)
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_build_final_design_guide_publication"
    )


def _controller_sample() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        DesignGuideControllerRequest,
        run_design_guide_controller_publication_authority,
    )

    response = run_design_guide_controller_publication_authority(
        DesignGuideControllerRequest(
            item={
                "title": "Combined cleanup rescue compatibility",
                "family": "COMBINED_OVERDESIGN_GOVERNS",
                "action_type": "cleanup",
                "candidate_id": "candidate-combined-rescue",
                "button_contract": {"enabled": True, "action_type": "cleanup"},
            },
            debug={"final_publication_verifier_payload": {}},
            verifier_payload={},
            final_visible_resolution={
                "render_reason": "combined_rescue_cutover",
                "presentation": {"tone": "pass", "status": "PASS"},
            },
            guidance_debug={},
            publication_reason="combined_rescue_cutover",
            source="combined_rescue_cutover",
        )
    )
    publication = dict(response.publication or {})
    proof = dict(response.post_resolver_mutation_proof or {})
    rescue = {
        "published_item_id": publication.get("published_item_id"),
        "selected_family": publication.get("selected_family"),
        "outcome_state": publication.get("outcome_state"),
        "cta_hash": _stable_hash(publication.get("cta") or {}),
        "display_hash": _stable_hash(publication.get("display") or {}),
        "evidence_hash": _stable_hash(publication.get("evidence") or {}),
        "resolver_projection_hash": _stable_hash(proof.get("resolver_projection") or {}),
        "selected_item_identity_hash": _stable_hash(proof.get("selected_item_identity") or {}),
        "publication_hash": response.publication_hash,
    }
    return {
        "controller_hash": response.controller_hash,
        "publication_hash": response.publication_hash,
        "rescue": rescue,
        "rescue_hash": _stable_hash(rescue),
    }


def _build_snapshot() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    helper_source = _function_source(source, HELPER_NAME)
    sample_a = _controller_sample()
    sample_b = _controller_sample()
    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "inputs_page.py",
            "design_brain/design_guide_controller.py",
        ]
    )
    direct_audit = _run(
        [sys.executable, "tools/verification/design_guide_remaining_direct_publication_build_audit.py"]
    )
    checks = {
        "helper_present": bool(helper_source),
        "helper_uses_controller": "_run_design_guide_controller_publication_authority(" in helper_source,
        "helper_uses_controller_request": "_DesignGuideControllerRequest(" in helper_source,
        "helper_consumes_controller_publication": "controller_response.publication" in helper_source,
        "helper_consumes_post_resolver_proof": "controller_response.post_resolver_mutation_proof" in helper_source,
        "helper_no_direct_publication_build": "_build_final_design_guide_publication(" not in helper_source,
        "helper_no_direct_post_resolver_build": "_build_final_design_guide_post_resolver_mutation_proof("
        not in helper_source,
        "compatibility_stamp_preserved": "final_publication_combined_cleanup_rescue_compatibility_proofs"
        in helper_source,
        "product_driving_false_preserved": '"product_driving": False' in helper_source,
        "render_driving_false_preserved": '"render_driving": False' in helper_source,
        "rescue_hash_stable": sample_a["rescue_hash"] == sample_b["rescue_hash"],
        "publication_hash_stable": sample_a["publication_hash"] == sample_b["publication_hash"],
        "direct_publication_build_count_now": _direct_publication_build_count(source),
    }
    errors: list[str] = []
    if not compile_run["passed"]:
        errors.append("py_compile_failed")
    if not direct_audit["passed"]:
        errors.append("remaining_direct_publication_build_audit_failed")
    if not all(value for key, value in checks.items() if key != "direct_publication_build_count_now"):
        errors.append("source_or_hash_check_failed")
    if checks["direct_publication_build_count_now"] != 0:
        errors.append("unexpected_direct_publication_build_count")
    return {
        "schema": "design_guide_controller_combined_rescue_compatibility_cutover.v1",
        "status": "PASS" if not errors else "FAIL",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "product_behavior_changed": False,
        "helper": HELPER_NAME,
        "checks": checks,
        "sample": sample_a,
        "compile_run": compile_run,
        "direct_audit": direct_audit,
        "errors": errors,
        "next_slice": "Move post-click exact blocker compatibility proof behind DesignGuideController.",
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    stamp = snapshot["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_controller_combined_rescue_compatibility_cutover_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_controller_combined_rescue_compatibility_cutover_{stamp}.md"
    lines = [
        "# Design Guide Controller Combined Rescue Compatibility Cutover",
        "",
        f"Result: **{snapshot['status']}**",
        "",
        f"Product behaviour changed: `{snapshot['product_behavior_changed']}`",
        f"Direct publication build count now: `{snapshot['checks']['direct_publication_build_count_now']}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in snapshot["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Slice", "", snapshot["next_slice"], ""])
    if snapshot["errors"]:
        lines.extend(["## Errors", "", "```json", json.dumps(snapshot["errors"], indent=2), "```", ""])
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    snapshot = _build_snapshot()
    json_path, md_path = _write(snapshot)
    print(f"design_guide_controller_combined_rescue_compatibility_cutover {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["errors"]:
        print("errors=" + json.dumps(snapshot["errors"]))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

