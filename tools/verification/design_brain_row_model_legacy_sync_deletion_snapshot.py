from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
VERIFICATION = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

TOKENS = ("row_model_legacy_sync_applied", "row_model_legacy_sync_diff_keys")


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-8:],
        "stderr_tail": proc.stderr.strip().splitlines()[-8:],
    }


def main() -> int:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)

    inputs_source = _read(INPUTS)
    controller_source = _read(CONTROLLER)
    failures: list[str] = []

    token_presence = {
        "inputs_page.py": {token: (token in inputs_source) for token in TOKENS},
        "design_brain/design_guide_controller.py": {
            token: (token in controller_source) for token in TOKENS
        },
    }
    for file_name, row in token_presence.items():
        for token, present in row.items():
            if present:
                failures.append(f"token_still_present:{file_name}:{token}")

    gate_compute_invalid = _run("tools/verification/design_guide_compute_invalid_state_debug_payload_extraction.py")
    gate_surface_audit = _run("tools/verification/design_brain_row_model_legacy_sync_surface_audit.py")

    if not gate_compute_invalid["passed"]:
        failures.append("compute_invalid_state_debug_payload_extraction_not_green")
    if not gate_surface_audit["passed"]:
        failures.append("row_model_legacy_sync_surface_audit_not_green")

    payload = {
        "snapshot_name": "design_brain_row_model_legacy_sync_deletion_snapshot",
        "generated_at": timestamp,
        "result": "PASS" if not failures else "FAIL",
        "token_presence": token_presence,
        "gates": {
            "compute_invalid_state_debug_payload_extraction": gate_compute_invalid,
            "row_model_legacy_sync_surface_audit": gate_surface_audit,
        },
        "failures": failures,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_target": "Refresh internal scaffolding inventory; if green, move to the remaining combined-candidate mirror surface audit.",
    }
    payload["snapshot_hash"] = _stable_hash(payload)

    json_path = VERIFICATION / f"design_brain_row_model_legacy_sync_deletion_snapshot_{timestamp.replace(':', '-')}.json"
    md_path = AUDITS / f"design_brain_row_model_legacy_sync_deletion_snapshot_{timestamp.replace(':', '-')}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Design Brain Row-Model Legacy Sync Deletion Snapshot",
        "",
        f"## Summary\n{payload['result']}",
        "",
        "## Token Presence",
        "",
    ]
    for file_name, row in token_presence.items():
        lines.append(f"- `{file_name}`: `{row}`")
    lines.extend(
        [
            "",
            "## Gates",
            "",
            f"- compute_invalid_state_debug_payload_extraction: `{gate_compute_invalid['passed']}`",
            f"- row_model_legacy_sync_surface_audit: `{gate_surface_audit['passed']}`",
            "",
            "## Failures",
            "",
            *([f"- `{failure}`" for failure in failures] or ["None."]),
            "",
            "## Next Safe Target",
            "",
            payload["next_safe_target"],
            "",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"design_brain_row_model_legacy_sync_deletion_snapshot {payload['result']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
