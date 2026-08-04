"""Lock the application Apply command's single-dispatch behavior."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application.apply_command import execute_apply_command
from design_brain.authority import EngineeringInputSnapshot, build_authoritative_design_result


def main() -> int:
    snapshot = EngineeringInputSnapshot(geometry={"b": 300.0})
    current_result = build_authoritative_design_result(
        engineering_snapshot=snapshot,
        apply_payload={"candidate_id": "candidate-a", "updates": {"b": 320.0}},
    )
    calls: list[dict] = []

    def executor(payload: dict) -> str:
        calls.append(dict(payload))
        return "dispatch_ok"

    accepted = execute_apply_command(
        current_result=current_result,
        recommendation={"candidate_id": "candidate-a", "updates": {"b": 320.0}},
        apply_fn=executor,
    )
    accepted_calls = len(calls)
    qualified = execute_apply_command(
        current_result=current_result,
        recommendation={
            "candidate_id": "SHEAR_FAIL_GOVERNS:shear_fail:repair:candidate-a",
            "family": "SHEAR_FAIL_GOVERNS",
            "updates": {"b": 320.0},
        },
        apply_fn=executor,
    )
    stale = execute_apply_command(
        current_result=current_result,
        recommendation={"candidate_id": "candidate-b", "updates": {"b": 340.0}},
        apply_fn=executor,
    )
    missing = execute_apply_command(
        current_result=current_result,
        recommendation={},
        apply_fn=executor,
    )
    checks = {
        "accepted_dispatch_ok": accepted.status == "dispatch_ok",
        "accepted_executor_called_once": accepted_calls == 1,
        "family_qualified_identity_accepted": qualified.status == "dispatch_ok",
        "qualified_identity_executor_called_once": len(calls) == 2,
        "stale_payload_rejected": stale.status == "failed" and stale.reason == "stale_authoritative_apply_payload",
        "stale_payload_did_not_dispatch": len(calls) == 2,
        "missing_payload_rejected": missing.status == "failed" and missing.reason == "missing_apply_payload",
        "missing_payload_did_not_dispatch": len(calls) == 2,
    }
    status = "LOCKED" if all(checks.values()) else "FAIL"
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    artifact_dir = ROOT / "artifacts" / "verification"
    audit_dir = ROOT / "artifacts" / "audits"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    artifact = artifact_dir / f"authoritative_apply_command_lock_{stamp}.json"
    report = audit_dir / f"authoritative_apply_command_lock_{stamp}.md"
    payload = {
        "schema": "authoritative_apply_command_lock.v1",
        "status": status,
        "checks": checks,
        "accepted": accepted.__dict__,
        "stale": stale.__dict__,
        "missing": missing.__dict__,
        "executor_call_count": len(calls),
    }
    artifact.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    report.write_text(
        "\n".join(
            [
                "# Authoritative Apply Command Lock",
                "",
                f"Status: **{status}**",
                "",
                "The application command validates the payload, rejects stale candidate identity, and dispatches the injected legacy executor at most once.",
                "",
                f"Machine-readable artifact: `{artifact.relative_to(ROOT).as_posix()}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "artifact": str(artifact), "report": str(report), "checks": checks}, indent=2))
    return 0 if status == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
