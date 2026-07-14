"""FinalDesignGuidePublication rebuild memo readiness snapshot.

Proof-only. This verifier inventories the remaining live controller/publication
build surface and proves whether identical controller requests produce stable
FinalDesignGuidePublication hashes before any memo/cache implementation.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    DesignGuideControllerRequest,
    run_design_guide_controller_publication_authority,
    stable_design_guide_controller_request_hash,
)
from design_brain.final_publication import stable_final_publication_hash  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

REQUIRED_LOCKS = {
    "cta_apply_binding_bypass_live_impact": "design_guide_cta_apply_binding_bypass_live_impact",
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = artifacts[-1]
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


def _line_numbers(source: str, token: str) -> list[int]:
    lines: list[int] = []
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            lines.append(index)
    return lines


def _count_call(source: str, name: str) -> int:
    return len(re.findall(rf"(?<!def )\b{re.escape(name)}\s*\(", source))


def _request_hash(request: DesignGuideControllerRequest) -> str:
    return stable_design_guide_controller_request_hash(request)


def _sample_request(**overrides: Any) -> DesignGuideControllerRequest:
    item = {
        "title": "Shear capacity is low",
        "title_main": "Shear capacity is low",
        "status": "FAIL",
        "bucket": "fail",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "published_item_id": "sample-shear-fail",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "label": "Apply repair",
            "action_type": "apply_resolved_candidate",
            "updates": {"D": 450, "s_lig": 100},
        },
    }
    debug = {
        "final_publication_cta_hash": "cta-a",
        "final_publication_display_hash": "display-a",
        "final_publication_verifier_payload": {"publication_hash": "publication-a"},
    }
    values = {
        "item": item,
        "debug": debug,
        "design_brain_result": {"selected_family": "SHEAR_FAIL_GOVERNS"},
        "verifier_payload": {"publication_hash": "publication-a"},
                "final_visible_resolution": {},
        "guidance_debug": dict(debug),
        "publication_reason": "sample_publication_reason",
        "source": "sample_memo_readiness",
    }
    values.update(overrides)
    return DesignGuideControllerRequest(**values)


def _stability_scenarios() -> list[dict[str, Any]]:
    stable_request = _sample_request()
    stable_a = run_design_guide_controller_publication_authority(stable_request)
    stable_b = run_design_guide_controller_publication_authority(stable_request)

    changed_item = dict(stable_request.item)
    changed_item["title"] = "Bending capacity is low"
    changed_item["title_main"] = "Bending capacity is low"
    changed_request = _sample_request(item=changed_item)
    changed = run_design_guide_controller_publication_authority(changed_request)

    changed_reason_request = _sample_request(publication_reason="different_reason")
    changed_reason = run_design_guide_controller_publication_authority(changed_reason_request)

    rows = [
        {
            "scenario_id": "identical_controller_request",
            "request_hash_a": _request_hash(stable_request),
            "request_hash_b": _request_hash(stable_request),
            "publication_hash_a": stable_a.publication_hash,
            "publication_hash_b": stable_b.publication_hash,
            "controller_hash_a": stable_a.controller_hash,
            "controller_hash_b": stable_b.controller_hash,
            "controller_request_hash_a": stable_a.request_hash,
            "controller_request_hash_b": stable_b.request_hash,
            "request_hash_stable": _request_hash(stable_request) == _request_hash(stable_request),
            "controller_request_hash_stable": stable_a.request_hash == stable_b.request_hash,
            "computed_request_matches_controller": stable_a.request_hash == _request_hash(stable_request),
            "publication_hash_stable": stable_a.publication_hash == stable_b.publication_hash,
            "controller_hash_stable": stable_a.controller_hash == stable_b.controller_hash,
            "expected_cacheable": True,
        },
        {
            "scenario_id": "changed_item_identity",
            "request_hash_a": _request_hash(stable_request),
            "request_hash_b": _request_hash(changed_request),
            "publication_hash_a": stable_a.publication_hash,
            "publication_hash_b": changed.publication_hash,
            "request_hash_stable": _request_hash(stable_request) == _request_hash(changed_request),
            "publication_hash_stable": stable_a.publication_hash == changed.publication_hash,
            "expected_cacheable": False,
        },
        {
            "scenario_id": "changed_publication_reason",
            "request_hash_a": _request_hash(stable_request),
            "request_hash_b": _request_hash(changed_reason_request),
            "publication_hash_a": stable_a.publication_hash,
            "publication_hash_b": changed_reason.publication_hash,
            "request_hash_stable": _request_hash(stable_request) == _request_hash(changed_reason_request),
            "publication_hash_stable": stable_a.publication_hash == changed_reason.publication_hash,
            "expected_cacheable": False,
        },
    ]
    return rows


def _inventory(input_source: str, controller_source: str, final_source: str) -> dict[str, Any]:
    publication_authority_lines = _line_numbers(
        input_source,
        "_run_design_guide_controller_publication_authority",
    )
    trace_only_lines = _line_numbers(input_source, "_run_design_guide_controller_trace_only")
    return {
        "inputs_direct_final_publication_build_calls": _count_call(
            input_source,
            "_build_final_design_guide_publication",
        ),
        "inputs_controller_publication_authority_calls": len(publication_authority_lines),
        "inputs_controller_trace_only_calls": len(trace_only_lines),
        "inputs_controller_publication_authority_lines": publication_authority_lines,
        "inputs_controller_trace_only_lines": trace_only_lines,
        "controller_direct_final_publication_build_calls": _count_call(
            controller_source,
            "build_final_design_guide_publication",
        ),
        "controller_has_plain_request_dataclass": "class DesignGuideControllerRequest" in controller_source,
        "controller_response_exposes_request_hash": (
            "request_hash: str" in controller_source
            and "request_source: str" in controller_source
            and "request_hash=request_hash" in controller_source
        ),
        "controller_builds_collapsed_guidance_item": (
            "build_collapsed_guidance_item_from_final_publication" in controller_source
        ),
        "controller_builds_post_resolver_proof": (
            "build_final_design_guide_post_resolver_mutation_proof" in controller_source
        ),
        "final_publication_no_page_imports": (
            "inputs_page" not in final_source and "streamlit" not in final_source
        ),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Final Publication Rebuild Memo Readiness Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Ready for live memo implementation: `{payload['ready_for_live_memo_implementation']}`",
        f"- Ready for live request-key wiring proof: `{payload['ready_for_live_request_key_wiring_proof']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Inventory",
        "",
        "```json",
        json.dumps(payload["inventory"], indent=2, sort_keys=True),
        "```",
        "",
        "## Stability Scenarios",
        "",
        "| Scenario | Request hash stable | Publication hash stable | Expected cacheable |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["stability_scenarios"]:
        lines.append(
            "| `{scenario}` | `{request}` | `{publication}` | `{expected}` |".format(
                scenario=_escape_md(row["scenario_id"]),
                request=row["request_hash_stable"],
                publication=row["publication_hash_stable"],
                expected=row["expected_cacheable"],
            )
        )
    lines.extend(["", "## Locks", ""])
    for name, lock in payload["locks"].items():
        lines.append(f"- `{name}`: passed=`{lock['passed']}`, path=`{lock['path']}`")
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

    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    controller_source = CONTROLLER.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    locks = {name: _latest(prefix) for name, prefix in REQUIRED_LOCKS.items()}
    inventory = _inventory(input_source, controller_source, final_source)
    scenarios = _stability_scenarios()

    failures: list[str] = []
    for name, lock in locks.items():
        if lock.get("passed") is not True:
            failures.append(f"{name}_not_passed")
    if inventory["inputs_direct_final_publication_build_calls"] != 0:
        failures.append("inputs_page_still_directly_builds_final_publication")
    if inventory["inputs_controller_publication_authority_calls"] <= 0:
        failures.append("no_live_controller_publication_authority_calls_found")
    if inventory["controller_direct_final_publication_build_calls"] != 1:
        failures.append("controller_publication_build_call_count_unexpected")
    if not inventory["controller_response_exposes_request_hash"]:
        failures.append("controller_response_does_not_expose_request_hash")
    if not inventory["final_publication_no_page_imports"]:
        failures.append("final_publication_imports_page_or_ui")

    stable = next(row for row in scenarios if row["scenario_id"] == "identical_controller_request")
    if not (
        stable["request_hash_stable"]
        and stable["controller_request_hash_stable"]
        and stable["computed_request_matches_controller"]
        and stable["publication_hash_stable"]
        and stable["controller_hash_stable"]
    ):
        failures.append("identical_controller_request_not_stable")
    for row in scenarios:
        if row["scenario_id"] != "identical_controller_request" and row["request_hash_stable"]:
            failures.append(f"{row['scenario_id']}_request_hash_did_not_change")

    passed = not failures
    ready_for_wiring = passed and inventory["inputs_controller_publication_authority_calls"] > 0
    payload = {
        "schema": "design_guide_final_publication_rebuild_memo_readiness_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if passed else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "inventory": inventory,
        "stability_scenarios": scenarios,
        "ready_for_live_request_key_wiring_proof": ready_for_wiring,
        "ready_for_live_memo_implementation": False,
        "memo_key_candidate": "DesignGuideControllerRequest normalized hash",
        "locks": {
            name: {"path": lock.get("path"), "passed": lock.get("passed"), "found": lock.get("found")}
            for name, lock in locks.items()
        },
        "snapshot_hash": _stable_hash(
            {
                "inventory": inventory,
                "scenarios": scenarios,
                "locks": {name: lock.get("path") for name, lock in locks.items()},
            }
        ),
        "recommended_next_slice": (
            "Wire a trace-only live request-key proof beside controller publication-authority calls, "
            "then compare repeated request hashes on stable reruns before implementing memoization."
        ),
    }

    stamp = payload["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_final_publication_rebuild_memo_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_publication_rebuild_memo_readiness_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_final_publication_rebuild_memo_readiness_snapshot {payload['status']}")
    print(f"ready_for_live_request_key_wiring_proof={payload['ready_for_live_request_key_wiring_proof']}")
    print(f"ready_for_live_memo_implementation={payload['ready_for_live_memo_implementation']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

