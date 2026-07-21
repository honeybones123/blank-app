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


def _run_side(module: Any, *, legacy: bool, ss: dict[str, Any]) -> tuple:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    def labels() -> dict[str, str]:
        return {"B1": "Beam 1", "B2": "Beam 2"}

    if legacy:
        original = legacy_inputs_page.build_batch_beam_option_labels
        try:
            legacy_inputs_page.build_batch_beam_option_labels = labels
            return module.render_inputs_batch_design_context_coordinator(ss=dict(ss))
        finally:
            legacy_inputs_page.build_batch_beam_option_labels = original

    original = route_bridge.build_batch_beam_option_labels
    try:
        route_bridge.build_batch_beam_option_labels = labels
        return module.render_inputs_batch_design_context_coordinator(ss=dict(ss))
    finally:
        route_bridge.build_batch_beam_option_labels = original


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases = {
        "active_present": {"beam_order": ["B1", "B2"], "active_beam_id": "B2"},
        "active_missing_uses_first": {"beam_order": ["B1", "B2"], "active_beam_id": "B3"},
        "empty_order_preserves_active": {"beam_order": [], "active_beam_id": "B3"},
    }
    results: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}
    for name, ss in cases.items():
        legacy_result = _run_side(legacy_inputs_page, legacy=True, ss=ss)
        bridge_result = _run_side(route_bridge, legacy=False, ss=ss)
        results[name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{name}_matches_legacy"] = legacy_result == bridge_result

    bridge_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["batch_context_does_not_delegate_to_old_page"] = (
        "_legacy_inputs_page.render_inputs_batch_design_context_coordinator" not in bridge_source
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_batch_context_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": results,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_batch_context_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_batch_context_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Batch Context Parity",
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
