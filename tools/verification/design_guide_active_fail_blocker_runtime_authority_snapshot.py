"""Audit active-fail blocker authority for combined/shear Design Guide blockers.

This proof-only snapshot checks whether the live active-fail blocker that
reached final publication is backed by locked family runtime evidence or by the
older practical repair catalogue/page-owned evidence path.
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
REPAIR_MODULE = ROOT / "design_brain" / "repair.py"
COMBINED_RUNTIME = ROOT / "design_brain" / "families" / "bending_and_shear_fail_govern" / "runtime.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

RUNTIME_REQUIRED_FIELDS = (
    "contract_hash",
    "runtime_hash",
    "combined_merge_trace",
    "candidate_repairs",
    "accepted_candidate_evidence",
    "rejected_candidate_evidence",
    "exhausted_proof",
    "candidate_source_proof",
    "ownership_proof",
    "selection_boundary_proof",
)

LEGACY_MARKERS = (
    "active_fail_combined_repair_search",
    "active_fail_repair_search",
    "practical_ladder_exhausted",
    "sectional shear capacity repair catalogue",
    "bending capacity repair catalogue",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest_artifact(prefix: str) -> dict[str, Any]:
    artifacts = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not artifacts:
        return {"path": None, "snapshot": None, "found": False, "passed": False}
    path = artifacts[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "path": str(path),
            "snapshot": None,
            "found": True,
            "passed": False,
            "error": str(exc),
        }
    return {
        "path": str(path),
        "snapshot": snapshot,
        "found": True,
        "passed": snapshot.get("status") == "PASS" or snapshot.get("result") == "PASS",
    }


def _run_compile() -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "tools/verification/design_guide_active_fail_blocker_runtime_authority_snapshot.py",
            "design_brain/families/bending_and_shear_fail_govern/runtime.py",
            "design_brain/repair.py",
            "inputs_page.py",
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _function_source(path: Path, function_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            segment = ast.get_source_segment(source, node)
            if segment:
                return segment
    return ""


def _collect_trace_evidence(trace: dict[str, Any]) -> dict[str, Any]:
    exact = dict(trace.get("exact_blockers_by_family") or {})
    post_exact = dict(trace.get("post_click_exact_blockers_by_family") or {})
    evidence_rows = {
        "bending": dict(exact.get("bending") or post_exact.get("bending") or {}),
        "shear": dict(exact.get("shear") or post_exact.get("shear") or {}),
    }
    combined_text = _stable_json(
        {
            "trace": trace,
            "bending": evidence_rows["bending"],
            "shear": evidence_rows["shear"],
        }
    )
    runtime_field_presence = {
        field: any(
            field in row
            for row in (
                trace,
                evidence_rows["bending"],
                evidence_rows["shear"],
                dict((trace.get("final_publication_verifier_payload") or {})),
            )
            if isinstance(row, dict)
        )
        for field in RUNTIME_REQUIRED_FIELDS
    }
    legacy_marker_presence = {
        marker: marker in combined_text
        for marker in LEGACY_MARKERS
    }
    return {
        "active_failure_keys": list(trace.get("active_failure_keys") or []),
        "selected_family": trace.get("selected_family"),
        "geometry_lock_enabled": trace.get("geometry_lock_enabled"),
        "root_hint": trace.get("root_hint"),
        "candidate_search_evidence": dict(trace.get("candidate_search_evidence") or {}),
        "bending_source": evidence_rows["bending"].get("source"),
        "shear_source": evidence_rows["shear"].get("source"),
        "bending_failed_check_name": evidence_rows["bending"].get("failed_check_name"),
        "shear_failed_check_name": evidence_rows["shear"].get("failed_check_name"),
        "bending_search_scope": evidence_rows["bending"].get("search_scope"),
        "shear_search_scope": evidence_rows["shear"].get("search_scope"),
        "bending_attempted_candidate_id": evidence_rows["bending"].get("attempted_candidate_id"),
        "shear_attempted_candidate_id": evidence_rows["shear"].get("attempted_candidate_id"),
        "runtime_field_presence": runtime_field_presence,
        "runtime_field_count": sum(1 for present in runtime_field_presence.values() if present),
        "legacy_marker_presence": legacy_marker_presence,
        "legacy_marker_count": sum(1 for present in legacy_marker_presence.values() if present),
        "trace_hash": _stable_hash(trace),
    }


def _source_authority_map() -> dict[str, Any]:
    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    repair_source = REPAIR_MODULE.read_text(encoding="utf-8")
    runtime_source = COMBINED_RUNTIME.read_text(encoding="utf-8")
    return {
        "inputs_page_contains_legacy_catalogue_markers": {
            marker: marker in input_source for marker in LEGACY_MARKERS
        },
        "repair_module_contains_legacy_catalogue_markers": {
            marker: marker in repair_source for marker in LEGACY_MARKERS
        },
        "combined_runtime_contains_runtime_fields": {
            field: field in runtime_source for field in RUNTIME_REQUIRED_FIELDS
        },
        "combined_runtime_exposes_authority": (
            "run_combined_bending_shear_fail_runtime" in runtime_source
            and "CombinedBendingShearFailResult" in runtime_source
            and "contract_hash" in runtime_source
            and "runtime_hash" in runtime_source
        ),
        "active_failure_blocker_payload_source_hash": _stable_hash(
            _function_source(REPAIR_MODULE, "active_failure_blocker_payload")
        ),
        "combined_runtime_source_hash": _stable_hash(runtime_source),
        "inputs_legacy_blocker_source_hash": _stable_hash(
            "\n".join(
                line
                for line in input_source.splitlines()
                if any(marker in line for marker in LEGACY_MARKERS)
            )
        ),
    }


def _build_snapshot() -> dict[str, Any]:
    latest_trace = _latest_artifact("design_guide_unlocked_active_failure_missing_apply_cta_guard_trace")
    latest_combined_lock = _latest_artifact("combined_bending_shear_fail_governs_lock_verifier")
    latest_shear_lock = _latest_artifact("shear_fail_governs_lock_verifier")
    compile_result = _run_compile()
    trace = latest_trace.get("snapshot") or {}
    trace_evidence = _collect_trace_evidence(trace) if trace else {}
    source_map = _source_authority_map()

    runtime_fields_present = int(trace_evidence.get("runtime_field_count") or 0)
    legacy_markers_present = int(trace_evidence.get("legacy_marker_count") or 0)
    combined_lock_passed = bool(latest_combined_lock.get("passed"))
    shear_lock_passed = bool(latest_shear_lock.get("passed"))
    trace_runtime_backed = runtime_fields_present >= len(RUNTIME_REQUIRED_FIELDS)
    trace_legacy_catalogue_sourced = legacy_markers_present > 0

    if trace_runtime_backed and not trace_legacy_catalogue_sourced:
        authority = "PASS_RUNTIME_BACKED"
        recommendation = "Continue with final render bridge lock/deletion path."
    elif trace_legacy_catalogue_sourced:
        authority = "FAIL_PAGE_CATALOGUE_SOURCED"
        recommendation = (
            "Do not trust this blocker as final family authority yet. Build a narrow cutover so "
            "active combined/shear failure blocker/exhausted publication consumes the locked "
            "combined/shear family runtime result and carries contract_hash/runtime_hash/exhausted_proof."
        )
    else:
        authority = "PARTIAL_UNPROVEN"
        recommendation = "Add live runtime provenance fields to the blocker publication path before accepting it."

    checks = {
        "py_compile_pass": compile_result["passed"],
        "guard_trace_found": bool(latest_trace.get("found")),
        "combined_family_lock_exists": combined_lock_passed,
        "shear_family_lock_exists": shear_lock_passed,
        "trace_has_runtime_authority_fields": trace_runtime_backed,
        "trace_has_legacy_catalogue_markers": trace_legacy_catalogue_sourced,
        "runtime_source_has_authority_fields": bool(source_map["combined_runtime_exposes_authority"]),
    }
    failures = []
    if not compile_result["passed"]:
        failures.append("py_compile_failed")
    if not latest_trace.get("found"):
        failures.append("guard_trace_missing")
    if not combined_lock_passed:
        failures.append("combined_family_lock_missing_or_not_pass")
    if not shear_lock_passed:
        failures.append("shear_family_lock_missing_or_not_pass")

    status = "PASS" if not failures else "FAIL"
    proof_surface = {
        "trace_evidence": trace_evidence,
        "source_map": source_map,
        "authority": authority,
        "checks": checks,
    }
    return {
        "snapshot_name": "design_guide_active_fail_blocker_runtime_authority_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "authority_result": authority,
        "trace_runtime_backed": trace_runtime_backed,
        "trace_legacy_catalogue_sourced": trace_legacy_catalogue_sourced,
        "trace_evidence": trace_evidence,
        "source_authority_map": source_map,
        "artifacts_used": {
            "guard_trace": latest_trace.get("path"),
            "combined_bending_shear_lock": latest_combined_lock.get("path"),
            "shear_fail_lock": latest_shear_lock.get("path"),
        },
        "checks": checks,
        "verification": {
            "py_compile": compile_result,
        },
        "recommendation": recommendation,
        "product_behavior_changed": False,
        "failures": failures,
        "snapshot_hash": _stable_hash(proof_surface),
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    trace = snapshot["trace_evidence"]
    runtime_rows = [
        f"- {field}: `{'yes' if present else 'no'}`"
        for field, present in dict(trace.get("runtime_field_presence") or {}).items()
    ]
    legacy_rows = [
        f"- {marker}: `{'yes' if present else 'no'}`"
        for marker, present in dict(trace.get("legacy_marker_presence") or {}).items()
    ]
    body = "\n".join(
        [
            "# Design Guide Active-Fail Blocker Runtime Authority Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Authority result: `{snapshot['authority_result']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Trace runtime-backed: `{snapshot['trace_runtime_backed']}`",
            f"- Trace legacy catalogue sourced: `{snapshot['trace_legacy_catalogue_sourced']}`",
            f"- Selected family: `{trace.get('selected_family')}`",
            f"- Bending source: `{trace.get('bending_source')}`",
            f"- Shear source: `{trace.get('shear_source')}`",
            f"- Shear failed check: `{trace.get('shear_failed_check_name')}`",
            f"- Shear search scope: `{trace.get('shear_search_scope')}`",
            "",
            "## Runtime Authority Fields In Trace",
            "",
            *runtime_rows,
            "",
            "## Legacy Catalogue Markers In Trace",
            "",
            *legacy_rows,
            "",
            "## Artifacts Used",
            "",
            f"- Guard trace: `{snapshot['artifacts_used']['guard_trace']}`",
            f"- Combined lock: `{snapshot['artifacts_used']['combined_bending_shear_lock']}`",
            f"- Shear lock: `{snapshot['artifacts_used']['shear_fail_lock']}`",
            "",
            "## Recommendation",
            "",
            snapshot["recommendation"],
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
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_blocker_runtime_authority_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_active_fail_blocker_runtime_authority_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_active_fail_blocker_runtime_authority_snapshot {snapshot['status']}")
    print(f"authority_result={snapshot['authority_result']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
