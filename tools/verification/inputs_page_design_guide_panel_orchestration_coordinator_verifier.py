"""Focused transaction-order proof for the extracted Design Guide panel pipeline."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _pipeline(*, loading: bool = False):
    calls: list[tuple[str, dict]] = []

    def called(name, result):
        def run(**kwargs):
            calls.append((name, dict(kwargs)))
            return result

        return run

    owner = object()
    coordinators = SimpleNamespace(
        render_design_guide_panel_entry_trace_and_stage_coordinator=called(
            "entry", (1.0, lambda _label: None)
        ),
        render_design_guide_initial_state_and_loading_coordinator=called(
            "initial",
            (
                {"current": True},
                ("fp",),
                False,
                {"_dg_initial": {"stage": lambda _label: None}},
                loading,
                False,
            ),
        ),
        render_design_guide_compute_preparation_coordinator=called(
            "compute",
            (
                [{"raw": True}],
                {"debug": True},
                False,
                False,
                True,
                False,
                False,
                False,
                False,
                {"display": True},
                1.2,
                False,
            ),
        ),
        render_design_guide_postprocess_pre_render_plan_coordinator=called(
            "postprocess",
            (
                [{"post": True}],
                {"debug": "post"},
                {"display": "post"},
                {"dedupe": True},
                {"recommendation": True},
                "terminal",
                "terminal_source",
                {"pending": True},
                {"plan": True},
                False,
                False,
            ),
        ),
        render_design_guide_active_guard_presentation_engine_coordinator=called(
            "active",
            (
                [{"active": True}],
                {"debug": "active"},
                None,
                "terminal",
                "terminal_source",
                {"recommendation": True},
                {"overview": True},
                {"mode": True},
                False,
                {"decision": True},
                {"presentation": True},
                {"utils": True},
            ),
        ),
        render_design_guide_presentation_post_cleanup_gate_coordinator=called(
            "cleanup_gate",
            (
                [{"clean": True}],
                {"presentation": "clean"},
                {"recommendation": "clean"},
                {"debug": "clean"},
                "terminal",
                "terminal_source",
                False,
                {"audit": True},
                False,
            ),
        ),
        render_design_guide_post_cleanup_publication_pre_render_coordinator=called(
            "publication",
            (
                None,
                None,
                [{"published": True}],
                "terminal",
                "terminal_source",
                {"overview": True},
                {"presentation": True},
                {"plan": True},
                None,
                None,
                None,
                None,
                None,
                {"visible": True},
                None,
                None,
                {"audit": True},
                None,
                False,
                {"debug": "published"},
            ),
        ),
        render_design_guide_final_render_branch_dispatch_coordinator=called(
            "render",
            (
                {"debug": "rendered"},
                {"plan": "rendered"},
                {"presentation": "rendered"},
                "terminal",
                {"utils": "rendered"},
                [{"rendered": True}],
            ),
        ),
        render_design_guide_panel_exit_state=called("exit", None),
    )
    return owner, coordinators, calls


def main() -> int:
    import inputs_page_modules.design_guide.panel_orchestration as orchestration

    original = orchestration.panel_coordinators
    checks: dict[str, bool] = {}
    try:
        owner, coordinators, calls = _pipeline()
        orchestration.panel_coordinators = coordinators
        orchestration.render_design_guide_panel_orchestration(
            current_owner=owner,
            inputs_render_audit={"audit": True},
            fast_focus_section="model",
        )
        names = [name for name, _kwargs in calls]
        checks["full_pipeline_order"] = names == [
            "entry",
            "initial",
            "compute",
            "postprocess",
            "active",
            "cleanup_gate",
            "publication",
            "render",
            "exit",
        ]
        owner_calls = [
            kwargs.get("current_owner")
            for name, kwargs in calls
            if name in {"initial", "postprocess", "active", "render"}
        ]
        checks["current_owner_is_explicit"] = owner_calls == [owner] * 4
        checks["legacy_coordinator_owner_removed"] = (
            "coordinator_owner" not in
            (ROOT / "inputs_page_modules/design_guide/panel_orchestration.py").read_text(
                encoding="utf-8"
            )
        )

        owner, coordinators, calls = _pipeline(loading=True)
        orchestration.panel_coordinators = coordinators
        orchestration.render_design_guide_panel_orchestration(current_owner=owner)
        checks["loading_short_circuit"] = [name for name, _kwargs in calls] == [
            "entry",
            "initial",
        ]
    finally:
        orchestration.panel_coordinators = original

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    payload = {
        "contract_version": "inputs_design_guide_panel_orchestration.v2",
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_panel_orchestration_coordinator_{stamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_panel_orchestration_coordinator_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "# Inputs Design Guide panel orchestration\n\n"
        f"Status: `{payload['status']}`\n\n"
        + "\n".join(f"- `{name}`: `{value}`" for name, value in checks.items())
        + "\n",
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
