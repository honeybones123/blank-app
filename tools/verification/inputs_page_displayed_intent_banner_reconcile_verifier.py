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
    json_path = ARTIFACT_DIR / f"inputs_page_displayed_intent_banner_reconcile_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_displayed_intent_banner_reconcile_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_design_guide_guidance_intent_debug_rows": inputs_page._design_guide_guidance_intent_debug_rows,
        "_design_guide_banner_matches_current_render": inputs_page._design_guide_banner_matches_current_render,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
    }
    banner_keys = [
        inputs_page.DESIGN_GUIDE_APPLY_BANNER_KEY,
        inputs_page.DESIGN_GUIDE_APPLY_BANNER_META_KEY,
        inputs_page.DESIGN_GUIDE_PENDING_STEP_CTX_KEY,
        "_design_guide_banner_generic_only",
    ]
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for original_name, original_value in originals.items():
            setattr(inputs_page, original_name, original_value)
        for key in banner_keys:
            try:
                inputs_page.st.session_state.pop(key, None)
            except Exception:
                pass

    def _run_case(
        name: str,
        *,
        guidance_items: list[dict],
        render_plan: dict[str, Any],
        terminal_state: str | None = None,
        fast_focus_section: str | None = None,
        banner_payload: dict | None = None,
        banner_meta: dict | None = None,
        banner_matches: bool = False,
        button_enabled: bool = True,
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []
        stages: list[str] = []
        debug: dict[str, Any] = {"existing": True}

        def _intent_rows(items):
            rows = [{"id": dict(item).get("id"), "intent": dict(item).get("guidance_intent")} for item in items]
            events.append({"event": "intent_rows", "rows": rows})
            return rows

        def _banner_matches(payload, meta, recommendation, pending, fingerprint):
            events.append(
                {
                    "event": "banner_matches",
                    "payload": dict(payload or {}),
                    "meta": dict(meta or {}),
                    "fingerprint": fingerprint,
                }
            )
            return banner_matches

        def _button_enabled(contract):
            events.append({"event": "button_enabled", "contract": dict(contract or {})})
            return button_enabled

        try:
            inputs_page._design_guide_guidance_intent_debug_rows = _intent_rows
            inputs_page._design_guide_banner_matches_current_render = _banner_matches
            inputs_page._design_guide_button_contract_enabled = _button_enabled
            if banner_payload is not None:
                inputs_page.st.session_state[inputs_page.DESIGN_GUIDE_APPLY_BANNER_KEY] = dict(banner_payload)
            if banner_meta is not None:
                inputs_page.st.session_state[inputs_page.DESIGN_GUIDE_APPLY_BANNER_META_KEY] = dict(banner_meta)
            inputs_page.st.session_state[inputs_page.DESIGN_GUIDE_PENDING_STEP_CTX_KEY] = {"pending": True}
            inputs_page.st.session_state["_design_guide_banner_generic_only"] = True

            (
                out_debug,
                visible_items,
                matches,
                reconciled,
                render_banner,
            ) = inputs_page.render_design_guide_displayed_intent_and_banner_reconcile(
                guidance_items=[dict(item) for item in guidance_items],
                guidance_debug=debug,
                render_plan=dict(render_plan),
                recommendation_result={"rec": True},
                pending_recommendation={"pending": True},
                fingerprint="fp-unit",
                terminal_state=terminal_state,
                fast_focus_section=fast_focus_section,
                stage=lambda label: stages.append(str(label)),
            )
            session_after = {
                key: inputs_page.st.session_state.get(key)
                for key in banner_keys
                if key in inputs_page.st.session_state
            }
        finally:
            _restore()

        case = {
            "name": name,
            "events": events,
            "stages": stages,
            "debug": out_debug,
            "visible_items": visible_items,
            "matches": matches,
            "reconciled": reconciled,
            "render_banner": render_banner,
            "session_after": session_after,
        }
        cases.append(case)
        return case

    primary_only = _run_case(
        "primary_only_no_banner",
        guidance_items=[
            {"id": "primary", "guidance_intent": "start"},
            {"id": "secondary", "guidance_intent": "secondary"},
        ],
        render_plan={"render_primary_only": True, "visible_guidance_items": [{"id": "secondary"}]},
    )
    if primary_only["visible_items"] != [{"id": "primary", "guidance_intent": "start"}]:
        failures.append(f"primary_only_visible_mismatch:{primary_only['visible_items']}")
    if primary_only["debug"].get("displayed_guidance_intent_items") != [{"id": "primary", "intent": "start"}]:
        failures.append(f"primary_only_intent_rows_mismatch:{primary_only['debug']}")
    if primary_only["reconciled"] != "no_banner_present" or primary_only["matches"] is not False:
        failures.append(f"primary_only_reconcile_mismatch:{primary_only}")

    kept = _run_case(
        "kept_matching_banner",
        guidance_items=[{"id": "primary"}],
        render_plan={"render_primary_only": False, "visible_guidance_items": [{"id": "visible"}]},
        fast_focus_section="model",
        banner_payload={"banner": True},
        banner_meta={"meta": True},
        banner_matches=True,
    )
    if kept["visible_items"] != [{"id": "visible"}]:
        failures.append(f"kept_visible_mismatch:{kept['visible_items']}")
    if kept["reconciled"] != "kept_matching_banner" or kept["matches"] is not True or kept["render_banner"] is not True:
        failures.append(f"kept_reconcile_mismatch:{kept}")
    if inputs_page.DESIGN_GUIDE_APPLY_BANNER_KEY not in kept["session_after"]:
        failures.append(f"kept_banner_missing:{kept['session_after']}")

    terminal = _run_case(
        "terminal_clears_banner",
        guidance_items=[{"id": "primary"}],
        render_plan={"render_primary_only": False, "visible_guidance_items": [{"id": "visible"}]},
        terminal_state="optimal",
        fast_focus_section="model",
        banner_payload={"banner": True},
        banner_meta={"meta": True},
        banner_matches=True,
    )
    if terminal["reconciled"] != "cleared_terminal_state" or terminal["matches"] is not False:
        failures.append(f"terminal_reconcile_mismatch:{terminal}")
    if terminal["render_banner"] is not False:
        failures.append(f"terminal_render_banner_mismatch:{terminal['render_banner']}")
    if terminal["session_after"] != {"_design_guide_banner_generic_only": False}:
        failures.append(f"terminal_session_mismatch:{terminal['session_after']}")

    stale = _run_case(
        "stale_banner_cleared",
        guidance_items=[{"id": "primary"}],
        render_plan={"render_primary_only": False, "visible_guidance_items": [{"id": "visible"}]},
        fast_focus_section="model",
        banner_payload={"banner": True},
        banner_meta={"meta": True},
        banner_matches=False,
    )
    if stale["reconciled"] != "cleared_stale_banner" or stale["render_banner"] is not False:
        failures.append(f"stale_reconcile_mismatch:{stale}")
    if inputs_page.DESIGN_GUIDE_APPLY_BANNER_KEY in stale["session_after"]:
        failures.append(f"stale_banner_not_cleared:{stale['session_after']}")

    duplicate = _run_case(
        "duplicate_terminal_primary_suppresses_banner",
        guidance_items=[{"id": "primary"}],
        render_plan={
            "render_primary_only": False,
            "visible_guidance_items": [
                {
                    "id": "visible",
                    "status": "PASS",
                    "button_contract": {"enabled": False},
                }
            ],
        },
        fast_focus_section="model",
        banner_payload={"banner": True},
        banner_meta={"meta": True},
        banner_matches=True,
        button_enabled=False,
    )
    if duplicate["reconciled"] != "suppressed_duplicate_terminal_primary_card":
        failures.append(f"duplicate_reconciled_mismatch:{duplicate['reconciled']}")
    if duplicate["render_banner"] is not False:
        failures.append(f"duplicate_render_banner_mismatch:{duplicate['render_banner']}")
    if not any(event.get("event") == "button_enabled" for event in duplicate["events"]):
        failures.append(f"duplicate_button_check_missing:{duplicate['events']}")

    expected_stages = ["post_plan.after_displayed_intent_debug_rows", "post_plan.after_banner_reconcile"]
    for case in cases:
        if case["stages"] != expected_stages:
            failures.append(f"{case['name']}_stages_mismatch:{case['stages']}")

    payload = {
        "verifier": "inputs_page_displayed_intent_banner_reconcile_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Displayed Intent Banner Reconcile Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` reconciled: `{case['reconciled']}`, render_banner: `{case['render_banner']}`"
                    for case in cases
                ),
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
        print("failures=" + ",".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
