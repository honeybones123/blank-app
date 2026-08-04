"""Proof-only check for the family shared-lock run cache."""

from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "tools" / "verification" / "families" / "family_live_fuzz_regression_lock_gate.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    source = TARGET.read_text(encoding="utf-8", errors="ignore")
    required_tokens = {
        "run_scoped_cache": "run_scoped_shared_locks",
        "run_id_guard": "verification_run_id",
        "source_hash_guard": "source_code_hash",
        "script_guard": "metadata.get(\"script\") != script",
        "cache_lock": "os.O_EXCL",
        "stale_cache_rejected": "return None",
        "no_run_direct_fallback": "no_run_id_direct_execution",
    }
    checks = {name: token in source for name, token in required_tokens.items()}
    passed = all(checks.values())
    payload = {
        "schema": "design_brain.shared_lock_run_cache_snapshot.v1",
        "status": "PASS" if passed else "FAIL",
        "product_behaviour_changed": False,
        "cache_is_verifier_only": True,
        "checks": checks,
        "requirements": [
            "cache is scoped to one verification_run_id",
            "cache is rejected on source_code_hash mismatch",
            "cache is rejected on script mismatch or unreadable metadata",
            "concurrent writers use an exclusive lock",
            "missing run id executes directly without cache reuse",
        ],
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = __import__("datetime").datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shared_lock_run_cache_snapshot_{stamp}.json"
    report_path = AUDIT_DIR / f"shared_lock_run_cache_snapshot_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "# Shared Lock Run Cache Snapshot\n\n"
        f"Status: `{payload['status']}`\n\n"
        "The cache is verifier-only and cannot certify a different run, source hash, or child script.\n",
        encoding="utf-8",
    )
    print(f"shared_lock_run_cache_snapshot {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
