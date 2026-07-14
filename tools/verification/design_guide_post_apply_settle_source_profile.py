"""Focused browser/live post-Apply settle source profile.

Proof-only. The broad smoothness profile currently reports a large
post-click elapsed value. This verifier isolates that path and classifies
whether the wait is caused by Design Brain recomputation, publication/card
readiness, browser-probe overhead, Streamlit rerun/layout churn, Plotly/model
remounts, or missing/actionless live state.

It does not change product behaviour, engineering logic, publication,
CTA/apply semantics, visible wording, widget keys, or family runtimes.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_browser_live_smoothness_profile import (  # noqa: E402
    DEFAULT_RECIPE,
    _query,
    _run_live_scenario,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _sum_browser_probe_ms(row: dict[str, Any]) -> float:
    total = 0.0
    for section in list(((row.get("counters") or {}).get("speed_profile_last_run_top") or [])):
        if not isinstance(section, dict):
            continue
        if str(section.get("name") or "").startswith("browser_probe."):
            try:
                total += float(section.get("total_ms") or 0.0)
            except Exception:
                pass
    return round(total, 3)


def _top_mutation_owner(row: dict[str, Any]) -> dict[str, Any]:
    totals: dict[str, int] = {}
    labels: dict[str, str] = {}
    for batch in list(((row.get("churn") or {}).get("mutation_recent_batches") or [])):
        for owner in list(batch.get("topOwners") or []):
            key = str(owner.get("owner") or "unknown")
            totals[key] = totals.get(key, 0) + int(owner.get("records") or 0)
            labels.setdefault(key, str(owner.get("label") or "")[:120])
    if not totals:
        return {"owner": None, "records": 0, "label": None}
    owner = max(totals, key=lambda key: totals[key])
    return {"owner": owner, "records": totals[owner], "label": labels.get(owner)}


def _install_post_click_mutation_probe(page) -> None:
    page.evaluate(
        r"""
        () => {
          if (window.__dgPostApplyMutationProbe && window.__dgPostApplyMutationProbe.stop) {
            try { window.__dgPostApplyMutationProbe.stop(); } catch (_err) {}
          }
          const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
          const visible = (el) => {
            if (!el || !el.getBoundingClientRect) return false;
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
          };
          const ownerFor = (target) => {
            const el = target && target.nodeType === 1 ? target : target && target.parentElement;
            if (!el) return {owner: "unknown", label: ""};
            const chain = [];
            let node = el;
            for (let i = 0; node && i < 8; i += 1, node = node.parentElement) {
              chain.push([
                String(node.className || ""),
                node.getAttribute ? String(node.getAttribute("data-testid") || "") : "",
                clean(node.innerText || node.textContent).slice(0, 160)
              ].join(" "));
            }
            const haystack = chain.join(" ");
            if (/summary-check-card|summary-card-stack|Bending\s+[-â€”]\s+ULS|Shear\s+[-â€”]\s+ULS/i.test(haystack)) return {owner: "summary_cards", label: "summary"};
            if (/js-plotly-plot|plotly|svg-container/i.test(haystack)) return {owner: "plotly_or_chart", label: clean(el.innerText || el.textContent).slice(0, 80)};
            if (/inputs_section_2d_diagram_chart|inputs_section_3d_diagram|Model/i.test(haystack)) return {owner: "model_panel", label: "Model"};
            if (/design-guide-proof-pending|design-guide-card|fast-guidance-item|Design Guide|Checking design guidance/i.test(haystack)) return {owner: "design_guide_panel", label: "Design Guide"};
            if (/Batch design|Active set|Active beam|Bulk Beam Manager/i.test(haystack)) return {owner: "batch_design_panel", label: "Batch design"};
            if (/stNumberInput|stTextInput|stSelectbox|stSlider|stCheckbox|button|Stop|Deploy/i.test(haystack)) return {owner: "input_widgets", label: clean(el.innerText || el.textContent).slice(0, 80)};
            if (/stMainBlockContainer|stVerticalBlock|stElementContainer|stLayoutWrapper|stColumn|stMarkdownContainer/i.test(haystack)) return {owner: "streamlit_layout_wrapper", label: clean(el.innerText || el.textContent).slice(0, 80)};
            return {owner: "unknown", label: clean(el.innerText || el.textContent).slice(0, 80)};
          };
          const probe = {
            startedAt: Math.round(performance.now()),
            batches: [],
            ownerTotals: {},
            stop: null
          };
          const observer = new MutationObserver((records) => {
            const owners = {};
            let chartRecords = 0;
            let added = 0;
            let removed = 0;
            let attributes = 0;
            for (const record of records) {
              if (record.type === "attributes") attributes += 1;
              added += record.addedNodes ? record.addedNodes.length : 0;
              removed += record.removedNodes ? record.removedNodes.length : 0;
              const owned = ownerFor(record.target);
              owners[owned.owner] = owners[owned.owner] || {records: 0, label: owned.label};
              owners[owned.owner].records += 1;
              probe.ownerTotals[owned.owner] = (probe.ownerTotals[owned.owner] || 0) + 1;
              if (owned.owner === "plotly_or_chart") chartRecords += 1;
            }
            probe.batches.push({
              at: Math.round(performance.now()),
              records: records.length,
              added,
              removed,
              attributes,
              chartRecords,
              owners: Object.entries(owners).map(([owner, row]) => ({owner, records: row.records, label: row.label}))
                .sort((a, b) => b.records - a.records)
                .slice(0, 8)
            });
            if (probe.batches.length > 80) {
              probe.batches = probe.batches.slice(-80);
            }
          });
          observer.observe(document.body, {subtree: true, childList: true, attributes: true});
          probe.stop = () => observer.disconnect();
          window.__dgPostApplyMutationProbe = probe;
        }
        """
    )


def _read_post_click_mutation_probe(page) -> dict[str, Any]:
    try:
        return dict(
            page.evaluate(
                r"""
                () => {
                  const probe = window.__dgPostApplyMutationProbe || {};
                  if (probe.stop) {
                    try { probe.stop(); } catch (_err) {}
                  }
                  return {
                    startedAt: probe.startedAt || null,
                    batches: Array.from(probe.batches || []),
                    ownerTotals: Object.assign({}, probe.ownerTotals || {})
                  };
                }
                """
            )
            or {}
        )
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _milestone_ms(row: dict[str, Any], name: str) -> int | None:
    value = ((row.get("milestones") or {}).get(name) or {}).get("elapsed_ms")
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _classify(initial: dict[str, Any], post: dict[str, Any], post_click_mutations: dict[str, Any]) -> dict[str, Any]:
    post_elapsed = int(post.get("elapsed_ms") or 0)
    browser_probe_ms = _sum_browser_probe_ms(post)
    candidate = dict(((post.get("counters") or {}).get("candidate_evaluation") or {}))
    product_candidate_ms = max(0.0, float(candidate.get("total_ms") or 0.0) - browser_probe_ms)
    mutation_owner = _top_mutation_owner(post)
    final_pub_ms = _milestone_ms(post, "final_design_guide_publication")
    card_model_ms = _milestone_ms(post, "card_render_model")
    rendered_card_ms = _milestone_ms(post, "rendered_design_guide_card")
    shell_ms = _milestone_ms(post, "design_guide_shell")
    layout_shift = float(((post.get("layout") or {}).get("layout_shift_total") or 0.0))
    mutation_count = int(((post.get("churn") or {}).get("mutation_count_total") or 0))
    focused_owner_totals = dict(post_click_mutations.get("ownerTotals") or {})
    focused_total = sum(int(value or 0) for value in focused_owner_totals.values())
    focused_top_owner = None
    if focused_owner_totals:
        focused_top_owner = max(focused_owner_totals, key=lambda key: int(focused_owner_totals[key] or 0))
    focused_owner_labels: dict[str, list[str]] = {}
    for batch in list(post_click_mutations.get("batches") or []):
        for owner in list(batch.get("owners") or []):
            key = str(owner.get("owner") or "unknown")
            label = str(owner.get("label") or "")[:120]
            if label and label not in focused_owner_labels.get(key, []):
                focused_owner_labels.setdefault(key, []).append(label)
    focused_top_owner_labels = focused_owner_labels.get(str(focused_top_owner), [])
    focused_top_is_design_guide_wrapper = (
        focused_top_owner == "streamlit_layout_wrapper"
        and any("Design Guide" in label for label in focused_top_owner_labels)
    )
    plotly_records = 0
    for batch in list(((post.get("churn") or {}).get("mutation_recent_batches") or [])):
        plotly_records += int(batch.get("chartInternalRecords") or 0)
    click_meta = dict(post.get("click_meta") or {})
    risks: list[str] = []
    if not click_meta.get("clicked"):
        risks.append("post_apply_action_not_clicked")
    if rendered_card_ms is None:
        risks.append("rendered_card_not_ready")
    if final_pub_ms is None:
        risks.append("final_publication_not_ready")
    if browser_probe_ms >= 1000:
        risks.append("browser_probe_dominates_post_apply_measurement")
    if product_candidate_ms >= 500:
        risks.append("product_candidate_evaluation_after_apply")
    if plotly_records >= 500:
        risks.append("plotly_model_remount_after_apply")
    if mutation_count >= 2500:
        risks.append("large_dom_mutation_after_apply")
    if focused_total >= 300:
        risks.append("focused_post_click_mutation_churn")
    if layout_shift >= 0.15:
        risks.append("post_apply_layout_shift")

    if "post_apply_action_not_clicked" in risks:
        decision = "POST_APPLY_UNAVAILABLE"
        next_slice = "Run a recipe with a visible executable Design Guide action before profiling post-Apply smoothness."
    elif "browser_probe_dominates_post_apply_measurement" in risks and product_candidate_ms < 100:
        decision = "POST_APPLY_PROFILE_DOMINATED_BY_BROWSER_PROBE"
        next_slice = "Do not optimize product candidate search from this result; profile browser probe cost separately."
    elif focused_top_owner in {"model_panel", "plotly_or_chart"}:
        decision = "POST_APPLY_MODEL_OR_CHART_MUTATION_HOTSPOT"
        next_slice = "Run model/diagram post-Apply render reuse readiness keyed by model fingerprint; implement reuse only if stale/changed/debug/post-click guards prove safe."
    elif focused_top_owner == "design_guide_panel" or focused_top_is_design_guide_wrapper:
        decision = "POST_APPLY_DESIGN_GUIDE_WRAPPER_MUTATION_HOTSPOT"
        next_slice = "Inspect Design Guide post-click wrapper/container remount before adding model or card reuse."
    elif "plotly_model_remount_after_apply" in risks:
        decision = "POST_APPLY_MODEL_PLOTLY_REMOUNT_HOTSPOT"
        next_slice = "Run model/diagram post-Apply render reuse readiness keyed by model fingerprint; implement reuse only if stale/changed/debug/post-click guards prove safe."
    elif "large_dom_mutation_after_apply" in risks or "post_apply_layout_shift" in risks:
        decision = "POST_APPLY_STREAMLIT_LAYOUT_CHURN_HOTSPOT"
        next_slice = "Attribute post-Apply DOM mutations to exact panels before CSS/cache changes."
    elif rendered_card_ms is not None and rendered_card_ms <= 1500 and product_candidate_ms < 100:
        decision = "POST_APPLY_PRODUCT_SETTLE_BOUNDED"
        next_slice = "Do not add post-Apply bypass; return to residual first-paint/layout source-node work."
    else:
        decision = "POST_APPLY_SOURCE_UNCLEAR"
        next_slice = "Capture more detailed post-Apply trace events before implementing reuse."

    return {
        "status": "PASS",
        "decision": decision,
        "risks": risks,
        "post_apply_elapsed_ms": post_elapsed,
        "post_apply_milestones_ms": {
            "design_guide_shell": shell_ms,
            "final_publication": final_pub_ms,
            "card_render_model": card_model_ms,
            "rendered_card": rendered_card_ms,
        },
        "browser_probe_ms": browser_probe_ms,
        "candidate_total_ms": float(candidate.get("total_ms") or 0.0),
        "candidate_product_ms_estimate": round(product_candidate_ms, 3),
        "candidate_count": int(candidate.get("count") or 0),
        "layout_shift_total": round(layout_shift, 6),
        "mutation_count_total": mutation_count,
        "plotly_chart_internal_records_tail": plotly_records,
        "top_mutation_owner": mutation_owner,
        "focused_post_click_mutation_total": focused_total,
        "focused_post_click_owner_totals": focused_owner_totals,
        "focused_post_click_top_owner": focused_top_owner,
        "focused_post_click_top_owner_labels": focused_top_owner_labels,
        "focused_post_click_top_is_design_guide_wrapper": focused_top_is_design_guide_wrapper,
        "focused_post_click_batches_tail": list(post_click_mutations.get("batches") or [])[-12:],
        "click_meta": click_meta,
        "initial_snapshot_hash": initial.get("snapshot_hash"),
        "post_apply_snapshot_hash": post.get("snapshot_hash"),
        "recommended_next_slice": next_slice,
    }


def _capture(base_url: str, *, recipe: str, timeout_s: float, headed: bool) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.set_default_timeout(30_000)
        initial = _run_live_scenario(
            page,
            scenario_id="initial_recipe_load",
            action="goto",
            base_url=base_url,
            recipe=recipe,
            timeout_s=timeout_s,
        )
        _install_post_click_mutation_probe(page)
        try:
            post = _run_live_scenario(
                page,
                scenario_id="post_click_apply",
                action="click_apply",
                base_url=base_url,
                recipe=recipe,
                timeout_s=timeout_s,
            )
        except PlaywrightTimeoutError as exc:
            post = {
                "scenario_id": "post_click_apply",
                "action": "click_apply",
                "elapsed_ms": None,
                "click_meta": {"clicked": False, "error": str(exc)},
                "milestones": {},
                "counters": {},
                "layout": {},
                "churn": {},
            }
        post_click_mutations = _read_post_click_mutation_probe(page)
        browser.close()
    return {"recipe": recipe, "initial": initial, "post_apply": post, "post_click_mutations": post_click_mutations}


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_post_apply_settle_source_profile_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_post_apply_settle_source_profile_{stamp}.md"
    summary = dict(payload.get("summary") or {})
    lines = [
        "# Design Guide Post-Apply Settle Source Profile",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{summary.get('decision')}`",
        f"- Recipe: `{payload.get('recipe')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Risks: `{', '.join(summary.get('risks') or []) or '-'}`",
        "",
        "## Post-Apply Metrics",
        "",
        f"- Elapsed: `{summary.get('post_apply_elapsed_ms')}` ms",
        f"- Milestones: `{summary.get('post_apply_milestones_ms')}`",
        f"- Browser probe ms: `{summary.get('browser_probe_ms')}`",
        f"- Candidate product ms estimate: `{summary.get('candidate_product_ms_estimate')}`",
        f"- Mutation count: `{summary.get('mutation_count_total')}`",
        f"- Plotly chart records tail: `{summary.get('plotly_chart_internal_records_tail')}`",
        f"- Top mutation owner: `{summary.get('top_mutation_owner')}`",
        "",
        "## Recommendation",
        "",
        str(summary.get("recommended_next_slice") or ""),
        "",
    ]
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8685)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_POST_APPLY_PROFILE_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--timeout-s", type=float, default=45.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://127.0.0.1:{args.port}")
    created_at = _stamp()
    try:
        if not args.base_url:
            env_before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            os.environ["PERF_TRACE_INPUTS"] = "1"
            try:
                process = _start_streamlit(args.port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)
            _wait_for_http(base_url, timeout_s=70.0)
        capture = _capture(
            base_url,
            recipe=str(args.recipe),
            timeout_s=float(args.timeout_s),
            headed=bool(args.headed),
        )
        summary = _classify(
            dict(capture.get("initial") or {}),
            dict(capture.get("post_apply") or {}),
            dict(capture.get("post_click_mutations") or {}),
        )
        payload = {
            "schema": "design_guide_post_apply_settle_source_profile.v1",
            "created_at": created_at,
            "status": summary["status"],
            "product_behaviour_changed": False,
            "base_url": base_url,
            "recipe": args.recipe,
            "summary": summary,
            **capture,
        }
        json_path, md_path = _write(payload)
        print(f"wrote {json_path}")
        print(f"wrote {md_path}")
        print(json.dumps({"status": payload["status"], "decision": summary.get("decision")}, indent=2))
        return 0
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
