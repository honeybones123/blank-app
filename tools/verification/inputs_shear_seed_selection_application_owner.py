"""Verify application-owned shear seed ranking and diversification parity."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.recipes.one_click_recipe_defs import build_state, find_named_case


RECIPES = (
    "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02",
    "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
    "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01",
)


def _candidate(
    base: dict,
    *,
    candidate_type: str,
    updates: dict,
    shear_util: float,
    score: float,
    label: str,
    compliant: bool = True,
) -> dict:
    state = dict(base)
    state.update(updates)
    return {
        "state": state,
        "updates": dict(updates),
        "overview": {"utils": {"shear": shear_util}},
        "shear_candidate_type": candidate_type,
        "score": score,
        "label": label,
        "is_compliant": compliant,
        "candidate_reaches_target_band": 0.88 <= shear_util <= 0.95,
        "Ast_bot": float(state.get("Ast_bot", 0.0) or 0.0),
    }


def main() -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_application.shear_candidate_selection import (
            combined_shear_seed_candidates,
        )
        from inputs_page_modules.recommendation_compute import (
            ShearRecommendationRuntime,
        )

    rows = []
    for recipe in RECIPES:
        base = build_state(find_named_case(recipe)["changes"])
        seed = {
            "state": dict(base),
            "Ast_bot": float(base.get("Ast_bot", 2000.0) or 2000.0),
        }
        candidates = [
            _candidate(
                base,
                candidate_type="spacing",
                updates={"s_lig": 100.0},
                shear_util=0.91,
                score=9.0,
                label="spacing-band",
            ),
            _candidate(
                base,
                candidate_type="more legs",
                updates={"lig_legs": 4},
                shear_util=0.97,
                score=7.0,
                label="legs",
            ),
            _candidate(
                base,
                candidate_type="width increase",
                updates={"b": float(base.get("b", 300.0) or 300.0) + 50.0},
                shear_util=0.89,
                score=6.0,
                label="width",
            ),
            _candidate(
                base,
                candidate_type="combined",
                updates={
                    "D": float(base.get("D", 600.0) or 600.0) + 50.0,
                    "s_lig": 100.0,
                },
                shear_util=0.93,
                score=8.0,
                label="combined",
            ),
        ]
        candidates.append(copy.deepcopy(candidates[0]))
        for limit in (2, 8):
            kwargs = {
                "seed_candidate": seed,
                "base_state": base,
                "severity_band": "severe",
                "seed_shear_util": 1.8,
                "limit": limit,
            }
            compatibility = bridge._combined_shear_seed_candidates(
                copy.deepcopy(candidates),
                **copy.deepcopy(kwargs),
            )
            application = combined_shear_seed_candidates(
                copy.deepcopy(candidates),
                **copy.deepcopy(kwargs),
            )
            rows.append(
                {
                    "recipe": recipe,
                    "limit": limit,
                    "exact_candidate_list_match": compatibility == application,
                    "compatibility_count": len(compatibility),
                    "application_count": len(application),
                }
            )

    runtime_fields = set(ShearRecommendationRuntime.__dataclass_fields__)
    checks = {
        "six_recipe_limit_cases_match_exactly": all(
            row["exact_candidate_list_match"] for row in rows
        ),
        "bridge_callback_removed_from_typed_runtime": (
            "_combined_shear_seed_candidates" not in runtime_fields
        ),
        "application_owner_imports_no_bridge": (
            "inputs_page_app_contract_bridge"
            not in (
                ROOT / "inputs_application" / "shear_candidate_selection.py"
            ).read_text(encoding="utf-8")
        ),
    }
    payload = {
        "contract_version": "inputs_shear_seed_selection_application_owner.v1",
        "checks": checks,
        "cases": rows,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
