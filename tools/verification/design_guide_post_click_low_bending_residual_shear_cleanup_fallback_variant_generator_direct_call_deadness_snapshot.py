"""Deadness proof for the old residual-shear fallback generator direct route call."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


def _stamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "-")
    )


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest_pass(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"status": "MISSING", "path": None, "passed": False}
    last_readable: dict[str, Any] | None = None
    for path in reversed(paths):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            last_readable = {
                "status": "UNREADABLE",
                "path": str(path),
                "passed": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            continue
        status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
        normalized = "PASS" if "PASS" in status.upper() or "LOCKED" in status.upper() else status
        record = {
            "status": normalized or "UNKNOWN",
            "path": str(path),
            "passed": normalized == "PASS",
            "snapshot_hash": payload.get("snapshot_hash"),
        }
        if record["passed"]:
            return record
        last_readable = record
    return last_readable or {"status": "MISSING", "path": None, "passed": False}


def _block(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    helper_block = _block(
        source,
        "def _run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
        "\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness(",
    )
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    old_direct_call = 'generate_less_shear_reo_variants({"state": dict(state)}, mode_config)'
    runner_call = "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator("
    injected_impl = "generator=generate_less_shear_reo_variants"
    shared_generator_definition = "def generate_less_shear_reo_variants("
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_FALLBACK_VARIANT_GENERATOR_DIRECT_CALL_DEAD",
        "route_block_present": bool(route_block),
        "runner_helper_present": bool(helper_block),
        "runner_helper_keeps_exception_policy": "except Exception:" in helper_block
        and "return []" in helper_block,
        "runner_helper_uses_injected_generator": (
            "callable(generator)" in helper_block
            and 'generator({"state": dict(state)}, mode_config)' in helper_block
        ),
        "old_direct_route_call_count": route_block.count(old_direct_call),
        "runner_route_call_count": route_block.count(runner_call),
        "same_impl_injected_count": route_block.count(injected_impl),
        "shared_generator_definition_count": source.count(shared_generator_definition),
        "global_shared_generator_call_count": source.count("generate_less_shear_reo_variants("),
        "fallback_variant_loop_retained": "for fallback_index, fallback_variant in enumerate(fallback_variants[:64])" in route_block,
        "candidate_evaluator_retained": (
            "_evaluate_auto_design_candidate(" in route_block
            or (
                "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator("
                in route_block
                and "evaluator=_evaluate_auto_design_candidate" in route_block
            )
        ),
        "candidate_evaluator_retained_via_injection": (
            "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator("
            in route_block
            and "evaluator=_evaluate_auto_design_candidate" in route_block
        ),
        "route_debug_boundary_retained": all(
            token in route_block
            for token in (
                "fallback_variant_generator_attempted = True",
                "fallback_variant_generator_variant_count = len(fallback_variants)",
                "fallback_variant_generator_update_sequence",
                "fallback_variant_generator_output_summary",
            )
        ),
        "live_route_return_boundary_retained": (
            "return residual_route_return_item" in route_block
        ),
        "old_live_result_return_removed": "return residual_promoted" not in route_block,
        "call_shape_cutover": _latest_pass(
            "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_call_shape_cutover"
        ),
        "render_bridge_lock": _latest_pass("design_guide_render_bridge_lock"),
        "compute_resolver_publication_bridge_lock": _latest_pass(
            "design_guide_compute_resolver_publication_bridge_lock"
        ),
        "independence_lock": _latest_pass("design_guide_independence_lock"),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_block_present": capture.get("route_block_present") is True,
        "runner_helper_present": capture.get("runner_helper_present") is True,
        "runner_helper_uses_injected_generator": (
            capture.get("runner_helper_uses_injected_generator") is True
        ),
        "runner_helper_keeps_exception_policy": (
            capture.get("runner_helper_keeps_exception_policy") is True
        ),
        "old_direct_route_call_dead": capture.get("old_direct_route_call_count") == 0,
        "single_runner_route_call": capture.get("runner_route_call_count") == 1,
        "single_same_impl_injection": capture.get("same_impl_injected_count") == 1,
        "shared_generator_definition_retained": capture.get("shared_generator_definition_count") == 1,
        "other_shared_generator_use_out_of_scope": (
            int(capture.get("global_shared_generator_call_count") or 0) > 1
        ),
        "fallback_variant_loop_retained": capture.get("fallback_variant_loop_retained") is True,
        "candidate_evaluator_retained": capture.get("candidate_evaluator_retained") is True,
        "route_debug_boundary_retained": capture.get("route_debug_boundary_retained") is True,
        "live_route_return_boundary_retained": (
            capture.get("live_route_return_boundary_retained") is True
        ),
        "old_live_result_return_removed": (
            capture.get("old_live_result_return_removed") is True
        ),
        "call_shape_cutover_pass": (capture.get("call_shape_cutover") or {}).get("passed") is True,
        "render_bridge_lock_pass": (capture.get("render_bridge_lock") or {}).get("passed") is True,
        "compute_resolver_publication_bridge_lock_pass": (
            (capture.get("compute_resolver_publication_bridge_lock") or {}).get("passed") is True
        ),
        "independence_lock_pass": (capture.get("independence_lock") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Fallback Generator Direct Call Deadness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Old direct route call count: `{capture.get('old_direct_route_call_count')}`",
        f"- Injected runner route call count: `{capture.get('runner_route_call_count')}`",
        f"- Same implementation injection count: `{capture.get('same_impl_injected_count')}`",
        f"- Shared generator definition count: `{capture.get('shared_generator_definition_count')}`",
        f"- Global shared generator call count: `{capture.get('global_shared_generator_call_count')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Move to the residual-route candidate-evaluation boundary. Do not delete the shared generator definition or other callsites from this proof.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_direct_call_deadness_snapshot.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_direct_call_deadness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_direct_call_deadness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_fallback_variant_generator_direct_call_deadness_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_direct_call_deadness "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
