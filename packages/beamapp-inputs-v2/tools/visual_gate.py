"""Validate that visual parity cannot be declared without captured artifacts."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "visual-baselines"


def main() -> None:
    manifest = json.loads((BASELINES / "manifest.json").read_text(encoding="utf-8"))
    status = manifest.get("status")
    if status == "reference_capture_pending":
        print("Visual gate pending: reference captures are not yet approved.")
        return
    if status != "passed":
        print(f"Visual gate rejected unknown status: {status!r}", file=sys.stderr)
        raise SystemExit(1)
    missing = []
    wrong_size = []
    for viewport in manifest["viewports"]:
        for state in manifest["states"]:
            stem = f"{viewport['name']}--{state}"
            for suffix in ("current", "v2"):
                path = BASELINES / f"{stem}--{suffix}.png"
                if not path.exists():
                    missing.append(path.name)
                else:
                    with Image.open(path) as image:
                        expected = (int(viewport["width"]), int(viewport["height"]))
                        if image.size != expected:
                            wrong_size.append(f"{path.name}: {image.size} != {expected}")
    if missing:
        print("Visual gate rejected missing captures:", file=sys.stderr)
        print("\n".join(missing), file=sys.stderr)
        raise SystemExit(1)
    if wrong_size:
        print("Visual gate rejected incorrect capture dimensions:", file=sys.stderr)
        print("\n".join(wrong_size), file=sys.stderr)
        raise SystemExit(1)
    print("Visual gate passed: all declared captures exist.")


if __name__ == "__main__":
    main()
