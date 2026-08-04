from __future__ import annotations

import json
import os
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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            row.pop("timestamp", None)
            rows.append(row)
    return rows


def _run_side(
    module: Any,
    *,
    legacy: bool,
    env_value: str | None,
    block: str,
    preseed_path: Path | None,
) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    session_state: dict[str, Any] = {}
    if preseed_path is not None:
        session_state["_inputs_pre_widget_trace_path"] = str(preseed_path)

    old_env = os.environ.get("PERF_TRACE_INPUTS")
    if env_value is None:
        os.environ.pop("PERF_TRACE_INPUTS", None)
    else:
        os.environ["PERF_TRACE_INPUTS"] = env_value

    if legacy:
        original_st = legacy_inputs_page.st
        try:
            legacy_inputs_page.st = SimpleNamespace(session_state=session_state)
            returned = module._inputs_pre_widget_trace(block, value=123)
        finally:
            legacy_inputs_page.st = original_st
            if old_env is None:
                os.environ.pop("PERF_TRACE_INPUTS", None)
            else:
                os.environ["PERF_TRACE_INPUTS"] = old_env
    else:
        original_st = route_bridge.st
        try:
            route_bridge.st = SimpleNamespace(session_state=session_state)
            returned = module._inputs_pre_widget_trace(block, value=123)
        finally:
            route_bridge.st = original_st
            if old_env is None:
                os.environ.pop("PERF_TRACE_INPUTS", None)
            else:
                os.environ["PERF_TRACE_INPUTS"] = old_env

    path = Path(str(session_state.get("_inputs_pre_widget_trace_path") or ""))
    return {
        "returned": returned,
        "session_has_path": bool(session_state.get("_inputs_pre_widget_trace_path")),
        "rows": _read_jsonl(path) if path else [],
    }


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    tmp_dir = ARTIFACT_DIR / "tmp_pre_widget_trace"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    cases: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}

    for case_name, env_value, block in (
        ("disabled", None, "render_summary"),
        ("blank_label", "1", " "),
        ("enabled_existing_path", "1", "render_summary"),
    ):
        legacy_path = tmp_dir / f"{timestamp}_{case_name}_legacy.jsonl"
        bridge_path = tmp_dir / f"{timestamp}_{case_name}_bridge.jsonl"
        legacy_result = _run_side(
            legacy_inputs_page,
            legacy=True,
            env_value=env_value,
            block=block,
            preseed_path=legacy_path,
        )
        bridge_result = _run_side(
            route_bridge,
            legacy=False,
            env_value=env_value,
            block=block,
            preseed_path=bridge_path,
        )
        cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_matches_legacy"] = legacy_result == bridge_result

    bridge_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["pre_widget_trace_does_not_delegate_to_old_page"] = (
        "_legacy_inputs_page._inputs_pre_widget_trace" not in bridge_source
    )
    checks["enabled_existing_path_writes_payload"] = cases["enabled_existing_path"]["bridge"]["rows"] == [
        {"block": "render_summary", "value": 123}
    ]
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_pre_widget_trace_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": cases,
    }

    json_path = ARTIFACT_DIR / f"inputs_page_route_pre_widget_trace_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_pre_widget_trace_parity_{timestamp}.md"
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Pre Widget Trace Parity",
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
