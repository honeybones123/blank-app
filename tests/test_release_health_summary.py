from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "verification" / "helpers" / "release_health_summary.py"


def _module():
    spec = importlib.util.spec_from_file_location("release_health_summary", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summary_classifies_apply_and_stale_revision_evidence():
    module = _module()
    result = module.summarise(
        [
            (
                "evidence.json",
                {
                    "case": {
                        "button_found": True,
                        "product_apply_updates_committed": True,
                        "transaction_error": None,
                    },
                    "stale": {"transaction_error": "stale_apply_candidate_source_revision"},
                    "session": {"session_contract": {"ok": False, "state_loss": True}},
                },
            )
        ]
    )
    assert result["apply_attempts"] == 2
    assert result["apply_successes"] == 1
    assert result["apply_failures"] == 1
    assert result["stale_revision_events"] == 1
    assert result["session_state_loss_events"] == 1

