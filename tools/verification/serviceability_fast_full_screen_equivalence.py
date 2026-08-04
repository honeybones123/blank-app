"""Prove fast serviceability ladder screening agrees with full confirmation."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.recommendation_candidate_adapter import (  # noqa: E402
    evaluate_fast_candidate,
    evaluate_full_candidate,
)
from tools.verification.recipes.one_click_recipe_defs import (  # noqa: E402
    build_state,
    find_named_case,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _close(left: Any, right: Any, *, tolerance: float = 1e-9) -> bool:
    left_number = _number(left)
    right_number = _number(right)
    if left_number is None or right_number is None:
        return left_number is right_number
    return abs(left_number - right_number) <= tolerance


def _valid(overview: dict[str, Any]) -> bool:
    return bool(overview.get("all_key_pass") and not overview.get("any_fail"))


def _candidate_updates(state: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    depth = float(state.get("D") or 500.0)
    width = float(state.get("b") or 300.0)
    count = int(state.get("bot1_count") or 3)
    return (
        {"bot1_count": count + 1},
        {"D": depth + 25.0, "bot1_count": count + 1},
        {"b": width + 25.0, "bot1_count": count + 1},
        {"D": depth + 100.0, "b": width + 100.0, "bot1_count": count + 4},
    )


def main() -> int:
    rows: list[dict[str, Any]] = []
    for index in range(1, 11):
        recipe = f"LIVE_FUZZ_SERVICEABILITY_GOVERNS_{index:02d}"
        case = find_named_case(recipe)
        if not isinstance(case, dict):
            rows.append({"recipe": recipe, "passed": False, "reason": "recipe_missing"})
            continue
        state = build_state(dict(case.get("changes") or {}))
        base_full = evaluate_full_candidate(
            state,
            session_state={},
            source="serviceability_equivalence_base",
        )
        base_overview = dict((base_full or {}).get("overview") or {})
        context = {
            "reference_overview": base_overview,
            "seed_overview": base_overview,
        }
        for ordinal, updates in enumerate(_candidate_updates(state), start=1):
            candidate_state = dict(state)
            candidate_state.update(updates)
            fast = evaluate_fast_candidate(
                candidate_state,
                context,
                session_state={},
            )
            full = evaluate_full_candidate(
                candidate_state,
                session_state={},
                source="serviceability_equivalence_full",
                updates=updates,
            )
            fast_overview = dict((fast or {}).get("overview") or {})
            full_overview = dict((full or {}).get("overview") or {})
            fast_statuses = dict(fast_overview.get("statuses") or {})
            full_statuses = dict(full_overview.get("statuses") or {})
            fast_utils = dict(fast_overview.get("utils") or {})
            full_utils = dict(full_overview.get("utils") or {})
            checks = {
                "validity_equal": _valid(fast_overview) == _valid(full_overview),
                "bending_status_equal": fast_statuses.get("bending")
                == full_statuses.get("bending"),
                "shear_status_equal": fast_statuses.get("shear")
                == full_statuses.get("shear"),
                "crack_status_equal": fast_statuses.get("crack")
                == full_statuses.get("crack"),
                "deflection_status_equal": fast_statuses.get("deflection")
                == full_statuses.get("deflection"),
                "bending_util_equal": _close(
                    fast_utils.get("bending"),
                    full_utils.get("bending"),
                ),
                "crack_util_equal": _close(
                    fast_utils.get("crack"),
                    full_utils.get("crack"),
                ),
                "deflection_util_equal": _close(
                    fast_utils.get("deflection"),
                    full_utils.get("deflection"),
                ),
            }
            rows.append(
                {
                    "recipe": recipe,
                    "ordinal": ordinal,
                    "updates": updates,
                    "checks": checks,
                    "passed": all(checks.values()),
                    "fast": {
                        "statuses": fast_statuses,
                        "utils": fast_utils,
                        "valid": _valid(fast_overview),
                    },
                    "full": {
                        "statuses": full_statuses,
                        "utils": full_utils,
                        "valid": _valid(full_overview),
                    },
                }
            )

    payload = {
        "schema": "serviceability_fast_full_screen_equivalence.v1",
        "status": "PASS" if rows and all(row.get("passed") for row in rows) else "FAIL",
        "recipe_count": 10,
        "candidate_count": len(rows),
        "rows": rows,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"serviceability_fast_full_screen_equivalence_{_stamp()}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"serviceability_fast_full_screen_equivalence {payload['status']}")
    print(f"artifact={path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
