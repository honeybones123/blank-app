"""Verify explicit severe-shear diagnostic wiring and reserve payload parity."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_application.secondary_bending_tightening import (
            secondary_action_reserves,
        )
        from inputs_page_modules.design_guide.severe_shear_escalation_log import (
            _log_severe_shear_escalation,
        )
        from inputs_page_modules.recommendation_compute import (
            ShearRecommendationRuntime,
        )

    seed = {
        "state": {
            "design_optimisation_goal": "balanced",
            "optimisation_lock_geometry": False,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 200.0,
        },
        "overview": {
            "utils": {"shear": 1.8, "bending": 0.6},
            "packs": {
                "bending": {
                    "summary_phiMu_kNm": 500.0,
                    "summary_Mu_star_kNm": 300.0,
                }
            },
        },
    }
    selected = {
        "candidate_key": "spacing-150",
        "family": "spacing tighter",
        "label": "N10 @ 150",
        "score_total": 1.0,
        "shear_util": 0.94,
        "survived_filters": True,
        "selected": True,
        "score_components": {},
    }
    audit = {"spacing tighter": [selected]}
    kwargs = {
        "source": "typed_parity",
        "seed_candidate": seed,
        "severity_band": "severe",
        "candidates": [selected],
        "selected": selected,
        "family_audit": audit,
    }
    calls = {"compatibility": [], "typed": [], "disabled": []}
    originals = {"st": bridge.st, "logger": bridge._agent_debug_log}
    try:
        bridge.st = SimpleNamespace(session_state={"_dev_mode": True})
        bridge._agent_debug_log = lambda *args, **named: calls[
            "compatibility"
        ].append((copy.deepcopy(args), copy.deepcopy(named)))
        bridge._log_severe_shear_escalation(**copy.deepcopy(kwargs))
    finally:
        bridge.st = originals["st"]
        bridge._agent_debug_log = originals["logger"]
    _log_severe_shear_escalation(
        **copy.deepcopy(kwargs),
        agent_debug_log=lambda *args, **named: calls["typed"].append(
            (copy.deepcopy(args), copy.deepcopy(named))
        ),
        enabled=True,
    )
    _log_severe_shear_escalation(
        **copy.deepcopy(kwargs),
        agent_debug_log=lambda *args, **named: calls["disabled"].append(
            (copy.deepcopy(args), copy.deepcopy(named))
        ),
        enabled=False,
    )
    runtime_fields = set(ShearRecommendationRuntime.__dataclass_fields__)
    checks = {
        "enabled_payload_matches_bridge_wiring": (
            calls["compatibility"] == calls["typed"]
        ),
        "disabled_emits_nothing": calls["disabled"] == [],
        "secondary_reserve_payload_matches_compatibility": (
            bridge._secondary_action_reserves(seed)
            == secondary_action_reserves(seed)
        ),
        "shear_runtime_has_only_permanent_typed_services": (
            runtime_fields == {"trace", "evaluation", "scoring"}
        ),
        "diagnostic_module_has_no_global_binder": (
            "bind_severe_shear_escalation_log_dependencies"
            not in (
                ROOT
                / "inputs_page_modules"
                / "design_guide"
                / "severe_shear_escalation_log.py"
            ).read_text(encoding="utf-8")
        ),
    }
    payload = {
        "contract_version": "inputs_severe_shear_escalation_typed_diagnostics.v1",
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
