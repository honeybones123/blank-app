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


class _FakeSidebar:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = events

    def caption(self, text: str) -> None:
        self.events.append({"event": "sidebar.caption", "text": text})


class _FakeStreamlit:
    def __init__(self, events: list[dict[str, Any]], dev_mode: bool) -> None:
        self.session_state = {"_dev_mode": dev_mode}
        self.sidebar = _FakeSidebar(events)


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_title_alignment_assertion_guard_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_title_alignment_assertion_guard_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_design_guide_title_alignment_verification_record": inputs_page._design_guide_title_alignment_verification_record,
        "_design_guide_debug_has_coherent_overview": inputs_page._design_guide_debug_has_coherent_overview,
        "_agent_debug_log": inputs_page._agent_debug_log,
        "st": inputs_page.st,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(
        name: str,
        *,
        overview: dict | None,
        coherent_overview: bool,
        actionable: bool,
        fresh_compute: bool,
        sidebar_debug: bool,
        dev_mode: bool,
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []
        stages: list[str] = []
        logs: list[dict[str, Any]] = []
        title_record = {"title_alignment": name, "ok": True}
        guidance_debug: dict[str, Any] = {
            "overview": overview,
            "design_guide_has_actionable_recommendation": actionable,
        }
        recommendation_result = {
            "winner_id": "winner-1",
            "recommendation_id": "rec-1",
            "apply": {"mode": "unit"},
        }

        def _title_alignment_record(**kwargs):
            events.append(
                {
                    "event": "title_alignment",
                    "guidance_items": [dict(item) for item in kwargs.get("guidance_items") or []],
                    "pending": dict(kwargs.get("pending_recommendation") or {}),
                }
            )
            return dict(title_record)

        def _coherent(debug):
            events.append({"event": "coherent_overview", "overview": dict(debug.get("overview") or {})})
            return coherent_overview

        def _debug_log(event, payload, **kwargs):
            logs.append(
                {
                    "event": event,
                    "payload": dict(payload or {}),
                    "location": kwargs.get("location"),
                    "hypothesis_id": kwargs.get("hypothesis_id"),
                }
            )

        try:
            inputs_page._design_guide_title_alignment_verification_record = _title_alignment_record
            inputs_page._design_guide_debug_has_coherent_overview = _coherent
            inputs_page._agent_debug_log = _debug_log
            inputs_page.st = _FakeStreamlit(events, dev_mode)
            out_debug = inputs_page.render_design_guide_title_alignment_and_assertion_guard(
                guidance_items=[{"id": "primary"}],
                guidance_debug=guidance_debug,
                guidance_disp_state={"state": True},
                recommendation_result=recommendation_result,
                pending_recommendation={"pending": True},
                guidance_fresh_compute_used=fresh_compute,
                render_coherence_repairs=[{"repair": 1}],
                render_coherence_needed=True,
                sidebar_debug=sidebar_debug,
                stage=lambda label: stages.append(str(label)),
            )
        finally:
            _restore()

        case = {
            "name": name,
            "events": events,
            "stages": stages,
            "logs": logs,
            "debug": out_debug,
        }
        cases.append(case)
        return case

    warning = _run_case(
        "warning_dev_sidebar",
        overview={},
        coherent_overview=False,
        actionable=True,
        fresh_compute=True,
        sidebar_debug=True,
        dev_mode=True,
    )
    if warning["stages"] != ["post_plan.after_title_alignment"]:
        failures.append(f"warning_stage_mismatch:{warning['stages']}")
    if warning["debug"].get("design_guide_title_alignment") != {"title_alignment": "warning_dev_sidebar", "ok": True}:
        failures.append(f"warning_title_alignment_mismatch:{warning['debug']}")
    if warning["debug"].get("design_guide_render_warning") != "overview_untrusted_after_fresh_recompute":
        failures.append(f"warning_render_warning_missing:{warning['debug']}")
    if not any(event.get("event") == "sidebar.caption" for event in warning["events"]):
        failures.append(f"warning_sidebar_caption_missing:{warning['events']}")
    warning_log_events = [log.get("event") for log in warning["logs"]]
    expected_warning_logs = [
        "final_assertion_guard_state",
        "Design guide canonical recommendation_result (post-dedupe)",
        inputs_page.DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT,
    ]
    if warning_log_events != expected_warning_logs:
        failures.append(f"warning_log_order_mismatch:{warning_log_events}")
    final_guard_payload = warning["logs"][0]["payload"] if warning["logs"] else {}
    if final_guard_payload.get("would_assert") is not True:
        failures.append(f"warning_final_guard_mismatch:{final_guard_payload}")

    clean = _run_case(
        "clean_no_sidebar",
        overview={"status": "ok"},
        coherent_overview=True,
        actionable=False,
        fresh_compute=True,
        sidebar_debug=False,
        dev_mode=False,
    )
    if clean["debug"].get("design_guide_render_warning") is not None:
        failures.append(f"clean_warning_unexpected:{clean['debug']}")
    if clean["logs"]:
        failures.append(f"clean_logs_unexpected:{clean['logs']}")
    if any(event.get("event") == "sidebar.caption" for event in clean["events"]):
        failures.append(f"clean_sidebar_caption_unexpected:{clean['events']}")
    if not any(event.get("event") == "coherent_overview" for event in clean["events"]):
        failures.append(f"clean_coherence_check_missing:{clean['events']}")

    payload = {
        "verifier": "inputs_page_title_alignment_assertion_guard_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Title Alignment Assertion Guard Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` logs: `{len(case['logs'])}`, warning: `{case['debug'].get('design_guide_render_warning')}`"
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
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
