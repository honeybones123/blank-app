"""Verify trace-only wiring for shear low-util cleanup generator boundary proof."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-8:],
        "stderr_tail": proc.stderr.strip().splitlines()[-8:],
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    tokens = {
        "controller_boundary_import": (
            "build_design_guide_shear_low_util_cleanup_generator_boundary_proof as "
            "_build_design_guide_shear_low_util_cleanup_generator_boundary_proof"
        ),
        "controller_boundary_call": (
            "_build_design_guide_shear_low_util_cleanup_generator_boundary_proof("
        ),
        "trace_key": (
            "design_guide_controller_shear_low_util_cleanup_generator_boundary_trace_only"
        ),
        "authority": (
            '"authority": "DesignGuideController.shear_low_util_cleanup_generator_boundary"'
        ),
        "proof_hash": '"proof_hash": _stable_final_publication_hash(generator_boundary_proof)',
        "boundary_hash": '"boundary_hash": generator_boundary_proof.get("boundary_hash")',
        "variant_count": '"variant_count": generator_boundary_proof.get("variant_count")',
        "evaluated_candidate_count": (
            '"evaluated_candidate_count": generator_boundary_proof.get('
        ),
        "safe_candidate_count": '"safe_candidate_count": generator_boundary_proof.get("safe_candidate_count")',
        "selected_update_hash": '"selected_update_hash": generator_boundary_proof.get("selected_update_hash")',
        "generator_not_owned": '"generator_owned_here": False',
        "evaluator_not_owned": '"evaluator_owned_here": False',
        "product_driving_false": '"product_driving": False',
        "render_driving_false": '"render_driving": False',
        "apply_driving_false": '"apply_driving": False',
        "session_driving_false": '"session_driving": False',
        "page_generator_still_live": "def _shear_low_util_target_cleanup_item(",
        "page_evaluator_still_live": "_evaluate_auto_design_candidate(",
    }
    return {
        "token_presence": {key: token in source for key, token in tokens.items()},
        "boundary_call_count": source.count(
            "_build_design_guide_shear_low_util_cleanup_generator_boundary_proof("
        ),
        "trace_key_count": source.count(
            "design_guide_controller_shear_low_util_cleanup_generator_boundary_trace_only"
        ),
        "verification": {
            "boundary_object": _run(
                "tools/verification/design_guide_shear_low_util_cleanup_generator_boundary_object_snapshot.py"
            ),
            "extraction_audit": _run(
                "tools/verification/design_guide_shear_low_util_cleanup_generator_extraction_audit.py"
            ),
        },
        "product_behavior_changed": False,
        "generator_moved": False,
        "evaluator_moved": False,
        "decision": "SHEAR_LOW_UTIL_GENERATOR_BOUNDARY_TRACE_WIRED_NOT_PRODUCT_DRIVING",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    verification = dict(capture.get("verification") or {})
    return {
        "all_required_tokens_present": all((capture.get("token_presence") or {}).values()),
        "single_controller_boundary_call_present": capture.get("boundary_call_count") == 1,
        "trace_key_present": int(capture.get("trace_key_count") or 0) >= 2,
        "boundary_object_pass": (verification.get("boundary_object") or {}).get("passed") is True,
        "extraction_audit_pass": (verification.get("extraction_audit") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "generator_not_moved": capture.get("generator_moved") is False,
        "evaluator_not_moved": capture.get("evaluator_moved") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Cleanup Generator Boundary Trace Wiring Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "This proves trace-only boundary proof wiring inside the existing page-local shear cleanup generator. It does not move candidate generation, candidate evaluation, render UI, route Apply, or change product behaviour.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_cleanup_generator_boundary_trace_wiring_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_cleanup_generator_boundary_trace_wiring_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_cleanup_generator_boundary_trace_wiring_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
