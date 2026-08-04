"""Prove legacy/permanent one-click parity across material browser transactions."""

from __future__ import annotations

import copy
import hashlib
import json
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "tools/verification/helpers/browser_one_click_regression.py"
APP = ROOT / "tools/verification/inputs_one_click_transaction_browser_app.py"
CASES = (
    "AB_IN_TARGET_BAND",
    "AB_BLOCKED_INVALID_STATE",
    "A_bending_under_only",
    "B_shear_under_only",
    "C_combined_underdesign",
    "D_bending_overdesign",
    "E_shear_overdesign",
    "F_combined_overdesign",
    "AB_COMMIT_ROLLBACK",
)
EXPECTED = {
    "AB_IN_TARGET_BAND": {
        "status": "pass",
        "stop_reason": "already_in_band",
        "shared": {"D": 400.0, "b": 300.0, "bot1_count": 4, "db_bot_1": 16.0},
    },
    "AB_BLOCKED_INVALID_STATE": {
        "status": "blocked",
        "stop_reason": "missing_or_invalid_D",
        "shared": {"D": -1.0, "b": 300.0, "bot1_count": 4, "db_bot_1": 16.0},
    },
    "A_bending_under_only": {
        "status": "ready",
        "stop_reason": "reached_target_band",
        "shared": {"D": 450.0, "b": 350.0, "bot1_count": 5, "db_bot_1": 24.0},
    },
    "B_shear_under_only": {
        "status": "ready",
        "stop_reason": "reached_target_band",
        "shared": {
            "D": 400.0,
            "b": 300.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 75.0,
        },
    },
    "C_combined_underdesign": {
        "status": "ready",
        "stop_reason": "reached_target_band",
        "shared": {
            "D": 450.0,
            "b": 350.0,
            "bot1_count": 5,
            "db_bot_1": 24.0,
            "lig_d": 20,
            "lig_legs": 2,
            "s_lig": 150.0,
        },
    },
    "D_bending_overdesign": {
        "status": "ready",
        "stop_reason": "reached_target_band",
        "shared": {
            "D": 400.0,
            "b": 300.0,
            "bot1_count": 3,
            "db_bot_1": 12.0,
            "s_lig": 300.0,
        },
    },
    "E_shear_overdesign": {
        "status": "ready",
        "stop_reason": "best_available_out_of_band_candidate",
        "shared": {
            "D": 400.0,
            "b": 300.0,
            "bot1_count": 2,
            "db_bot_1": 24.0,
            "s_lig": 300.0,
        },
    },
    "F_combined_overdesign": {
        "status": "ready",
        "stop_reason": "reached_target_band",
        "shared": {
            "D": 325.0,
            "b": 300.0,
            "bot1_count": 4,
            "db_bot_1": 16.0,
            "s_lig": 220.0,
        },
    },
    "AB_COMMIT_ROLLBACK": {
        "status": "rejected",
        "stop_reason": "commit_validation_failed",
        "shared": {"D": 400.0, "b": 300.0, "bot1_count": 4, "db_bot_1": 16.0},
    },
}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run(case: str, implementation: str) -> dict[str, Any]:
    command = [
        sys.executable,
        str(HELPER),
        "--case",
        case,
        "--summary-only",
        "--app-script",
        str(APP),
        "--one-click-implementation",
        implementation,
        "--transaction-timeout-sec",
        "180",
        "--port",
        str(_free_port()),
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"{implementation}/{case} exited {completed.returncode}:\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    payload = json.loads(completed.stdout)
    return dict(payload[case])


def _comparable(value: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(value)
    result.pop("implementation", None)
    return result


def _updates_digest(value: dict[str, Any]) -> str | None:
    updates = (
        value.get("solver_result", {})
        .get("one_click_solve", {})
        .get("final_updates")
    )
    if not updates:
        return None
    encoded = json.dumps(
        updates,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _assert_contract(case: str, value: dict[str, Any]) -> None:
    expected = EXPECTED[case]
    solver = dict(value.get("solver_result") or {})
    if solver.get("status") != expected["status"]:
        raise AssertionError(
            f"{case}: status {solver.get('status')!r} != {expected['status']!r}"
        )
    if solver.get("stop_reason") != expected["stop_reason"]:
        raise AssertionError(
            f"{case}: stop_reason {solver.get('stop_reason')!r} "
            f"!= {expected['stop_reason']!r}"
        )
    if value.get("transaction_error") is not None:
        raise AssertionError(f"{case}: transaction error: {value['transaction_error']}")
    session = dict(value.get("session_contract") or {})
    expected_latches = {
        "compute_in_progress": False,
        "invoke_consumed": False,
        "invoke_pending": False,
        "invoke_present": False,
        "solver_running": False,
    }
    for key, expected_value in expected_latches.items():
        if session.get(key) != expected_value:
            raise AssertionError(
                f"{case}: session latch {key}={session.get(key)!r}, "
                f"expected {expected_value!r}"
            )
    shared = dict(value.get("shared_subset") or {})
    for key, expected_value in expected["shared"].items():
        if shared.get(key) != expected_value:
            raise AssertionError(
                f"{case}: shared {key}={shared.get(key)!r}, "
                f"expected {expected_value!r}"
            )


def main() -> int:
    evidence: dict[str, Any] = {
        "gate": "inputs_one_click_browser_transaction_parity",
        "generated_at": datetime.now().astimezone().isoformat(),
        "cases": {},
    }
    for case in CASES:
        legacy = _run(case, "legacy")
        permanent = _run(case, "permanent")
        _assert_contract(case, legacy)
        _assert_contract(case, permanent)
        equal = _comparable(legacy) == _comparable(permanent)
        evidence["cases"][case] = {
            "equal": equal,
            "legacy": legacy,
            "permanent": permanent,
            "final_updates_sha256": _updates_digest(legacy),
        }
        if not equal:
            raise AssertionError(f"{case}: legacy/permanent transaction mismatch")

    evidence["status"] = "PASS"
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    artifact = (
        ROOT
        / "artifacts/verification"
        / f"inputs_one_click_browser_transaction_parity_{stamp}.json"
    )
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, allow_nan=True),
        encoding="utf-8",
    )
    print(
        "PASS: legacy/permanent browser transaction parity "
        f"{len(CASES)}/{len(CASES)}; artifact={artifact.relative_to(ROOT)}"
    )
    for case in CASES:
        result = evidence["cases"][case]["legacy"]
        solver = result["solver_result"]
        print(
            f"  {case}: {solver.get('status')}/"
            f"{solver.get('stop_reason')} "
            f"updates_sha256={evidence['cases'][case]['final_updates_sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
