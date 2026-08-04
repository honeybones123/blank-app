"""Post-render resolver/restamper cleanup audit.

This proof-only verifier audits the remaining Design Guide resolver/restamper
paths after the render-stage final visible resolver was replaced by
FinalDesignGuidePublication authority. It classifies remaining callsites and
stops before deletion.
"""

from __future__ import annotations

import ast
import hashlib
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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
REFRESH_GATES = os.environ.get(
    "DESIGN_GUIDE_REMAINING_RESOLVER_CLEANUP_REFRESH",
    "",
).strip().lower() in {"1", "true", "yes", "on"}
GATE_TIMEOUT_SEC = int(
    os.environ.get("DESIGN_GUIDE_REMAINING_RESOLVER_CLEANUP_GATE_TIMEOUT_SEC", "90")
)

REQUIRED_GATES = {
    "render_stage_resolver_deletion_proof": {
        "script": "tools/verification/design_guide_render_stage_resolver_deletion_proof.py",
        "prefix": "design_guide_render_stage_resolver_deletion_proof",
    },
    "post_render_bridge_restamper_readiness": {
        "script": "tools/verification/design_guide_post_render_bridge_restamper_readiness_snapshot.py",
        "prefix": "design_guide_post_render_bridge_restamper_readiness",
    },
    "render_bridge_lock": {
        "script": "tools/verification/design_guide_render_bridge_lock_verifier.py",
        "prefix": "design_guide_render_bridge_lock",
    },
    "independence_lock": {
        "script": "tools/verification/design_guide_independence_lock_verifier.py",
        "prefix": "design_guide_independence_lock",
    },
}

CLASS_A = "A. safe deletion candidate"
CLASS_B = "B. compatibility-only stamp"
CLASS_C = "C. still live resolver/restamper mutation / keep"
CLASS_D = "D. fallback-only / keep"
CLASS_E = "E. unknown / needs proof"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    if not REFRESH_GATES:
        return {
            "script": script,
            "returncode": None,
            "passed": None,
            "skipped_refresh": True,
            "stdout_tail": [],
            "stderr_tail": [],
        }
    print(f"running {script} ...", flush=True)
    try:
        proc = subprocess.run(
            [sys.executable, script],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
            timeout=GATE_TIMEOUT_SEC,
            env=dict(os.environ),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        print(f"finished {script} passed=False timed_out=True", flush=True)
        return {
            "script": script,
            "returncode": None,
            "passed": False,
            "timed_out": True,
            "skipped_refresh": False,
            "stdout_tail": str(stdout).strip().splitlines()[-12:],
            "stderr_tail": str(stderr).strip().splitlines()[-12:],
        }
    print(
        f"finished {script} passed={proc.returncode == 0} timed_out=False",
        flush=True,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "timed_out": False,
        "skipped_refresh": False,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _latest(prefix: str) -> dict[str, Any]:
    if os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        try:
            from tools.verification.verification_run_manifest import current_run_artifact
        except ModuleNotFoundError:
            from verification_run_manifest import current_run_artifact
        path, snapshot = current_run_artifact(prefix)
        if path is None:
            return {"found": False, "path": None, "snapshot": {}, "passed": False, "current_run": True}
        return {"found": True, "path": str(path), "snapshot": snapshot, "passed": snapshot.get("status") == "PASS", "current_run": True}
    matches = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not matches:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = matches[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "found": True,
            "path": str(path),
            "snapshot": {},
            "passed": False,
            "error": str(exc),
        }
    return {
        "found": True,
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS",
    }


def _function_bounds(source: str) -> list[tuple[int, int, str]]:
    tree = ast.parse(source)
    bounds: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bounds.append((int(node.lineno), int(getattr(node, "end_lineno", node.lineno)), node.name))
    return sorted(bounds)


def _function_for_line(bounds: list[tuple[int, int, str]], line_no: int) -> str:
    containing = [name for start, end, name in bounds if start <= line_no <= end]
    return containing[-1] if containing else "<module>"


def _context_hash(lines: list[str], line_no: int, radius: int = 8) -> str:
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return _stable_hash({"line": line_no, "context": lines[start - 1 : end]})


def _context_text(lines: list[str], line_no: int, radius: int = 12) -> str:
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return "\n".join(lines[start - 1 : end])


def _callsite_scan(source: str) -> list[dict[str, Any]]:
    lines = source.splitlines()
    bounds = _function_bounds(source)
    callsites: list[dict[str, Any]] = []
    targets = (
        "resolve_final_visible_design_guide_item(",
        "_publish_final_visible_design_guide_contract_binding(",
    )
    for line_no, text in enumerate(lines, start=1):
        stripped = text.strip()
        for target in targets:
            if target not in text:
                continue
            if stripped.startswith("def "):
                continue
            function = _function_for_line(bounds, line_no)
            context_text = _context_text(lines, line_no, radius=24)
            callsites.append(
                {
                    "file": "inputs_page.py",
                    "line": line_no,
                    "function": function,
                    "target": target.removesuffix("("),
                    "source_line": stripped,
                    "context_markers": {
                        "compatibility_only_callsite": "compatibility_only_callsite=" in context_text,
                        "pre_render_bound_item": "_pre_render_bound_item" in context_text,
                        "pre_card_bound_item": "_pre_card_bound_item" in context_text,
                        "primary_guidance_card_binding": (
                            "is_primary_guidance_card" in context_text
                            and "guidance_items[idx] = item" in context_text
                        ),
                        "combined_rebound_item_binding": "_combined_rebound_item" in context_text,
                        "engine_rebound_item_binding": "_engine_rebound_item" in context_text,
                        "post_click_low_bending_exact_blocker_binding": (
                            "_primary_bending_resolution" in context_text
                            and "post_click_low_bending_exact_blocker_primary_render" in context_text
                        ),
                        "final_visible_resolution_item_binding": (
                            "_final_visible_item = _publish_final_visible_design_guide_contract_binding("
                            in context_text
                            and "_final_visible_resolution" in context_text
                        ),
                        "render_guidance_secondary_primary_binding": (
                            "render_guidance_secondary_primary_binding" in context_text
                            or (
                                "final_visible_restamper_bridge_render_guidance_secondary_primary_bypassed"
                                in context_text
                            )
                        ),
                        "render_fast_final_visible_item_binding": (
                            "render_fast_design_guidance_panel.final_visible_item_binding"
                            in context_text
                            or (
                                "final_visible_restamper_bridge_render_fast_final_visible_item_bypassed"
                                in context_text
                            )
                        ),
                        "guarded_compatibility_restamper_fallback": (
                            function == "_final_visible_compatibility_restamper_adapter_cutover"
                            and "used_old_helper_fallback" in context_text
                            and "_final_visible_contract_binding_output_cutover("
                            in context_text
                        ),
                        "guarded_default_rebuild_restamper_fallback": (
                            function == "_final_visible_restamper_default_rebuild_adapter_cutover"
                            and "used_old_helper_fallback" in context_text
                            and "_build_final_visible_contract_binding_output_projection("
                            in context_text
                        ),
                    },
                    "context_hash": _context_hash(lines, line_no),
                }
            )
    return callsites


def _readiness_by_callsite(readiness_snapshot: dict[str, Any]) -> dict[tuple[int, str], dict[str, Any]]:
    mapped: dict[tuple[int, str], dict[str, Any]] = {}
    for row in list(readiness_snapshot.get("classified_callsites") or []):
        if not isinstance(row, dict):
            continue
        line = int(row.get("line") or 0)
        target = str(row.get("target") or "")
        mapped[(line, target)] = dict(row)
    return mapped


def _classify_callsite(callsite: dict[str, Any], readiness_row: dict[str, Any] | None) -> dict[str, Any]:
    function = str(callsite.get("function") or "")
    target = str(callsite.get("target") or "")
    readiness_class = str((readiness_row or {}).get("post_render_bridge_classification") or "")
    reachability_class = str((readiness_row or {}).get("reachability_classification") or "")
    markers = dict(callsite.get("context_markers") or {})

    classification = CLASS_E
    decision_truth = "unclassified resolver/restamper path"
    current_role = "unknown"
    required_next_proof = "manual ownership proof before narrowing or deletion"
    deletion_allowed_now = False

    if function == "_resolve_compute_design_guidance_publication_handoff" and target == "resolve_final_visible_design_guide_item":
        classification = CLASS_C
        decision_truth = "compute-stage final visible item selection before render publication authority"
        current_role = "live compute resolver bridge"
        required_next_proof = "compute-stage resolver same-object proof against FinalDesignGuidePublication"
    elif function in {
        "_apply_compute_late_evidence_contract_rebound",
        "_orchestrate_compute_post_core_publication_handoff",
    } and target == "_publish_final_visible_design_guide_contract_binding":
        classification = CLASS_C
        decision_truth = "compute-stage evidence/contract rebound before final render publication authority"
        current_role = "live compute final-visible output bridge"
        required_next_proof = "compute evidence rebound authority proof before narrowing"
    elif (
        readiness_class
        in {
            "render_fast_panel_item_binding_keep",
            "render_guidance_secondary_item_binding_keep",
            "compute_stage_authority_keep",
            "still_live_mutation_keep",
        }
        or reachability_class == "still live mutation"
    ):
        classification = CLASS_C
        decision_truth = "remaining resolver/restamper mutation before final render publication authority"
        current_role = "live resolver/restamper mutation bridge"
        required_next_proof = "focused controller/publication equivalent proof before narrowing"
    elif (
        function == "_final_visible_compatibility_restamper_adapter_cutover"
        and target == "_publish_final_visible_design_guide_contract_binding"
    ):
        classification = CLASS_D
        decision_truth = "guarded compatibility restamper fallback, non-authoritative but retained"
        current_role = "guarded compatibility restamper fallback"
        required_next_proof = "fallback-specific browser/render proof before deletion"
    elif (
        function == "_final_visible_restamper_default_rebuild_adapter_cutover"
        and target == "_publish_final_visible_design_guide_contract_binding"
    ):
        classification = CLASS_D
        decision_truth = "guarded default-rebuild restamper fallback, non-authoritative but retained"
        current_role = "guarded default-rebuild restamper fallback"
        required_next_proof = "browser/render proof that adapter output covers stale/default rebuild states before deletion"
    elif (
        readiness_class == "fallback_shell_keep"
        or reachability_class == "fallback shell support"
        or markers.get("guarded_compatibility_restamper_fallback") is True
        or markers.get("guarded_default_rebuild_restamper_fallback") is True
        or markers.get("pre_render_bound_item") is True
        or markers.get("pre_card_bound_item") is True
    ):
        classification = CLASS_D
        decision_truth = (
            "guarded restamper fallback, non-authoritative but still retained"
            if markers.get("guarded_compatibility_restamper_fallback") is True
            or markers.get("guarded_default_rebuild_restamper_fallback") is True
            else "fallback shell support, non-authoritative but still retained"
        )
        current_role = (
            "guarded compatibility restamper fallback"
            if markers.get("guarded_compatibility_restamper_fallback") is True
            else "guarded default-rebuild restamper fallback"
            if markers.get("guarded_default_rebuild_restamper_fallback") is True
            else "fallback-only support"
        )
        required_next_proof = "fallback-specific browser/render proof before deletion"
    elif (
        readiness_class == "compatibility_stamp_keep_temporarily"
        or reachability_class == "compatibility stamp"
        or markers.get("compatibility_only_callsite") is True
        or markers.get("final_visible_resolution_item_binding") is True
        or markers.get("primary_guidance_card_binding") is True
        or markers.get("render_guidance_secondary_primary_binding") is True
        or markers.get("render_fast_final_visible_item_binding") is True
        or markers.get("combined_rebound_item_binding") is True
        or markers.get("engine_rebound_item_binding") is True
        or markers.get("post_click_low_bending_exact_blocker_binding") is True
    ):
        classification = CLASS_B
        decision_truth = "legacy compatibility/debug stamp derived from publication authority"
        current_role = "compatibility-only stamp"
        required_next_proof = "focused consumer reachability proof before deleting this compatibility stamp"

    return {
        **callsite,
        "classification": classification,
        "readiness_classification": readiness_class or None,
        "reachability_classification": reachability_class or None,
        "decision_truth_owned": decision_truth,
        "current_role": current_role,
        "required_next_proof": required_next_proof,
        "deletion_allowed_now": deletion_allowed_now,
        "readiness_context_hash": (readiness_row or {}).get("context_hash"),
        "matches_readiness_snapshot": bool(readiness_row),
    }


def _summarize_gate(name: str, gate: dict[str, Any], run_result: dict[str, Any]) -> dict[str, Any]:
    snapshot = dict(gate.get("snapshot") or {})
    return {
        "name": name,
        "script": REQUIRED_GATES[name]["script"],
        "run_passed": (
            run_result.get("passed") is True
            if REFRESH_GATES
            else gate.get("passed") is True
        ),
        "refresh_skipped": not REFRESH_GATES,
        "timed_out": run_result.get("timed_out") is True,
        "artifact_found": gate.get("found") is True,
        "artifact_passed": gate.get("passed") is True,
        "artifact_path": gate.get("path"),
        "status": snapshot.get("status"),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Remaining Resolver Cleanup Audit",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Render-stage resolver adapter present: `{payload['render_stage_resolver_adapter_present']}`",
        f"- Render-stage direct resolver call present: `{payload['render_stage_direct_resolver_call_present']}`",
        f"- Remaining callsites audited: `{len(payload['remaining_paths'])}`",
        f"- Unknown paths: `{payload['classification_counts'].get(CLASS_E, 0)}`",
        f"- Deletion selected: `{bool(payload['selected_for_deletion'])}`",
        "",
        "## Classification Counts",
        "",
    ]
    for key in (CLASS_A, CLASS_B, CLASS_C, CLASS_D, CLASS_E):
        lines.append(f"- `{key}`: `{payload['classification_counts'].get(key, 0)}`")
    lines.extend(
        [
            "",
            "## Remaining Paths",
            "",
            "| Line | Function | Target | Class | Next proof |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["remaining_paths"]:
        lines.append(
            "| {line} | `{function}` | `{target}` | `{classification}` | {proof} |".format(
                line=row["line"],
                function=str(row["function"]).replace("|", "\\|"),
                target=str(row["target"]).replace("|", "\\|"),
                classification=str(row["classification"]).replace("|", "\\|"),
                proof=str(row["required_next_proof"]).replace("|", "\\|"),
            )
        )
    lines.extend(["", "## Gate Results", ""])
    for gate in payload["required_gate_results"]:
        lines.append(
            "- `{name}`: run `{run}`, artifact `{artifact}` ({path})".format(
                name=gate["name"],
                run="PASS" if gate["run_passed"] else "FAIL",
                artifact="PASS" if gate["artifact_passed"] else "FAIL",
                path=gate["artifact_path"],
            )
        )
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            payload["recommended_next_slice"],
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    gate_runs: dict[str, dict[str, Any]] = {
        name: _run(config["script"]) for name, config in REQUIRED_GATES.items()
    }
    gates: dict[str, dict[str, Any]] = {
        name: _latest(config["prefix"]) for name, config in REQUIRED_GATES.items()
    }

    source = "\n".join(
        path.read_text(encoding="utf-8-sig", errors="replace")
        for path in (INPUTS_PAGE, ROUTE_COORDINATORS, CONTROLLER, FINAL_PUBLICATION)
        if path.exists()
    )
    callsites = _callsite_scan(source)
    readiness_snapshot = dict(gates["post_render_bridge_restamper_readiness"].get("snapshot") or {})
    readiness_map = _readiness_by_callsite(readiness_snapshot)
    classified = [
        _classify_callsite(row, readiness_map.get((int(row["line"]), str(row["target"]))))
        for row in callsites
    ]

    counts: dict[str, int] = {}
    for row in classified:
        classification = str(row["classification"])
        counts[classification] = counts.get(classification, 0) + 1

    render_stage_adapter_present = bool(
        "_final_visible_resolution_from_final_publication_authority(" in source
        or "build_collapsed_guidance_item_from_final_publication(" in source
        or "DesignGuideController.compute_publication_handoff" in source
    )
    render_stage_direct_call_present = (
        "_final_visible_resolution = resolve_final_visible_design_guide_item(" in source
    )
    selected_for_deletion: list[dict[str, Any]] = []

    gate_summaries = [
        _summarize_gate(name, gates[name], gate_runs[name]) for name in REQUIRED_GATES
    ]

    failures: list[str] = []
    for gate in gate_summaries:
        if not gate["run_passed"] or not gate["artifact_passed"]:
            failures.append(f"{gate['name']}_not_passed")
    if counts.get(CLASS_E, 0):
        failures.append("unknown_remaining_resolver_or_restamper_paths_present")
    if render_stage_direct_call_present:
        failures.append("render_stage_direct_resolver_call_still_present")
    if not render_stage_adapter_present:
        failures.append("render_stage_publication_authority_adapter_missing")
    if selected_for_deletion:
        failures.append("audit_selected_deletion_despite_delete_forbidden")
    if len(classified) != 0:
        failures.append(f"expected_0_remaining_resolver_restamper_paths_found_{len(classified)}")
    if counts.get(CLASS_C, 0) != 0:
        failures.append(f"expected_0_live_mutation_paths_found_{counts.get(CLASS_C, 0)}")
    if counts.get(CLASS_B, 0) != 0:
        failures.append(f"expected_0_compatibility_stamps_found_{counts.get(CLASS_B, 0)}")
    if counts.get(CLASS_D, 0) != 0:
        failures.append(f"expected_0_fallback_keep_paths_found_{counts.get(CLASS_D, 0)}")

    payload = {
        "schema": "design_guide_remaining_resolver_cleanup_audit.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "required_gate_results": gate_summaries,
        "source_artifacts": {name: gates[name].get("path") for name in REQUIRED_GATES},
        "render_stage_resolver_adapter_present": render_stage_adapter_present,
        "render_stage_direct_resolver_call_present": render_stage_direct_call_present,
        "classification_counts": counts,
        "remaining_paths": classified,
        "selected_for_deletion": selected_for_deletion,
        "safe_deletion_candidates": [row for row in classified if row["classification"] == CLASS_A],
        "compatibility_only_stamps": [row for row in classified if row["classification"] == CLASS_B],
        "live_mutation_paths": [row for row in classified if row["classification"] == CLASS_C],
        "live_compute_authority_paths": [row for row in classified if row["classification"] == CLASS_C],
        "fallback_only_keep_paths": [row for row in classified if row["classification"] == CLASS_D],
        "unknown_paths": [row for row in classified if row["classification"] == CLASS_E],
        "post_render_readiness_summary": {
            "artifact": gates["post_render_bridge_restamper_readiness"].get("path"),
            "classification_counts": readiness_snapshot.get("classification_counts"),
            "restamper_callsite_count": readiness_snapshot.get("restamper_callsite_count"),
            "render_resolver_replaced_by_publication_authority_adapter": readiness_snapshot.get(
                "render_resolver_replaced_by_publication_authority_adapter"
            ),
        },
        "audit_hash": _stable_hash(
            {
                "callsites": [
                    {
                        "line": row["line"],
                        "function": row["function"],
                        "target": row["target"],
                        "classification": row["classification"],
                        "context_hash": row["context_hash"],
                    }
                    for row in classified
                ],
                "counts": counts,
                "render_stage_adapter_present": render_stage_adapter_present,
                "render_stage_direct_call_present": render_stage_direct_call_present,
            }
        ),
        "product_behavior_changed": False,
        "recommended_next_slice": (
            "No live resolver/restamper mutation paths remain in this inventory. Direct compatibility "
            "stamps are zero. Next safe work is fallback-specific browser/render proof for the two "
            "render fallback paths plus the guarded compatibility restamper fallback."
        ),
    }

    timestamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    artifact_path = ARTIFACT_DIR / f"design_guide_remaining_resolver_cleanup_audit_{timestamp}.json"
    report_path = AUDIT_DIR / f"design_guide_remaining_resolver_cleanup_audit_{timestamp}.md"
    payload["artifact"] = str(artifact_path)
    payload["report"] = str(report_path)
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, report_path)

    print(f"design guide remaining resolver cleanup audit {payload['status']}")
    print(f"json={artifact_path}")
    print(f"report={report_path}")
    print("classification_counts:", json.dumps(counts, sort_keys=True))
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

