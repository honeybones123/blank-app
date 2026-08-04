"""Proof-only readiness for moving compatibility/debug stamps behind controller.

This snapshot does not change product behaviour. It proves the remaining
compatibility/debug-only `_build_final_design_guide_publication(...)` callsites
in `inputs_page.py` can be represented from `DesignGuideController` response
surfaces before any helper is rewired.
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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

EXPECTED_COMPATIBILITY_HELPERS = {
    "_mark_compute_publication_evidence_a_class_compatibility_only": {
        "surface": "publication.evidence.compute_publication_evidence",
        "required_paths": [
            ("publication", "evidence", "compute_publication_evidence"),
            ("publication", "evidence", "compute_publication_evidence_hashes"),
            ("publication", "evidence", "compute_publication_evidence_hash"),
        ],
    },
    "_stamp_final_publication_resolver_identity_compatibility_proof": {
        "surface": "publication.cta + publication identity",
        "required_paths": [
            ("publication", "published_item_id"),
            ("publication", "selected_family"),
            ("publication", "cta", "action_type"),
            ("publication", "cta", "source_candidate_id"),
        ],
    },
    "_stamp_final_publication_resolution_metadata_compatibility_proof": {
        "surface": "publication.display + post_resolver_mutation_proof.resolver_projection",
        "required_paths": [
            ("publication", "display"),
            ("post_resolver_mutation_proof", "resolver_projection"),
            ("final_visible_resolution", "render_reason"),
        ],
    },
    "_stamp_final_publication_safe_low_util_replacement_compatibility_proof": {
        "surface": "publication cta/display/evidence + post_resolver projections",
        "required_paths": [
            ("publication", "cta"),
            ("publication", "display"),
            ("publication", "evidence"),
            ("post_resolver_mutation_proof", "resolver_projection"),
            ("post_resolver_mutation_proof", "selected_item_identity"),
        ],
    },
    "_stamp_final_publication_combined_cleanup_rescue_compatibility_proof": {
        "surface": "publication cta/display/evidence + post_resolver projections",
        "required_paths": [
            ("publication", "cta"),
            ("publication", "display"),
            ("publication", "evidence"),
            ("post_resolver_mutation_proof", "resolver_projection"),
            ("post_resolver_mutation_proof", "selected_item_identity"),
            ("final_visible_resolution", "render_reason"),
        ],
    },
    "_stamp_final_publication_post_click_exact_blocker_compatibility_proof": {
        "surface": "publication state + post_resolver blocker/evidence projections",
        "required_paths": [
            ("publication", "published_item_id"),
            ("publication", "post_click_design_guide_state"),
            ("post_resolver_mutation_proof", "blocker_projection"),
            ("post_resolver_mutation_proof", "evidence_projection"),
        ],
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


def _nested(value: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current.get(part)
    return current


def _function_direct_builds(source: str) -> dict[str, int]:
    tree = ast.parse(source)
    counts: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        count = 0
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                if child.func.id == "_build_final_design_guide_publication":
                    count += 1
        if count:
            counts[node.name] = count
    return counts


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _controller_sample() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_publication_authority,
    )

    response = run_design_guide_controller_publication_authority(
        {
            "item": {
                "title": "Synthetic controller compatibility proof",
                "family": "BENDING_FAIL_GOVERNS",
                "action_type": "apply",
                "candidate_id": "candidate-controller-compatibility",
                "post_click_design_guide_state": "synthetic_post_click_ready",
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply",
                    "candidate_id": "candidate-controller-compatibility",
                },
            },
            "debug": {
                "final_publication_verifier_payload": {},
                "post_click_design_guide_state": "synthetic_post_click_ready",
                "candidate_search_evidence": {"synthetic": True},
                "compute_publication_handoff_rebound_decision_proof": {
                    "raw_selected_item_identity": {"candidate_id": "candidate-controller-compatibility"},
                    "render_reason": "synthetic_controller_compatibility",
                    "state_fingerprint": "synthetic-state",
                    "raw_rebound_item_identity": {"candidate_id": "candidate-controller-compatibility"},
                },
            },
            "verifier_payload": {},
            "final_visible_resolution": {
                "render_reason": "synthetic_controller_compatibility",
                "presentation": {"tone": "action"},
            },
            "guidance_debug": {
                "candidate_search_evidence": {"synthetic": True},
                "exact_blockers_by_family": {"bending": {"blocked": False}},
            },
            "publication_reason": "synthetic_controller_compatibility",
            "source": "controller_compatibility_surface_readiness",
        }
    )
    return response.to_dict()


def _build_snapshot() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    input_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    controller_imports = _imported_modules(controller_source)
    direct_builds = _function_direct_builds(input_source)
    sample = _controller_sample()

    helper_readiness: dict[str, dict[str, Any]] = {}
    for helper, meta in EXPECTED_COMPATIBILITY_HELPERS.items():
        missing = [
            ".".join(path)
            for path in meta["required_paths"]
            if _nested(sample, path) in (None, {})
        ]
        helper_readiness[helper] = {
            "surface": meta["surface"],
            "direct_publication_build_count": direct_builds.get(helper, 0),
            "required_paths": [".".join(path) for path in meta["required_paths"]],
            "missing_paths": missing,
            "ready_for_controller_backed_compatibility_stamp": not missing
            and direct_builds.get(helper, 0) == 0,
        }

    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "inputs_page.py",
            "design_brain/design_guide_controller.py",
            "tools/verification/design_guide_remaining_direct_publication_build_audit.py",
        ]
    )
    direct_audit = _run(
        [sys.executable, "tools/verification/design_guide_remaining_direct_publication_build_audit.py"]
    )

    ownership_guards = {
        "controller_has_no_streamlit_import": "streamlit" not in controller_imports,
        "controller_has_no_apply_routing": "_record_rendered_design_guide_primary_apply_payload"
        not in controller_source,
        "controller_has_no_rendering": "design_guide_page" not in controller_source
        and "ui.design_guide_cards" not in controller_source,
        "controller_publication_authority_exists": "run_design_guide_controller_publication_authority"
        in controller_source,
        "controller_post_resolver_proof_exists": "post_resolver_mutation_proof" in controller_source,
    }
    errors: list[str] = []
    if not compile_run["passed"]:
        errors.append("py_compile_failed")
    if not direct_audit["passed"]:
        errors.append("remaining_direct_publication_build_audit_failed")
    if not all(ownership_guards.values()):
        errors.append("controller_ownership_guard_failed")
    if not all(row["ready_for_controller_backed_compatibility_stamp"] for row in helper_readiness.values()):
        errors.append("compatibility_helper_surface_not_ready")

    return {
        "schema": "design_guide_controller_compatibility_proof_surface_readiness.v1",
        "status": "PASS" if not errors else "FAIL",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "product_behavior_changed": False,
        "direct_publication_builds": direct_builds,
        "helper_readiness": helper_readiness,
        "ownership_guards": ownership_guards,
        "controller_sample_hash": _stable_hash(sample),
        "controller_sample_publication_hash": sample.get("publication_hash"),
        "controller_sample_controller_hash": sample.get("controller_hash"),
        "compile_run": compile_run,
        "direct_audit": direct_audit,
        "errors": errors,
        "ready_for_controller_backed_compatibility_stamps": not errors,
        "next_slice": (
            "Move one compatibility/debug stamp helper behind DesignGuideController, "
            "starting with resolver identity or resolution metadata."
        ),
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    stamp = snapshot["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_controller_compatibility_proof_surface_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_controller_compatibility_proof_surface_readiness_{stamp}.md"
    lines = [
        "# Design Guide Controller Compatibility Proof Surface Readiness",
        "",
        f"Result: **{snapshot['status']}**",
        "",
        f"Product behaviour changed: `{snapshot['product_behavior_changed']}`",
        f"Ready for controller-backed compatibility stamps: `{snapshot['ready_for_controller_backed_compatibility_stamps']}`",
        "",
        "## Helper Readiness",
        "",
        "| Helper | Direct builds | Surface | Missing paths | Ready |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for helper, row in snapshot["helper_readiness"].items():
        lines.append(
            f"| `{helper}` | {row['direct_publication_build_count']} | {row['surface']} | "
            f"`{', '.join(row['missing_paths']) or 'none'}` | "
            f"`{row['ready_for_controller_backed_compatibility_stamp']}` |"
        )
    lines.extend(
        [
            "",
            "## Ownership Guards",
            "",
        ]
    )
    for key, value in snapshot["ownership_guards"].items():
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
    print(f"design_guide_controller_compatibility_proof_surface_readiness {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["errors"]:
        print("errors=" + json.dumps(snapshot["errors"]))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
