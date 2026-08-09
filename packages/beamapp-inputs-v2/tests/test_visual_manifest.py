import json
from pathlib import Path


def test_visual_manifest_declares_required_reference_capture() -> None:
    path = Path(__file__).resolve().parents[1] / "visual-baselines" / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "inputs_v2.visual_baseline_manifest.v1"
    assert "desktop" in {item["name"] for item in manifest["viewports"]}
    assert "narrow" in {item["name"] for item in manifest["viewports"]}
    assert "default" in manifest["states"]
    assert manifest["status"] == "reference_capture_pending"

