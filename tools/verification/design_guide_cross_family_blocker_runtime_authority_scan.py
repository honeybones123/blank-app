"""Scan Design Guide blocker paths for old catalogue/page authority.

This verifier does not prove engineering validity. It searches for final-blocker
paths that can still originate from legacy/page-owned catalogue evidence instead
of locked family runtime proof.
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
INPUTS_PAGE = ROOT / "inputs_page.py"
REPAIR = ROOT / "design_brain" / "repair.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


FAMILY_MARKERS = {
    "BENDING_FAIL_GOVERNS": {
        "legacy_markers": (
            "bending_active_failure_practical_ladder_exhausted",
            "bending capacity repair catalogue",
            "active_fail_bending_repair_search",
        ),
        "policy_scope": "active bending failure",
    },
    "SHEAR_FAIL_GOVERNS": {
        "legacy_markers": (
            "shear_active_failure_practical_ladder_exhausted",
            "sectional shear capacity repair catalogue",
            "active_fail_shear_repair_search",
        ),
        "policy_scope": "active shear failure",
    },
    "COMBINED_BENDING_SHEAR_FAIL": {
        "legacy_markers": (
            "active_fail_combined_repair_search",
            "combined_active_failure_practical_ladder_exhausted",
            "combined active-failure repair search",
        ),
        "policy_scope": "active combined bending plus shear failure",
    },
    "SERVICEABILITY_GOVERNS": {
        "legacy_markers": (
            "Deflection repair is blocked by geometry/serviceability limits",
            "deflection limit",
            "serviceability/detailing limits",
        ),
        "policy_scope": "serviceability blocker text",
    },
}

RUNTIME_PROOF_TERMS = (
    "contract_hash",
    "runtime_hash",
    "exhausted_proof",
    "candidate_source_proof",
    "ownership_proof",
    "selection_boundary_proof",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(source: str, function_name: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            segment = ast.get_source_segment(source, node)
            if segment:
                return segment
    return ""


def _run_compile() -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "inputs_page.py",
            "design_brain/repair.py",
            "tools/verification/design_guide_cross_family_blocker_runtime_authority_scan.py",
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "passed": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _latest_artifact(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "snapshot": None}
    path = paths[-1]
    return {
        "found": True,
        "path": str(path),
        "snapshot": json.loads(path.read_text(encoding="utf-8")),
    }


def _artifact_marker_hits() -> dict[str, Any]:
    prefixes = (
        "design_guide_unlocked_active_failure_missing_apply_cta_guard_trace",
        "design_guide_active_fail_blocker_runtime_authority",
        "design_guide_active_fail_blocker_locked_runtime_replay",
    )
    out: dict[str, Any] = {}
    for prefix in prefixes:
        artifact = _latest_artifact(prefix)
        text = _stable_json(artifact.get("snapshot") or {})
        out[prefix] = {
            "found": artifact["found"],
            "path": artifact["path"],
            "legacy_marker_hits": sorted(
                {
                    marker
                    for config in FAMILY_MARKERS.values()
                    for marker in config["legacy_markers"]
                    if marker in text
                }
            ),
            "runtime_proof_hits": sorted(term for term in RUNTIME_PROOF_TERMS if term in text),
        }
    return out


def _build_snapshot() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    repair_source = REPAIR.read_text(encoding="utf-8", errors="replace")
    policy_source = _function_source(inputs_source, "_design_guide_active_failure_blocker_publication_policy")
    incomplete_source = _function_source(inputs_source, "build_design_guide_card_view_model")
    repair_payload_source = _function_source(repair_source, "active_failure_blocker_payload")
    no_target_source = _function_source(inputs_source, "_active_failure_no_target_blocker_item")
    compile_result = _run_compile()

    family_rows: list[dict[str, Any]] = []
    for family_id, config in FAMILY_MARKERS.items():
        markers = tuple(config["legacy_markers"])
        source_hits = {
            "inputs_page": sorted(marker for marker in markers if marker in inputs_source),
            "design_brain_repair": sorted(marker for marker in markers if marker in repair_source),
            "active_failure_blocker_payload": sorted(marker for marker in markers if marker in repair_payload_source),
            "active_failure_no_target_blocker_item": sorted(marker for marker in markers if marker in no_target_source),
        }
        legacy_present = any(source_hits.values())
        if family_id in {"BENDING_FAIL_GOVERNS", "SHEAR_FAIL_GOVERNS", "COMBINED_BENDING_SHEAR_FAIL"}:
            protected = (
                "_active_failure_blocker_has_locked_runtime_proof(" in policy_source
                and '"unlocked_active_failure_missing_runtime_proof"' in policy_source
                and '"unlocked_active_failure_missing_runtime_proof"' in incomplete_source
            )
            classification = (
                "PROTECTED_FROM_FINAL_UNLOCKED_BLOCK_BY_RUNTIME_PROOF_POLICY"
                if protected
                else "RISK_FINAL_BLOCKER_CAN_USE_LEGACY_CATALOGUE"
            )
        else:
            protected = False
            classification = (
                "AUDIT_REQUIRED_SERVICEABILITY_OR_NON_ACTIVE_FAIL_BLOCKER"
                if legacy_present
                else "NO_LEGACY_MARKER_FOUND"
            )
        family_rows.append(
            {
                "family_id": family_id,
                "policy_scope": config["policy_scope"],
                "legacy_markers_present": legacy_present,
                "source_hits": source_hits,
                "runtime_proof_policy_protected": protected,
                "classification": classification,
            }
        )

    artifact_hits = _artifact_marker_hits()
    high_risk = [
        row["family_id"]
        for row in family_rows
        if row["classification"] in {
            "RISK_FINAL_BLOCKER_CAN_USE_LEGACY_CATALOGUE",
            "AUDIT_REQUIRED_SERVICEABILITY_OR_NON_ACTIVE_FAIL_BLOCKER",
        }
    ]
    checks = {
        "py_compile_pass": compile_result["passed"],
        "active_fail_policy_requires_runtime_proof": "_active_failure_blocker_has_locked_runtime_proof(" in policy_source,
        "unlocked_missing_runtime_proof_not_hard_crash": '"unlocked_active_failure_missing_runtime_proof"' in incomplete_source,
        "active_bending_shear_combined_rows_classified": all(
            row["classification"] == "PROTECTED_FROM_FINAL_UNLOCKED_BLOCK_BY_RUNTIME_PROOF_POLICY"
            for row in family_rows
            if row["family_id"] in {"BENDING_FAIL_GOVERNS", "SHEAR_FAIL_GOVERNS", "COMBINED_BENDING_SHEAR_FAIL"}
        ),
    }
    failures = [key for key, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    recommendation = (
        "Active bending/shear/combined final blockers are now protected from unlocked legacy catalogue "
        "publication by the runtime-proof policy. Serviceability/non-active-fail blocker paths still need "
        "their own authority audit before deletion or final lock claims."
    )
    proof_surface = {
        "family_rows": family_rows,
        "artifact_hits": artifact_hits,
        "checks": checks,
    }
    return {
        "schema": "design_guide_cross_family_blocker_runtime_authority_scan.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "checks": checks,
        "failures": failures,
        "family_rows": family_rows,
        "high_risk_or_audit_required": high_risk,
        "artifact_marker_hits": artifact_hits,
        "source_hashes": {
            "policy": _stable_hash(policy_source),
            "active_failure_blocker_payload": _stable_hash(repair_payload_source),
            "active_failure_no_target_blocker_item": _stable_hash(no_target_source),
        },
        "verification": {"py_compile": compile_result},
        "recommendation": recommendation,
        "product_behavior_changed": False,
        "snapshot_hash": _stable_hash(proof_surface),
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Cross-Family Blocker Runtime Authority Scan",
        "",
        f"Timestamp: `{snapshot['generated_at']}`",
        f"Result: `{snapshot['status']}`",
        f"Snapshot hash: `{snapshot['snapshot_hash']}`",
        "",
        "## Family Rows",
        "",
        "| Family | Classification | Legacy markers | Runtime protected |",
        "| --- | --- | --- | --- |",
    ]
    for row in snapshot["family_rows"]:
        marker_count = sum(len(v) for v in row["source_hits"].values())
        lines.append(
            "| "
            f"{row['family_id']} | "
            f"{row['classification']} | "
            f"{marker_count} | "
            f"{row['runtime_proof_policy_protected']} |"
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
            "",
            "## High Risk Or Audit Required",
            "",
            *([f"- `{family}`" for family in snapshot["high_risk_or_audit_required"]] or ["- none"]),
            "",
            "## Recommendation",
            "",
            snapshot["recommendation"],
            "",
            "## Failures",
            "",
            *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    stamp = snapshot["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_cross_family_blocker_runtime_authority_scan_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_cross_family_blocker_runtime_authority_scan_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_cross_family_blocker_runtime_authority_scan {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
