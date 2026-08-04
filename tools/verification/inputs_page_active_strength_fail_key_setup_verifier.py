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
    json_path = ARTIFACT_DIR / f"inputs_page_active_strength_fail_key_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_active_strength_fail_key_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_overview_active_failure_keys": inputs_page._overview_active_failure_keys,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _install_key_reader() -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []

        def _reader(overview):
            calls.append(dict(overview))
            if overview.get("raise"):
                raise RuntimeError("boom")
            return set(overview.get("active_keys") or [])

        inputs_page._overview_active_failure_keys = _reader
        return calls

    try:
        calls = _install_key_reader()
        debug: dict[str, Any] = {}
        result = inputs_page.render_design_guide_active_strength_fail_key_setup(
            guidance_items=[{"selected_family_id": "BENDING_FAIL_GOVERNS"}],
            dg_overview={"active_keys": ["combined", "sectional_shear", "ignored"]},
            dg_presentation={"headline": ""},
            guidance_debug=debug,
            debug_trace={},
        )
    finally:
        _restore()
    cases.append({"name": "normalises_overview_keys", "result": sorted(result), "debug": debug, "calls": calls})
    if result != {"bending", "shear"}:
        failures.append(f"normalises_overview_keys_mismatch:{result}")
    if len(calls) != 1:
        failures.append(f"normalises_overview_call_count_mismatch:{calls}")

    try:
        calls = _install_key_reader()
        debug = {"overview": {"active_keys": ["bending"]}}
        result = inputs_page.render_design_guide_active_strength_fail_key_setup(
            guidance_items=[{}],
            dg_overview={},
            dg_presentation={"headline": ""},
            guidance_debug=debug,
            debug_trace={"overview": {"active_keys": ["shear"]}},
        )
    finally:
        _restore()
    cases.append({"name": "fallback_uses_guidance_debug_overview", "result": sorted(result), "debug": debug, "calls": calls})
    if result != {"bending"}:
        failures.append(f"fallback_guidance_debug_mismatch:{result}")
    if calls != [{}, {"active_keys": ["bending"]}]:
        failures.append(f"fallback_guidance_debug_calls_mismatch:{calls}")

    try:
        calls = _install_key_reader()
        debug = {}
        result = inputs_page.render_design_guide_active_strength_fail_key_setup(
            guidance_items=[{}],
            dg_overview={},
            dg_presentation={"headline": "Bending and shear capacity are low"},
            guidance_debug=debug,
            debug_trace={"overview": {"raise": True}},
        )
    finally:
        _restore()
    cases.append({"name": "headline_infers_bending_and_shear_after_fallback_exception", "result": sorted(result), "debug": debug, "calls": calls})
    if result != {"bending", "shear"}:
        failures.append(f"headline_inference_mismatch:{result}")
    if calls != [{}, {"raise": True}]:
        failures.append(f"headline_exception_calls_mismatch:{calls}")

    try:
        calls = _install_key_reader()
        debug = {}
        result = inputs_page.render_design_guide_active_strength_fail_key_setup(
            guidance_items=[
                {
                    "candidate_search_evidence": {
                        "selected_family_id": "GEOMETRY_DETAILING_GOVERNS",
                    }
                }
            ],
            dg_overview={"active_keys": ["bending", "shear"]},
            dg_presentation={"headline": "Bending capacity is low"},
            guidance_debug=debug,
            debug_trace={},
        )
    finally:
        _restore()
    cases.append({"name": "geometry_detailing_suppresses_restamp", "result": sorted(result), "debug": debug, "calls": calls})
    if result != set():
        failures.append(f"geometry_suppression_mismatch:{result}")
    if debug.get("active_strength_card_restamp_suppressed_by_geometry_detailing") is not True:
        failures.append(f"geometry_suppression_debug_missing:{debug}")

    payload = {
        "verifier": "inputs_page_active_strength_fail_key_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Active Strength Fail Key Setup Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`" for case in cases),
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
