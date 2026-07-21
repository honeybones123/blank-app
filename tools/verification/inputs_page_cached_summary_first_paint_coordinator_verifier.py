from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_cached_summary_first_paint_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_cached_summary_first_paint_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patch_names = [
        "st",
        "_resolved_inputs_summary_state",
        "resolve_design_actions",
        "_get_design_guide_fp",
        "_stable_final_publication_hash",
        "_design_guide_sidebar_debug_enabled",
    ]
    originals: dict[str, Any] = {name: getattr(inputs_page, name) for name in patch_names}
    failures: list[str] = []
    cases: list[dict[str, Any]] = []
    hash_inputs: list[Any] = []
    hash_values = iter(["summary_hash", "result_hash"])

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def resolved_summary_state():
        return (
            {"sigma_s_sls": 123.0, "b": 300, "D": 600},
            {"summary_shared_vs_widget_diffs": {"inputs_b": "300"}},
        )

    def resolved_actions(_state):
        return {
            "Mu": 1.0,
            "Mu_pos": 2.0,
            "Mu_neg": 3.0,
            "Vu": 4.0,
            "Nu": 5.0,
            "SLS_M": 6.0,
            "SLS_M_pos": 7.0,
            "SLS_M_neg": 8.0,
            "SLS_V": 9.0,
            "Tu": 10.0,
            "Pu": 11.0,
            "source": "manual",
            "actions_source": "Manual design actions (inputs below)",
            "actions_mode": "manual",
        }

    def stable_hash(value):
        hash_inputs.append(value)
        return next(hash_values)

    try:
        inputs_page._resolved_inputs_summary_state = resolved_summary_state
        inputs_page.resolve_design_actions = resolved_actions
        inputs_page._get_design_guide_fp = lambda state: ("fp", state.get("b"), state.get("D"))
        inputs_page._stable_final_publication_hash = stable_hash
        inputs_page._design_guide_sidebar_debug_enabled = lambda: False
        inputs_page.st = SimpleNamespace(
            session_state={
                "_final_publication_summary_card_html_cache": {
                    "reuse_keys": {
                        "results_version": 2,
                        "result_cache_hash": "result_hash",
                        "summary_action_fp": "summary_hash",
                        "show_landing": False,
                    },
                    "summary_cards_html": "<div>cached summary</div>",
                },
                inputs_page.RESULT_CACHE_KEY: {"result": "cache"},
                "results_version": 2,
            }
        )

        html, debug = inputs_page.render_inputs_cached_summary_html_for_first_paint_coordinator(
            first_paint_landing_expected=False,
        )
        cases.append({"name": "stable_cache_reused", "html": html, "debug": debug})
        if html != "<div>cached summary</div>":
            failures.append(f"stable_cache_html_mismatch:{html}")
        if debug.get("first_paint_cached_summary_reused") is not True:
            failures.append(f"stable_cache_reuse_flag_mismatch:{debug}")
        if debug.get("bypass_reason") != "stable_result_hash":
            failures.append(f"stable_cache_bypass_reason_mismatch:{debug}")
        if debug.get("current_results_version") != 2:
            failures.append(f"stable_cache_results_version_mismatch:{debug}")
        if debug.get("current_result_cache_hash") != "result_hash":
            failures.append(f"stable_cache_result_hash_mismatch:{debug}")
        if debug.get("current_summary_action_fp") != "summary_hash":
            failures.append(f"stable_cache_summary_hash_mismatch:{debug}")

        hash_values = iter(["summary_hash", "result_hash"])
        inputs_page.st.session_state["inputs_dirty"] = True
        html, debug = inputs_page.render_inputs_cached_summary_html_for_first_paint_coordinator(
            first_paint_landing_expected=False,
        )
        cases.append({"name": "dirty_inputs_rejected", "html": html, "debug": debug})
        if html is not None:
            failures.append(f"dirty_inputs_html_not_none:{html}")
        if debug.get("first_paint_cached_summary_reused") is not False:
            failures.append(f"dirty_inputs_reuse_flag_mismatch:{debug}")
        if "inputs_dirty" not in str(debug.get("bypass_reason") or ""):
            failures.append(f"dirty_inputs_reason_missing:{debug}")
    finally:
        _restore()

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def _cached_summary_html_for_first_paint" in source:
        failures.append("nested_cached_summary_first_paint_helper_still_present")
    if "render_inputs_cached_summary_html_for_first_paint_coordinator" not in source:
        failures.append("cached_summary_first_paint_coordinator_missing")
    if len(hash_inputs) != 4:
        failures.append(f"hash_call_count_mismatch:{len(hash_inputs)}")

    payload = {
        "verifier": "inputs_page_cached_summary_first_paint_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
        "hash_call_count": len(hash_inputs),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Cached Summary First Paint Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
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
