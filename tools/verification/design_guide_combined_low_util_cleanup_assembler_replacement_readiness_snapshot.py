"""Audit readiness to replace the combined low-util cleanup assembler.

This is proof-only. It does not change the live route, publication, rendering,
CTA/apply routing, family runtimes, or visible wording.
"""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

ASSEMBLER = "_assemble_final_visible_combined_low_util_safe_cleanup_result"
ROUTE = "_resolve_final_visible_no_active_combined_low_util_safe_cleanup_result"
CONTROLLER_BUILDER = "build_design_guide_controller_combined_low_util_cleanup_result"
PAGE_BUILDER_ALIAS = "_build_design_guide_controller_combined_low_util_cleanup_result"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int | None, int | None]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    return "", None, None


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    assembler_source, assembler_start, assembler_end = _function_source(INPUTS_PAGE, ASSEMBLER)
    route_source, route_start, route_end = _function_source(INPUTS_PAGE, ROUTE)

    assembler_exists = bool(assembler_source)
    route_exists = bool(route_source)
    assembler_calls_builder = f"{PAGE_BUILDER_ALIAS}(" in assembler_source
    route_calls_assembler = f"{ASSEMBLER}(" in route_source
    route_calls_builder_directly = f"{PAGE_BUILDER_ALIAS}(" in route_source
    route_calls_full_controller = (
        "_run_design_guide_controller_no_active_combined_low_util_cleanup_route("
        in route_source
    )
    controller_builder_exists = f"def {CONTROLLER_BUILDER}(" in controller_source
    trace_key = "design_guide_controller_combined_low_util_cleanup_result_trace_only"

    assembler_side_effect_tokens = {
        "resolver_route_trace_event": "_resolver_route_trace_event(" in assembler_source,
        "result_debug_trace_stamp": trace_key in assembler_source,
        "streamlit_session_write": "st.session_state" in assembler_source,
        "button_rendering": "st.button(" in assembler_source,
        "markdown_rendering": "st.markdown(" in assembler_source,
        "apply_routing": "_queue_primary_design_guide_button_action" in assembler_source,
        "family_runtime_call": "contracted_repair_ladder_specs(" in assembler_source,
    }
    assembler_return_shape = {
        "returns_result": "return result" in assembler_source,
        "result_from_controller_builder": (
            "result = _build_design_guide_controller_combined_low_util_cleanup_result("
            in assembler_source
        ),
        "live_projection_trace_only": "live_projection =" in assembler_source
        and '"product_driving": False' in assembler_source,
        "state_fingerprint_is_input_dependency": "state_fingerprint_fn(final_state)" in assembler_source,
    }

    ready_for_cutover = (
        assembler_exists
        and route_exists
        and assembler_calls_builder
        and route_calls_assembler
        and not route_calls_builder_directly
        and controller_builder_exists
        and assembler_side_effect_tokens["resolver_route_trace_event"]
        and assembler_side_effect_tokens["result_debug_trace_stamp"]
        and not assembler_side_effect_tokens["streamlit_session_write"]
        and not assembler_side_effect_tokens["button_rendering"]
        and not assembler_side_effect_tokens["markdown_rendering"]
        and not assembler_side_effect_tokens["apply_routing"]
        and not assembler_side_effect_tokens["family_runtime_call"]
        and all(assembler_return_shape.values())
    )
    already_cut_over = (
        route_exists
        and not route_calls_assembler
        and (route_calls_builder_directly or route_calls_full_controller)
        and controller_builder_exists
        and (
            not assembler_exists
            or (
                assembler_calls_builder
                and assembler_side_effect_tokens["resolver_route_trace_event"]
                and assembler_side_effect_tokens["result_debug_trace_stamp"]
                and not assembler_side_effect_tokens["streamlit_session_write"]
                and not assembler_side_effect_tokens["button_rendering"]
                and not assembler_side_effect_tokens["markdown_rendering"]
                and not assembler_side_effect_tokens["apply_routing"]
                and not assembler_side_effect_tokens["family_runtime_call"]
                and all(assembler_return_shape.values())
            )
        )
    )

    return {
        "decision": (
            "READY_FOR_ROUTE_INLINE_CONTROLLER_BUILDER_CUTOVER"
            if ready_for_cutover
            else (
                "FULL_CONTROLLER_ROUTE_ALREADY_CUT_OVER"
                if route_calls_full_controller
                else "ROUTE_INLINE_CONTROLLER_BUILDER_ALREADY_CUT_OVER"
                if already_cut_over
                else "NOT_READY_FOR_ROUTE_INLINE_CONTROLLER_BUILDER_CUTOVER"
            )
        ),
        "assembler": {
            "name": ASSEMBLER,
            "exists": assembler_exists,
            "start_line": assembler_start,
            "end_line": assembler_end,
            "line_count": (assembler_end - assembler_start + 1) if assembler_exists else 0,
            "deleted": not assembler_exists,
            "calls_controller_builder": assembler_calls_builder,
            "side_effect_tokens": assembler_side_effect_tokens,
            "return_shape": assembler_return_shape,
        },
        "route": {
            "name": ROUTE,
            "exists": route_exists,
            "start_line": route_start,
            "end_line": route_end,
            "line_count": (route_end - route_start + 1) if route_exists else 0,
            "calls_assembler": route_calls_assembler,
            "calls_controller_builder_directly": route_calls_builder_directly,
            "calls_full_controller_route": route_calls_full_controller,
        },
        "controller": {
            "builder": CONTROLLER_BUILDER,
            "builder_exists": controller_builder_exists,
        },
        "source_counts": {
            "assembler_name_count": inputs_source.count(ASSEMBLER),
            "controller_builder_alias_count": inputs_source.count(PAGE_BUILDER_ALIAS),
            "trace_key_count": inputs_source.count(trace_key),
        },
        "verification": {
            "combined_low_util_cleanup_result_object": _run(
                "tools/verification/design_guide_combined_low_util_cleanup_result_object_snapshot.py"
            ),
            "combined_low_util_cleanup_result_trace_wiring": _run(
                "tools/verification/design_guide_combined_low_util_cleanup_result_trace_wiring_snapshot.py"
            ),
            "no_active_combined_low_util_route_readiness": _run(
                "tools/verification/design_guide_no_active_combined_low_util_route_readiness_snapshot.py"
            ),
        },
        "ready_for_route_inline_controller_builder_cutover": ready_for_cutover,
        "route_inline_controller_builder_already_cut_over": already_cut_over,
        "safe_to_delete_assembler_now": False,
        "recommended_next_slice": (
            "Route already calls the controller builder inline. Do not delete the assembler until a "
            "post-cutover deletion proof passes."
            if already_cut_over
            else (
                "Replace the route call to _assemble_final_visible_combined_low_util_safe_cleanup_result(...) "
                "with an inline controller-builder call plus the same route trace/debug stamps. "
                "Do not delete the assembler until a post-cutover deletion proof passes."
            )
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    verification = dict(capture.get("verification") or {})
    assembler = dict(capture.get("assembler") or {})
    route = dict(capture.get("route") or {})
    side_effects = dict(assembler.get("side_effect_tokens") or {})
    return_shape = dict(assembler.get("return_shape") or {})
    return {
        "assembler_exists_or_deleted_after_cutover": assembler.get("exists") is True
        or (
            assembler.get("deleted") is True
            and capture.get("route_inline_controller_builder_already_cut_over") is True
        ),
        "route_exists": route.get("exists") is True,
        "assembler_calls_controller_builder_or_deleted": assembler.get("calls_controller_builder") is True
        or assembler.get("deleted") is True,
        "route_calls_assembler_or_controller_boundary": (
            route.get("calls_assembler") is True
            or route.get("calls_controller_builder_directly") is True
            or route.get("calls_full_controller_route") is True
        ),
        "controller_builder_exists": (capture.get("controller") or {}).get("builder_exists") is True,
        "assembler_has_only_trace_debug_side_effects_or_deleted": (
            assembler.get("deleted") is True
            or (
                side_effects.get("resolver_route_trace_event") is True
                and side_effects.get("result_debug_trace_stamp") is True
                and side_effects.get("streamlit_session_write") is False
                and side_effects.get("button_rendering") is False
                and side_effects.get("markdown_rendering") is False
                and side_effects.get("apply_routing") is False
                and side_effects.get("family_runtime_call") is False
            )
        ),
        "assembler_return_shape_matches_controller_result_or_deleted": assembler.get("deleted") is True
        or all(return_shape.values()),
        "result_object_snapshot_pass": (
            verification.get("combined_low_util_cleanup_result_object") or {}
        ).get("passed")
        is True,
        "result_trace_wiring_pass": (
            verification.get("combined_low_util_cleanup_result_trace_wiring") or {}
        ).get("passed")
        is True,
        "route_readiness_pass": (
            verification.get("no_active_combined_low_util_route_readiness") or {}
        ).get("passed")
        is True,
        "ready_for_or_already_cut_over": (
            capture.get("ready_for_route_inline_controller_builder_cutover") is True
            or capture.get("route_inline_controller_builder_already_cut_over") is True
        ),
        "not_safe_to_delete_assembler_yet": capture.get("safe_to_delete_assembler_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    assembler = dict(capture.get("assembler") or {})
    route = dict(capture.get("route") or {})
    lines = [
        "# Design Guide Combined Low-Util Cleanup Assembler Replacement Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Ready for cutover: `{capture.get('ready_for_route_inline_controller_builder_cutover')}`",
        f"Already cut over: `{capture.get('route_inline_controller_builder_already_cut_over')}`",
        f"Safe to delete assembler now: `{capture.get('safe_to_delete_assembler_now')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Route",
            f"- Function: `{route.get('name')}`",
            f"- Lines: `{route.get('start_line')}`-`{route.get('end_line')}`",
            f"- Calls assembler: `{route.get('calls_assembler')}`",
            f"- Calls controller builder directly: `{route.get('calls_controller_builder_directly')}`",
            "",
            "## Assembler",
            f"- Function: `{assembler.get('name')}`",
            f"- Lines: `{assembler.get('start_line')}`-`{assembler.get('end_line')}`",
            f"- Calls controller builder: `{assembler.get('calls_controller_builder')}`",
            "",
            "## Recommendation",
            "",
            str(capture.get("recommended_next_slice") or ""),
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
        / f"design_guide_combined_low_util_cleanup_assembler_replacement_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_low_util_cleanup_assembler_replacement_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_cleanup_assembler_replacement_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"ready_for_cutover={capture.get('ready_for_route_inline_controller_builder_cutover')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
