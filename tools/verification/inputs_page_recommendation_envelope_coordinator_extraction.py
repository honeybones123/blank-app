"""Verify one-click recommendation-envelope coordinator extraction."""

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


def _run_case(module: Any, name: str, dbg: dict[str, Any]) -> dict[str, Any]:
    original = getattr(module, "_build_recommendation_envelope", None)
    captured: dict[str, Any] = {}

    def _fake_build_recommendation_envelope(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"captured": dict(kwargs)}

    try:
        module._build_recommendation_envelope = _fake_build_recommendation_envelope
        returned = module._result_recommendation_envelope_coordinator(
            status="ready",
            dbg=dbg,
            commit_audit={"audit": True},
            updates={"D": 650},
            blocked_reason=None,
            commit_eligible=True,
        )
    finally:
        if original is not None:
            module._build_recommendation_envelope = original

    expected_domains = (
        dbg.get("final_target_domains_eval")
        or dbg.get("target_domains_for_band")
        or dbg.get("target_domain_for_band")
        or []
    )
    return {
        "case": name,
        "returned": returned,
        "captured": captured,
        "matches": (
            captured.get("updates") == {"D": 650}
            and captured.get("source") == "one_click_auto_design"
            and captured.get("status") == "ready"
            and captured.get("blocked_reason") is None
            and captured.get("commit_eligible") is True
            and captured.get("audit") == {"audit": True}
            and captured.get("required_domains") == expected_domains
        ),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_result_recommendation_envelope_coordinator")
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    rows = [
        _run_case(module, "final_domains_first", {"final_target_domains_eval": ["shear"], "target_domains_for_band": ["bending"]}),
        _run_case(module, "target_domains_fallback", {"target_domains_for_band": ["bending", "shear"]}),
        _run_case(module, "single_domain_fallback", {"target_domain_for_band": "bending"}),
        _run_case(module, "empty_domains", {}),
    ]
    static_checks = {
        "helper_present": "def _result_recommendation_envelope_coordinator(" in source,
        "helper_contains_envelope_call": "_build_recommendation_envelope(" in helper,
        "helper_sets_one_click_source": 'source="one_click_auto_design"' in helper,
        "helper_preserves_required_domain_precedence": all(
            token in helper
            for token in (
                'dbg.get("final_target_domains_eval")',
                'dbg.get("target_domains_for_band")',
                'dbg.get("target_domain_for_band")',
            )
        ),
        "nested_adapter_delegates": "_result_recommendation_envelope_coordinator(" in run_body,
        "nested_adapter_no_longer_builds_envelope_directly": "_build_recommendation_envelope(" not in run_body,
        "return_call_sites_preserved": run_body.count("_result_recommendation_envelope(") >= 6,
    }
    status = "PASS"
    if not all(static_checks.values()) or any(not row["matches"] for row in rows):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_recommendation_envelope_coordinator",
        "helper_segment": {
            "function": "_result_recommendation_envelope_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "run_segment": {
            "function": "run_one_click_auto_design",
            "start_line": run_start,
            "end_line": run_end,
            "line_count": run_end - run_start + 1,
        },
        "static_checks": static_checks,
        "runtime_rows": rows,
        "product_behavior_changed": False,
        "next_safe_slice": "extract no-action visibility helper or return-payload assembly block",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_recommendation_envelope_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_recommendation_envelope_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# One-Click Recommendation Envelope Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Runtime Rows"])
    for row in payload["runtime_rows"]:
        lines.append(f"- `{row['case']}`: `{row['matches']}`")
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
