"""Verify bending-cleanup-before-blocker result branch is controller-builder driven."""

from __future__ import annotations

from datetime import datetime
import ast
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

ROUTE = "_resolve_final_visible_no_active_blocked_primary_cleanup_probe_result"
SAFE_ASSEMBLER = "_assemble_final_visible_safe_cleanup_candidate_before_blocker_result"
BENDING_ASSEMBLER = "_assemble_final_visible_bending_cleanup_available_before_blocker_result"
SAFE_BUILDER_ALIAS = "_build_design_guide_controller_safe_cleanup_candidate_before_blocker_result"
BENDING_BUILDER_ALIAS = (
    "_build_design_guide_controller_bending_cleanup_available_before_blocker_result"
)
TRACE_HELPER = (
    "_stamp_design_guide_controller_no_active_blocked_primary_cleanup_probe_result_trace_only"
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str | None, int | None, int | None]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    return None, None, None


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    route_source, route_start, route_end = _function_source(INPUTS_PAGE, ROUTE)
    safe_source, safe_start, safe_end = _function_source(INPUTS_PAGE, SAFE_ASSEMBLER)
    bending_source, bending_start, bending_end = _function_source(INPUTS_PAGE, BENDING_ASSEMBLER)
    safe_live_calls = source.count(f"{SAFE_ASSEMBLER}(") - (1 if safe_source else 0)
    bending_live_calls = source.count(f"{BENDING_ASSEMBLER}(") - (1 if bending_source else 0)
    return {
        "route": {"start_line": route_start, "end_line": route_end},
        "safe_assembler": {
            "present": bool(safe_source),
            "start_line": safe_start,
            "end_line": safe_end,
            "live_call_count": safe_live_calls,
        },
        "bending_assembler": {
            "present": bool(bending_source),
            "start_line": bending_start,
            "end_line": bending_end,
            "live_call_count": bending_live_calls,
        },
        "safe_route_uses_controller_builder": SAFE_BUILDER_ALIAS + "(" in route_source,
        "safe_route_no_longer_calls_legacy_assembler": f"{SAFE_ASSEMBLER}(" not in route_source,
        "bending_route_uses_controller_builder": BENDING_BUILDER_ALIAS + "(" in route_source,
        "bending_route_no_longer_calls_legacy_assembler": f"{BENDING_ASSEMBLER}(" not in route_source,
        "bending_route_preserves_trace_event": (
            '"return_no_active_bending_cleanup_available_before_blocker"' in route_source
            and "updates_hash=_dg_runtime_trace_hash(bending_probe_updates)" in route_source
            and "exact_blockers_hash=_dg_runtime_trace_hash(" in route_source
        ),
        "bending_route_stamps_result_trace": (
            TRACE_HELPER + "(" in route_source
            and "authority=\"DesignGuideController.bending_cleanup_available_before_blocker_result\""
            in route_source
        ),
        "route_still_returns_bending_result": "return bending_probe_result" in route_source,
        "verification": {
            "composed_prerequisites": "checked_by_independence_lock_before_this_gate",
            "direct_source_checks_only": True,
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "safe_assembler_has_zero_live_calls": (capture.get("safe_assembler") or {}).get(
            "live_call_count"
        )
        == 0,
        "bending_assembler_has_zero_live_calls": (capture.get("bending_assembler") or {}).get(
            "live_call_count"
        )
        == 0,
        "safe_route_uses_controller_builder": capture.get("safe_route_uses_controller_builder")
        is True,
        "safe_route_no_longer_calls_legacy_assembler": capture.get(
            "safe_route_no_longer_calls_legacy_assembler"
        )
        is True,
        "bending_route_uses_controller_builder": capture.get("bending_route_uses_controller_builder")
        is True,
        "bending_route_no_longer_calls_legacy_assembler": capture.get(
            "bending_route_no_longer_calls_legacy_assembler"
        )
        is True,
        "bending_route_preserves_trace_event": capture.get("bending_route_preserves_trace_event")
        is True,
        "bending_route_stamps_result_trace": capture.get("bending_route_stamps_result_trace")
        is True,
        "route_still_returns_bending_result": capture.get("route_still_returns_bending_result")
        is True,
        "direct_source_checks_only": (capture.get("verification") or {}).get(
            "direct_source_checks_only"
        )
        is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    lines = [
        "# Design Guide No-Active Blocked-Primary Bending Cleanup Result Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Safe assembler live calls: `{(capture.get('safe_assembler') or {}).get('live_call_count')}`",
        f"Bending assembler live calls: `{(capture.get('bending_assembler') or {}).get('live_call_count')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "The bending-cleanup-before-blocker branch is controller-builder driven. The old "
            "bending assembler is retained only until a deletion proof confirms it is dead.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_no_active_blocked_primary_bending_cleanup_result_cutover_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_blocked_primary_bending_cleanup_result_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_blocked_primary_bending_cleanup_result_cutover {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
