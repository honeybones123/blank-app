"""Lock deletion of post-compute active-fail compatibility authority."""

from __future__ import annotations

from dataclasses import fields
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACT = (
    ROOT
    / "artifacts"
    / "verification"
    / "inputs_guidance_entry_guards_runtime_owner.json"
)


def _production_sources() -> list[Path]:
    roots = (
        ROOT / "app.py",
        ROOT / "inputs_page.py",
        ROOT / "application",
        ROOT / "design_brain",
        ROOT / "inputs_application",
        ROOT / "inputs_page_modules",
    )
    paths: list[Path] = []
    for root in roots:
        if root.is_file():
            paths.append(root)
        elif root.is_dir():
            paths.extend(root.rglob("*.py"))
    return sorted(set(paths))


def main() -> int:
    from inputs_application import guidance_entrypoint as entrypoint

    retired_symbol = "_replace_unsafe_combined_active_fail_single_family_action"
    retired_module = (
        ROOT
        / "inputs_page_modules"
        / "design_guide"
        / "active_fail_single_family_guard.py"
    )
    reference_paths = [
        str(path.relative_to(ROOT))
        for path in _production_sources()
        if retired_symbol in path.read_text(encoding="utf-8-sig")
        or "active_fail_single_family_guard" in path.read_text(encoding="utf-8-sig")
    ]

    original_bind = entrypoint._bind_guidance_compute_runtime
    original_compute = entrypoint.compute_design_guidance_items
    calls: list[dict[str, Any]] = []
    payload = {
        "guidance_items": [
            {
                "family": "bending",
                "status": "ACTION",
                "button_contract": {
                    "family": "bending",
                    "enabled": True,
                    "actionable": True,
                    "updates": {"D": 500.0},
                },
            }
        ],
        "debug_trace": {
            "overview": {
                "statuses": {"bending": "FAIL", "shear": "FAIL"},
                "worst_util": 1.4,
            },
            "candidate_search_evidence": {
                "combined_fail_contract_ladder_attempted": False,
                "family_ladder_runtime_result": {},
                "total_candidates_considered": 1,
            },
        },
    }

    try:
        entrypoint._bind_guidance_compute_runtime = lambda **kwargs: calls.append(
            {"stage": "bind", "kwargs": sorted(kwargs)}
        )
        entrypoint.compute_design_guidance_items = (
            lambda *args, **kwargs: json.loads(json.dumps(payload))
        )
        runtime = entrypoint.GuidanceEntrypointRuntime(
            compute_runtime=object(),
            st_module=SimpleNamespace(),
            os_module=SimpleNamespace(),
            sys_module=SimpleNamespace(),
            serviceability_preflight=lambda state: None,
            mixed_width_cleanup_promotion=lambda value, *, state: (
                calls.append({"stage": "promotion", "state": dict(state)})
                or value
            ),
        )
        result = entrypoint.compute_inputs_guidance(
            runtime,
            {"geometry_lock": False},
        )
    finally:
        entrypoint._bind_guidance_compute_runtime = original_bind
        entrypoint.compute_design_guidance_items = original_compute

    runtime_fields = {field.name for field in fields(entrypoint.GuidanceEntrypointRuntime)}
    checks = {
        "retired_module_deleted": not retired_module.exists(),
        "zero_production_references": not reference_paths,
        "runtime_has_no_active_fail_guard_port": "active_fail_guard" not in runtime_fields,
        "not_run_combined_ladder_payload_is_not_terminalised_post_compute": result
        == payload,
        "remaining_post_compute_promotion_runs_once": [
            row.get("stage") for row in calls
        ].count("promotion")
        == 1,
    }
    failures = [name for name, passed in checks.items() if not passed]
    artifact = {
        "schema": "inputs_guidance_entry_guards_runtime_owner.v2",
        "status": "PASS" if not failures else "FAIL",
        "root_cause_category": "candidate_search_failure",
        "checks": checks,
        "failures": failures,
        "production_reference_paths": reference_paths,
        "runtime_fields": sorted(runtime_fields),
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PASS: post-compute active-fail compatibility authority is deleted"
        if not failures
        else f"FAIL: {failures}"
    )
    print(f"Artifact: {ARTIFACT}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
