"""Verify normalized shear truth publish coordinator extraction."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AUTO_DESIGN_COMPUTE = ROOT / "inputs_page_modules" / "auto_design_compute.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _run_success_case(module: Any) -> dict[str, Any]:
    original_st = getattr(module, "st", None)
    original_publish = getattr(module, "publish_normalized_final_shear_truth_to_session", None)
    calls: list[dict[str, Any]] = []
    bundle = {
        "final_shear_truth_bundle_complete": True,
        "shear_truth_status": "resolved",
        "final_shear_truth_resolved": True,
        "final_shear_truth_failure_reason": None,
        "published_result_spacing_mm": 175,
        "published_result_spacing_meaning": "clear_spacing",
    }

    class _FakeSt:
        session_state = {
            "_final_shear_truth_normalized_source": "session-source",
            "_final_shear_truth_normalized_latest": {"from_session": True},
        }

    def _fake_publish(*, source: str) -> dict[str, Any]:
        calls.append({"source": source})
        return dict(bundle)

    target: dict[str, Any] = {"existing": "kept"}
    try:
        module.st = _FakeSt()
        module.publish_normalized_final_shear_truth_to_session = _fake_publish
        returned = module._publish_current_normalized_shear_truth_coordinator(
            "unit-test-source",
            target,
        )
    finally:
        if original_st is not None:
            module.st = original_st
        if original_publish is not None:
            module.publish_normalized_final_shear_truth_to_session = original_publish

    expected_projection = {
        "final_shear_truth_normalized_source": "session-source",
        "final_shear_truth_normalized_latest": {"from_session": True},
        "final_shear_truth_bundle_complete": True,
        "shear_truth_status": "resolved",
        "final_shear_truth_resolved": True,
        "final_shear_truth_failure_reason": None,
        "published_result_spacing_mm": 175,
        "published_result_spacing_meaning": "clear_spacing",
    }
    return {
        "returned": returned,
        "target": target,
        "calls": calls,
        "matches": (
            returned == bundle
            and calls == [{"source": "unit-test-source"}]
            and target.get("existing") == "kept"
            and all(target.get(key) == value for key, value in expected_projection.items())
        ),
    }


def _run_bundle_fallback_case(module: Any) -> dict[str, Any]:
    original_st = getattr(module, "st", None)

    class _FakeSt:
        session_state = {
            "_final_shear_truth_normalized_source": "fallback-source",
            "_final_shear_truth_normalized_latest": None,
        }

    target: dict[str, Any] = {}
    bundle = {"shear_truth_status": "fallback_status", "published_result_spacing_mm": 200}
    try:
        module.st = _FakeSt()
        module._attach_normalized_shear_truth_debug_coordinator(target, bundle)
    finally:
        if original_st is not None:
            module.st = original_st

    return {
        "target": target,
        "matches": (
            target.get("final_shear_truth_normalized_source") == "fallback-source"
            and target.get("final_shear_truth_normalized_latest") == bundle
            and target.get("shear_truth_status") == "fallback_status"
            and target.get("published_result_spacing_mm") == 200
        ),
    }


def _run_exception_case(module: Any) -> dict[str, Any]:
    original_publish = getattr(module, "publish_normalized_final_shear_truth_to_session", None)

    def _raise_publish(*, source: str) -> dict[str, Any]:
        raise RuntimeError(f"boom:{source}")

    target: dict[str, Any] = {"existing": "kept"}
    try:
        module.publish_normalized_final_shear_truth_to_session = _raise_publish
        returned = module._publish_current_normalized_shear_truth_coordinator("failure-source", target)
    finally:
        if original_publish is not None:
            module.publish_normalized_final_shear_truth_to_session = original_publish

    return {
        "returned": returned,
        "target": target,
        "matches": returned is None and target == {"existing": "kept"},
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    attach_start, attach_end, attach_helper = _function_segment(source, "_attach_normalized_shear_truth_debug_coordinator")
    publish_start, publish_end, publish_helper = _function_segment(source, "_publish_current_normalized_shear_truth_coordinator")
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = {
        "success": _run_success_case(module),
        "bundle_fallback": _run_bundle_fallback_case(module),
        "exception": _run_exception_case(module),
    }
    static_checks = {
        "attach_helper_present": "def _attach_normalized_shear_truth_debug_coordinator(" in source,
        "publish_helper_present": "def _publish_current_normalized_shear_truth_coordinator(" in source,
        "attach_helper_projects_expected_fields": all(
            token in attach_helper
            for token in (
                "final_shear_truth_normalized_source",
                "final_shear_truth_normalized_latest",
                "final_shear_truth_bundle_complete",
                "shear_truth_status",
                "final_shear_truth_resolved",
                "final_shear_truth_failure_reason",
                "published_result_spacing_mm",
                "published_result_spacing_meaning",
            )
        ),
        "publish_helper_uses_existing_publisher": "publish_normalized_final_shear_truth_to_session(source=source)" in publish_helper,
        "publish_helper_preserves_exception_return": "except Exception:" in publish_helper and "return None" in publish_helper,
        "run_uses_direct_attach_coordinator": "_attach_normalized_shear_truth_debug_coordinator(" in run_body,
        "run_uses_direct_publish_coordinator": run_body.count("_publish_current_normalized_shear_truth_coordinator(") >= 5,
        "local_adapters_removed": "def _attach_normalized_shear_truth_debug(" not in run_body
        and "def _publish_current_normalized_shear_truth(" not in run_body,
        "legacy_call_sites_removed_from_run": "_publish_current_normalized_shear_truth(" not in run_body
        and "_attach_normalized_shear_truth_debug(" not in run_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or any(not row["matches"] for row in runtime.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_normalized_shear_truth_publish_coordinator",
        "helper_segments": {
            "_attach_normalized_shear_truth_debug_coordinator": {
                "start_line": attach_start,
                "end_line": attach_end,
                "line_count": attach_end - attach_start + 1,
            },
            "_publish_current_normalized_shear_truth_coordinator": {
                "start_line": publish_start,
                "end_line": publish_end,
                "line_count": publish_end - publish_start + 1,
            },
        },
        "run_segment": {
            "function": "run_one_click_auto_design",
            "start_line": run_start,
            "end_line": run_end,
            "line_count": run_end - run_start + 1,
        },
        "static_checks": static_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract the run return latch-clear helper or begin solver-internal trace helper extraction",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_normalized_shear_truth_publish_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_normalized_shear_truth_publish_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Normalized Shear Truth Publish Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Runtime"])
    for key, row in payload["runtime"].items():
        lines.append(f"- `{key}`: `{row['matches']}`")
    lines.extend(["", "## Next Safe Slice", "", str(payload["next_safe_slice"])])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
