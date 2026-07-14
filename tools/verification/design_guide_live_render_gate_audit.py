"""Browser/live Design Guide render-gate audit.

Audit-only. This script identifies the gate that decides whether the real
Design Guide section is created after Batch design, then joins that static map
with live browser evidence from the running Inputs page. It does not change
family runtimes, contracts, CTA/publication/apply semantics, visible wording, or
final publication authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_URL = "http://localhost:8504/?page=inputs&browser_recipe=R1A_M300_V0"


STATIC_PATTERNS: dict[str, str] = {
    "actions_or_loads_predicate": r"def inputs_has_design_actions_or_loads\(",
    "page_level_design_guide_gate": r"show_design_guide_for_current_inputs\s*=\s*bool\(",
    "design_guide_slot_default": r"design_guide_slot\s*=\s*None",
    "design_guide_slot_created": r"design_guide_slot\s*=\s*st\.empty\(\)",
    "pre_widget_placeholder": r"design_guide_page\.render_pre_widget_placeholder\(st, design_guide_slot\)",
    "fresh_panel_skip_gate": r"if not show_design_guide_for_current_inputs or design_guide_slot is None:",
    "fresh_panel_skip_marker": r"_mark\(\"render_design_guide_skipped\"\)",
    "fresh_panel_called": r"_render_fresh_design_guide_panel\(\)",
    "real_panel_heading": r"st\.markdown\(\"### Design Guide\"\)",
    "render_final_panel_call": r"design_guide_page\.render_final_panel\(",
    "settle_gate_waiting_shell": r"_render_design_guide_settle_waiting_shell\(settle_gate_decision\)",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _datetime_stamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _wait_for_live_url(url: str, *, timeout_s: float = 30.0) -> None:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}/"
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urlopen(base) as response:  # noqa: S310 - local verifier only
                if 200 <= int(response.status) < 500:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.4)
    raise RuntimeError(f"Timed out waiting for live app at {base}: {last_error}")


def _line_map(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    out: dict[str, Any] = {}
    for key, pattern in STATIC_PATTERNS.items():
        compiled = re.compile(pattern)
        match_line: int | None = None
        for idx, line in enumerate(lines, start=1):
            if compiled.search(line):
                match_line = idx
                break
        snippet = []
        if match_line is not None:
            start = max(1, match_line - 4)
            end = min(len(lines), match_line + 6)
            snippet = [
                {"line": line_no, "text": lines[line_no - 1]}
                for line_no in range(start, end + 1)
            ]
        out[key] = {
            "found": match_line is not None,
            "line": match_line,
            "pattern": pattern,
            "snippet": snippet,
        }
    return out


def _capture_live(page, *, url: str) -> dict[str, Any]:
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_timeout(1200)
    snapshots: list[dict[str, Any]] = []
    scrolls: list[dict[str, Any]] = []
    for index in range(7):
        snapshots.append(_dom_snapshot(page, label=f"step_{index}"))
        if snapshots[-1]["product_design_guide_heading_count"] or snapshots[-1]["design_guide_card_candidate_count"]:
            break
        scrolls.append(_scroll_app_container(page, index=index))
        page.wait_for_timeout(650)
    return {
        "url": page.url,
        "snapshots": snapshots,
        "scrolls": scrolls,
        "live_hash": _stable_hash({"snapshots": snapshots, "scrolls": scrolls}),
    }


def _dom_snapshot(page, *, label: str) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            (label) => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const bodyText = String(document.body && document.body.innerText || "");
              const all = Array.from(document.querySelectorAll("body *"));
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
              };
              const rectPayload = (el) => {
                const rect = el.getBoundingClientRect();
                return {
                  top: Math.round(rect.top),
                  bottom: Math.round(rect.bottom),
                  width: Math.round(rect.width),
                  height: Math.round(rect.height)
                };
              };
              const elementPayload = (el) => ({
                tag: String(el.tagName || "").toLowerCase(),
                text: clean(el.innerText || el.textContent).slice(0, 260),
                testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                cls: String(el.className || "").slice(0, 140),
                visible: visible(el),
                rect: rectPayload(el)
              });
              const productDesignGuideHeadings = all.filter((el) => {
                const text = clean(el.innerText || el.textContent);
                if (text !== "Design Guide") return false;
                const parentText = clean(el.parentElement ? el.parentElement.innerText || el.parentElement.textContent : "");
                return !/Design Guide Debug|Debug session state/i.test(parentText.slice(0, 280));
              });
              const designGuideDebugMatches = all.filter((el) => /Design Guide Debug|Debug session state/i.test(clean(el.innerText || el.textContent))).slice(0, 20);
              const cardCandidates = all.filter((el) => {
                const text = clean(el.innerText || el.textContent);
                const meta = `${el.getAttribute ? el.getAttribute("data-testid") || "" : ""} ${String(el.className || "")}`;
                return /design-guide|fast-guidance|final-publication/i.test(meta)
                  || /Run one-click auto design|Apply recommendation|Design is efficient|Strengthening required|Design Guide family contract|repair is blocked|cleanup required/i.test(text);
              }).slice(0, 40);
              const summaryCandidates = all.filter((el) => {
                const text = clean(el.innerText || el.textContent);
                return /Bending.*ULS|Shear.*ULS|summary-card-stack|Utilisation|Capacity/i.test(text);
              }).slice(0, 40);
              const gateText = {
                hasPreparingCurrentSummary: /Preparing current summary/i.test(bodyText),
                hasStartYourDesign: /Start Your Design/i.test(bodyText),
                hasInputsStableRerunShell: /Inputs page stable rerun shell/i.test(bodyText),
                hasBatchDesign: /Batch design/i.test(bodyText),
                hasDesignMode: /Design mode/i.test(bodyText),
                hasDesignActions: /Design Actions/i.test(bodyText)
              };
              const designActionValue = (label) => {
                const idx = bodyText.indexOf(label);
                if (idx < 0) return null;
                return bodyText.slice(idx, idx + 120).split(/\r?\n/).map((line) => line.trim()).filter(Boolean).slice(0, 8);
              };
              const actionEvidence = {
                mu: designActionValue("Positive design moment"),
                vu: designActionValue("Design shear"),
                tu: designActionValue("Design torsion"),
                axial: designActionValue("Axial force")
              };
              const scrollables = Array.from(document.querySelectorAll("body, body *")).filter((el) => {
                if (!el || !el.getBoundingClientRect) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return (el.scrollHeight || 0) > (el.clientHeight || 0) + 8
                  && (/(auto|scroll|overlay)/i.test(String(style.overflowY || style.overflow || "")) || rect.height >= window.innerHeight * 0.45);
              }).map((el) => ({
                tag: String(el.tagName || "").toLowerCase(),
                testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                cls: String(el.className || "").slice(0, 140),
                scrollTop: Math.round(el.scrollTop || 0),
                scrollHeight: Math.round(el.scrollHeight || 0),
                clientHeight: Math.round(el.clientHeight || 0),
                text: clean(el.innerText || el.textContent).slice(0, 180)
              })).sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight)).slice(0, 10);
              return {
                label,
                body_text_hash_seed: bodyText.slice(0, 3600),
                body_text_length: bodyText.length,
                gate_text: gateText,
                action_evidence: actionEvidence,
                product_design_guide_heading_count: productDesignGuideHeadings.length,
                product_design_guide_headings: productDesignGuideHeadings.slice(0, 10).map(elementPayload),
                design_guide_debug_match_count: designGuideDebugMatches.length,
                design_guide_debug_matches: designGuideDebugMatches.slice(0, 8).map(elementPayload),
                design_guide_card_candidate_count: cardCandidates.length,
                design_guide_card_candidates: cardCandidates.slice(0, 12).map(elementPayload),
                summary_candidate_count: summaryCandidates.length,
                summary_candidates: summaryCandidates.slice(0, 12).map(elementPayload),
                scrollables
              };
            }
            """,
            label,
        )
    )


def _scroll_app_container(page, *, index: int) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            (index) => {
              const candidates = Array.from(document.querySelectorAll("body, body *")).filter((el) => {
                if (!el || !el.getBoundingClientRect) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return (el.scrollHeight || 0) > (el.clientHeight || 0) + 8
                  && (/(auto|scroll|overlay)/i.test(String(style.overflowY || style.overflow || "")) || rect.height >= window.innerHeight * 0.45);
              }).sort((a, b) => {
                return ((b.scrollHeight || 0) - (b.clientHeight || 0)) - ((a.scrollHeight || 0) - (a.clientHeight || 0));
              });
              const target = candidates[0] || document.scrollingElement || document.documentElement;
              const before = {
                scrollTop: Math.round(target.scrollTop || 0),
                scrollHeight: Math.round(target.scrollHeight || 0),
                clientHeight: Math.round(target.clientHeight || 0)
              };
              const next = Math.min(before.scrollHeight, before.scrollTop + Math.max(420, Math.round(window.innerHeight * 0.75)));
              target.scrollTop = next;
              const after = {
                scrollTop: Math.round(target.scrollTop || 0),
                scrollHeight: Math.round(target.scrollHeight || 0),
                clientHeight: Math.round(target.clientHeight || 0)
              };
              return {
                index,
                before,
                after,
                moved: before.scrollTop !== after.scrollTop,
                reached_bottom: after.scrollTop + after.clientHeight >= after.scrollHeight - 8,
                target: {
                  tag: String(target.tagName || "").toLowerCase(),
                  testid: target.getAttribute ? target.getAttribute("data-testid") : null,
                  cls: String(target.className || "").slice(0, 140)
                },
                candidate_count: candidates.length
              };
            }
            """,
            index,
        )
    )


def _classify(static_map: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    snapshots = list(live.get("snapshots") or [])
    any_summary = any(snap.get("summary_candidate_count") for snap in snapshots)
    any_real_dg = any(
        snap.get("product_design_guide_heading_count") or snap.get("design_guide_card_candidate_count")
        for snap in snapshots
    )
    any_debug_dg = any(snap.get("design_guide_debug_match_count") for snap in snapshots)
    any_start_your_design = any((snap.get("gate_text") or {}).get("hasStartYourDesign") for snap in snapshots)
    any_stable_shell = any((snap.get("gate_text") or {}).get("hasInputsStableRerunShell") for snap in snapshots)
    action_evidence_rows = [
        snap.get("action_evidence") or {}
        for snap in snapshots
        if (snap.get("gate_text") or {}).get("hasDesignActions")
    ]
    action_text = _stable_json(action_evidence_rows)
    visible_zero_actions = bool(action_evidence_rows and not re.search(r"\b[1-9][0-9]*(?:\.[0-9]+)?\b", action_text))
    page_gate_present = all(
        static_map.get(key, {}).get("found")
        for key in (
            "page_level_design_guide_gate",
            "design_guide_slot_created",
            "fresh_panel_skip_gate",
            "real_panel_heading",
        )
    )

    if any_real_dg:
        diagnosis = "real_design_guide_rendered_live"
    elif page_gate_present and (visible_zero_actions or any_start_your_design or any_stable_shell):
        diagnosis = "page_level_actions_or_loads_gate_prevents_design_guide_slot"
    elif page_gate_present:
        diagnosis = "design_guide_slot_not_created_or_panel_skipped"
    else:
        diagnosis = "render_gate_static_map_incomplete"

    blockers: list[str] = []
    if not any_summary:
        blockers.append("summary_not_visible_during_live_probe")
    if not any_real_dg:
        blockers.append("real_design_guide_not_created_in_live_dom")
    if any_debug_dg:
        blockers.append("debug_design_guide_heading_present")
    if visible_zero_actions:
        blockers.append("visible_design_actions_are_zero_or_not_applied")
    if any_start_your_design:
        blockers.append("landing_start_your_design_gate_visible")
    if any_stable_shell:
        blockers.append("inputs_stable_rerun_shell_visible")

    return {
        "diagnosis": diagnosis,
        "page_gate_present": page_gate_present,
        "summary_visible_during_probe": bool(any_summary),
        "real_design_guide_created": bool(any_real_dg),
        "debug_design_guide_heading_present": bool(any_debug_dg),
        "visible_zero_actions": visible_zero_actions,
        "start_your_design_visible": bool(any_start_your_design),
        "stable_rerun_shell_visible": bool(any_stable_shell),
        "blockers": blockers,
        "next_recommendation": _recommendation(diagnosis, blockers),
    }


def _recommendation(diagnosis: str, blockers: list[str]) -> str:
    if diagnosis == "page_level_actions_or_loads_gate_prevents_design_guide_slot":
        return (
            "Next slice should prove whether GEOMETRY_DETAILING_GOVERNS invalid-input repair should bypass "
            "the actions/load gate, or whether the live browser recipe/application state is failing to apply actions."
        )
    if diagnosis == "design_guide_slot_not_created_or_panel_skipped":
        return (
            "Next slice should instrument the page-level Design Guide render gate values "
            "show_design_guide_for_current_inputs and design_guide_slot creation as trace-only evidence."
        )
    if diagnosis == "real_design_guide_rendered_live":
        return "The product card exists; update the visual consistency verifier selector rather than changing render logic."
    return "First fix the static render-gate map before deciding a live render change."


def _markdown(payload: dict[str, Any]) -> str:
    cls = payload.get("classification") or {}
    lines = [
        "# Design Guide Live Render Gate Audit",
        "",
        f"- Result: `{payload.get('status')}`",
        f"- Created: `{payload.get('created_at')}`",
        f"- URL: `{payload.get('url')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Diagnosis",
        "",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Page gate present: `{cls.get('page_gate_present')}`",
        f"- Summary visible during probe: `{cls.get('summary_visible_during_probe')}`",
        f"- Real Design Guide created: `{cls.get('real_design_guide_created')}`",
        f"- Visible zero actions: `{cls.get('visible_zero_actions')}`",
        f"- Start Your Design visible: `{cls.get('start_your_design_visible')}`",
        f"- Stable rerun shell visible: `{cls.get('stable_rerun_shell_visible')}`",
        "",
        "## Blockers",
        "",
    ]
    lines.extend([f"- `{item}`" for item in cls.get("blockers") or []] or ["- None"])
    lines.extend(["", "## Static Render Gate Map", ""])
    for key, row in (payload.get("static_render_gate_map") or {}).items():
        lines.append(f"- `{key}`: found `{row.get('found')}`, line `{row.get('line')}`")
    lines.extend(["", "## Live Snapshots", ""])
    for snap in (payload.get("live_probe") or {}).get("snapshots", [])[:12]:
        gate = snap.get("gate_text") or {}
        lines.append(
            f"- `{snap.get('label')}`: summary `{snap.get('summary_candidate_count')}`, "
            f"real DG headings `{snap.get('product_design_guide_heading_count')}`, "
            f"card candidates `{snap.get('design_guide_card_candidate_count')}`, "
            f"Start Your Design `{gate.get('hasStartYourDesign')}`, stable shell `{gate.get('hasInputsStableRerunShell')}`"
        )
    lines.extend(["", "## Recommendation", ""])
    lines.append(str(cls.get("next_recommendation") or "No recommendation recorded."))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _datetime_stamp()
    static_map = _line_map(INPUTS_PAGE)
    errors: list[str] = []
    live: dict[str, Any] = {}
    try:
        _wait_for_live_url(args.url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context = browser.new_context(viewport={"width": 1600, "height": 1100})
            page = context.new_page()
            page.set_default_timeout(25_000)
            live = _capture_live(page, url=args.url)
            context.close()
            browser.close()
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")

    classification = _classify(static_map, live) if live else {
        "diagnosis": "live_probe_failed",
        "blockers": list(errors),
        "next_recommendation": "Repair the live browser probe before changing render gates.",
    }
    status = "PASS" if not errors and bool(live) else "FAIL"
    payload = {
        "schema": "design_guide_live_render_gate_audit.v1",
        "status": status,
        "created_at": stamp,
        "url": args.url,
        "product_behaviour_changed": False,
        "family_runtimes_changed": False,
        "contracts_changed": False,
        "cta_publication_apply_semantics_changed": False,
        "visible_wording_changed": False,
        "final_publication_authority_changed": False,
        "static_render_gate_map": static_map,
        "live_probe": live,
        "classification": classification,
        "errors": errors,
        "audit_hash": _stable_hash({"static": static_map, "live": live, "classification": classification, "errors": errors}),
    }
    json_path = ARTIFACT_DIR / f"design_guide_live_render_gate_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_render_gate_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_live_render_gate_audit {status}")
    print(f"diagnosis={classification.get('diagnosis')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if errors:
        print("errors=" + json.dumps(errors))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
