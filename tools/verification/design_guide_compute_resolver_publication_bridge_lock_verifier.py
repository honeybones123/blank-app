"""Final lock verifier for the compute resolver/publication bridge.

This verifier composes the current compute handoff, publication boundary,
exact-blocker routes, and the two external Design Guide locks. Historical
recursive audit/snapshot chains are supporting diagnostics, not release gates.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
import os

try:
    from tools.verification.verification_run_manifest import current_run_artifact
except ModuleNotFoundError:
    from verification_run_manifest import current_run_artifact


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
ROUTE_COORDINATORS = ROOT / "inputs_page_modules" / "guidance_compute.py"
CURRENT_RUNTIME_FILES = (
    ROOT / "inputs_application" / "page_runtime" / "common.py",
    ROOT / "inputs_page_modules" / "design_guide" / "primary_apply_payload_recorder.py",
    ROOT / "inputs_page_modules" / "design_guide" / "primary_button_queue.py",
    ROOT / "inputs_page_modules" / "design_guide" / "render_coordinators.py",
)
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
DESIGN_GUIDE_CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

COMPOSED_GATES: tuple[dict[str, str], ...] = (
    {
        "id": "controller_compute_handoff_object",
        "script": "tools/verification/design_guide_controller_compute_handoff_object_snapshot.py",
        "artifact_prefix": "design_guide_controller_compute_handoff_object",
        "label": "Controller compute handoff object",
    },
    {
        "id": "final_publication_boundary",
        "script": "tools/verification/design_guide_final_publication_boundary_snapshot.py",
        "artifact_prefix": "design_guide_final_publication_boundary",
        "label": "Final publication boundary",
    },
    {
        "id": "active_action_exact_blocker_route",
        "script": "tools/verification/design_guide_active_action_post_click_exact_blocker_route_object_snapshot.py",
        "artifact_prefix": "design_guide_active_action_post_click_exact_blocker_route_object",
        "label": "Active-action exact-blocker route object",
    },
    {
        "id": "no_active_route",
        "script": "tools/verification/design_guide_no_active_low_shear_or_blocker_route_object_snapshot.py",
        "artifact_prefix": "design_guide_no_active_low_shear_or_blocker_route_object",
        "label": "No-active low-shear/blocker route object",
    },
    {
        "id": "design_guide_independence_lock",
        "script": "tools/verification/design_guide_independence_lock_verifier.py",
        "artifact_prefix": "design_guide_independence_lock",
        "label": "Design Guide independence lock",
    },
    {
        "id": "render_bridge_lock",
        "script": "tools/verification/design_guide_render_bridge_lock_verifier.py",
        "artifact_prefix": "design_guide_render_bridge_lock",
        "label": "Render bridge lock",
    },
)

EXTERNAL_LOCK_GATE_IDS = {
    "design_guide_independence_lock",
    "render_bridge_lock",
}
GATE_TIMEOUT_SEC = int(os.environ.get("DESIGN_GUIDE_COMPUTE_BRIDGE_GATE_TIMEOUT_SEC", "180"))

B_D_LIVE_GUARD_TOKENS: dict[str, tuple[str, ...]] = {
    "late_evidence_acceptance_condition": ("_late_evidence_acceptance", "late_evidence_acceptance"),
    "post_core_evidence_mismatch_condition": ("_post_core_mismatch", "post_core_evidence_mismatch"),
    "rebound_update_payload_summary_hash": (
        '_late_rebound_contract.get("updates")',
        "rebound_update_payload",
        "contract.get(\"updates\")",
    ),
    "rebound_contract_enabled_safety": (
        "_design_guide_button_contract_enabled(_late_rebound_contract)",
        "_controller_button_contract_enabled(contract)",
    ),
    "pre_resolver_collapsed_item_mutation": (
        "collapsed_guidance_items[0] = dict(_post_evidence_rebound)",
        "_post_mutation_collapsed_items = list(",
        "collapsed_guidance_items=list(collapsed_items)",
    ),
}

FORBIDDEN_FINAL_PUBLICATION_TOKENS = (
    "import inputs_page",
    "from inputs_page",
    "import streamlit",
    "st.session_state",
    "session_state",
    "render_html",
    "route_apply",
    "_queue_primary_design_guide_button_action",
    "_record_rendered_design_guide_primary_apply_payload",
    "design_guide_page.render_final_panel",
    "_design_guide_dashboard_card_html_from_render_model",
)

FORBIDDEN_TOKEN_EXCEPTIONS = {
    "session_state": ("stale_fresh_token_proof",),
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest(prefix: str) -> dict[str, Any]:
    if os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        path, snapshot = current_run_artifact(prefix)
        if path is None:
            return {"found": False, "path": None, "snapshot": {}, "passed": False, "current_run": True}
        return {"found": True, "path": str(path), "snapshot": snapshot, "passed": snapshot.get("status") == "PASS", "current_run": True}
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = artifacts[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "snapshot": {}, "passed": False, "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS",
    }


def _run_composed_gate(gate: dict[str, str]) -> dict[str, Any]:
    """Run one diagnostic and bind the lock to its freshly emitted artifact.

    Diagnostics are deliberately not canonical release gates. They execute
    serially inside this composed lock, without the outer run-manifest lookup,
    so each step can consume the immediately preceding fresh artifact. The
    canonical runner then hash-binds every child artifact referenced by this
    lock's result.
    """
    env = dict(os.environ)
    env.pop("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST", None)
    env.pop("DESIGN_BRAIN_VERIFICATION_RUN_ID", None)
    started_epoch = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, gate["script"]],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
            timeout=GATE_TIMEOUT_SEC,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "script": gate["script"],
            "returncode": None,
            "passed": False,
            "stdout_tail": str(exc.stdout or "").splitlines()[-12:],
            "stderr_tail": str(exc.stderr or "").splitlines()[-12:],
            "artifact": {
                "found": False,
                "path": None,
                "snapshot": {},
                "passed": False,
            },
            "timed_out": True,
        }

    artifact_path: Path | None = None
    for raw_line in proc.stdout.splitlines():
        line = raw_line.strip()
        candidate = ""
        if line.startswith("json="):
            candidate = line[5:].strip()
        elif line.startswith("JSON:"):
            candidate = line[5:].strip()
        if not candidate:
            continue
        path = Path(candidate)
        if not path.is_absolute():
            path = ROOT / path
        if (
            path.exists()
            and path.name.startswith(f"{gate['artifact_prefix']}_")
            and path.stat().st_mtime >= started_epoch
        ):
            artifact_path = path

    snapshot: dict[str, Any] = {}
    if artifact_path is not None:
        try:
            loaded = json.loads(artifact_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                snapshot = loaded
        except (OSError, json.JSONDecodeError):
            snapshot = {}
    artifact_passed = snapshot.get("status") == "PASS"
    return {
        "script": gate["script"],
        "returncode": proc.returncode,
        "passed": proc.returncode == 0 and artifact_passed,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
        "artifact": {
            "found": artifact_path is not None,
            "path": str(artifact_path) if artifact_path is not None else None,
            "snapshot": snapshot,
            "passed": artifact_passed,
        },
        "timed_out": False,
    }


def _source_guards() -> dict[str, bool]:
    input_source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (INPUTS_PAGE, ROUTE_COORDINATORS, *CURRENT_RUNTIME_FILES)
        if path.exists()
    )
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    controller_source = DESIGN_GUIDE_CONTROLLER.read_text(encoding="utf-8")
    renderer_source = (ROOT / "ui" / "final_design_guide_card.py").read_text(
        encoding="utf-8", errors="replace"
    )
    b_d_live_source = input_source + "\n" + controller_source
    forbidden: dict[str, bool] = {}
    for token in FORBIDDEN_FINAL_PUBLICATION_TOKENS:
        scrubbed = final_source
        for allowed in FORBIDDEN_TOKEN_EXCEPTIONS.get(token, ()):
            scrubbed = scrubbed.replace(allowed, "")
        forbidden[f"final_publication_forbidden_absent::{token}"] = token not in scrubbed
    return {
        "final_publication_object_exists": "class FinalDesignGuidePublication" in final_source,
        "final_publication_evidence_has_compute_surface": "compute_publication_evidence:" in final_source,
        "final_publication_evidence_has_compute_hash": "compute_publication_evidence_hash:" in final_source,
        "a_class_rows_removed_or_compatibility_stamped": (
            (
                "_mark_compute_publication_evidence_a_class_compatibility_only" not in input_source
                and "final_publication_compute_a_class_evidence_rows" not in input_source
            )
            or (
                "_mark_compute_publication_evidence_a_class_compatibility_only" in input_source
                and "final_publication_compute_a_class_evidence_rows" in input_source
            )
        ),
        "compute_debug_rows_removed_or_compatibility_stamped": (
            (
                "_mark_compute_debug_restamp_metadata_compatibility_only" not in input_source
                and "final_publication_compute_debug_restamp_metadata_rows" not in input_source
            )
            or (
                "_mark_compute_debug_restamp_metadata_compatibility_only" in input_source
                and "final_publication_compute_debug_restamp_metadata_rows" in input_source
            )
        ),
        "b_d_guard_tokens_live": all(
            any(token in b_d_live_source for token in alternatives)
            for alternatives in B_D_LIVE_GUARD_TOKENS.values()
        ),
        "apply_routing_still_page_owned": (
            "def _record_rendered_design_guide_primary_apply_payload(" in input_source
            and "_record_rendered_design_guide_primary_apply_payload" not in final_source
        ),
        "cta_rendering_still_page_owned": (
            "def render_final_design_guide_card_html(" in renderer_source
            and "render_final_design_guide_card_html(" not in final_source
        ),
        "session_ui_not_moved_to_design_brain": (
            "streamlit" not in final_source and "st.session_state" not in final_source
        ),
        **forbidden,
    }


def _direct_artifact_guards(gate_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    handoff = dict(gate_results["controller_compute_handoff_object"]["artifact"].get("snapshot") or {})
    boundary = dict(gate_results["final_publication_boundary"]["artifact"].get("snapshot") or {})
    active_route = dict(gate_results["active_action_exact_blocker_route"]["artifact"].get("snapshot") or {})
    no_active_route = dict(gate_results["no_active_route"]["artifact"].get("snapshot") or {})
    handoff_checks = dict(handoff.get("checks") or {})
    active_checks = dict(active_route.get("checks") or {})
    no_active_checks = dict(no_active_route.get("checks") or {})

    return {
        "handoff_contract_complete": bool(handoff_checks) and all(handoff_checks.values()),
        "handoff_covers_all_blocking_fields": handoff_checks.get("all_blocking_fields_covered") is True,
        "handoff_has_blocker_evidence": handoff_checks.get("blocker_evidence_surface_present") is True,
        "handoff_excludes_page_ui_session_apply": handoff_checks.get("no_page_ui_session_apply_imports") is True,
        "handoff_is_trace_only": handoff_checks.get("trace_only_not_product_driving") is True,
        "final_publication_boundary_stable": (
            boundary.get("status") == "PASS"
            and boundary.get("product_behavior_changed") is False
            and not boundary.get("failures")
            and not boundary.get("preservation_failures")
            and not boundary.get("product_driving_failures")
            and not boundary.get("stable_hash_failures")
            and not boundary.get("forbidden_final_publication_imports")
        ),
        "active_exact_blocker_route_complete": bool(active_checks) and all(active_checks.values()),
        "active_exact_blocker_preserves_engineering_cta_family_wording": all(
            active_checks.get(key) is True
            for key in (
                "engineering_behavior_unchanged",
                "cta_apply_semantics_unchanged",
                "family_runtime_unchanged",
                "visible_wording_unchanged",
                "product_behavior_unchanged",
            )
        ),
        "no_active_route_complete": bool(no_active_checks) and all(no_active_checks.values()),
        "no_active_route_preserves_engineering_cta_family_wording": all(
            no_active_checks.get(key) is True
            for key in (
                "engineering_behavior_unchanged",
                "cta_apply_semantics_unchanged",
                "family_runtime_unchanged",
                "visible_wording_unchanged",
                "product_behavior_unchanged",
            )
        ),
        "external_independence_lock_current": gate_results["design_guide_independence_lock"]["artifact_passed"],
        "external_render_bridge_lock_current": gate_results["render_bridge_lock"]["artifact_passed"],
        "lock_status": "Design Guide compute resolver/publication bridge locked",
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Compute Resolver/Publication Bridge Lock Verifier",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Lock status: `{payload['lock_status']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        f"- Compute handoff contract complete: `{payload['direct_proof']['handoff_contract_complete']}`",
        f"- Final publication boundary stable: `{payload['direct_proof']['final_publication_boundary_stable']}`",
        f"- Active exact-blocker route complete: `{payload['direct_proof']['active_exact_blocker_route_complete']}`",
        f"- No-active route complete: `{payload['direct_proof']['no_active_route_complete']}`",
        "",
        "## Composed Gates",
        "",
        "| Gate | Script | PASS | Artifact |",
        "| --- | --- | --- | --- |",
    ]
    for gate_id, result in payload["gates"].items():
        lines.append(
            "| `{gate}` | `{script}` | `{passed}` | {artifact} |".format(
                gate=_escape_md(gate_id),
                script=_escape_md(result["script"]),
                passed=result["passed"] and result["artifact_passed"],
                artifact=_escape_md(result.get("artifact_path")),
            )
        )
    lines.extend(["", "## Direct Proof", "", "| Check | PASS |", "| --- | --- |"])
    for key, value in payload["direct_proof"].items():
        if isinstance(value, bool):
            lines.append(f"| `{_escape_md(key)}` | `{value}` |")
    lines.extend(["", "## Source Guards", "", "| Check | PASS |", "| --- | --- |"])
    for key, value in payload["source_guards"].items():
        lines.append(f"| `{_escape_md(key)}` | `{value}` |")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Recommendation", "", payload["recommended_next_slice"]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    gate_results: dict[str, dict[str, Any]] = {}
    for gate in COMPOSED_GATES:
        if gate["id"] in EXTERNAL_LOCK_GATE_IDS:
            artifact = _latest(gate["artifact_prefix"])
            run = {
                "script": gate["script"],
                "returncode": 0 if artifact.get("passed") is True else 1,
                "passed": artifact.get("passed") is True,
                "stdout_tail": [],
                "stderr_tail": [],
                "timed_out": False,
            }
        else:
            print(f"running {gate['id']} ...", flush=True)
            run = _run_composed_gate(gate)
            artifact = run["artifact"]
            print(
                f"finished {gate['id']} passed={run['passed']} "
                f"artifact={artifact.get('path')}",
                flush=True,
            )
        gate_results[gate["id"]] = {
            "script": gate["script"],
            "returncode": run["returncode"],
            "passed": run["passed"],
            "stdout_tail": run["stdout_tail"],
            "stderr_tail": run["stderr_tail"],
            "label": gate["label"],
            "artifact": artifact,
            "artifact_path": artifact.get("path"),
            "artifact_passed": artifact.get("passed") is True,
            "executed_in_this_run": gate["id"] not in EXTERNAL_LOCK_GATE_IDS,
        }

    source_guards = _source_guards()
    direct_proof = _direct_artifact_guards(gate_results)

    failures: list[str] = []
    for gate_id, result in gate_results.items():
        if not result["passed"] or not result["artifact_passed"]:
            failures.append(f"{gate_id}_not_passed")
    for key, value in source_guards.items():
        if value is not True:
            failures.append(f"source_guard_failed::{key}")
    for key, value in direct_proof.items():
        if isinstance(value, bool) and value is not True:
            failures.append(f"direct_proof_failed::{key}")

    payload = {
        "schema": "design_guide_compute_resolver_publication_bridge_lock_verifier.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "composition_mode": "bounded_current_boundary_checks_plus_current_external_locks",
        "lock_status": (
            "Design Guide compute resolver/publication bridge locked"
            if not failures
            else "Design Guide compute resolver/publication bridge not locked"
        ),
        "gates": {
            gate_id: {
                "script": result["script"],
                "returncode": result["returncode"],
                "passed": result["passed"],
                "artifact_path": result["artifact_path"],
                "artifact_passed": result["artifact_passed"],
                "executed_in_this_run": result["executed_in_this_run"],
                "stdout_tail": result["stdout_tail"],
                "stderr_tail": result["stderr_tail"],
            }
            for gate_id, result in gate_results.items()
        },
        "source_guards": source_guards,
        "direct_proof": direct_proof,
        "lock_hash": _stable_hash(
            {
                "gates": {
                    gate_id: result["artifact_path"]
                    for gate_id, result in gate_results.items()
                },
                "source_guards": source_guards,
                "direct_proof": direct_proof,
            }
        ),
        "recommended_next_slice": (
            "Run the canonical live family and browser gates. The recursive historical compute "
            "diagnostic chain is no longer part of release-gate execution."
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_resolver_publication_bridge_lock_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_resolver_publication_bridge_lock_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_compute_resolver_publication_bridge_lock_verifier {payload['status']}")
    print(payload["lock_status"])
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
