"""Proof-only source audit for SHEAR_FAIL_GOVERNS blocked Design Guide cards.

This does not change product behaviour. It records whether a visible blocked
shear card is sourced from the locked family runtime ladder or from later
page-owned repair/blocker publication paths.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def _run(command: list[str], *, timeout: int = 120) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "stdout_tail": completed.stdout.strip().splitlines()[-20:],
        "stderr_tail": completed.stderr.strip().splitlines()[-20:],
    }


def _fixture_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 600.0,
        "L": 6000.0,
        "fc": 40.0,
        "fsy": 500.0,
        "uls_Mstar": 90.0,
        "uls_Vstar": 220.0,
        "bot1_count": 4,
        "db_bot_1": 16,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200.0,
    }


def _family_ladder_probe() -> dict[str, Any]:
    from design_brain.families.registry import family_strategy_for

    strategy = family_strategy_for("SHEAR_FAIL_GOVERNS")
    ladder = strategy.contracted_repair_ladder_specs(_fixture_state()) if strategy else {}
    specs = [dict(spec) for spec in list(ladder.get("specs") or []) if isinstance(spec, dict)]
    return {
        "strategy_available": strategy is not None,
        "runtime_authority": ladder.get("runtime_authority"),
        "runtime_ladder_hash_present": bool(ladder.get("runtime_ladder_hash") or ladder.get("ladder_hash")),
        "spec_count": len(specs),
        "spec_lanes": [spec.get("lane_id") for spec in specs],
        "specs_have_runtime_evidence": all(
            spec.get("ladder_hash")
            and spec.get("update_hash")
            and spec.get("candidate_state_hash")
            and spec.get("evaluation_hash")
            for spec in specs
        ),
        "accepted_lane_count": len(list(ladder.get("accepted_lane_evidence") or [])),
        "rejected_lane_count": len(list(ladder.get("rejected_lane_evidence") or [])),
        "stop_reason_if_no_candidate": ladder.get("stop_reason_if_no_candidate"),
    }


def _source_probe() -> dict[str, Any]:
    inputs = _read("inputs_page.py")
    family = _read("design_brain/families/shear_fail.py")
    runtime = _read("design_brain/families/shear_fail_governs/runtime.py")
    publication = _read("design_brain/publication.py")
    return {
        "locked_family_runtime": {
            "runtime_file_has_runner": "run_shear_fail_governs_ladder_runtime" in runtime,
            "family_contract_specs_delegate_to_runtime": "run_shear_fail_governs_ladder_runtime" in family
            or "_run_contract_runtime(" in family,
            "family_specs_return_runtime_authority": '"runtime_authority": "run_shear_fail_governs_ladder_runtime"' in family,
            "runtime_has_no_inputs_page_import": "inputs_page" not in runtime,
        },
        "page_candidate_evaluation_path": {
            "active_shear_early_dispatch": 'early_governing_state == "SHEAR_FAIL_GOVERNS"' in inputs,
            "active_fail_near_current_repair_item_used": "_active_fail_near_current_repair_item(" in inputs,
            "family_strategy_for_shear": 'family_strategy_for("SHEAR_FAIL_GOVERNS")' in inputs,
            "contract_ladder_specs_called": "shear_family_strategy.contracted_repair_ladder_specs(" in inputs,
            "candidate_evaluator_source_stamped": 'eval_source = "shear_fail_contract_ladder"' in inputs,
            "breaks_after_first_compliant_shear_candidate": (
                "if (\n                    isinstance(evaluated, dict)\n                    and bool(evaluated.get(\"is_compliant\"))"
                in inputs
            ),
        },
        "page_blocker_materialization_path": {
            "active_under_capacity_materializer_present": "def _materialize_compute_active_under_capacity_blocker(" in inputs,
            "default_shear_attempted_updates_page_owned": '"s_lig": "tighten link spacing trial"' in inputs
            and '"D": "increase section depth trial"' in inputs
            and '"b": "increase section width trial"' in inputs,
            "blocked_card_generic_shear_text_page_owned": "The checked repair options could not restore shear" in inputs,
            "active_blocker_attempted_id_page_owned": 'f"{_family_for_evidence}_active_failure_practical_ladder_exhausted"' in inputs,
            "publication_can_title_shear_blocker": "Shear repair blocked by shear/detailing limits" in publication,
        },
        "screenshot_string_sources": {
            "design_guide_blocker_proof_incomplete": "Design Guide blocker proof incomplete" in inputs,
            "blocked_by_shear_capacity": "Blocked by shear capacity" in inputs,
            "could_not_restore_shear": "could not restore shear" in inputs,
            "maximum_depth_reached_text": "Maximum depth reached" in inputs,
            "maximum_width_reached_text": "maximum width reached" in inputs.lower(),
        },
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    checks = payload["checks"]
    lines = [
        "# Design Guide Shear Blocked Source Audit",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Finding",
        "",
        f"- locked shear runtime reachable: `{checks['locked_shear_runtime_reachable']}`",
        f"- family specs available for page evaluation: `{checks['family_specs_available_for_page_evaluation']}`",
        f"- blocked screenshot wording is page/view-model owned: `{checks['blocked_wording_page_owned']}`",
        f"- page blocker materializer can publish exhausted shear blocker: `{checks['page_blocker_materializer_present']}`",
        f"- current proof says source classification: `{payload['source_classification']}`",
        "",
        "## Meaning",
        "",
        (
            "The locked `SHEAR_FAIL_GOVERNS` family owns the contract ladder and candidate generation. "
            "The final blocked card text is assembled later in page/shared publication/view-model code from "
            "candidate-search evidence. If the card says max depth/width was reached, the next proof must "
            "show whether those caps came from evaluated contract-ladder candidates or from the page-owned "
            "active-under-capacity blocker materializer."
        ),
        "",
        "## Verification",
        "",
        f"- shear lock verifier: `{payload['verification']['shear_lock']['status']}`",
        f"- active-under-capacity blocker snapshot: `{payload['verification']['active_under_capacity_blocker']['status']}`",
        "",
        "## Next Safe Step",
        "",
        payload["next_safe_step"],
        "",
        "## Output",
        "",
        f"- `{payload['artifact']}`",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_guide_shear_blocked_source_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_blocked_source_audit_{stamp}.md"
    source_probe = _source_probe()
    ladder_probe = _family_ladder_probe()
    verification = {
        "shear_lock": _run(
            [sys.executable, "tools/verification/families/shear_fail_governs_lock_verifier.py"],
            timeout=120,
        ),
        "active_under_capacity_blocker": _run(
            [sys.executable, "tools/verification/compute_active_under_capacity_blocker_snapshot.py"],
            timeout=120,
        ),
    }
    checks = {
        "locked_shear_runtime_reachable": all(source_probe["locked_family_runtime"].values())
        and ladder_probe["runtime_authority"] == "run_shear_fail_governs_ladder_runtime",
        "family_specs_available_for_page_evaluation": bool(ladder_probe["spec_count"])
        and bool(ladder_probe["specs_have_runtime_evidence"]),
        "page_evaluates_family_specs": all(source_probe["page_candidate_evaluation_path"].values()),
        "blocked_wording_page_owned": bool(
            source_probe["screenshot_string_sources"]["blocked_by_shear_capacity"]
            and source_probe["screenshot_string_sources"]["could_not_restore_shear"]
            and source_probe["screenshot_string_sources"]["design_guide_blocker_proof_incomplete"]
        ),
        "page_blocker_materializer_present": all(source_probe["page_blocker_materialization_path"].values()),
        "verification_passed": all(result["status"] == "PASS" for result in verification.values()),
    }
    source_classification = (
        "FAMILY_RUNTIME_CANDIDATES_PAGE_EVALUATED_PAGE_BLOCKER_PUBLISHED"
        if checks["locked_shear_runtime_reachable"]
        and checks["family_specs_available_for_page_evaluation"]
        and checks["page_evaluates_family_specs"]
        and checks["blocked_wording_page_owned"]
        and checks["page_blocker_materializer_present"]
        else "SOURCE_PROOF_INCOMPLETE"
    )
    payload = {
        "schema": "design_guide_shear_blocked_source_audit.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "source_classification": source_classification,
        "source_probe": source_probe,
        "family_ladder_probe": ladder_probe,
        "verification": verification,
        "artifact": str(artifact_path),
        "report": str(report_path),
        "next_safe_step": (
            "Add a live/synthetic candidate-rejection trace for `SHEAR_FAIL_GOVERNS` that records every "
            "contract spec generated, every evaluated candidate, each rejection reason, and whether "
            "depth/width cap evidence came from the family ladder or the page blocker materializer."
        ),
    }
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"{payload['status']}: {artifact_path}")
    print(f"REPORT: {report_path}")
    print(f"CLASSIFICATION: {source_classification}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
