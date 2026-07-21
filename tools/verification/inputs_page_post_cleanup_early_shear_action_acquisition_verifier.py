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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_early_shear_action_acquisition_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_early_shear_action_acquisition_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patched_names = [
        "_shear_low_util_target_cleanup_item",
        "_post_active_repair_residual_shear_exact_blocker",
        "_post_click_applied_residual_shear_exact_blocker",
        "_cleanup_evidence_has_executable_target_band_proof",
        "_shear_best_safe_cleanup_item_from_evidence",
        "_design_guide_cleanup_item_publishable",
    ]
    originals = {name: getattr(inputs_page, name) for name in patched_names}

    failures: list[str] = []
    cases: list[dict] = []
    calls: list[str] = []
    config: dict = {}

    def fake_target_item(state, overview, *, threshold, allow_best_safe_below_threshold):
        calls.append("target_item")
        if config.get("target_raises"):
            raise RuntimeError("target failure")
        return config.get("target_action")

    def fake_residual_evidence(state, overview, *, threshold):
        calls.append("residual_evidence")
        return dict(config.get("residual_evidence") or {})

    def fake_applied_evidence(state, overview):
        calls.append("applied_evidence")
        applied = config.get("applied_evidence")
        return dict(applied) if isinstance(applied, dict) else applied

    def fake_has_proof(evidence, *, expected_util, state):
        calls.append(f"proof:{expected_util}")
        return bool(config.get("has_proof"))

    def fake_best_safe(state, overview, evidence):
        calls.append("best_safe")
        return dict(config.get("best_safe_action") or {"source": "best_safe"})

    def fake_publishable(action):
        calls.append("publishable")
        return bool(config.get("publishable"))

    def run_case(
        name: str,
        *,
        target_action,
        target_raises: bool = False,
        publishable: bool = True,
        residual_evidence: dict | None = None,
        applied_evidence=None,
        has_proof: bool = True,
        best_safe_action: dict | None = None,
        expected_action,
        expected_calls: list[str],
        unexpected_calls: list[str] | None = None,
    ) -> None:
        calls.clear()
        config.clear()
        config.update(
            {
                "target_action": target_action,
                "target_raises": target_raises,
                "publishable": publishable,
                "residual_evidence": residual_evidence or {"selected_candidate_util": "0.82"},
                "applied_evidence": applied_evidence,
                "has_proof": has_proof,
                "best_safe_action": best_safe_action or {"source": "best_safe"},
            }
        )
        actual = inputs_page.render_design_guide_post_cleanup_early_shear_action_acquisition(
            early_shear_cleanup_state={"D": 500},
            early_shear_cleanup_overview={"utils": {"shear": 0.7}},
            early_shear_target_low=0.75,
        )
        cases.append({"name": name, "actual": actual, "calls": list(calls)})
        if actual != expected_action:
            failures.append(f"{name}:action:expected={expected_action}:actual={actual}")
        for expected_call in expected_calls:
            if expected_call not in calls:
                failures.append(f"{name}:missing_call:{expected_call}:calls={calls}")
        for unexpected_call in list(unexpected_calls or []):
            if unexpected_call in calls:
                failures.append(f"{name}:unexpected_call:{unexpected_call}:calls={calls}")

    try:
        inputs_page._shear_low_util_target_cleanup_item = fake_target_item
        inputs_page._post_active_repair_residual_shear_exact_blocker = fake_residual_evidence
        inputs_page._post_click_applied_residual_shear_exact_blocker = fake_applied_evidence
        inputs_page._cleanup_evidence_has_executable_target_band_proof = fake_has_proof
        inputs_page._shear_best_safe_cleanup_item_from_evidence = fake_best_safe
        inputs_page._design_guide_cleanup_item_publishable = fake_publishable

        run_case(
            "publishable_target_action_is_returned",
            target_action={"source": "target"},
            publishable=True,
            expected_action={"source": "target"},
            expected_calls=["target_item", "publishable"],
            unexpected_calls=["residual_evidence", "best_safe"],
        )
        run_case(
            "target_exception_falls_back_to_best_safe_evidence",
            target_action=None,
            target_raises=True,
            residual_evidence={"selected_candidate_util": "0.82"},
            has_proof=True,
            best_safe_action={"source": "best_safe_exception"},
            expected_action={"source": "best_safe_exception"},
            expected_calls=["target_item", "residual_evidence", "applied_evidence", "proof:0.82", "best_safe"],
        )
        run_case(
            "missing_target_action_uses_applied_evidence_when_available",
            target_action=None,
            applied_evidence={"best_safe_final_util": "0.91"},
            has_proof=True,
            best_safe_action={"source": "best_safe_applied"},
            expected_action={"source": "best_safe_applied"},
            expected_calls=["target_item", "residual_evidence", "applied_evidence", "proof:0.91", "best_safe"],
        )
        run_case(
            "non_publishable_target_action_uses_best_safe_evidence",
            target_action={"source": "target_non_publishable"},
            publishable=False,
            residual_evidence={"closest_safe_candidate_util": "0.77"},
            has_proof=True,
            best_safe_action={"source": "best_safe_non_publishable"},
            expected_action={"source": "best_safe_non_publishable"},
            expected_calls=["target_item", "publishable", "residual_evidence", "proof:0.77", "best_safe"],
        )
        run_case(
            "fallback_without_target_band_proof_returns_original_non_publishable_action",
            target_action={"source": "target_non_publishable"},
            publishable=False,
            residual_evidence={"closest_safe_candidate_util": "0.77"},
            has_proof=False,
            expected_action={"source": "target_non_publishable"},
            expected_calls=["target_item", "publishable", "residual_evidence", "proof:0.77"],
            unexpected_calls=["best_safe"],
        )
        run_case(
            "missing_target_without_proof_returns_none",
            target_action=None,
            residual_evidence={"closest_safe_candidate_util": "0.77"},
            has_proof=False,
            expected_action=None,
            expected_calls=["target_item", "residual_evidence", "proof:0.77"],
            unexpected_calls=["best_safe"],
        )
    finally:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    payload_out = {
        "verifier": "inputs_page_post_cleanup_early_shear_action_acquisition_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Early Shear Action Acquisition Verifier",
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
