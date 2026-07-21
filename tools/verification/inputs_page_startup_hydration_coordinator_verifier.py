from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _function_source(source: str, name: str) -> tuple[str, int]:
    tree = ast.parse(source)
    matches: list[tuple[int, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            size = node.end_lineno - node.lineno + 1
            matches.append((size, node.lineno, node.end_lineno))
    if not matches:
        return "", 0
    size, start, end = max(matches, key=lambda item: item[0])
    lines = source.splitlines()
    return "\n".join(lines[start - 1 : end]), size


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_startup_hydration_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_startup_hydration_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    startup_module_source = (
        ROOT / "inputs_page_modules" / "session" / "startup_hydration.py"
    ).read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        startup_module_source,
        "render_inputs_startup_hydration",
    )
    route_startup_source, _ = _function_source(
        route_source,
        "render_inputs_startup_hydration_coordinator",
    )
    page_setup_source, _ = _function_source(
        route_source,
        "render_inputs_page_setup_current_coordinator",
    )
    render_inputs_source, _ = _function_source(shell_source, "render_inputs_page")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("startup_hydration_coordinator_missing")
    if coordinator_size > 180:
        failures.append(f"startup_hydration_coordinator_too_large:{coordinator_size}")
    for required in [
        "load_active_beam_into_shared_fn()",
        "_pending_inputs_apply_refresh",
        "_force_inputs_widget_reseed_once",
        "_force_inputs_shear_widget_reseed_once",
        "render_inputs_pending_refresh_skip_force_cycle",
        "force_inputs_widget_and_shear_widget_reseed_once",
        "mark(\"hydrate_widgets\")",
        "Inputs beam-module startup trace",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for stale in [
        "inputs_startup_debug",
        "pending_refresh_source",
        "browser_recipe_pre_widget_reseed",
        "explicit_beam_hydrate",
        "force_inputs_row_reseed_once",
        "render_inputs.after_pending_refresh_pop",
        "Inputs beam-module startup trace",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    page_load_index = page_setup_source.find("render_inputs_page_load_start_coordinator(")
    call_index = page_setup_source.find("render_inputs_startup_hydration_coordinator(ss=ss, mark=_mark)")
    if "render_inputs_startup_hydration_module(" not in route_startup_source:
        failures.append("route_startup_hydration_missing_module_delegate")
    pre_widget_index = page_setup_source.find(
        "render_inputs_pre_widget_apply_and_render_setup_coordinator("
    )
    if call_index < 0:
        failures.append("render_inputs_missing_startup_hydration_call")
    if not (page_load_index >= 0 and page_load_index < call_index < pre_widget_index):
        failures.append(
            "startup_hydration_call_order_changed:"
            f"page_load={page_load_index}:call={call_index}:pre_widget={pre_widget_index}"
        )

    payload = {
        "verifier": "inputs_page_startup_hydration_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Startup Hydration Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
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
