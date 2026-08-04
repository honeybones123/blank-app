from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_final_local_cleanup_adapter_promotion_branch_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_final_local_cleanup_adapter_promotion_branch_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original = inputs_page._maybe_promote_safe_local_cleanup_primary
    calls: list[dict[str, Any]] = []
    stages: list[str] = []
    traces: list[dict[str, Any]] = []
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        inputs_page._maybe_promote_safe_local_cleanup_primary = original

    def _install(*, promoted: bool, items: list[dict] | None = None) -> None:
        calls.clear()
        stages.clear()
        traces.clear()

        def _adapter(seed_items, *, state, overview, efficiency_state, mode_config, debug_sink, source):
            calls.append(
                {
                    "seed_items": [dict(item) for item in list(seed_items or [])],
                    "state": dict(state or {}),
                    "overview": dict(overview or {}),
                    "efficiency_state": dict(efficiency_state or {}),
                    "mode_config": dict(mode_config or {}),
                    "source": source,
                }
            )
            if isinstance(debug_sink, dict):
                debug_sink["adapter_touched_debug"] = True
            return list(items or [{"title": "Promoted cleanup", "family": "cleanup"}]), {
                "local_cleanup_promoted": bool(promoted),
                "meta": "ok",
            }

        inputs_page._maybe_promote_safe_local_cleanup_primary = _adapter

    def _stage(label: str) -> None:
        stages.append(label)

    def _trace(label: str, **payload: Any) -> None:
        traces.append({"label": label, **payload})

    def _run_case(
        name: str,
        *,
        seed_items: list[dict],
        skip: bool,
        promoted: bool,
        adapter_items: list[dict] | None = None,
        terminal_state: Any = "optimal",
        terminal_state_source: Any = "old_source",
    ) -> tuple[dict, list, object, object, bool, bool]:
        try:
            _install(promoted=promoted, items=adapter_items)
            result = inputs_page.render_design_guide_final_local_cleanup_adapter_promotion_branch(
                local_cleanup_seed_items=[dict(item) for item in seed_items],
                skip_final_local_cleanup_adapter=skip,
                guidance_items=[{"title": "Original card"}],
                guidance_debug={},
                guidance_disp_state={"D": 400},
                dg_overview={"utils": {"bending": 0.9}},
                efficiency_state={"score": 1},
                dg_mode_cfg={"goal": "balanced"},
                terminal_state=terminal_state,
                terminal_state_source=terminal_state_source,
                stage=_stage,
                trace=_trace,
            )
        finally:
            case = {
                "name": name,
                "calls": list(calls),
                "stages": list(stages),
                "traces": list(traces),
            }
            cases.append(case)
            _restore()
        return result

    promoted_result = _run_case(
        "promotion_updates_guidance_and_terminal_state",
        seed_items=[{"title": "Seed"}],
        skip=False,
        promoted=True,
        adapter_items=[{"title": "Promoted cleanup", "family": "cleanup"}],
    )
    promoted_debug, promoted_items, promoted_terminal, promoted_source, promoted_ran, promoted_flag = promoted_result
    if promoted_items != [{"title": "Promoted cleanup", "family": "cleanup"}]:
        failures.append(f"promoted_items_mismatch:{promoted_items}")
    if promoted_terminal is not None or promoted_source != "blocked_by_safe_local_cleanup":
        failures.append(f"promoted_terminal_mismatch:{promoted_terminal}:{promoted_source}")
    if promoted_debug.get("design_guide_terminal_state") is not None:
        failures.append(f"promoted_terminal_debug_mismatch:{promoted_debug}")
    if promoted_debug.get("design_guide_terminal_state_source") != "blocked_by_safe_local_cleanup":
        failures.append(f"promoted_terminal_source_debug_mismatch:{promoted_debug}")
    if promoted_debug.get("design_guide_has_actionable_recommendation") is not True:
        failures.append(f"promoted_actionable_debug_missing:{promoted_debug}")
    if promoted_debug.get("adapter_touched_debug") is not True:
        failures.append(f"promoted_adapter_debug_not_preserved:{promoted_debug}")
    if promoted_ran is not True or promoted_flag is not True:
        failures.append(f"promoted_flags_mismatch:{promoted_ran}:{promoted_flag}")
    if cases[-1]["stages"] != [
        "post_plan.before_final_local_cleanup_adapter",
        "post_plan.after_final_local_cleanup_adapter",
        "post_plan.after_local_cleanup_promoted_branch",
    ]:
        failures.append(f"promoted_stage_order_mismatch:{cases[-1]['stages']}")
    if not cases[-1]["traces"] or cases[-1]["traces"][0].get("local_cleanup_promoted") is not True:
        failures.append(f"promoted_trace_mismatch:{cases[-1]['traces']}")
    if cases[-1]["traces"][0].get("seed_item_count") != 1 or cases[-1]["traces"][0].get("render_item_count") != 1:
        failures.append(f"promoted_trace_counts_mismatch:{cases[-1]['traces']}")

    no_promote = _run_case(
        "adapter_runs_without_promotion",
        seed_items=[{"title": "Seed"}],
        skip=False,
        promoted=False,
        adapter_items=[{"title": "Candidate but not promoted"}],
        terminal_state="very_low_demand",
        terminal_state_source="old_source",
    )
    if no_promote[1] != [{"title": "Original card"}]:
        failures.append(f"no_promote_items_changed:{no_promote[1]}")
    if no_promote[2] != "very_low_demand" or no_promote[3] != "old_source":
        failures.append(f"no_promote_terminal_changed:{no_promote[2]}:{no_promote[3]}")
    if no_promote[4] is not True or no_promote[5] is not False:
        failures.append(f"no_promote_flags_mismatch:{no_promote[4]}:{no_promote[5]}")
    if cases[-1]["stages"] != [
        "post_plan.before_final_local_cleanup_adapter",
        "post_plan.after_final_local_cleanup_adapter",
    ]:
        failures.append(f"no_promote_stage_order_mismatch:{cases[-1]['stages']}")
    if cases[-1]["traces"][0].get("local_cleanup_promoted") is not False:
        failures.append(f"no_promote_trace_mismatch:{cases[-1]['traces']}")

    skipped = _run_case(
        "skip_flag_bypasses_adapter",
        seed_items=[{"title": "Seed"}],
        skip=True,
        promoted=True,
    )
    if cases[-1]["calls"] or cases[-1]["stages"] or cases[-1]["traces"]:
        failures.append(f"skip_called_unexpectedly:{cases[-1]}")
    if skipped[1] != [{"title": "Original card"}]:
        failures.append(f"skip_items_changed:{skipped[1]}")
    if skipped[4] is not False or skipped[5] is not False:
        failures.append(f"skip_flags_mismatch:{skipped[4]}:{skipped[5]}")

    empty_seed = _run_case(
        "empty_seed_bypasses_adapter",
        seed_items=[],
        skip=False,
        promoted=True,
    )
    if cases[-1]["calls"] or cases[-1]["stages"] or cases[-1]["traces"]:
        failures.append(f"empty_seed_called_unexpectedly:{cases[-1]}")
    if empty_seed[1] != [{"title": "Original card"}]:
        failures.append(f"empty_seed_items_changed:{empty_seed[1]}")
    if empty_seed[4] is not False or empty_seed[5] is not False:
        failures.append(f"empty_seed_flags_mismatch:{empty_seed[4]}:{empty_seed[5]}")

    payload = {
        "verifier": "inputs_page_final_local_cleanup_adapter_promotion_branch_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": [
            {
                "name": case["name"],
                "call_count": len(case["calls"]),
                "stages": case["stages"],
                "traces": case["traces"],
            }
            for case in cases
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Final Local Cleanup Adapter Promotion Branch Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}` stages={case['stages']}" for case in cases),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
