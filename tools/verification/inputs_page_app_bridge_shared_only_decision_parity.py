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


def _run_side(module: Any, *, legacy: bool, session_values: dict[str, Any]) -> tuple:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    if legacy:
        original_st = legacy_inputs_page.st
        try:
            legacy_inputs_page.st = SimpleNamespace(session_state=dict(session_values))
            return module._inputs_summary_should_use_shared_only()
        finally:
            legacy_inputs_page.st = original_st

    original_st = bridge.st
    try:
        bridge.st = SimpleNamespace(session_state=dict(session_values))
        return module._inputs_summary_should_use_shared_only_for_app_bridge()
    finally:
        bridge.st = original_st


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases = {
        "normal": {},
        "applying_auto_design": {"_applying_auto_design": True},
        "force_reseed": {"_force_inputs_widget_reseed_once": True},
        "pending_refresh": {"_pending_inputs_apply_refresh": {"source": "test"}},
        "post_force_refresh": {"_inputs_longitudinal_reo_force_refresh_processed_this_run": True},
        "priority_first_wins": {
            "_applying_auto_design": True,
            "_pending_inputs_apply_refresh": {"source": "test"},
        },
    }
    results: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}
    for name, session_values in cases.items():
        legacy_value = _run_side(legacy_inputs_page, legacy=True, session_values=session_values)
        bridge_value = _run_side(bridge, legacy=False, session_values=session_values)
        results[name] = {"legacy": legacy_value, "bridge": bridge_value}
        checks[f"{name}_matches_legacy"] = legacy_value == bridge_value

    bridge_source = (ROOT / "inputs_page_app_contract_bridge.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["shared_only_decision_does_not_delegate_to_old_page"] = (
        "_legacy_inputs_page._inputs_summary_should_use_shared_only" not in bridge_source
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_app_bridge_shared_only_decision_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": results,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_shared_only_decision_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_shared_only_decision_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Shared-Only Decision Parity",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Checks",
                "",
                *(f"- `{name}`: `{passed}`" for name, passed in checks.items()),
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
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
