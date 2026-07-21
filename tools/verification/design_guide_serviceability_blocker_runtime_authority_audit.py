"""Audit live Design Guide serviceability blocker authority.

This is proof-only. It checks whether crack/deflection/serviceability blocked
Design Guide cards are backed by the locked SERVICEABILITY_GOVERNS runtime or
still sourced from page-owned practical ladder/catalogue logic.
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
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
CRACK_GUIDANCE = ROOT / "inputs_page_modules" / "design_guide" / "crack_guidance.py"
SERVICEABILITY_PREFLIGHT = ROOT / "inputs_page_modules" / "design_guide" / "serviceability_preflight.py"
SERVICEABILITY_FAMILY = ROOT / "design_brain" / "families" / "serviceability.py"
SERVICEABILITY_RUNTIME = ROOT / "design_brain" / "families" / "serviceability_governs" / "runtime.py"
SERVICEABILITY_CONTRACT = ROOT / "design_brain" / "families" / "serviceability_governs" / "contract.json"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.families.serviceability import ServiceabilityFamily  # noqa: E402


LIVE_SERVICEABILITY_FUNCTIONS = (
    "_crack_guidance_item",
    "_deflection_guidance_item",
    "_serviceability_governs_preflight_payload",
    "_active_failure_no_target_blocker_item",
)

LIVE_SERVICEABILITY_SOURCE_PATHS = {
    "_crack_guidance_item": (CRACK_GUIDANCE, APP_CONTRACT_BRIDGE, INPUTS_PAGE),
    "_deflection_guidance_item": (APP_CONTRACT_BRIDGE, INPUTS_PAGE),
    "_serviceability_governs_preflight_payload": (SERVICEABILITY_PREFLIGHT, APP_CONTRACT_BRIDGE, INPUTS_PAGE),
    "_active_failure_no_target_blocker_item": (APP_CONTRACT_BRIDGE, INPUTS_PAGE),
}

LEGACY_SERVICEABILITY_MARKERS = (
    "serviceability_crack_active_failure_ladder",
    "serviceability_deflection_active_failure_ladder",
    "crack_serviceability_practical_ladder_exhausted",
    "deflection_serviceability_practical_ladder_exhausted",
    "No one-click crack-control arrangement from the practical",
    "No one-click deflection arrangement from the practical",
    "Deflection repair is blocked by geometry/serviceability limits",
    "deflection limit",
    "crack control limit",
)

SERVICEABILITY_PREFLIGHT_MARKERS = (
    "SERVICEABILITY_GOVERNS",
    "serviceability_governs_preflight_blocker",
    "serviceability_preflight_family_route",
    "build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence",
)

RUNTIME_AUTHORITY_MARKERS = (
    "evaluate_serviceability_governs",
    "run_serviceability_governs_ladder_runtime",
    "contracted_serviceability_ladder_result",
    "runtime_result",
    "ladder_hash",
    "exhausted_proof",
    "ownership_proof",
    "accepted_lane_evidence",
    "rejected_lane_evidence",
)

REQUIRED_CONTRACT_FIELDS = {
    "serviceability_governing_proof",
    "ladder_trace",
    "accepted_candidate_evidence",
    "rejected_candidate_evidence",
    "ranking_evidence",
    "exact_stop_proof",
    "exhausted_proof",
    "ownership_proof",
    "contract_version",
}


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


def _latest_artifact(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "snapshot": None, "passed": False}
    path = paths[-1]
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    return {
        "found": True,
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS" or snapshot.get("result") == "PASS",
    }


def _run_compile() -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "inputs_page.py",
            "inputs_page_app_contract_bridge.py",
            "inputs_page_modules/design_guide/crack_guidance.py",
            "inputs_page_modules/design_guide/serviceability_preflight.py",
            "design_brain/families/serviceability.py",
            "design_brain/families/serviceability_governs/runtime.py",
            "tools/verification/design_guide_serviceability_blocker_runtime_authority_audit.py",
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


def _contract_coverage() -> dict[str, Any]:
    contract = json.loads(SERVICEABILITY_CONTRACT.read_text(encoding="utf-8"))
    evidence_fields = set(
        ((contract.get("family_result_schema") or {}).get("evidence_required_fields") or [])
    )
    family_owns = set((contract.get("ownership_contract") or {}).get("family_owns") or [])
    return {
        "evidence_required_fields": sorted(evidence_fields),
        "missing_required_runtime_evidence_fields": sorted(REQUIRED_CONTRACT_FIELDS - evidence_fields),
        "family_owns_serviceability_blockers": "serviceability blockers" in family_owns,
        "family_must_not_own_publication": "publication" in set(
            (contract.get("ownership_contract") or {}).get("family_must_not_own") or []
        ),
    }


def _runtime_gateway_probe() -> dict[str, Any]:
    try:
        result = ServiceabilityFamily().contracted_serviceability_ladder_result(
            {
                "selected_family_id": "SERVICEABILITY_GOVERNS",
                "geometry": {"beam_depth_mm": 500.0, "beam_width_mm": 300.0},
                "reinforcement": {"bottom_bar_count": 3},
                "actions": {"current_serviceability_utilisation": 1.2},
                "constraints": {"blocker_reasons": ["proof probe"]},
            }
        )
    except Exception as exc:  # pragma: no cover - surfaced in snapshot
        return {
            "called": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    runtime_result = dict(result.get("runtime_result") or {})
    return {
        "called": True,
        "error": "",
        "contract_runtime_driven": result.get("contract_runtime_driven") is True,
        "runtime_authority": result.get("runtime_authority"),
        "has_ladder_hash": bool(result.get("ladder_hash")),
        "status": result.get("status"),
        "runtime_result_has_exhausted_proof": isinstance(runtime_result.get("exhausted_proof"), dict),
        "runtime_result_has_ownership_proof": isinstance(runtime_result.get("ownership_proof"), dict),
        "runtime_result_keys": sorted(runtime_result.keys()),
    }


def _live_source_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for function_name in LIVE_SERVICEABILITY_FUNCTIONS:
        selected_path = None
        function_source = ""
        for path in LIVE_SERVICEABILITY_SOURCE_PATHS.get(function_name, (INPUTS_PAGE,)):
            source = path.read_text(encoding="utf-8", errors="replace")
            function_source = _function_source(source, function_name)
            if function_source:
                selected_path = path
                break
        legacy_hits = sorted(marker for marker in LEGACY_SERVICEABILITY_MARKERS if marker in function_source)
        runtime_hits = sorted(marker for marker in RUNTIME_AUTHORITY_MARKERS if marker in function_source)
        preflight_hits = sorted(marker for marker in SERVICEABILITY_PREFLIGHT_MARKERS if marker in function_source)
        if runtime_hits and {"ladder_hash", "exhausted_proof"}.issubset(set(runtime_hits)):
            classification = "LIVE_RUNTIME_BACKED"
        elif preflight_hits:
            classification = "LIVE_SERVICEABILITY_PREFLIGHT_BACKED"
        elif legacy_hits:
            classification = "PAGE_PRACTICAL_LADDER_SOURCED"
        else:
            classification = "NO_SERVICEABILITY_BLOCKER_PATH_FOUND"
        rows.append(
            {
                "function": function_name,
                "source_path": str(selected_path) if selected_path else None,
                "legacy_marker_hits": legacy_hits,
                "runtime_authority_hits": runtime_hits,
                "serviceability_preflight_hits": preflight_hits,
                "legacy_marker_count": len(legacy_hits),
                "runtime_authority_hit_count": len(runtime_hits),
                "serviceability_preflight_hit_count": len(preflight_hits),
                "source_hash": _stable_hash(function_source),
                "classification": classification,
            }
        )
    return rows


def _build_snapshot() -> dict[str, Any]:
    compile_result = _run_compile()
    contract = _contract_coverage()
    gateway = _runtime_gateway_probe()
    rows = _live_source_rows()
    latest_lock = _latest_artifact("serviceability_governs_lock_verifier")
    latest_cross_scan = _latest_artifact("design_guide_cross_family_blocker_runtime_authority_scan")

    page_sourced_rows = [row for row in rows if row["classification"] == "PAGE_PRACTICAL_LADDER_SOURCED"]
    runtime_backed_rows = [row for row in rows if row["classification"] == "LIVE_RUNTIME_BACKED"]
    preflight_backed_rows = [row for row in rows if row["classification"] == "LIVE_SERVICEABILITY_PREFLIGHT_BACKED"]
    contract_ready = (
        not contract["missing_required_runtime_evidence_fields"]
        and contract["family_owns_serviceability_blockers"]
    )
    runtime_available = (
        gateway.get("called") is True
        and gateway.get("contract_runtime_driven") is True
        and gateway.get("runtime_authority") == "run_serviceability_governs_ladder_runtime"
    )
    if page_sourced_rows and contract_ready and runtime_available:
        authority_result = "FAIL_PAGE_SERVICEABILITY_BLOCKER_SOURCED"
        recommendation = (
            "Do not treat serviceability blocked cards as runtime-backed yet. Create a narrow cutover so "
            "crack/deflection/serviceability no-repair publication consumes SERVICEABILITY_GOVERNS runtime "
            "evidence, including ladder_hash, exhausted_proof, ownership_proof, accepted/rejected lane evidence, "
            "and contract lane order."
        )
    elif runtime_backed_rows and not page_sourced_rows:
        authority_result = "PASS_RUNTIME_BACKED"
        recommendation = "Serviceability blockers are runtime-backed; proceed to deletion readiness proof."
    elif preflight_backed_rows and not page_sourced_rows:
        authority_result = "PARTIAL_PREFLIGHT_BACKED"
        recommendation = (
            "Serviceability blockers route through the controller-backed preflight path, but this audit "
            "does not prove full SERVICEABILITY_GOVERNS runtime-backed publication."
        )
    else:
        authority_result = "PARTIAL_UNPROVEN"
        recommendation = "Add live serviceability blocker trace coverage before changing product behavior."

    checks = {
        "py_compile_pass": compile_result["passed"],
        "serviceability_lock_artifact_pass": bool(latest_lock.get("passed")),
        "contract_owns_serviceability_blockers": contract_ready,
        "runtime_gateway_available": runtime_available,
        "live_serviceability_blocker_paths_found": bool(page_sourced_rows or runtime_backed_rows or preflight_backed_rows),
        "live_serviceability_blockers_runtime_backed": bool(runtime_backed_rows) and not page_sourced_rows,
        "cross_family_scan_found_serviceability_audit_required": (
            "SERVICEABILITY_GOVERNS" in _stable_json((latest_cross_scan.get("snapshot") or {}).get("high_risk_or_audit_required") or [])
        ),
    }
    required_checks = {
        "py_compile_pass",
        "contract_owns_serviceability_blockers",
        "runtime_gateway_available",
        "live_serviceability_blocker_paths_found",
    }
    failures = [key for key in required_checks if not checks[key]]
    status = "PASS" if not failures else "FAIL"
    proof_surface = {
        "authority_result": authority_result,
        "contract": contract,
        "gateway": gateway,
        "rows": rows,
        "checks": checks,
    }
    return {
        "schema": "design_guide_serviceability_blocker_runtime_authority_audit.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "authority_result": authority_result,
        "checks": checks,
        "failures": failures,
        "contract_coverage": contract,
        "runtime_gateway_probe": gateway,
        "live_source_rows": rows,
        "artifacts_used": {
            "serviceability_lock": latest_lock.get("path"),
            "cross_family_scan": latest_cross_scan.get("path"),
        },
        "verification": {"py_compile": compile_result},
        "recommendation": recommendation,
        "product_behavior_changed": False,
        "snapshot_hash": _stable_hash(proof_surface),
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Serviceability Blocker Runtime Authority Audit",
        "",
        f"Timestamp: `{snapshot['generated_at']}`",
        f"Result: `{snapshot['status']}`",
        f"Authority result: `{snapshot['authority_result']}`",
        f"Snapshot hash: `{snapshot['snapshot_hash']}`",
        "",
        "## Live Source Rows",
        "",
        "| Function | Classification | Legacy markers | Runtime markers |",
        "| --- | --- | --- | --- |",
    ]
    for row in snapshot["live_source_rows"]:
        lines.append(
            "| "
            f"{row['function']} | "
            f"{row['classification']} | "
            f"{row['legacy_marker_count']} | "
            f"{row['runtime_authority_hit_count']} |"
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
            "",
            "## Artifacts Used",
            "",
            f"- Serviceability lock: `{snapshot['artifacts_used']['serviceability_lock']}`",
            f"- Cross-family scan: `{snapshot['artifacts_used']['cross_family_scan']}`",
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
    json_path = ARTIFACT_DIR / f"design_guide_serviceability_blocker_runtime_authority_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_serviceability_blocker_runtime_authority_audit_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_serviceability_blocker_runtime_authority_audit {snapshot['status']}")
    print(f"authority_result={snapshot['authority_result']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
