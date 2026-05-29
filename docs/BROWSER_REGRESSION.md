# Browser Regression

This repo now includes a dev-only browser regression layer for the frozen one-click recipes.

It is intentionally narrow:

- real browser session via Playwright for Python
- exact frozen case loaded by query param
- fresh browser context per case
- no production behaviour change unless `CODEX_BROWSER_TEST_MODE` is enabled

## Install

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

## List available cases

```powershell
python tools/browser_one_click_regression.py --list
```

## Open a single frozen case in the browser hook

```powershell
python tools/browser_one_click_regression.py --case R5_combined_underdesign --headed
```

## Click the one-click CTA in-browser

```powershell
python tools/browser_one_click_regression.py --case R5_combined_underdesign --click-one-click --headed
```

## Run all six core regression cases in browser mode

```powershell
python tools/browser_one_click_regression.py --all-core --click-one-click
```

## How it works

- `app.py` reads `?browser_recipe=<name>` only when `CODEX_BROWSER_TEST_MODE=1`
- it applies the exact frozen state from `tools/one_click_recipe_defs.py`
- it clears stale recommendation/solver state before render
- it exposes a hidden JSON blob in the DOM at `#codex-browser-state`
- the browser runner reads that blob before and after clicking

This keeps the browser layer aligned with the frozen recipe harness rather than inventing a second source of truth.
