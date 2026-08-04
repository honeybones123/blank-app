from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_early_shear_direct_shell_projection_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_early_shear_direct_shell_projection_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_builder = inputs_page._build_final_design_guide_direct_shell_card_projection
    original_enabled = inputs_page._design_guide_button_contract_enabled

    failures: list[str] = []
    cases: list[dict] = []
    builder_calls: list[dict] = []
    enabled = True

    def fake_enabled(contract):
        return bool(enabled)

    def fake_builder(**kwargs):
        builder_calls.append(dict(kwargs))
        return {"projection": "built", "kwargs": dict(kwargs)}

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def run_case(name: str, *, contract: dict, expected_pill: str) -> None:
        nonlocal builder_calls
        builder_calls = []
        action = {"title_main": "Action source", "updates": {"s_lig": 150}}
        overview = {"utils": {"shear": 0.88}}
        projection = inputs_page.render_design_guide_post_cleanup_early_shear_direct_shell_projection_setup(
            early_shear_cleanup_action=action,
            early_shear_cleanup_overview=overview,
            early_shear_cleanup_seed_contract=contract,
            early_shear_cleanup_label="Tighten shear spacing",
        )
        cases.append({"name": name, "projection": projection, "builder_calls": list(builder_calls)})
        expect(name, projection.get("projection") == "built", f"projection={projection}")
        expect(name, len(builder_calls) == 1, f"builder_call_count={len(builder_calls)}")
        if not builder_calls:
            return
        call = builder_calls[0]
        expected = {
            "title": "Tighten shear spacing",
            "pill": expected_pill,
            "current_overview": overview,
            "candidate_family": contract.get("family"),
            "expected_util": contract.get("expected_util"),
            "preview_pass": contract.get("preview_pass"),
            "family_identity": action,
            "summary_line": "Run one-click auto design.",
            "reason_text": "Run one-click auto design.",
            "card_class": "fast-guidance-item efficiency",
        }
        for key, expected_value in expected.items():
            expect(name, call.get(key) == expected_value, f"{key}:expected={expected_value}:actual={call.get(key)}")
        action["new_top_level"] = "mutated_after"
        overview["new_top_level"] = "mutated_after"
        expect(name, "new_top_level" not in call["family_identity"], "family_identity_top_level_not_copied")
        expect(name, "new_top_level" not in call["current_overview"], "overview_top_level_not_copied")

    try:
        inputs_page._build_final_design_guide_direct_shell_card_projection = fake_builder
        inputs_page._design_guide_button_contract_enabled = fake_enabled

        enabled = True
        run_case(
            "enabled_contract_uses_action_pill",
            contract={"enabled": True, "family": "shear", "expected_util": 0.91, "preview_pass": True},
            expected_pill="ACTION",
        )
        enabled = False
        run_case(
            "disabled_contract_uses_next_pill",
            contract={"enabled": False, "family": "shear", "expected_util": 0.72, "preview_pass": False},
            expected_pill="NEXT",
        )
    finally:
        inputs_page._build_final_design_guide_direct_shell_card_projection = original_builder
        inputs_page._design_guide_button_contract_enabled = original_enabled

    payload_out = {
        "verifier": "inputs_page_post_cleanup_early_shear_direct_shell_projection_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Early Shear Direct Shell Projection Setup Verifier",
                "",
                f"Status: `{payload_out['status']}`",
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
    print(payload_out["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
