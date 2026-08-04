"""Canonical release-gate entry point for root-cause proof policy."""

from __future__ import annotations

try:
    from tools.verification.root_cause_proof_policy_snapshot import main
except ModuleNotFoundError:
    from root_cause_proof_policy_snapshot import main


if __name__ == "__main__":
    raise SystemExit(main())

