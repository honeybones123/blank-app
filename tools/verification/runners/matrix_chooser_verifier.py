from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
RUNNERS = REPO / "tools" / "verification" / "runners"
ARTIFACT_DIR = REPO / "artifacts" / "verification" / "latest"
TIMESTAMP = datetime.now().isoformat(timespec="seconds").replace(":", "-")

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.verification.runners.real_user_design_guide_ladder import ACTIVE_FAILURE_MATRIX_CASES  # noqa: E402
from tools.verification.helpers.overdesign_assertions import (  # noqa: E402
    assert_visible_output_matches_one_click_contract,
)


MATRIX_CASE_IDS = [str(case["case_id"]) for case in ACTIVE_FAILURE_MATRIX_CASES]


def _latest_artifact(pattern: str, *, newer_than: float) -> Path | None:
    candidates = [
        path
        for path in ARTIFACT_DIR.glob(pattern)
        if path.is_file() and path.stat().st_mtime >= newer_than
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _load_json(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_load_error": str(exc)}


def _case_contract_failures(case: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    case_id = str(case.get("case_id") or "")
    if case.get("browser_mode") != "browser_live":
        failures.append(f"matrix_browser_mode_not_live:{case_id}:{case.get('browser_mode') or 'missing'}")
    if case.get("verdict") != "PASS":
        failures.append(f"matrix_case_not_pass:{case_id}:{case.get('fail_reasons')}")
    if int(case.get("visible_card_count_before") or 0) != 1:
        failures.append(f"matrix_visible_card_count_not_one:{case_id}:{case.get('visible_card_count_before')}")
    if not bool((case.get("final_browser_state_wait_meta") or {}).get("final_probe_rendered")):
        failures.append(f"matrix_final_proof_not_rendered:{case_id}")
    if (case.get("final_browser_state_wait_meta") or {}).get("visible_card_agrees_with_probe") is False:
        failures.append(f"matrix_visible_card_disagrees_with_probe:{case_id}")
    if case.get("one_click_button_enabled_before"):
        contract = dict(case.get("button_contract") or {})
        if contract.get("actionable") is not True:
            failures.append(f"matrix_enabled_cta_not_actionable:{case_id}")
        if not dict(contract.get("updates") or {}):
            failures.append(f"matrix_enabled_cta_empty_updates:{case_id}")
        if contract.get("preview_pass") is not True:
            failures.append(f"matrix_enabled_cta_preview_not_pass:{case_id}")
        if contract.get("blocking_reason"):
            failures.append(f"matrix_enabled_cta_has_blocking_reason:{case_id}:{contract.get('blocking_reason')}")
    for reason in list(case.get("fail_reasons") or []):
        reason_text = str(reason)
        if reason_text.startswith("matrix_") or "stale" in reason_text:
            failures.append(f"matrix_contract_failure:{case_id}:{reason_text}")
    visible_contract_failures = assert_visible_output_matches_one_click_contract(case_id, case)
    failures.extend(f"matrix_visible_contract_failure:{case_id}:{reason}" for reason in visible_contract_failures)
    return failures


def _summarise(
    real_user_data: dict[str, Any],
    *,
    runner_status: str,
    artifact: Path | None,
    selected_case_ids: list[str],
) -> dict[str, Any]:
    cases = [dict(case) for case in list(real_user_data.get("cases") or [])]
    by_id = {str(case.get("case_id") or ""): case for case in cases}
    failures: list[dict[str, Any]] = []
    missing = [case_id for case_id in selected_case_ids if case_id not in by_id]
    for case_id in missing:
        failures.append({"case_id": case_id, "fail_reasons": ["matrix_case_missing_from_child_artifact"]})
    for case_id in selected_case_ids:
        case = by_id.get(case_id)
        if not case:
            continue
        reasons = _case_contract_failures(case)
        if reasons:
            failures.append({"case_id": case_id, "fail_reasons": reasons})

    source_verdict = str(real_user_data.get("verdict") or "").upper()
    source_validity = str(real_user_data.get("verifier_validity_status") or "").upper()
    source_one_click = str(real_user_data.get("one_click_contract_status") or "").upper()
    if runner_status != "PASS":
        failures.append({"case_id": "__runner__", "fail_reasons": [f"runner_status:{runner_status}"]})
    if source_verdict != "PASS":
        failures.append({"case_id": "__child_verdict__", "fail_reasons": [f"child_verdict:{source_verdict or 'missing'}"]})
    if source_validity != "VALID":
        failures.append({"case_id": "__child_validity__", "fail_reasons": [f"child_validity:{source_validity or 'missing'}"]})
    if source_one_click != "PASS":
        failures.append({"case_id": "__child_one_click__", "fail_reasons": [f"child_one_click:{source_one_click or 'missing'}"]})

    pass_count = len(selected_case_ids) - len({f["case_id"] for f in failures if not str(f["case_id"]).startswith("__")})
    return {
        "generated_at": datetime.now().isoformat(),
        "verdict": "PASS" if not failures else "FAIL",
        "status": "PASS" if not failures else "FAIL",
        "matrix_chooser_required_gate": True,
        "matrix_chooser_status": "PASS" if not failures else "FAIL",
        "matrix_chooser_total": len(selected_case_ids),
        "matrix_chooser_pass": pass_count,
        "matrix_chooser_fail": len(selected_case_ids) - pass_count,
        "total_cases": len(selected_case_ids),
        "pass_count": pass_count,
        "fail_count": len(selected_case_ids) - pass_count,
        "runner_status": runner_status,
        "source_real_user_artifact": str(artifact) if artifact else None,
        "source_verdict": real_user_data.get("verdict"),
        "source_verifier_validity_status": real_user_data.get("verifier_validity_status"),
        "source_one_click_contract_status": real_user_data.get("one_click_contract_status"),
        "case_ids": selected_case_ids,
        "failures": failures,
        "fail_reasons": [reason for failure in failures for reason in list(failure.get("fail_reasons") or [])],
        "cases": [
            {
                "case_id": case_id,
                "verdict": by_id.get(case_id, {}).get("verdict"),
                "browser_mode": by_id.get(case_id, {}).get("browser_mode"),
                "visible_card_count_before": by_id.get(case_id, {}).get("visible_card_count_before"),
                "selected_action_family": by_id.get(case_id, {}).get("selected_action_family"),
                "selected_action_title": by_id.get(case_id, {}).get("selected_action_title"),
                "one_click_button_visible_before": by_id.get(case_id, {}).get("one_click_button_visible_before"),
                "one_click_button_enabled_before": by_id.get(case_id, {}).get("one_click_button_enabled_before"),
                "fail_reasons": by_id.get(case_id, {}).get("fail_reasons"),
            }
            for case_id in selected_case_ids
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the required browser-live Design Guide matrix chooser verifier.")
    parser.add_argument("--port", type=int, default=9090)
    parser.add_argument("--case", action="append", dest="cases", default=None)
    parser.add_argument("--cases", dest="cases_csv", default=None, help="Comma-separated matrix case_id list.")
    parser.add_argument("--list-cases", action="store_true")
    args = parser.parse_args(argv)

    selected = list(MATRIX_CASE_IDS)
    if args.list_cases:
        for case_id in selected:
            print(case_id)
        return 0
    if args.cases:
        selected = [str(case_id).strip() for case_id in args.cases if str(case_id).strip()]
    if args.cases_csv:
        selected = [case_id.strip() for case_id in str(args.cases_csv).split(",") if case_id.strip()]
    unknown = sorted(set(selected) - set(MATRIX_CASE_IDS))
    if unknown:
        raise SystemExit(f"Unknown matrix chooser case(s): {', '.join(unknown)}")

    started_at = datetime.now().timestamp()
    cmd = [
        sys.executable,
        str(RUNNERS / "real_user_design_guide_ladder.py"),
        "--port",
        str(args.port),
    ]
    for case_id in selected:
        cmd.extend(["--case", case_id])
    result = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=7200)  # noqa: S603
    runner_status = "PASS" if result.returncode == 0 else "FAIL"
    source_artifact = _latest_artifact("real_user_design_guide_ladder_*.json", newer_than=started_at)
    source_data = _load_json(source_artifact)
    output = _summarise(
        source_data,
        runner_status=runner_status,
        artifact=source_artifact,
        selected_case_ids=selected,
    )
    output["stdout_tail"] = (result.stdout or "")[-20000:]
    output["stderr_tail"] = (result.stderr or "")[-20000:]
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARTIFACT_DIR / f"matrix_chooser_verifier_{TIMESTAMP}.json"
    output["matrix_chooser_artifact"] = str(out_path)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": output["verdict"],
                "output": str(out_path),
                "total_cases": output["total_cases"],
                "pass_count": output["pass_count"],
                "fail_count": output["fail_count"],
                "source_real_user_artifact": str(source_artifact) if source_artifact else None,
            },
            indent=2,
        )
    )
    return 0 if output["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
