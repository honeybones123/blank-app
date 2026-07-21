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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_early_shear_candidate_packaging_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_early_shear_candidate_packaging_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_candidate_id = inputs_page._guidance_cleanup_candidate_id

    failures: list[str] = []
    cases: list[dict] = []

    def fake_candidate_id(family, updates):
        return f"generated-{family}-{sorted(dict(updates or {}).items())}"

    def run_case(
        name: str,
        *,
        action: dict,
        evidence: dict,
        updates: dict,
        expected_candidate_id: str,
        expected_label: str,
    ) -> None:
        returned_action, candidate_id, label = (
            inputs_page.render_design_guide_post_cleanup_early_shear_candidate_packaging(
                early_shear_cleanup_action=action,
                early_shear_cleanup_seed_evidence=evidence,
                early_shear_cleanup_seed_updates=updates,
            )
        )
        cases.append(
            {
                "name": name,
                "candidate_id": candidate_id,
                "label": label,
                "action": dict(returned_action),
            }
        )
        if returned_action is not action:
            failures.append(f"{name}:returned_action_not_same_object")
        if candidate_id != expected_candidate_id:
            failures.append(f"{name}:candidate_id:expected={expected_candidate_id}:actual={candidate_id}")
        if label != expected_label:
            failures.append(f"{name}:label:expected={expected_label}:actual={label}")
        expected_top_level = {
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "check_key": "shear",
            "updates": dict(updates),
            "candidate_id": expected_candidate_id,
            "source_candidate_id": expected_candidate_id,
            "guidance_intent": "efficiency_tightening",
            "primary_action": "Run one-click auto design",
            "has_resolved_candidate_payload": True,
        }
        for key, expected in expected_top_level.items():
            actual = returned_action.get(key)
            if actual != expected:
                failures.append(f"{name}:top_level:{key}:expected={expected}:actual={actual}")
        payload = dict(returned_action.get("action_payload") or {})
        resolved = dict(returned_action.get("resolved_candidate") or {})
        payload_expectations = {
            "resolved_candidate_updates": dict(updates),
            "resolved_candidate_label": expected_label,
            "resolved_candidate_action_type": "apply_resolved_candidate",
            "resolved_candidate_family_tag": "shear",
            "updates": dict(updates),
        }
        resolved_expectations = {
            "updates": dict(updates),
            "action_type": "apply_resolved_candidate",
            "label": expected_label,
            "family": "shear",
        }
        for key, expected in payload_expectations.items():
            actual = payload.get(key)
            if actual != expected:
                failures.append(f"{name}:payload:{key}:expected={expected}:actual={actual}")
        for key, expected in resolved_expectations.items():
            actual = resolved.get(key)
            if actual != expected:
                failures.append(f"{name}:resolved:{key}:expected={expected}:actual={actual}")

    try:
        inputs_page._guidance_cleanup_candidate_id = fake_candidate_id

        run_case(
            "best_safe_id_and_title_main_precedence",
            action={
                "title_main": "Tighten shear spacing",
                "action_payload": {"keep_payload": "yes"},
                "resolved_candidate": {"keep_resolved": "yes"},
            },
            evidence={
                "best_safe_candidate_id": "best-safe-id",
                "selected_candidate_id": "selected-id",
                "closest_safe_candidate_id": "closest-id",
            },
            updates={"s_lig": 150},
            expected_candidate_id="best-safe-id",
            expected_label="Tighten shear spacing",
        )
        first_action = cases[-1]["action"]
        if dict(first_action.get("action_payload") or {}).get("keep_payload") != "yes":
            failures.append("best_safe_id_and_title_main_precedence:payload_existing_key_lost")
        if dict(first_action.get("resolved_candidate") or {}).get("keep_resolved") != "yes":
            failures.append("best_safe_id_and_title_main_precedence:resolved_existing_key_lost")

        run_case(
            "selected_id_and_title_fallback",
            action={"title": "Selected cleanup"},
            evidence={"selected_candidate_id": "selected-id"},
            updates={"lig_legs": 4},
            expected_candidate_id="selected-id",
            expected_label="Selected cleanup",
        )

        run_case(
            "generated_id_and_default_label_fallback",
            action={},
            evidence={},
            updates={"s_lig": 175},
            expected_candidate_id="generated-shear-[('s_lig', 175)]",
            expected_label="Shear cleanup - best safe one-click reduction",
        )
    finally:
        inputs_page._guidance_cleanup_candidate_id = original_candidate_id

    payload_out = {
        "verifier": "inputs_page_post_cleanup_early_shear_candidate_packaging_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Early Shear Candidate Packaging Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`: `{case['candidate_id']}` / `{case['label']}`" for case in cases),
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
