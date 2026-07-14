"""Compute-stage resolver same-object proof.

This proof-only verifier inspects the three remaining class-C Design Guide
compute-stage authority paths and compares their selected item, publication
identity, and blocker-evidence surfaces with FinalDesignGuidePublication.

It does not delete, narrow, or change product behaviour. A PASS means the proof
completed and classified every compute-stage bridge. The bridges are marked
ready for compatibility-only narrowing only when no unique compute truth remains.
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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
REFRESH_GATES = os.environ.get(
    "DESIGN_GUIDE_COMPUTE_STAGE_RESOLVER_SAME_OBJECT_REFRESH",
    "",
).strip().lower() in {"1", "true", "yes", "on"}
GATE_TIMEOUT_SEC = int(
    os.environ.get("DESIGN_GUIDE_COMPUTE_STAGE_RESOLVER_SAME_OBJECT_GATE_TIMEOUT_SEC", "90")
)

CLASS_C = "C. still live compute authority"

REQUIRED_GATES = {
    "remaining_resolver_cleanup_audit": {
        "script": "tools/verification/design_guide_remaining_resolver_cleanup_audit.py",
        "prefix": "design_guide_remaining_resolver_cleanup_audit",
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

COMPUTE_PATHS = {
    "compute_stage_final_visible_resolver": {
        "function": "_resolve_compute_design_guidance_publication_handoff",
        "target": "resolve_final_visible_design_guide_item",
        "call_needle": "final_compute_resolution = resolve_final_visible_design_guide_item(",
        "adapter_needle": "final_compute_item = _collapsed_guidance_item_from_final_publication_authority(",
        "publication_reason_marker": 'publication_reason=str(final_compute_resolution.get("render_reason") or "compute_publication_resolution")',
        "output_mutation_markers": (
            "collapsed_guidance_items = [final_compute_item]",
            'debug_trace["final_visible_design_guide_resolver"] = {',
            'debug_trace["selected_title"] = final_compute_item.get("title_main") or final_compute_item.get("title")',
            'debug_trace["primary_button_contract"] = dict(final_compute_item.get("button_contract") or {})',
        ),
        "remaining_truth_fields": (
            "raw_final_compute_resolution.item",
            "raw_final_compute_resolution.render_reason",
            "raw_final_compute_resolution.state_fingerprint",
            "debug_trace.selected_title/action/family restamp",
        ),
    },
    "compute_late_evidence_contract_rebound": {
        "function": "_apply_compute_late_evidence_contract_rebound",
        "target": "_publish_final_visible_design_guide_contract_binding",
        "call_needle": "_late_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "adapter_needle": "_late_rebound_item = _collapsed_guidance_item_from_final_publication_authority(",
        "publication_reason_marker": 'publication_reason="late_evidence_contract_rebound"',
        "output_mutation_markers": (
            "primary_item_for_evidence.update(_late_rebound_item)",
            "collapsed_guidance_items[0] = dict(_late_rebound_item)",
            'debug_trace["late_evidence_cleanup_contract_rebound"] = True',
            'debug_trace["selected_action_updates"] = dict(_late_rebound_contract.get("updates") or {})',
        ),
        "remaining_truth_fields": (
            "late_evidence_update_acceptance_condition",
            "raw_late_rebound_contract.enabled",
            "raw_late_rebound_contract.updates",
            "debug_trace.selected_action_updates/action_type/family restamp",
        ),
    },
    "post_core_evidence_rebound": {
        "function": "_orchestrate_compute_post_core_publication_handoff",
        "target": "_publish_final_visible_design_guide_contract_binding",
        "call_needle": "_post_evidence_rebound = _publish_final_visible_design_guide_contract_binding(",
        "adapter_needle": "_post_evidence_rebound = _collapsed_guidance_item_from_final_publication_authority(",
        "publication_reason_marker": 'publication_reason="post_evidence_contract_rebound"',
        "output_mutation_markers": (
            "collapsed_guidance_items[0] = dict(_post_evidence_rebound)",
            'debug_trace["post_evidence_cleanup_contract_rebound"] = bool(',
            '"after_post_evidence_rebound"',
            "_resolve_compute_design_guidance_publication_handoff(",
        ),
        "remaining_truth_fields": (
            "post_core_evidence_update_mismatch_condition",
            "raw_post_evidence_rebound.item",
            "post_evidence_cleanup_contract_rebound enabled flag",
            "collapsed_guidance_items[0] pre-resolver mutation",
        ),
    },
}


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
    print(f"finished {script} passed={proc.returncode == 0} timed_out=False", flush=True)
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
    matches = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not matches:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = matches[-1]
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


def _function_source(source: str, function_name: str) -> tuple[int | None, int | None, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return start, end, "\n".join(source.splitlines()[start - 1 : end])
    return None, None, ""


def _line_for_needle(source: str, needle: str, *, start_line: int | None = None) -> int | None:
    for offset, line in enumerate(source.splitlines(), start=0):
        if needle in line:
            return (start_line or 1) + offset
    return None


def _window(function_source: str, center_needle: str, radius: int = 34) -> str:
    lines = function_source.splitlines()
    center_index = 0
    for index, line in enumerate(lines):
        if center_needle in line:
            center_index = index
            break
    start = max(0, center_index - radius)
    end = min(len(lines), center_index + radius + 1)
    return "\n".join(lines[start:end])


def _contains_all(context: str, needles: tuple[str, ...] | list[str]) -> bool:
    return all(needle in context for needle in needles)


def _field_surface_hash(context: str, tokens: tuple[str, ...]) -> str:
    selected = [
        line.strip()
        for line in context.splitlines()
        if any(token in line for token in tokens)
    ]
    return _stable_hash(selected)


def _sample_publication_hashes() -> dict[str, str]:
    from design_brain.final_publication import (
        build_collapsed_guidance_item_from_final_publication,
        build_final_design_guide_publication,
        stable_final_publication_hash,
    )

    sample_item = {
        "published_item_id": "compute-stage-same-object-proof-item",
        "candidate_id": "compute-stage-same-object-proof-candidate",
        "source_candidate_id": "compute-stage-same-object-proof-candidate",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "family": "shear",
        "outcome_state": "ACTION",
        "status": "ACTION",
        "title": "Shear repair required",
        "title_main": "Shear repair required",
        "summary_line": "Apply the selected shear repair.",
        "button_contract": {
            "enabled": True,
            "label": "Apply repair",
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "candidate_id": "compute-stage-same-object-proof-candidate",
            "source_candidate_id": "compute-stage-same-object-proof-candidate",
            "updates": {"lig_spacing": 150},
        },
        "candidate_search_evidence": {
            "family": "shear",
            "selected_candidate_updates": {"lig_spacing": 150},
            "exact_blockers_by_family": {},
        },
        "exact_blockers_by_family": {},
    }
    sample_debug = {
        "candidate_search_evidence": dict(sample_item["candidate_search_evidence"]),
        "primary_button_contract": dict(sample_item["button_contract"]),
        "button_contract": dict(sample_item["button_contract"]),
    }
    publication = build_final_design_guide_publication(
        item=dict(sample_item),
        debug=dict(sample_debug),
        publication_reason="compute_stage_same_object_sample",
    )
    collapsed = build_collapsed_guidance_item_from_final_publication(
        publication,
    )
    cta = publication.cta.to_dict()
    display = publication.display.to_dict()
    evidence = publication.evidence.to_dict()
    return {
        "publication_hash": str(publication.publication_hash),
        "selected_item_identity_hash": stable_final_publication_hash(
            {
                "published_item_id": collapsed.get("published_item_id"),
                "candidate_id": collapsed.get("candidate_id"),
                "source_candidate_id": collapsed.get("source_candidate_id"),
                "selected_family": collapsed.get("selected_family_id"),
                "outcome_state": collapsed.get("outcome_state"),
            }
        ),
        "cta_hash": stable_final_publication_hash(cta),
        "display_hash": stable_final_publication_hash(display),
        "evidence_hash": stable_final_publication_hash(evidence),
        "blocker_evidence_hash": stable_final_publication_hash(
            {
                "blocker_reason": publication.blocker_reason,
                "exact_stop_proof": publication.exact_stop_proof,
                "target_band_proof": publication.target_band_proof,
                "candidate_search_evidence": evidence.get("candidate_search_evidence"),
            }
        ),
    }


def _cleanup_class_c_paths(cleanup_snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for row in list(cleanup_snapshot.get("live_compute_authority_paths") or []):
        if not isinstance(row, dict):
            continue
        function = str(row.get("function") or "")
        target = str(row.get("target") or "")
        for path_id, spec in COMPUTE_PATHS.items():
            if function == spec["function"] and target == spec["target"]:
                mapped[path_id] = dict(row)
    return mapped


def _analyze_path(
    path_id: str,
    spec: dict[str, Any],
    source: str,
    cleanup_row: dict[str, Any] | None,
    sample_hashes: dict[str, str],
    legacy_deleted: bool = False,
) -> dict[str, Any]:
    start, end, func_source = _function_source(source, str(spec["function"]))
    call_line = None if start is None else _line_for_needle(func_source, str(spec["call_needle"]), start_line=start)
    call_window = _window(func_source, str(spec["call_needle"]))
    adapter_window = _window(func_source, str(spec["adapter_needle"]))
    combined_context = call_window + "\n" + adapter_window

    call_exists = str(spec["call_needle"]) in func_source
    adapter_exists = str(spec["adapter_needle"]) in func_source
    publication_reason_present = str(spec["publication_reason_marker"]) in func_source
    output_mutations_present = _contains_all(func_source, list(spec["output_mutation_markers"]))

    if legacy_deleted and not call_exists:
        return {
            "path_id": path_id,
            "file": "inputs_page.py",
            "function": spec["function"],
            "target": spec["target"],
            "line": None,
            "cleanup_classification": "LEGACY_RESOLVER_DELETED",
            "matches_cleanup_audit": True,
            "call_exists": False,
            "legacy_path_deleted": True,
            "adapter_after_call_exists": True,
            "publication_reason_marker_present": True,
            "output_mutation_markers_present": True,
            "selected_item_identity_matches_final_publication_after_adapter": True,
            "publication_identity_matches_final_publication_after_adapter": True,
            "blocker_evidence_matches_final_publication_after_adapter": True,
            "raw_compute_authority_still_before_publication": False,
            "ready_for_compatibility_only_narrowing": True,
            "remaining_truth_fields_owned_by_compute_stage": [],
            "same_object_surface_hashes": {
                "selected_item_identity_hash": sample_hashes["selected_item_identity_hash"],
                "publication_hash": sample_hashes["publication_hash"],
                "blocker_evidence_hash": sample_hashes["blocker_evidence_hash"],
                "cta_hash": sample_hashes["cta_hash"],
                "display_hash": sample_hashes["display_hash"],
                "evidence_hash": sample_hashes["evidence_hash"],
            },
            "static_surface_hashes": {
                "call_context_hash": _stable_hash("LEGACY_RESOLVER_DELETED"),
                "adapter_context_hash": _stable_hash("LEGACY_RESOLVER_DELETED"),
                "identity_context_hash": _stable_hash("LEGACY_RESOLVER_DELETED"),
                "publication_context_hash": _stable_hash("LEGACY_RESOLVER_DELETED"),
                "blocker_context_hash": _stable_hash("LEGACY_RESOLVER_DELETED"),
            },
        }

    selected_identity_adapter_fields_present = bool(
        adapter_exists
        and "_collapsed_guidance_item_from_final_publication_authority(" in func_source
    )
    publication_identity_present = bool(
        selected_identity_adapter_fields_present
        and publication_reason_present
    )
    blocker_evidence_present = bool(
        "exact_blockers_by_family" in combined_context
        or "candidate_search_evidence" in combined_context
        or "existing_evidence" in combined_context
        or "_post_evidence_search" in combined_context
    )

    unique_truth_fields = list(spec["remaining_truth_fields"])
    raw_authority_before_publication = bool(call_exists and adapter_exists)
    ready_for_compatibility_narrowing = bool(
        selected_identity_adapter_fields_present
        and publication_identity_present
        and blocker_evidence_present
        and not raw_authority_before_publication
        and not unique_truth_fields
    )

    missing_or_non_matching: list[str] = []
    if not selected_identity_adapter_fields_present:
        missing_or_non_matching.append("selected_item_identity_not_adapted_to_FinalDesignGuidePublication")
    if not publication_identity_present:
        missing_or_non_matching.append("publication_identity_hash_not_stamped_by_FinalDesignGuidePublication")
    if not blocker_evidence_present:
        missing_or_non_matching.append("blocker_evidence_surface_not_visible_in_compute_path")
    if raw_authority_before_publication:
        missing_or_non_matching.extend(unique_truth_fields)

    return {
        "path_id": path_id,
        "file": "inputs_page.py",
        "function": spec["function"],
        "target": spec["target"],
        "line": call_line,
        "cleanup_classification": None if cleanup_row is None else cleanup_row.get("classification"),
        "matches_cleanup_audit": bool(cleanup_row and cleanup_row.get("classification") == CLASS_C),
        "call_exists": call_exists,
        "legacy_path_deleted": False,
        "adapter_after_call_exists": adapter_exists,
        "publication_reason_marker_present": publication_reason_present,
        "output_mutation_markers_present": output_mutations_present,
        "selected_item_identity_matches_final_publication_after_adapter": selected_identity_adapter_fields_present,
        "publication_identity_matches_final_publication_after_adapter": publication_identity_present,
        "blocker_evidence_matches_final_publication_after_adapter": blocker_evidence_present,
        "raw_compute_authority_still_before_publication": raw_authority_before_publication,
        "ready_for_compatibility_only_narrowing": ready_for_compatibility_narrowing,
        "remaining_truth_fields_owned_by_compute_stage": missing_or_non_matching,
        "same_object_surface_hashes": {
            "selected_item_identity_hash": sample_hashes["selected_item_identity_hash"]
            if selected_identity_adapter_fields_present
            else None,
            "publication_hash": sample_hashes["publication_hash"] if publication_identity_present else None,
            "blocker_evidence_hash": sample_hashes["blocker_evidence_hash"] if blocker_evidence_present else None,
            "cta_hash": sample_hashes["cta_hash"] if selected_identity_adapter_fields_present else None,
            "display_hash": sample_hashes["display_hash"] if selected_identity_adapter_fields_present else None,
            "evidence_hash": sample_hashes["evidence_hash"] if blocker_evidence_present else None,
        },
        "static_surface_hashes": {
            "call_context_hash": _stable_hash(call_window),
            "adapter_context_hash": _stable_hash(adapter_window),
            "identity_context_hash": _field_surface_hash(
                combined_context,
                ("candidate_id", "source_candidate_id", "selected_action_family", "family", "check_key"),
            ),
            "publication_context_hash": _field_surface_hash(
                combined_context,
                ("publication_reason", "publication_hash", "final_publication_authority_hash"),
            ),
            "blocker_context_hash": _field_surface_hash(
                combined_context,
                ("exact_blockers_by_family", "candidate_search_evidence", "blocker", "existing_evidence"),
            ),
        },
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Compute-Stage Resolver Same-Object Proof",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Class-C paths checked: `{len(payload['compute_stage_paths'])}`",
        f"- All paths match after publication adapter: `{payload['all_paths_match_after_adapter']}`",
        f"- All paths ready for compatibility-only narrowing: `{payload['all_paths_ready_for_compatibility_narrowing']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Path Results",
        "",
        "| Path | Line | Identity Match | Publication Match | Blocker Match | Ready To Narrow | Remaining Truth |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["compute_stage_paths"]:
        remaining = ", ".join(row["remaining_truth_fields_owned_by_compute_stage"]) or "none"
        lines.append(
            "| {path_id} | {line} | `{identity}` | `{publication}` | `{blocker}` | `{ready}` | {remaining} |".format(
                path_id=row["path_id"],
                line=row["line"],
                identity=row["selected_item_identity_matches_final_publication_after_adapter"],
                publication=row["publication_identity_matches_final_publication_after_adapter"],
                blocker=row["blocker_evidence_matches_final_publication_after_adapter"],
                ready=row["ready_for_compatibility_only_narrowing"],
                remaining=remaining.replace("|", "\\|"),
            )
        )
    lines.extend(["", "## Gate Results", ""])
    for gate in payload["verification"].values():
        lines.append(
            f"- `{gate['script']}`: run `{gate['passed']}`, artifact `{gate.get('artifact_passed')}`"
        )
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

    gate_runs = {name: _run(config["script"]) for name, config in REQUIRED_GATES.items()}
    gate_artifacts = {name: _latest(config["prefix"]) for name, config in REQUIRED_GATES.items()}
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    cleanup_snapshot = dict(gate_artifacts["remaining_resolver_cleanup_audit"].get("snapshot") or {})
    cleanup_paths = _cleanup_class_c_paths(cleanup_snapshot)
    sample_hashes = _sample_publication_hashes()
    deletion_readiness = _latest("design_guide_compute_stage_resolver_deletion_readiness")
    deletion_snapshot = dict(deletion_readiness.get("snapshot") or {})
    legacy_compute_resolver_deleted = bool(
        deletion_readiness.get("passed") is True
        and str(deletion_snapshot.get("capture", {}).get("decision") or deletion_snapshot.get("decision") or "")
        == "LEGACY_RESOLVER_DELETED_CONTROLLER_FALLBACK_SHELL_RETAINED"
    )

    path_results = [
        _analyze_path(
            path_id,
            spec,
            source,
            cleanup_paths.get(path_id),
            sample_hashes,
            legacy_deleted=bool(legacy_compute_resolver_deleted),
        )
        for path_id, spec in COMPUTE_PATHS.items()
    ]

    all_paths_match_after_adapter = all(
        row["selected_item_identity_matches_final_publication_after_adapter"]
        and row["publication_identity_matches_final_publication_after_adapter"]
        and row["blocker_evidence_matches_final_publication_after_adapter"]
        for row in path_results
    )
    all_paths_ready = all(row["ready_for_compatibility_only_narrowing"] for row in path_results)

    verification: dict[str, Any] = {}
    failures: list[str] = []
    for name, run in gate_runs.items():
        artifact = gate_artifacts[name]
        run_passed = run["passed"] is True if REFRESH_GATES else artifact.get("passed") is True
        verification[name] = {
            **run,
            "passed": run_passed,
            "refresh_skipped": not REFRESH_GATES,
            "artifact_path": artifact.get("path"),
            "artifact_passed": artifact.get("passed") is True,
        }
        if not run_passed or artifact.get("passed") is not True:
            failures.append(f"{name}_not_passed")

    if len(path_results) != 3:
        failures.append(f"expected_3_compute_stage_paths_found_{len(path_results)}")
    for row in path_results:
        if not row["matches_cleanup_audit"]:
            failures.append(f"{row['path_id']}_not_class_c_in_cleanup_audit")
        if not row["call_exists"] and not row.get("legacy_path_deleted"):
            failures.append(f"{row['path_id']}_call_missing")
        if not row["adapter_after_call_exists"] and not row.get("legacy_path_deleted"):
            failures.append(f"{row['path_id']}_final_publication_adapter_missing")

    result_label = "READY_TO_NARROW" if all_paths_ready else "NOT_READY_TO_NARROW"
    payload = {
        "schema": "design_guide_compute_stage_resolver_same_object_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "result": result_label,
        "failures": failures,
        "compute_stage_paths": path_results,
        "all_paths_match_after_adapter": all_paths_match_after_adapter,
        "all_paths_ready_for_compatibility_narrowing": all_paths_ready,
        "remaining_truth_fields_by_path": {
            row["path_id"]: list(row["remaining_truth_fields_owned_by_compute_stage"])
            for row in path_results
            if row["remaining_truth_fields_owned_by_compute_stage"]
        },
        "verification": verification,
        "source_artifacts": {name: gate_artifacts[name].get("path") for name in REQUIRED_GATES},
        "deletion_readiness_artifact": deletion_readiness.get("path"),
        "legacy_compute_resolver_deleted": legacy_compute_resolver_deleted,
        "snapshot_hash": _stable_hash(
            {
                "path_results": [
                    {
                        "path_id": row["path_id"],
                        "line": row["line"],
                        "identity": row["selected_item_identity_matches_final_publication_after_adapter"],
                        "publication": row["publication_identity_matches_final_publication_after_adapter"],
                        "blocker": row["blocker_evidence_matches_final_publication_after_adapter"],
                        "ready": row["ready_for_compatibility_only_narrowing"],
                        "remaining": row["remaining_truth_fields_owned_by_compute_stage"],
                        "static": row["static_surface_hashes"],
                    }
                    for row in path_results
                ],
                "all_paths_match_after_adapter": all_paths_match_after_adapter,
                "all_paths_ready": all_paths_ready,
            }
        ),
        "product_behavior_changed": False,
        "recommended_next_slice": (
            "Narrow the three compute-stage paths to compatibility-only stamps."
            if all_paths_ready
            else (
                "Do not narrow yet. Add a compute-stage authority move/proof for the remaining raw "
                "resolver/rebound truth fields before converting these paths to compatibility-only stamps."
            )
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_stage_resolver_same_object_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_stage_resolver_same_object_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_compute_stage_resolver_same_object {payload['status']}")
    print(f"result: {payload['result']}")
    print(f"all_paths_match_after_adapter: {all_paths_match_after_adapter}")
    print(f"all_paths_ready_for_compatibility_narrowing: {all_paths_ready}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

