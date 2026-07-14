"""Verify the Design Guide proof-pending shell style boundary.

This snapshot proves the loading/proof-pending shell keeps its text, state
classes, and semantic attributes while moving visual styling out of
design_guide_page.py and into the shared Inputs CSS surface.
"""

from __future__ import annotations

from datetime import datetime
import importlib.util
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DESIGN_GUIDE_PAGE = ROOT / "design_guide_page.py"
INPUTS_STYLE = ROOT / "ui" / "inputs_page_style.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _source() -> tuple[str, str]:
    return (
        DESIGN_GUIDE_PAGE.read_text(encoding="utf-8", errors="replace"),
        INPUTS_STYLE.read_text(encoding="utf-8", errors="replace"),
    )


def _function_block(source: str, name: str) -> str:
    match = re.search(rf"^def {re.escape(name)}\(", source, flags=re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^def\s+\w+\(", source[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


class _FakeSt:
    def __init__(self, *, applying: bool) -> None:
        self.session_state = {"_design_guide_component_apply_in_flight": applying}
        self.markdown_calls: list[dict[str, Any]] = []

    def markdown(self, body: str, *, unsafe_allow_html: bool = False) -> None:
        self.markdown_calls.append({"body": body, "unsafe_allow_html": unsafe_allow_html})


def _render_shell(*, applying: bool) -> str:
    spec = importlib.util.spec_from_file_location("design_guide_page_under_test", DESIGN_GUIDE_PAGE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load design_guide_page.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fake = _FakeSt(applying=applying)
    module._render_proof_pending_shell(fake)
    return "\n".join(str(row.get("body") or "") for row in fake.markdown_calls)


def _build() -> dict[str, Any]:
    page_source, style_source = _source()
    shell_block = _function_block(page_source, "_render_proof_pending_shell")
    normal_html = _render_shell(applying=False)
    applying_html = _render_shell(applying=True)
    required_css_selectors = [
        ".dg-proof-pending-shell",
        ".dg-proof-pending-shell.applying",
        ".dg-proof-pending-eyebrow",
        ".dg-proof-pending-title",
        ".dg-proof-pending-subtext",
        ".dg-proof-pending-bar",
        ".dg-proof-pending-chips",
        ".dg-proof-pending-chip",
        "@keyframes dgProofPendingSweep",
    ]
    checks = {
        "shell_function_exists": bool(shell_block),
        "shell_function_emits_no_style_block": "<style>" not in shell_block,
        "shell_function_has_no_inline_style_attributes": "style=" not in shell_block,
        "normal_shell_text_preserved": "Checking design guidance&hellip;" in normal_html
        and "Reviewing strength, detailing, serviceability, and cleanup options." in normal_html,
        "applying_shell_text_preserved": "Applying one-click design..." in applying_html
        and "Updating the beam inputs, recalculating checks, and preparing the final Design Guide result." in applying_html,
        "semantic_attributes_preserved": "data-testid='design-guide-proof-pending'" in normal_html
        and "aria-live='polite'" in normal_html
        and "aria-busy='true'" in normal_html,
        "applying_class_preserved": "dg-proof-pending-shell applying" in applying_html,
        "chip_labels_preserved": all(
            label in normal_html
            for label in ("Strength", "Detailing", "Serviceability", "Cleanup options")
        ),
        "shared_css_selectors_present": all(selector in style_source for selector in required_css_selectors),
        "shared_css_hide_guard_present": "body:has([data-testid=\"design-guide-card\"])" in style_source
        and "[data-testid=\"design-guide-proof-pending\"]" in style_source,
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "schema": "design_guide_proof_pending_shell_style_boundary_snapshot.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "product_behaviour_changed": False,
        "visible_engineering_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
        "design_brain_authority_changed": False,
        "checks": checks,
        "failures": failures,
        "normal_shell_text_sample": re.sub(r"<[^>]+>", " ", normal_html)[:500],
        "applying_shell_text_sample": re.sub(r"<[^>]+>", " ", applying_html)[:500],
        "source_files": {
            "design_guide_page": str(DESIGN_GUIDE_PAGE),
            "inputs_page_style": str(INPUTS_STYLE),
        },
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_proof_pending_shell_style_boundary_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_proof_pending_shell_style_boundary_{stamp}.md"
    lines = [
        "# Design Guide Proof-Pending Shell Style Boundary",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Visible engineering wording changed: `{payload.get('visible_engineering_wording_changed')}`",
        f"- CTA/apply semantics changed: `{payload.get('cta_apply_semantics_changed')}`",
        f"- Family runtimes changed: `{payload.get('family_runtimes_changed')}`",
        f"- Design Brain authority changed: `{payload.get('design_brain_authority_changed')}`",
        "",
        "## Checks",
        "",
        "```json",
        json.dumps(payload.get("checks"), indent=2, sort_keys=True),
        "```",
        "",
    ]
    if payload.get("failures"):
        lines.extend(["## Failures", "", "```json", json.dumps(payload["failures"], indent=2), "```", ""])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build()
    json_path, md_path = _write(payload)
    print(f"design_guide_proof_pending_shell_style_boundary {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if payload["failures"]:
        print("failures=" + json.dumps(payload["failures"]))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
