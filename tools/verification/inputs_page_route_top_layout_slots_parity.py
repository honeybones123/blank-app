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


class _FakeContext:
    def __init__(self, calls: list[tuple[str, Any]], label: str) -> None:
        self.calls = calls
        self.label = label

    def __enter__(self):
        self.calls.append(("enter", self.label))
        return self

    def __exit__(self, exc_type, exc, tb):
        self.calls.append(("exit", self.label))
        return False


class _FakeStreamlit:
    def __init__(self, calls: list[tuple[str, Any]]) -> None:
        self._calls = calls
        self._counter = 0

    def columns(self, spec, *, gap=None, vertical_alignment=None):
        spec_list = list(spec) if isinstance(spec, (list, tuple)) else [spec]
        self._calls.append(("columns", spec_list, gap, vertical_alignment))
        contexts = []
        for idx, _ in enumerate(spec_list):
            self._counter += 1
            contexts.append(_FakeContext(self._calls, f"column:{self._counter}:{idx}"))
        return contexts

    def container(self):
        self._counter += 1
        label = f"container:{self._counter}"
        self._calls.append(("container", label))
        return _FakeContext(self._calls, label)


def _normalise_return(result: tuple[Any, ...]) -> list[Any]:
    out: list[Any] = []
    for value in result:
        if value is None:
            out.append(None)
        else:
            out.append(getattr(value, "label", type(value).__name__))
    return out


def _run_case(module, *, detailed: bool) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    fake_st = _FakeStreamlit(calls)
    legacy_bridge = getattr(module, "_legacy_inputs_page", module)

    original_st = module.st
    original_design_guide = legacy_bridge.render_design_guide_panel_orchestration_coordinator
    original_extracted_design_guide = getattr(
        module,
        "render_design_guide_panel_orchestration",
        None,
    )

    def _render_design_guide_panel_orchestration_coordinator(
        sync_callbacks,
        inputs_render_audit,
        *,
        fast_focus_section=None,
    ):
        calls.append(
            (
                "render_design_guide_panel_orchestration_coordinator",
                sorted(sync_callbacks.keys()),
                dict(inputs_render_audit),
                fast_focus_section,
            )
        )

    def _render_design_guide_panel_orchestration(
        *,
        coordinator_owner,
        sync_callbacks=None,
        inputs_render_audit=None,
        fast_focus_section=None,
    ):
        _ = coordinator_owner
        _render_design_guide_panel_orchestration_coordinator(
            sync_callbacks,
            inputs_render_audit,
            fast_focus_section=fast_focus_section,
        )

    try:
        module.st = fake_st
        legacy_bridge.render_design_guide_panel_orchestration_coordinator = (
            _render_design_guide_panel_orchestration_coordinator
        )
        if original_extracted_design_guide is not None:
            module.render_design_guide_panel_orchestration = (
                _render_design_guide_panel_orchestration
            )
        result = module.render_inputs_top_section_layout_slots_coordinator(
            inputs_detailed_mode=detailed,
            sync_callbacks={"a": lambda: None, "b": lambda: None},
            inputs_render_audit={"design_guide_rendered": "no"},
            fast_focus_section="geometry",
        )
    finally:
        module.st = original_st
        legacy_bridge.render_design_guide_panel_orchestration_coordinator = original_design_guide
        if original_extracted_design_guide is not None:
            module.render_design_guide_panel_orchestration = original_extracted_design_guide

    return {
        "return": _normalise_return(result),
        "calls": calls,
    }


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route

    cases = {
        "detailed": {
            "legacy": _run_case(legacy_inputs_page, detailed=True),
            "route": _run_case(route, detailed=True),
        },
        "fast": {
            "legacy": _run_case(legacy_inputs_page, detailed=False),
            "route": _run_case(route, detailed=False),
        },
    }
    checks = {
        "all_returns_match_legacy": all(case["legacy"]["return"] == case["route"]["return"] for case in cases.values()),
        "all_call_sequences_match_legacy": all(case["legacy"]["calls"] == case["route"]["calls"] for case in cases.values()),
    }
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8")
    checks["route_no_longer_delegates_top_layout_slots"] = (
        "_legacy_inputs_page.render_inputs_top_section_layout_slots_coordinator" not in route_source
    )

    status = "PASS" if all(checks.values()) else "FAIL"
    artifact = {
        "status": status,
        "timestamp": timestamp,
        "checks": checks,
        "cases": cases,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_top_layout_slots_parity_{timestamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_route_top_layout_slots_parity_{timestamp}.md"
    json_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Top Layout Slots Parity",
                "",
                f"Status: {status}",
                "",
                "## Checks",
                *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
                "",
                "## Scope",
                "- Compares detailed and fast layout orchestration against the old coordinator.",
                "- Verifies Design Guide render call ordering, column specs/gaps, container creation order, returned slots, and fast-mode right diagram behavior.",
                "- Verifies the extracted Design Guide panel orchestration route boundary is invoked before layout slots.",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "artifact": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
