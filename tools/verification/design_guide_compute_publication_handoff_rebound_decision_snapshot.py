"""Proof-only compute publication handoff/rebound decision snapshot."""

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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

EXPECTED_COMPUTE_PATHS = {
    "compute_stage_final_visible_resolver": "def run_design_guide_controller_compute_resolver_replacement_trace_only(",
    "compute_late_evidence_contract_rebound": "def run_design_guide_controller_compute_publication_handoff_trace_only(",
    "post_core_evidence_rebound": "def run_design_guide_controller_compute_rebound_publication_item_trace_only(",
}

FORBIDDEN_DESIGN_BRAIN_TOKENS = (
    "import inputs_page",
    "from inputs_page",
    "import streamlit",
    "st.session_state",
    "session_state",
    "render_html",
    "route_apply",
)

FORBIDDEN_TOKEN_EXCEPTIONS: dict[str, tuple[str, ...]] = {}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
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
            return {"found": False, "path": None, "snapshot": {}, "passed": False}
        return {"found": True, "path": str(path), "snapshot": snapshot, "passed": snapshot.get("status") == "PASS"}
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


def _function_bounds(source: str) -> dict[str, tuple[int, int]]:
    tree = ast.parse(source)
    bounds: dict[str, tuple[int, int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bounds[node.name] = (int(node.lineno), int(getattr(node, "end_lineno", node.lineno)))
    return bounds


def _line_for(source: str, needle: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            return index
    return None


def _sample_surfaces() -> dict[str, Any]:
    raw_selected_item = {
        "published_item_id": "compute-proof-published",
        "candidate_id": "compute-proof-candidate",
        "source_candidate_id": "compute-proof-source",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "family": "shear",
        "status": "ACTION",
        "action_type": "apply_resolved_candidate",
        "guidance_intent": "required_fix",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "candidate_id": "compute-proof-candidate",
            "source_candidate_id": "compute-proof-source",
            "updates": {"lig_spacing": 150},
        },
        "candidate_search_evidence": {
            "family": "shear",
            "selected_candidate_updates": {"lig_spacing": 150},
            "candidate_search_exhaustive": True,
        },
    }
    rebound_contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "shear",
        "candidate_id": "compute-proof-candidate",
        "source_candidate_id": "compute-proof-source",
        "updates": {"lig_spacing": 150, "lig_d": "N12"},
    }
    raw_rebound_item = {
        **raw_selected_item,
        "candidate_id": "compute-proof-rebound-candidate",
        "source_candidate_id": "compute-proof-rebound-source",
        "button_contract": dict(rebound_contract),
    }
    return {
        "raw_selected_item": raw_selected_item,
        "render_reason": "compute_publication_resolution",
        "state_fingerprint": "compute-state-fingerprint-proof",
        "late_evidence_acceptance": {
            "late_updates_present": True,
            "contract_disabled_or_mismatched": True,
            "active_under_capacity_blocker": False,
            "accepted": True,
        },
        "rebound_contract": rebound_contract,
        "rebound_update_payload": {"lig_spacing": 150, "lig_d": "N12"},
        "post_core_evidence_mismatch": {
            "post_evidence_updates_present": True,
            "contract_disabled_or_mismatched": True,
            "family": "combined",
            "accepted": True,
        },
        "raw_rebound_item": raw_rebound_item,
        "pre_resolver_collapsed_item_mutation": {
            "before_identity": {
                "candidate_id": "compute-proof-candidate",
                "source_candidate_id": "compute-proof-source",
            },
            "after_identity": {
                "candidate_id": "compute-proof-rebound-candidate",
                "source_candidate_id": "compute-proof-rebound-source",
            },
            "mutation_reason": "post_evidence_contract_rebound",
        },
    }


def _forbidden_token_hits(source: str) -> dict[str, bool]:
    hits: dict[str, bool] = {}
    for token in FORBIDDEN_DESIGN_BRAIN_TOKENS:
        scrubbed = source
        for allowed in FORBIDDEN_TOKEN_EXCEPTIONS.get(token, ()):
            scrubbed = scrubbed.replace(allowed, "")
        hits[token] = token in scrubbed
    return hits


def _build_proof_dict() -> dict[str, Any]:
    from design_brain.final_publication import (
        COMPUTE_PUBLICATION_HANDOFF_REBOUND_BLOCKING_FIELDS,
        build_final_design_guide_compute_publication_handoff_rebound_decision_proof,
    )

    proof = build_final_design_guide_compute_publication_handoff_rebound_decision_proof(
        **_sample_surfaces()
    )
    return {
        "proof": proof.to_dict(),
        "expected_blocking_fields": list(COMPUTE_PUBLICATION_HANDOFF_REBOUND_BLOCKING_FIELDS),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    proof = payload["proof"]
    lines = [
        "# Compute Publication Handoff/Rebound Decision Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Blocking fields covered: `{payload['blocking_field_coverage']['covered_count']}`",
        f"- Missing blocking fields: `{payload['blocking_field_coverage']['missing_count']}`",
        f"- Stable hash repeat: `{payload['stable_hash_repeat']}`",
        f"- Three compute C paths still live: `{payload['three_compute_c_paths_still_live']}`",
        f"- Product driving: `{proof['product_driving']}`",
        f"- Render driving: `{proof['render_driving']}`",
        f"- Apply driving: `{proof['apply_driving']}`",
        f"- Session driving: `{proof['session_driving']}`",
        "",
        "## Covered Fields",
        "",
    ]
    for field in proof["covered_blocking_fields"]:
        lines.append(f"- `{field}`: `{proof['field_hashes'].get(field)}`")
    lines.extend(["", "## Verification", ""])
    for name, result in payload["verification"].items():
        lines.append(f"- `{name}`: `{result['passed']}`")
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

    raw_audit_run = _run("tools/verification/design_guide_raw_compute_resolver_truth_ownership_audit.py")
    raw_audit = _latest("design_guide_raw_compute_resolver_truth_ownership_audit")
    source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (INPUTS_PAGE, CONTROLLER)
        if path.exists()
    )
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    proof_a = _build_proof_dict()
    proof_b = _build_proof_dict()
    proof = proof_a["proof"]
    expected_fields = list(proof_a["expected_blocking_fields"])
    covered = list(proof.get("covered_blocking_fields") or [])
    missing = list(proof.get("missing_blocking_fields") or [])
    source_lines = {
        path_id: _line_for(source, needle)
        for path_id, needle in EXPECTED_COMPUTE_PATHS.items()
    }
    c_paths_live = all(line is not None for line in source_lines.values())
    forbidden_hits = _forbidden_token_hits(final_source)
    stable_hash_repeat = bool(
        proof.get("decision_hash")
        and proof.get("decision_hash") == proof_b["proof"].get("decision_hash")
        and proof.get("field_hashes") == proof_b["proof"].get("field_hashes")
    )

    failures: list[str] = []
    if not raw_audit_run["passed"] or raw_audit.get("passed") is not True:
        failures.append("raw_compute_truth_ownership_audit_not_passed")
    if set(covered) != set(expected_fields):
        failures.append("not_all_blocking_fields_covered")
    if missing:
        failures.append("missing_blocking_fields_present")
    if not stable_hash_repeat:
        failures.append("proof_hashes_not_stable")
    if any(forbidden_hits.values()):
        failures.append("forbidden_page_ui_session_token_in_design_brain_final_publication")
    if not c_paths_live:
        failures.append("three_compute_c_paths_not_still_live")
    if any(
        bool(proof.get(flag))
        for flag in ("product_driving", "render_driving", "apply_driving", "session_driving")
    ):
        failures.append("proof_object_is_driving_product_or_ui")

    payload = {
        "schema": "design_guide_compute_publication_handoff_rebound_decision_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "proof": proof,
        "blocking_field_coverage": {
            "expected": expected_fields,
            "covered": covered,
            "missing": missing,
            "covered_count": len(covered),
            "missing_count": len(missing),
        },
        "stable_hash_repeat": stable_hash_repeat,
        "three_compute_c_paths_still_live": c_paths_live,
        "compute_c_path_lines": source_lines,
        "forbidden_design_brain_token_hits": forbidden_hits,
        "source_raw_compute_truth_audit": raw_audit.get("path"),
        "verification": {
            "raw_compute_truth_ownership_audit": {
                **raw_audit_run,
                "artifact_path": raw_audit.get("path"),
                "artifact_passed": raw_audit.get("passed") is True,
            }
        },
        "snapshot_hash": _stable_hash(
            {
                "decision_hash": proof.get("decision_hash"),
                "field_hashes": proof.get("field_hashes"),
                "source_lines": source_lines,
                "forbidden_hits": forbidden_hits,
            }
        ),
        "product_behavior_changed": False,
        "recommended_next_slice": (
            "Wire this proof shape trace-only beside the three compute-stage C paths, still without narrowing, "
            "so live raw resolver/rebound decisions can be compared to the Design Brain proof object."
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_publication_handoff_rebound_decision_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_publication_handoff_rebound_decision_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_compute_publication_handoff_rebound_decision_snapshot {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print(f"covered={len(covered)} missing={len(missing)}")
    print(f"stable_hash_repeat={stable_hash_repeat}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
