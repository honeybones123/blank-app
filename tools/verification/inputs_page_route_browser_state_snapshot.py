from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_helpers import _load_browser_state  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _query,
    _start_streamlit,
)


APP = ROOT / "app.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]


def _route_target() -> str:
    tree = ast.parse(APP.read_text(encoding="utf-8", errors="replace"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "PAGES" for target in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for key, value in zip(node.value.keys, node.value.values):
            if not (isinstance(key, ast.Constant) and key.value == "inputs"):
                continue
            if (
                isinstance(value, ast.Tuple)
                and len(value.elts) >= 2
                and isinstance(value.elts[1], ast.Attribute)
                and isinstance(value.elts[1].value, ast.Name)
            ):
                return f"{value.elts[1].value.id}.{value.elts[1].attr}"
    return ""


def _compact_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return round(float(value), 6)
    except Exception:
        return None


def _selected_shared_state(state: dict[str, Any]) -> dict[str, Any]:
    shared = dict(state.get("browser_shared_probe") or {})
    keys = (
        "D",
        "b",
        "bf",
        "tf",
        "bw",
        "tw",
        "L",
        "fc",
        "fsy",
        "uls_Mstar",
        "uls_Vstar",
        "load_Mstar_proxy",
        "load_Vstar_proxy",
        "inputs_load_Mstar_pos_proxy",
        "inputs_load_Vstar_proxy",
        "inputs_detailed_mode",
        "sec_shape",
        "inputs_sec_shape",
        "design_optimisation_goal",
    )
    result: dict[str, Any] = {}
    for key in keys:
        value = shared.get(key)
        numeric = _compact_float(value)
        result[key] = numeric if numeric is not None else value
    return result


def _selected_summary(state: dict[str, Any]) -> dict[str, Any]:
    summary = dict(state.get("summary_state_probe") or {})
    overview = dict(state.get("summary_overview_probe") or {})
    return {
        "summary_keys": sorted(summary.keys()),
        "summary_values": {
            key: (_compact_float(summary.get(key)) if _compact_float(summary.get(key)) is not None else summary.get(key))
            for key in (
                "D",
                "b",
                "L",
                "fc",
                "fsy",
                "uls_Mstar",
                "uls_Vstar",
                "sec_shape",
                "design_optimisation_goal",
            )
        },
        "overview": {
            "worst_util": _compact_float(overview.get("worst_util")),
            "governing_check": overview.get("governing_check"),
            "statuses": dict(overview.get("statuses") or {}),
            "any_fail": bool(overview.get("any_fail")),
            "all_pass": bool(overview.get("all_pass")),
        },
    }


def _selected_publication(state: dict[str, Any]) -> dict[str, Any]:
    publication = dict(
        state.get("final_publication")
        or state.get("final_design_guide_publication")
        or {}
    )
    guidance = dict(state.get("guidance_compute_probe") or {})
    return {
        "publication_keys": sorted(publication.keys()),
        "publication_hash": publication.get("publication_hash") or state.get("publication_hash"),
        "display_hash": publication.get("display_hash") or state.get("display_hash"),
        "guidance_probe_keys": sorted(guidance.keys()),
    }


def _normalise_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "top_level_keys": sorted(state.keys()),
        "shared": _selected_shared_state(state),
        "summary": _selected_summary(state),
        "publication": _selected_publication(state),
    }


def _dom_summary(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            """
            () => {
              const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim();
              const hash = (value) => {
                const text = String(value || "");
                let h = 2166136261;
                for (let i = 0; i < text.length; i += 1) {
                  h ^= text.charCodeAt(i);
                  h = Math.imul(h, 16777619);
                }
                return (h >>> 0).toString(16);
              };
              const sourceRoot = document.querySelector("[data-testid='stMain']")
                || document.querySelector("main")
                || document.body
                || document.createElement("body");
              const clone = sourceRoot.cloneNode(true);
              for (const selector of ["textarea", "pre", "code", "[data-testid='stCodeBlock']", "[data-testid='stTextArea']"]) {
                for (const el of Array.from(clone.querySelectorAll(selector))) {
                  el.remove();
                }
              }
              const visibleText = clean(clone.innerText || clone.textContent || "");
              const normalisedVisibleText = visibleText
                .replace(/Inputs render:\\s*[0-9]+(?:\\.[0-9]+)?\\s*ms/g, "Inputs render: <ms>")
                .replace(/Render time:\\s*[0-9]+(?:\\.[0-9]+)?\\s*ms/g, "Render time: <ms>");
              const buttons = Array.from(sourceRoot.querySelectorAll("button"))
                .map((button) => clean(button.innerText || button.textContent))
                .filter(Boolean);
              const labels = Array.from(sourceRoot.querySelectorAll("label, [aria-label]"))
                .map((el) => clean(el.getAttribute("aria-label") || el.innerText || el.textContent))
                .filter(Boolean)
                .slice(0, 160);
              return {
                visible_text_hash: hash(visibleText),
                normalised_visible_text_hash: hash(normalisedVisibleText),
                visible_text_length: visibleText.length,
                normalised_visible_text_length: normalisedVisibleText.length,
                visible_text_sample: visibleText.slice(0, 1200),
                button_texts: buttons.slice(0, 120),
                label_texts: labels,
                has_inputs_title: /\\bInputs\\b/.test(visibleText),
                has_design_guide: /Design Guide/i.test(visibleText),
                has_apply_text: /\\bApply\\b/i.test(visibleText)
              };
            }
            """
        )
    )


def _wait_for_inputs_dom_settled(page) -> None:
    page.wait_for_function(
        """
        () => {
          const text = String(document.body ? document.body.innerText : "");
          const buttons = Array.from(document.querySelectorAll("button"))
            .map((button) => String(button.innerText || button.textContent || ""));
          const labels = Array.from(document.querySelectorAll("label, [aria-label]"))
            .map((el) => String(el.getAttribute("aria-label") || el.innerText || el.textContent || ""));
          return text.includes("Inputs")
            && /Design Guide/i.test(text)
            && buttons.length >= 32
            && labels.length >= 150
            && labels.some((label) => /Use calculated design actions/i.test(label))
            && labels.some((label) => /3D model/i.test(label))
            && labels.some((label) => /Width b \\(mm\\)/i.test(label))
            && labels.some((label) => /Depth D \\(mm\\)/i.test(label))
            && labels.some((label) => /Span L \\(mm\\)/i.test(label))
            && labels.some((label) => /Steel MPa/i.test(label))
            && labels.some((label) => /Concrete MPa/i.test(label))
            && buttons.some((label) => /Reset workspace/i.test(label))
            && buttons.some((label) => /Duplicate/i.test(label))
            && buttons.some((label) => /Delete/i.test(label))
            && buttons.some((label) => /Load recommendation tools/i.test(label));
        }
        """,
        timeout=45_000,
    )


def _compare(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    baseline_norm = dict(baseline.get("normalised_state") or {})
    current_norm = dict(current.get("normalised_state") or {})
    baseline_dom = dict(baseline.get("dom") or {})
    current_dom = dict(current.get("dom") or {})
    checks = {
        "normalised_browser_state_hash_matches": current.get("normalised_state_hash")
        == baseline.get("normalised_state_hash"),
        "normalised_visible_text_hash_matches": current_dom.get("normalised_visible_text_hash")
        == baseline_dom.get("normalised_visible_text_hash"),
        "button_texts_match": current_dom.get("button_texts") == baseline_dom.get("button_texts"),
        "label_texts_match": current_dom.get("label_texts") == baseline_dom.get("label_texts"),
        "summary_matches": current_norm.get("summary") == baseline_norm.get("summary"),
        "shared_probe_matches": current_norm.get("shared") == baseline_norm.get("shared"),
        "publication_probe_matches": current_norm.get("publication") == baseline_norm.get("publication"),
        "inputs_title_visible": bool(current_dom.get("has_inputs_title")),
        "design_guide_visible": bool(current_dom.get("has_design_guide")),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "checks": checks,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Route Browser State Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Label: `{payload['label']}`",
        f"Route target: `{payload['route_target']}`",
        f"Normalised state hash: `{payload['normalised_state_hash']}`",
        f"Normalised visible text hash: `{payload['dom'].get('normalised_visible_text_hash')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--port", type=int, default=8527)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--compare-to", default=None)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    timestamp = _stamp()
    process = None
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    if args.base_url is None:
        process = _start_streamlit(args.port)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            page = browser.new_page(viewport={"width": 1440, "height": 1200})
            page.goto(_query(base_url, {"page": "inputs"}), wait_until="domcontentloaded", timeout=60_000)
            state = _load_browser_state(page, timeout_s=60.0)
            _wait_for_inputs_dom_settled(page)
            dom = _dom_summary(page)
            browser.close()
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    normalised = _normalise_state(state)
    payload: dict[str, Any] = {
        "audit": "inputs_page_route_browser_state_snapshot",
        "timestamp": timestamp,
        "label": args.label,
        "route_target": _route_target(),
        "status": "PASS",
        "checks": {
            "browser_state_loaded": bool(state),
            "inputs_title_visible": bool(dom.get("has_inputs_title")),
            "design_guide_visible": bool(dom.get("has_design_guide")),
        },
        "failures": [],
        "normalised_state": normalised,
        "normalised_state_hash": _stable_hash(normalised),
        "dom": dom,
        "dom_hash": _stable_hash(dom),
        "actual_browser_run": True,
    }
    payload["failures"] = [name for name, passed in payload["checks"].items() if not passed]
    if args.compare_to:
        baseline = json.loads(Path(args.compare_to).read_text(encoding="utf-8"))
        comparison = _compare(payload, baseline)
        payload["comparison"] = comparison
        payload["checks"].update({f"compare_{key}": value for key, value in comparison["checks"].items()})
        payload["failures"].extend([f"compare_{failure}" for failure in comparison["failures"]])
    payload["status"] = "PASS" if not payload["failures"] else "FAIL"
    payload["decision"] = (
        "INPUTS_ROUTE_BROWSER_STATE_PARITY_PASS"
        if payload["status"] == "PASS" and args.compare_to
        else "INPUTS_ROUTE_BROWSER_STATE_SNAPSHOT_CAPTURED"
        if payload["status"] == "PASS"
        else "INPUTS_ROUTE_BROWSER_STATE_PARITY_FAIL"
    )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_browser_state_{args.label}_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_browser_state_{args.label}_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(payload["status"])
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload["failures"]:
        print("failures=" + ";".join(payload["failures"]))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
