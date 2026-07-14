from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _css_block(source: str, selector: str) -> str:
    start = source.find(selector)
    if start == -1:
        return ""
    brace = source.find("{", start)
    if brace == -1:
        return ""
    depth = 0
    for idx in range(brace, len(source)):
        char = source[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : idx + 1]
    return ""


def _css_exact_block(source: str, selector: str) -> str:
    return _css_block(source, f"\n        {selector}")


def _latest(prefix: str) -> str | None:
    paths = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return str(paths[0]) if paths else None


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    style_path = ROOT / "ui" / "inputs_page_style.py"
    style = style_path.read_text(encoding="utf-8")
    shell_block = _css_exact_block(style, ".dg-proof-pending-shell")
    card_block = _css_exact_block(style, ".fast-guidance-item:not(.secondary),")
    legacy_card_block = _css_exact_block(style, ".dg-card")

    checks = {
        "proof_pending_shell_reserves_height": "min-height: 10.5rem" in shell_block,
        "final_card_reserves_matching_height": "min-height: 10.5rem" in card_block,
        "final_card_uses_border_box": "box-sizing: border-box" in card_block,
        "legacy_card_selector_still_present": ".dg-card" in legacy_card_block,
        "no_cta_or_apply_logic_in_style": "apply_payload" not in card_block.lower()
        and "button_contract" not in card_block.lower()
        and "family_runtime" not in card_block.lower(),
    }
    failures = [name for name, ok in checks.items() if not ok]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_card_shell_stable_height_snapshot.v1",
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
        "status": status,
        "product_behaviour_changed": False,
        "style_file": str(style_path),
        "checks": checks,
        "height_contract": {
            "proof_pending_shell_min_height": "10.5rem",
            "final_card_min_height": "10.5rem",
            "purpose": "prevent proof-pending shell to final-card vertical collapse",
        },
        "latest_supporting_artifacts": {
            "browser_live_smoothness_profile": _latest("design_guide_browser_live_smoothness_profile"),
            "first_paint_placeholder_height_readiness": _latest(
                "design_guide_first_paint_placeholder_height_readiness"
            ),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        },
        "failures": failures,
    }
    stamp = payload["created_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_card_shell_stable_height_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_card_shell_stable_height_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide Card/Shell Stable Height Snapshot",
                "",
                f"Status: **{status}**",
                "",
                "The final Design Guide card now reserves the same minimum height as the proof-pending shell.",
                "This is a visual stability guard only; it does not own CTA, apply routing, publication truth, or family decisions.",
                "",
                "## Checks",
                "",
                *(f"- {key}: `{value}`" for key, value in checks.items()),
                "",
                "## Failures",
                "",
                *(f"- {failure}" for failure in failures),
            ]
        ),
        encoding="utf-8",
    )
    print(f"design_guide_card_shell_stable_height_snapshot {status}")
    print(json_path)
    print(md_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
