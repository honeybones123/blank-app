from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


class _FakeSessionState(dict):
    pass


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state = _FakeSessionState()


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_terminal_exact_acceptance_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_terminal_exact_acceptance_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patched_names = [
        "st",
        "_terminal_exact_cleanup_blocker_should_render_green",
        "_normalise_terminal_exact_cleanup_card",
        "_overview_active_failure_keys",
        "_overview_required_checks_acceptable",
    ]
    originals = {name: getattr(inputs_page, name) for name in patched_names}
    fake_st = _FakeStreamlit()
    calls: list[dict] = []
    failures: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def should_render_green(item, overview, contract, exact):
        exact_dict = dict(exact or {})
        calls.append(
            {
                "event": "should_render_green",
                "title": (item or {}).get("title_main"),
                "overview": dict(overview or {}),
                "contract": dict(contract or {}),
                "exact": exact_dict,
            }
        )
        return bool(exact_dict.get("shear") or exact_dict.get("bending"))

    def normalise(item, overview, contract, exact):
        exact_dict = dict(exact or {})
        calls.append(
            {
                "event": "normalise",
                "title": (item or {}).get("title_main"),
                "overview": dict(overview or {}),
                "contract": dict(contract or {}),
                "exact": exact_dict,
            }
        )
        out = dict(item or {})
        out["title_main"] = out.get("title_main") or "Further cleanup blocked"
        out["display_truth"] = {"displayed_status": "PASS", "displayed_util": 0.91}
        new_contract = dict(contract or {})
        new_contract.update({"enabled": False, "normalised": True})
        return out, new_contract

    try:
        inputs_page.st = fake_st
        inputs_page._terminal_exact_cleanup_blocker_should_render_green = should_render_green
        inputs_page._normalise_terminal_exact_cleanup_card = normalise
        inputs_page._overview_active_failure_keys = lambda overview: []
        inputs_page._overview_required_checks_acceptable = lambda overview: True

        current_debug = {"overview": {"utils": {"shear": 0.7}}}
        current_item, current_contract, current_truth = (
            inputs_page.render_design_guide_post_cleanup_invalid_render_terminal_exact_acceptance(
                blocked_render_item={
                    "title_main": "Shear cleanup blocked by final efficiency threshold",
                    "button_contract": {"enabled": False},
                    "exact_blockers_by_family": {
                        "shear": {
                            "failed_check_name": "final_shear_threshold",
                            "reason": "No more safe shear cleanup",
                            "no_second_cta_required": True,
                            "cleanup_search_exhaustive": True,
                            "executable_target_band_candidate_count": 0,
                        }
                    },
                },
                blocked_render_truth={"displayed_status": "BLOCKED"},
                blocked_render_util=0.7,
                dg_overview={},
                guidance_debug=current_debug,
            )
        )

        fake_st.session_state[inputs_page.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY] = {
            "post_apply_exact_blockers_by_family": {
                "bending": {
                    "failed_check_name": "final_bending_threshold",
                    "reason": "No more safe bending cleanup",
                    "no_second_cta_required": True,
                    "cleanup_search_exhaustive": True,
                    "executable_target_band_candidate_count": 0,
                }
            }
        }
        last_apply_debug = {"overview": {"utils": {"bending": 0.75}}}
        last_apply_item, last_apply_contract, last_apply_truth = (
            inputs_page.render_design_guide_post_cleanup_invalid_render_terminal_exact_acceptance(
                blocked_render_item={
                    "title_main": "Specific blocker",
                    "button_contract": {"enabled": False},
                },
                blocked_render_truth={"displayed_status": "BLOCKED"},
                blocked_render_util=0.75,
                dg_overview={},
                guidance_debug=last_apply_debug,
            )
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    normalise_calls = [call for call in calls if call["event"] == "normalise"]
    expect(
        "current_exact_acceptance",
        current_contract == {"enabled": False, "normalised": True}
        and current_truth == {"displayed_status": "PASS", "displayed_util": 0.91}
        and current_item.get("button_contract") == current_contract
        and current_item.get("display_truth") == current_truth
        and current_debug.get("post_click_design_guide_state") == "accepted_green"
        and current_debug.get("post_click_accepted_green") is True
        and current_debug.get("design_guide_terminal_state") == "optimal"
        and current_debug.get("terminal_state_blocked_by_local_cleanup") is False
        and current_debug.get("primary_guidance_intent") == "already_efficient",
        f"current_item={current_item} current_contract={current_contract} current_debug={current_debug}",
    )
    expect(
        "last_apply_exact_acceptance",
        last_apply_contract == {"enabled": False, "normalised": True}
        and last_apply_truth == {"displayed_status": "PASS", "displayed_util": 0.91}
        and last_apply_item.get("exact_blockers_by_family") == {
            "bending": {
                "failed_check_name": "final_bending_threshold",
                "reason": "No more safe bending cleanup",
                "no_second_cta_required": True,
                "cleanup_search_exhaustive": True,
                "executable_target_band_candidate_count": 0,
            }
        }
        and last_apply_debug.get("exact_blockers_by_family") == last_apply_item.get("exact_blockers_by_family")
        and last_apply_debug.get("post_click_design_guide_state") == "accepted_green"
        and last_apply_debug.get("terminal_state_blocked_by_local_cleanup") is False
        and last_apply_debug.get("primary_guidance_intent") == "already_efficient",
        f"last_apply_item={last_apply_item} last_apply_debug={last_apply_debug}",
    )
    expect(
        "normalise_call_sources",
        len(normalise_calls) == 2
        and normalise_calls[0]["exact"].get("shear")
        and normalise_calls[1]["exact"].get("bending"),
        f"normalise_calls={normalise_calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "current_item": current_item,
        "current_contract": current_contract,
        "current_truth": current_truth,
        "current_debug": current_debug,
        "last_apply_item": last_apply_item,
        "last_apply_contract": last_apply_contract,
        "last_apply_truth": last_apply_truth,
        "last_apply_debug": last_apply_debug,
        "calls": calls,
        "failures": failures,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Terminal Exact Acceptance Verifier",
                "",
                f"Verdict: `{result['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Failures",
                "",
                *(f"- {failure}" for failure in failures),
            ]
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "json": str(json_path),
                "report": str(report_path),
                "failures": failures,
            },
            indent=2,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
