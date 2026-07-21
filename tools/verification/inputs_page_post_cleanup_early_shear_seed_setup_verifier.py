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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_early_shear_seed_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_early_shear_seed_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_updates_match_state = inputs_page._updates_match_state

    failures: list[str] = []
    cases: list[dict] = []
    updates_match = False

    def fake_updates_match_state(state, updates):
        return bool(updates_match)

    def run_case(
        name: str,
        *,
        action: dict,
        match_state: bool,
        expected_evidence: dict,
        expected_updates: dict,
        expected_allowed: bool,
    ) -> None:
        nonlocal updates_match
        updates_match = match_state
        evidence, updates, allowed = inputs_page.render_design_guide_post_cleanup_early_shear_seed_setup(
            early_shear_cleanup_action=action,
            early_shear_cleanup_state={"D": 500},
        )
        cases.append({"name": name, "evidence": evidence, "updates": updates, "allowed": allowed})
        if evidence != expected_evidence:
            failures.append(f"{name}:evidence:expected={expected_evidence}:actual={evidence}")
        if updates != expected_updates:
            failures.append(f"{name}:updates:expected={expected_updates}:actual={updates}")
        if allowed is not expected_allowed:
            failures.append(f"{name}:allowed:expected={expected_allowed}:actual={allowed}")

    try:
        inputs_page._updates_match_state = fake_updates_match_state

        run_case(
            "best_safe_updates_take_precedence_and_allow",
            action={
                "candidate_search_evidence": {
                    "best_safe_candidate_updates": {"s_lig": 150},
                    "selected_candidate_updates": {"s_lig": 175},
                },
                "updates": {"s_lig": 200},
            },
            match_state=False,
            expected_evidence={
                "best_safe_candidate_updates": {"s_lig": 150},
                "selected_candidate_updates": {"s_lig": 175},
            },
            expected_updates={"s_lig": 150},
            expected_allowed=True,
        )
        run_case(
            "selected_updates_fallback_allow",
            action={"candidate_search_evidence": {"selected_candidate_updates": {"lig_legs": 4}}},
            match_state=False,
            expected_evidence={"selected_candidate_updates": {"lig_legs": 4}},
            expected_updates={"lig_legs": 4},
            expected_allowed=True,
        )
        run_case(
            "action_updates_fallback_allow",
            action={"candidate_search_evidence": {}, "updates": {"s_lig": 125}},
            match_state=False,
            expected_evidence={},
            expected_updates={"s_lig": 125},
            expected_allowed=True,
        )
        run_case(
            "matching_state_blocks",
            action={"candidate_search_evidence": {"best_safe_candidate_updates": {"s_lig": 150}}},
            match_state=True,
            expected_evidence={"best_safe_candidate_updates": {"s_lig": 150}},
            expected_updates={"s_lig": 150},
            expected_allowed=False,
        )
        run_case(
            "non_compound_shear_key_blocks",
            action={"candidate_search_evidence": {"best_safe_candidate_updates": {"D": 650}}},
            match_state=False,
            expected_evidence={"best_safe_candidate_updates": {"D": 650}},
            expected_updates={"D": 650},
            expected_allowed=False,
        )
        run_case(
            "empty_updates_blocks",
            action={"candidate_search_evidence": {}},
            match_state=False,
            expected_evidence={},
            expected_updates={},
            expected_allowed=False,
        )
    finally:
        inputs_page._updates_match_state = original_updates_match_state

    payload_out = {
        "verifier": "inputs_page_post_cleanup_early_shear_seed_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Early Shear Seed Setup Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`: `{case['allowed']}`" for case in cases),
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
