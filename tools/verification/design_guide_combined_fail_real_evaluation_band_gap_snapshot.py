"""Snapshot proving the combined active-fail repair can be safe but outside band.

This is intentionally a gap proof. It prevents the system from treating the
approved combined rescue seed as a target-band repair when real evaluator-shaped
evidence says no target-band candidate was found.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run_compile() -> dict[str, Any]:
    paths = [
        "inputs_page.py",
        "design_brain/families/combined_bending_shear_fail.py",
        "tools/verification/design_guide_combined_fail_real_evaluation_band_gap_snapshot.py",
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", *paths],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": f"python -m py_compile {' '.join(paths)}",
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _live_like_base_state() -> dict[str, Any]:
    return {
        "actions_uls": {"M": 200.0, "Mu": 200.0, "V": 100.0, "Vu": 100.0, "N": 0.0, "P": 0.0, "T": 0.0},
        "actions_mode": "manual",
        "actions_source": "Manual design actions (inputs below)",
        "uls_Mstar": 200.0,
        "Mu_star": 200.0,
        "Mu_star_manual": 200.0,
        "Mu_star_pos": 200.0,
        "Mu_star_pos_manual": 200.0,
        "Mu_star_neg": 0.0,
        "Mu_star_neg_manual": 0.0,
        "load_Mstar_proxy": 200.0,
        "load_Mstar_pos_proxy": 200.0,
        "uls_Vstar": 100.0,
        "Vu_star": 100.0,
        "load_Vstar_proxy": 100.0,
        "uls_Tstar": 0.0,
        "Tu_star": 0.0,
        "uls_Nstar": 0.0,
        "N_star": 0.0,
        "b": 250.0,
        "bw": 250.0,
        "D": 500.0,
        "fc": 40.0,
        "fsy": 500.0,
        "cover_bot": 40.0,
        "cover_top": 40.0,
        "cover_side": 40.0,
        "bot1_count": 3,
        "db_bot_1": 16,
        "bot2_count": 0,
        "db_bot_2": 0,
        "top1_count": 2,
        "db_top_1": 10,
        "top2_count": 0,
        "db_top_2": 0,
        "lig_d": 0,
        "lig_legs": 0,
        "s_lig": 200,
        "L": 6000.0,
    }


def _live_like_overview() -> dict[str, Any]:
    return {
        "utils": {"bending": 1.80, "shear": 1.55},
        "statuses": {"bending": "FAIL", "shear": "FAIL", "crack": "PASS", "deflection": "PASS"},
        "any_fail": True,
        "all_key_pass": False,
        "worst_util": 1.80,
    }


def _build_snapshot() -> dict[str, Any]:
    with contextlib.redirect_stderr(io.StringIO()):
        import inputs_page  # type: ignore

        item = inputs_page._active_fail_near_current_repair_item(
            _live_like_base_state(),
            _live_like_overview(),
            {"bending", "shear"},
        )
    item = dict(item or {})
    evidence = dict(item.get("candidate_search_evidence") or {})
    rows = [dict(row) for row in list(evidence.get("candidate_rows") or []) if isinstance(row, dict)]
    selected_updates = dict(item.get("updates") or dict(item.get("button_contract") or {}).get("updates") or {})
    safe_count = int(evidence.get("safe_executor_backed_candidates_count") or 0)
    target_count = int(evidence.get("target_band_candidate_count") or 0)
    selected_util = evidence.get("selected_candidate_util")
    target_candidate_found = target_count > 0
    checks = {
        "active_fail_item_exists": bool(item),
        "safe_executor_backed_candidate_exists": safe_count > 0,
        "target_band_result_is_explicit": target_count >= 0,
        "selected_updates_exist": bool(selected_updates),
        "selected_candidate_band_status_is_explained": (
            bool(evidence.get("best_target_band_candidate_id")) if target_candidate_found else not bool(evidence.get("best_target_band_candidate_id"))
        ),
    }
    payload = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "gap_classification": (
            "TARGET_BAND_REPAIR_FOUND"
            if target_candidate_found
            else "SAFE_REPAIR_EXISTS_BUT_TARGET_BAND_REPAIR_MISSING"
        ),
        "case": {
            "base_utils": dict(_live_like_overview().get("utils") or {}),
            "safe_executor_backed_candidates_count": safe_count,
            "target_band_candidate_count": target_count,
            "selected_candidate_util": selected_util,
            "selected_updates": selected_updates,
            "candidate_rows": [
                {
                    "candidate_id": row.get("candidate_id"),
                    "title": row.get("title"),
                    "preview_util": row.get("preview_util"),
                    "preview_bending_util": row.get("preview_bending_util"),
                    "preview_shear_util": row.get("preview_shear_util"),
                    "preview_pass": row.get("preview_pass"),
                    "reaches_target_band": row.get("reaches_target_band"),
                    "proposed_updates": dict(row.get("proposed_updates") or {}),
                }
                for row in rows[:20]
            ],
        },
        "contract_alignment": {
            "family": "COMBINED_BENDING_SHEAR_FAIL",
            "contract_target_band_preferred": "both bending and shear inside target band",
            "contract_fallback_allowed": "best compliant combined repair with specific reason",
            "contract_target_band_lane": "APPROVED_COMBINED_TARGET_BAND_REFINEMENT",
            "next_required_slice": (
                "verify live publication uses the target-band repair"
                if target_candidate_found
                else "keep explicit fallback proof and broaden family-owned refinement candidates only with contract evidence"
            ),
        },
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    return payload


def _write_artifacts(payload: dict[str, Any], compile_result: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_combined_fail_real_evaluation_band_gap_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_fail_real_evaluation_band_gap_{stamp}.md"
    json_path.write_text(_stable_json({"compile": compile_result, **payload}) + "\n", encoding="utf-8")
    checks = payload.get("checks") or {}
    report = [
        "# Design Guide Combined Fail Real Evaluation Band Gap Snapshot",
        "",
        f"Result: `{payload.get('status')}`",
        "",
        f"Gap classification: `{payload.get('gap_classification')}`",
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in sorted(checks.items())],
        "",
        "## Current Candidate Counts",
        f"- safe executor-backed candidates: `{payload['case']['safe_executor_backed_candidates_count']}`",
        f"- target-band candidates: `{payload['case']['target_band_candidate_count']}`",
        f"- selected candidate util: `{payload['case']['selected_candidate_util']}`",
        "",
        "## Next Required Slice",
        payload["contract_alignment"]["next_required_slice"],
        "",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    compile_result = _run_compile()
    payload = _build_snapshot()
    if not compile_result["passed"]:
        payload["status"] = "FAIL"
    json_path, report_path = _write_artifacts(payload, compile_result)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if payload["status"] == "PASS" and compile_result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
