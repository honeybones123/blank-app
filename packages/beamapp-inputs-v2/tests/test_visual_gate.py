from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_visual_manifest_cannot_claim_pass_without_capture_artifacts() -> None:
    manifest = json.loads((ROOT / "visual-baselines" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "reference_capture_pending"

def test_visual_manifest_declares_two_viewports_and_nine_states() -> None:
    manifest = json.loads((ROOT / "visual-baselines" / "manifest.json").read_text(encoding="utf-8"))
    assert {(item["width"], item["height"]) for item in manifest["viewports"]} == {(1440, 1000), (900, 1000)}
    assert len(manifest["states"]) == 9
