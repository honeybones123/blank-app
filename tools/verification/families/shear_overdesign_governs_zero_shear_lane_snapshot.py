from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.families.shear_overdesign_governs_lane_snapshot_common import zero_shear_lane_main


if __name__ == "__main__":
    raise SystemExit(zero_shear_lane_main())
