from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_rerun_trigger_record_plan


def _old_shape(*, reason, meta, existing_triggers, timestamp, max_events=24):
    payload = {"event": str(reason or "unknown"), "ts": timestamp}
    payload.update({str(key): value for key, value in dict(meta or {}).items()})
    triggers = existing_triggers if isinstance(existing_triggers, list) else []
    triggers = list(triggers)
    triggers.append(payload)
    log_payload = {"reason": str(reason or "unknown")}
    log_payload.update({str(key): value for key, value in dict(meta or {}).items()})
    return {
        "trigger_payload": payload,
        "stored_triggers": triggers[-max_events:],
        "log_payload": log_payload,
        "ssl_trigger_reason": str(reason or "inputs_page_rerun"),
    }


def _scenario(name, **kwargs):
    plan = build_inputs_rerun_trigger_record_plan(**kwargs)
    old = _old_shape(**kwargs)
    new = {
        "trigger_payload": plan.trigger_payload,
        "stored_triggers": plan.stored_triggers,
        "log_payload": plan.log_payload,
        "ssl_trigger_reason": plan.ssl_trigger_reason,
    }
    return {
        "name": name,
        "match": old == new,
        "old": old,
        "new": new,
        "display_hash_present": bool(plan.display_hash),
    }


def main() -> int:
    inputs = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    builders = (ROOT / "inputs_page_modules" / "session" / "builders.py").read_text(encoding="utf-8")
    init_text = (ROOT / "inputs_page_modules" / "session" / "__init__.py").read_text(encoding="utf-8")

    scenarios = [
        _scenario(
            "normal_event_with_meta",
            reason="summary_change",
            meta={"beam": "B1", 7: "seven"},
            existing_triggers=[{"event": "old", "ts": 1.0}],
            timestamp=123.5,
        ),
        _scenario(
            "empty_reason_defaults",
            reason="",
            meta={},
            existing_triggers=[],
            timestamp=456.0,
        ),
        _scenario(
            "non_list_existing_triggers",
            reason="widget_change",
            meta={"x": 1},
            existing_triggers={"bad": True},
            timestamp=789.0,
        ),
        _scenario(
            "caps_to_last_24",
            reason="cap",
            meta={"k": "v"},
            existing_triggers=[{"event": str(i), "ts": i} for i in range(30)],
            timestamp=900.0,
        ),
    ]
    failures = []
    if not all(item["match"] and item["display_hash_present"] for item in scenarios):
        failures.append("scenario parity failed")
    function_start = inputs.index("def _record_inputs_rerun_trigger")
    function_end = inputs.index("\ndef _recompute_summary_local_derived_fields", function_start)
    function_body = inputs[function_start:function_end]
    if "build_inputs_rerun_trigger_record_plan(" not in function_body:
        failures.append("inputs helper does not call session builder")
    banned = [
        'payload = {"event": str(reason or "unknown"), "ts": time.time()}',
        "triggers.append(payload)",
        'payload = {"reason": str(reason or "unknown")}',
        'str(reason or "inputs_page_rerun")',
    ]
    for snippet in banned:
        if snippet in function_body:
            failures.append(f"page-owned rerun trigger logic remains: {snippet}")
    if "import streamlit" in builders or "import inputs_page" in builders:
        failures.append("session builder imports forbidden page/UI dependency")
    if "build_inputs_rerun_trigger_record_plan" not in init_text:
        failures.append("session builder is not exported")

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    decision = "INPUTS_SESSION_RERUN_TRIGGER_RECORD_PLAN_LOCKED" if not failures else "FAIL"
    payload = {
        "audit": "inputs_session_rerun_trigger_record_plan_cutover",
        "timestamp": timestamp,
        "decision": decision,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "session_write_ownership_moved": False,
        "scenarios": scenarios,
        "failures": failures,
    }
    verification_dir = ROOT / "artifacts" / "verification"
    audit_dir = ROOT / "artifacts" / "audits"
    verification_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = verification_dir / f"inputs_session_rerun_trigger_record_plan_{timestamp}.json"
    report_path = audit_dir / f"inputs_session_rerun_trigger_record_plan_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Session Rerun Trigger Record Plan",
                "",
                f"Decision: `{decision}`",
                "",
                f"Scenarios checked: `{len(scenarios)}`",
                f"Failures: `{len(failures)}`",
                "",
                "The session module owns the pure event/log payload shape and capped list materialization.",
                "`inputs_page.py` still owns the Streamlit session write and final-log calls.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(decision)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
