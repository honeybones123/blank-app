"""Live impact summary for the same-page Inputs landing flash guard.

Compares the pre-guard readiness/gap artifact with the latest post-guard
browser gap owner artifact. It proves the stale landing shell is no longer in
the largest-gap sample and records the remaining Streamlit status/wrapper gap
for the next slice.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return None, {}
    path = paths[-1]
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return path, {}


def _largest_sample(artifact: dict[str, Any]) -> dict[str, Any]:
    return max(
        list(artifact.get("samples") or []),
        key=lambda row: int(((row.get("gap") or {}).get("px") or -10_000)),
        default={},
    )


def _sample_text(sample: dict[str, Any]) -> str:
    return " ".join(str((row or {}).get("text") or "") for row in sample.get("elements_in_gap") or [])


def _classify(
    readiness_path: Path | None,
    readiness: dict[str, Any],
    implementation_path: Path | None,
    implementation: dict[str, Any],
    latest_gap_path: Path | None,
    latest_gap: dict[str, Any],
) -> dict[str, Any]:
    readiness_cls = dict(readiness.get("classification") or {})
    implementation_cls = dict(implementation.get("classification") or {})
    latest_cls = dict(latest_gap.get("classification") or {})
    latest_sample = _largest_sample(latest_gap)
    text = _sample_text(latest_sample)
    prior_gap = int(readiness_cls.get("largest_gap_px") or 0)
    latest_gap_px = int(latest_cls.get("largest_gap_px") or 0)
    start_shell_present = "Start Your Design" in text
    stable_shell_present = "Inputs page stable rerun shell" in text
    improved_px = prior_gap - latest_gap_px if prior_gap else None
    guard_active = bool(implementation_cls.get("implementation_ok"))
    latest_gap_found = latest_gap_path is not None and latest_cls.get("largest_gap_px") is not None
    status = "PASS" if guard_active and latest_gap_found and not start_shell_present and latest_gap_px < prior_gap else "FAIL"
    if status == "PASS" and latest_gap_px == 0:
        result = "LANDING_FLASH_REMOVED_NO_LARGE_GAP_REPRODUCED"
    elif status == "PASS" and latest_gap_px >= 300:
        result = "LANDING_FLASH_REMOVED_REMAINING_STATUS_WRAPPER_GAP"
    elif status == "PASS":
        result = "LANDING_FLASH_REMOVED_GAP_ACCEPTABLE"
    else:
        result = "LANDING_FLASH_GUARD_NOT_PROVEN"
    return {
        "status": status,
        "result": result,
        "prior_readiness_artifact": str(readiness_path) if readiness_path else None,
        "implementation_artifact": str(implementation_path) if implementation_path else None,
        "latest_gap_artifact": str(latest_gap_path) if latest_gap_path else None,
        "prior_largest_gap_px": prior_gap,
        "latest_largest_gap_px": latest_gap_px,
        "gap_delta_px": improved_px,
        "start_your_design_present_in_largest_gap": start_shell_present,
        "stable_rerun_shell_present_in_largest_gap": stable_shell_present,
        "latest_owner_counts": dict(latest_cls.get("owner_counts_in_largest_gap") or {}),
        "recommended_next_slice": (
            "Profile same-session no-change rerun triggers next."
            if latest_gap_px == 0
            else (
                "Add a focused readiness proof for the remaining status-wrapper/stable-rerun-shell gap, "
                "then apply a narrow stable-height or shell-clear guard if proven safe."
            )
        ),
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    return "\n".join(
        [
            "# Design Guide Same-Page Landing Flash Guard Live Impact Snapshot",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Result: `{cls.get('result')}`",
            f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
            f"- Prior largest gap px: `{cls.get('prior_largest_gap_px')}`",
            f"- Latest largest gap px: `{cls.get('latest_largest_gap_px')}`",
            f"- Gap delta px: `{cls.get('gap_delta_px')}`",
            f"- Start Your Design in largest gap: `{cls.get('start_your_design_present_in_largest_gap')}`",
            f"- Stable rerun shell in largest gap: `{cls.get('stable_rerun_shell_present_in_largest_gap')}`",
            f"- Latest owner counts: `{cls.get('latest_owner_counts')}`",
            "",
            "## Artifacts",
            "",
            f"- Readiness: `{cls.get('prior_readiness_artifact')}`",
            f"- Implementation: `{cls.get('implementation_artifact')}`",
            f"- Latest gap: `{cls.get('latest_gap_artifact')}`",
            "",
            "## Next Safe Slice",
            "",
            str(cls.get("recommended_next_slice") or ""),
            "",
        ]
    )


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_same_page_landing_flash_guard_live_impact_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_same_page_landing_flash_guard_live_impact_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    readiness_path, readiness = _latest("design_guide_same_page_inputs_dispatch_gap_readiness")
    implementation_path, implementation = _latest("design_guide_same_page_landing_flash_guard_implementation")
    latest_gap_path, latest_gap = _latest("design_guide_rerun_status_widget_gap_owner")
    classification = _classify(
        readiness_path,
        readiness,
        implementation_path,
        implementation,
        latest_gap_path,
        latest_gap,
    )
    payload: dict[str, Any] = {
        "schema": "design_guide_same_page_landing_flash_guard_live_impact.v1",
        "created_at": _stamp(),
        "status": classification["status"],
        "classification": classification,
        "product_behaviour_changed": False,
        "behaviour_scope": {
            "layout_changed": True,
            "rendering_changed": False,
            "publication_changed": False,
            "cta_apply_changed": False,
            "family_runtime_changed": False,
            "visible_wording_changed": False,
            "engineering_behaviour_changed": False,
        },
    }
    json_path, md_path = _write(payload)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(json.dumps({"status": payload["status"], **classification}, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
