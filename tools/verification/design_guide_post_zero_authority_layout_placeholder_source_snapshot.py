"""Post-zero-authority layout/placeholder source snapshot.

Proof-only. Measures visible gaps, layout shift, scroll behaviour, and DOM
mutation attribution around the Inputs heading, summary cards, model/diagram
panel, Batch design, and Design Guide after Design Brain zero-authority
extraction. This script does not change layout, caching, publication, CTA/apply,
family runtimes, wording, or engineering behaviour.
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

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_browser_live_layout_stability_snapshot import (  # noqa: E402
    _install_layout_probe,
    _layout_snapshot,
    _scroll_probe,
    _stable_hash,
)
from tools.verification.helpers.browser_helpers import _page_cycle_churn_snapshot  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _query,
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_RECIPE = "R1A_M300_V0"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest_payload(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda item: item.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "path": str(path), "status": payload.get("status"), "payload": payload}


def _take_sample(page, *, label: str) -> dict[str, Any]:
    layout = _layout_snapshot(page, label=label)
    try:
        churn = _page_cycle_churn_snapshot(page, slug="inputs", detail=True)
    except Exception as exc:
        churn = {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "label": label,
        "layout": layout,
        "churn": {
            "mutation_count_total": churn.get("mutation_count_total"),
            "last_mutation_batch_size": churn.get("last_mutation_batch_size"),
            "mutation_recent_batches": list(churn.get("mutation_recent_batches") or [])[-8:],
            "mutation_top_attribution": list(churn.get("mutation_top_attribution") or [])[:15],
            "chart_internal_mutation_count": churn.get("chart_internal_mutation_count"),
            "non_chart_mutation_count": churn.get("non_chart_mutation_count"),
            "dom_node_count": churn.get("dom_node_count"),
            "streamlit_block_count": churn.get("streamlit_block_count"),
            "error": churn.get("error"),
        },
    }


def _capture_sequence(page, *, base_url: str, recipe: str, timeout_s: float) -> dict[str, Any]:
    url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    try:
        _page_cycle_churn_snapshot(page, slug="inputs", detail=True)
    except Exception:
        pass

    samples: list[dict[str, Any]] = []
    for label, wait_ms in (
        ("initial_t0", 0),
        ("initial_350ms", 350),
        ("initial_800ms", 450),
        ("initial_1500ms", 700),
        ("initial_3000ms", 1500),
        ("initial_timeout", max(0, int(timeout_s * 1000) - 3000)),
    ):
        if wait_ms:
            page.wait_for_timeout(wait_ms)
        samples.append(_take_sample(page, label=label))

    page.reload(wait_until="domcontentloaded", timeout=90_000)
    try:
        _page_cycle_churn_snapshot(page, slug="inputs", detail=True)
    except Exception:
        pass
    for label, wait_ms in (
        ("reload_t0", 0),
        ("reload_350ms", 350),
        ("reload_800ms", 450),
        ("reload_1500ms", 700),
        ("reload_3000ms", 1500),
        ("reload_timeout", max(0, int(timeout_s * 1000) - 3000)),
    ):
        if wait_ms:
            page.wait_for_timeout(wait_ms)
        samples.append(_take_sample(page, label=label))

    scroll_probe = _scroll_probe(page)
    samples.append(_take_sample(page, label="after_scroll_probe"))
    return {"url": url, "samples": samples, "scroll_probe": scroll_probe}


def _capture(base_url: str, *, recipe: str, timeout_s: float, headed: bool) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.set_default_timeout(30_000)
        _install_layout_probe(page)
        try:
            return _capture_sequence(page, base_url=base_url, recipe=recipe, timeout_s=timeout_s)
        finally:
            browser.close()


def _gap_values(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sample in samples:
        layout = dict(sample.get("layout") or {})
        gaps = dict(layout.get("gaps") or {})
        for name, value in gaps.items():
            if isinstance(value, (int, float)):
                rows.append({"sample": sample.get("label"), "gap": name, "px": int(value)})
    rows.sort(key=lambda item: abs(int(item.get("px") or 0)), reverse=True)
    return rows


def _plotly_mutation_rows(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sample in samples:
        for item in ((sample.get("churn") or {}).get("mutation_top_attribution") or []):
            if not isinstance(item, dict):
                continue
            owner = str(item.get("owner") or item.get("family") or "")
            label = str(item.get("label") or "")
            if "plotly" in owner.lower() or "chart" in owner.lower() or "plotly" in label.lower():
                rows.append({"sample": sample.get("label"), **item})
    return rows


def _max_layout_shift(samples: list[dict[str, Any]]) -> float:
    return max([float(((sample.get("layout") or {}).get("layout_shift_total") or 0.0)) for sample in samples] or [0.0])


def _sample_with_max_shift(samples: list[dict[str, Any]]) -> dict[str, Any]:
    return max(samples, key=lambda sample: float(((sample.get("layout") or {}).get("layout_shift_total") or 0.0)), default={})


def _classify(samples: list[dict[str, Any]], scroll_probe: dict[str, Any]) -> dict[str, Any]:
    gaps = _gap_values(samples)
    largest_gap = gaps[0] if gaps else {}
    max_shift = _max_layout_shift(samples)
    max_shift_sample = _sample_with_max_shift(samples)
    plotly_rows = _plotly_mutation_rows(samples)
    largest_mutation = max(
        samples,
        key=lambda sample: int(((sample.get("churn") or {}).get("last_mutation_batch_size") or 0)),
        default={},
    )
    risks: list[str] = []
    if max_shift > 0.15:
        risks.append("high_layout_shift")
    if abs(int(largest_gap.get("px") or 0)) > 220:
        risks.append(f"large_gap:{largest_gap.get('gap')}")
    if bool(scroll_probe.get("locked_while_scrollable")):
        risks.append("scroll_locked_while_scrollable")
    if plotly_rows:
        risks.append("plotly_or_chart_mutations_seen")

    likely_source = "no_major_source_identified"
    if "scroll_locked_while_scrollable" in risks:
        likely_source = "scroll_container_lock"
    elif largest_gap.get("gap") in {"nav_to_inputs", "inputs_to_summary"} and abs(int(largest_gap.get("px") or 0)) > 220:
        likely_source = "inputs_shell_or_page_content_placeholder"
    elif largest_gap.get("gap") == "summary_to_batch" and abs(int(largest_gap.get("px") or 0)) > 160:
        likely_source = "summary_to_batch_placeholder_or_summary_band_height"
    elif largest_gap.get("gap") == "batch_to_design_guide" and abs(int(largest_gap.get("px") or 0)) > 180:
        likely_source = "batch_design_to_design_guide_placeholder"
    elif plotly_rows:
        likely_source = "model_diagram_plotly_dom_mutation"
    elif max_shift > 0.15:
        likely_source = "layout_shift_without_specific_gap_owner"

    next_slice = {
        "inputs_shell_or_page_content_placeholder": "Add readiness proof for stable page shell/Inputs placeholder height reservation.",
        "summary_to_batch_placeholder_or_summary_band_height": "Add readiness proof for summary-to-batch stable height preservation.",
        "batch_design_to_design_guide_placeholder": "Add readiness proof for Batch/Design Guide slot placeholder height preservation.",
        "model_diagram_plotly_dom_mutation": "Add readiness proof for model/diagram panel render reuse keyed by model state fingerprint.",
        "scroll_container_lock": "Add browser/live scroll-container ownership audit before changing layout.",
        "layout_shift_without_specific_gap_owner": "Add focused layout-shift source snapshot with per-entry source nodes.",
        "no_major_source_identified": "Return to stable no-change render reuse profiling for the next measured hotspot.",
    }.get(likely_source, "Add focused layout source audit before implementation.")

    return {
        "audit_result": "RISKS_FOUND" if risks else "NO_MAJOR_LAYOUT_PLACEHOLDER_SOURCE_DETECTED",
        "risks": risks,
        "likely_source": likely_source,
        "largest_gap": largest_gap,
        "top_gaps": gaps[:10],
        "max_layout_shift_total": max_shift,
        "max_layout_shift_sample": {
            "label": max_shift_sample.get("label"),
            "layout_shift_entries_tail": ((max_shift_sample.get("layout") or {}).get("layout_shift_entries") or [])[-10:],
        },
        "largest_mutation_sample": {
            "label": largest_mutation.get("label"),
            "last_mutation_batch_size": (largest_mutation.get("churn") or {}).get("last_mutation_batch_size"),
            "mutation_top_attribution": (largest_mutation.get("churn") or {}).get("mutation_top_attribution"),
        },
        "plotly_or_chart_mutation_rows": plotly_rows[:20],
        "scroll_probe": scroll_probe,
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    classification = dict(payload.get("classification") or {})
    lines = [
        "# Post-Zero-Authority Layout Placeholder Source Snapshot",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Audit result: `{classification.get('audit_result')}`",
        f"- Recipe: `{payload.get('recipe')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Likely source: `{classification.get('likely_source')}`",
        f"- Risks: `{', '.join(classification.get('risks') or []) or '-'}`",
        f"- Max layout shift: `{classification.get('max_layout_shift_total')}`",
        f"- Largest gap: `{json.dumps(classification.get('largest_gap'), sort_keys=True)}`",
        f"- Scroll locked while scrollable: `{(classification.get('scroll_probe') or {}).get('locked_while_scrollable')}`",
        "",
        "## Recommended Next Slice",
        "",
        str(classification.get("recommended_next_slice") or ""),
        "",
        "## Top Gaps",
        "",
    ]
    for row in classification.get("top_gaps") or []:
        lines.append(f"- `{row.get('sample')}` `{row.get('gap')}` = `{row.get('px')}` px")
    lines.extend(["", "## Snapshot Summary", ""])
    for sample in payload.get("samples") or []:
        layout = dict(sample.get("layout") or {})
        churn = dict(sample.get("churn") or {})
        lines.append(
            f"- `{sample.get('label')}` gaps `{json.dumps(layout.get('gaps'), sort_keys=True)}`, "
            f"CLS `{layout.get('layout_shift_total')}`, mutations `{churn.get('last_mutation_batch_size')}`"
        )
    lines.extend(["", "## Notes", ""])
    lines.append("This is measurement-only. It does not implement placeholders, reuse, caching, bypasses, deletion, or UI changes.")
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_post_zero_authority_layout_placeholder_source_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_post_zero_authority_layout_placeholder_source_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8586)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--timeout-s", type=float, default=8.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://127.0.0.1:{args.port}")
    created_at = _stamp()
    errors: list[str] = []
    try:
        if not args.base_url:
            env_before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            os.environ["CODEX_RENDER_TIMING_TRACE"] = "1"
            os.environ["AUTO_DESIGN_SPEED_PROFILE"] = "1"
            try:
                process = _start_streamlit(args.port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)
            _wait_for_http(base_url, timeout_s=60.0)
        capture = _capture(base_url, recipe=str(args.recipe), timeout_s=float(args.timeout_s), headed=bool(args.headed))
    except Exception as exc:
        capture = {"url": base_url, "samples": [], "scroll_probe": {}}
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    samples = list(capture.get("samples") or [])
    classification = _classify(samples, dict(capture.get("scroll_probe") or {})) if samples else {
        "audit_result": "NO_BROWSER_SAMPLES",
        "risks": ["no_browser_samples"],
        "likely_source": "not_measured",
        "recommended_next_slice": "Fix browser/live capture before layout implementation.",
    }
    zero = _latest_payload("design_brain_inputs_page_zero_authority_inventory_lock")
    status = "PASS" if samples and not errors else "FAIL"
    payload = {
        "schema": "design_guide_post_zero_authority_layout_placeholder_source_snapshot.v1",
        "status": status,
        "created_at": created_at,
        "recipe": args.recipe,
        "base_url": base_url,
        "product_behaviour_changed": False,
        "new_bypasses_implemented": False,
        "code_deleted": False,
        "zero_authority_lock": {"path": zero.get("path"), "status": zero.get("status")},
        "capture_url": capture.get("url"),
        "classification": classification,
        "samples": samples,
        "snapshot_hash": _stable_hash({"samples": samples, "classification": classification, "errors": errors}),
        "errors": errors,
    }
    json_path, md_path = _write(payload)
    print(f"design_guide_post_zero_authority_layout_placeholder_source_snapshot {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print(f"likely_source={classification.get('likely_source')}")
    print(f"recommended_next_slice={classification.get('recommended_next_slice')}")
    if errors:
        print("errors=" + json.dumps(errors, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
