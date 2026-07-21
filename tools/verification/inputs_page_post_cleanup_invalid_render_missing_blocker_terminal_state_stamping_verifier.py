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


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_missing_blocker_terminal_state_stamping_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_missing_blocker_terminal_state_stamping_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_guidance_item": inputs_page._guidance_item,
        "_design_guide_item_is_accepted_terminal_with_exact_stop": (
            inputs_page._design_guide_item_is_accepted_terminal_with_exact_stop
        ),
    }
    calls: list[dict] = []
    failures: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def guidance_item(family, title, reasoning, a, why, checks, b, c, *, status, util):
        calls.append(
            {
                "event": "guidance_item",
                "family": family,
                "title": title,
                "reasoning": reasoning,
                "why": why,
                "checks": checks,
                "status": status,
                "util": util,
            }
        )
        return {
            "family": family,
            "title_main": title,
            "reasoning": reasoning,
            "status": status,
            "util": util,
        }

    def is_terminal_exact(item):
        calls.append({"event": "is_terminal_exact", "title": (item or {}).get("title_main")})
        return bool((item or {}).get("terminal_exact"))

    try:
        inputs_page._guidance_item = guidance_item
        inputs_page._design_guide_item_is_accepted_terminal_with_exact_stop = is_terminal_exact

        missing_debug = {}
        missing_item, missing_terminal = (
            inputs_page.render_design_guide_post_cleanup_invalid_render_missing_blocker_terminal_state_stamping(
                blocked_render_item=None,
                blocked_render_truth={"displayed_status": "BLOCKED"},
                blocked_render_is_best_safe_action=False,
                blocked_render_reason="no exact blocker evidence",
                blocked_render_util=0.62,
                shear_blocker_util=None,
                guidance_debug=missing_debug,
            )
        )

        exact_debug = {}
        exact_item, exact_terminal = (
            inputs_page.render_design_guide_post_cleanup_invalid_render_missing_blocker_terminal_state_stamping(
                blocked_render_item={"title_main": "Accepted exact", "terminal_exact": True},
                blocked_render_truth={"displayed_status": "PASS"},
                blocked_render_is_best_safe_action=False,
                blocked_render_reason="unused",
                blocked_render_util=0.92,
                shear_blocker_util=None,
                guidance_debug=exact_debug,
            )
        )

        shear_debug = {}
        shear_item, shear_terminal = (
            inputs_page.render_design_guide_post_cleanup_invalid_render_missing_blocker_terminal_state_stamping(
                blocked_render_item={"title_main": "Shear cleanup blocked by final efficiency threshold"},
                blocked_render_truth={"displayed_status": "BLOCKED", "displayed_util": 0.58},
                blocked_render_is_best_safe_action=True,
                blocked_render_reason="blocked by threshold",
                blocked_render_util=0.58,
                shear_blocker_util=0.58,
                guidance_debug=shear_debug,
            )
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    expect(
        "missing_fallback_item",
        missing_terminal is False
        and missing_item.get("title_main") == "Design Guide blocker evidence is missing"
        and missing_item.get("guidance_intent") == "specific_blocker"
        and missing_item.get("terminal_state_blocked_by_local_cleanup") is True
        and missing_item.get("button_contract", {}).get("enabled") is False
        and missing_item.get("button_contract", {}).get("blocking_reason") == "no exact blocker evidence",
        f"missing_item={missing_item}",
    )
    expect(
        "missing_debug",
        missing_debug == {
            "post_click_accepted_green": False,
            "terminal_state_blocked_by_local_cleanup": True,
            "terminal_state_blocked_reason": "no exact blocker evidence",
        },
        f"missing_debug={missing_debug}",
    )
    expect(
        "accepted_terminal_debug",
        exact_terminal is True
        and exact_item == {"title_main": "Accepted exact", "terminal_exact": True}
        and exact_debug == {
            "post_click_accepted_green": True,
            "terminal_state_blocked_by_local_cleanup": False,
            "terminal_state_blocked_reason": None,
        },
        f"exact_item={exact_item} exact_debug={exact_debug}",
    )
    expect(
        "best_safe_not_blocked_debug",
        shear_terminal is False
        and shear_debug.get("post_click_accepted_green") is False
        and shear_debug.get("terminal_state_blocked_by_local_cleanup") is False
        and shear_debug.get("terminal_state_blocked_reason") == "blocked by threshold",
        f"shear_debug={shear_debug}",
    )
    expect(
        "shear_display_truth_stamping",
        shear_item.get("family") == "shear"
        and shear_item.get("check_key") == "shear"
        and shear_item.get("bucket") == "efficiency"
        and shear_item.get("status") == "EFFICIENCY"
        and shear_item.get("util") == 0.58
        and shear_item.get("title_util") == "(utilisation = 0.58)"
        and shear_item.get("display_truth") == {"displayed_status": "BLOCKED", "displayed_util": 0.58}
        and shear_item.get("displayed_status") == "BLOCKED"
        and shear_item.get("displayed_util") == 0.58
        and shear_item.get("display_truth_source") == "post_commit_truth",
        f"shear_item={shear_item}",
    )
    expect(
        "call_shape",
        [call["event"] for call in calls] == [
            "guidance_item",
            "is_terminal_exact",
            "is_terminal_exact",
            "is_terminal_exact",
        ],
        f"calls={calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "missing_item": missing_item,
        "missing_terminal": missing_terminal,
        "missing_debug": missing_debug,
        "exact_item": exact_item,
        "exact_terminal": exact_terminal,
        "exact_debug": exact_debug,
        "shear_item": shear_item,
        "shear_terminal": shear_terminal,
        "shear_debug": shear_debug,
        "calls": calls,
        "failures": failures,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Missing Blocker Terminal State Stamping Verifier",
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
