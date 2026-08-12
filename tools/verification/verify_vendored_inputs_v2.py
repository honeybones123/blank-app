"""Verify Render's vendored Inputs V2 wheel exactly matches its source tree."""

from __future__ import annotations

from email.parser import BytesParser
from pathlib import Path
import re
import tomllib
import zipfile


RUNTIME_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = RUNTIME_ROOT / "packages" / "beamapp-inputs-v2"
SOURCE_ROOT = PACKAGE_ROOT / "src" / "inputs_v2"
VENDOR_ROOT = RUNTIME_ROOT / "vendor"
REQUIREMENTS = RUNTIME_ROOT / "requirements.txt"


def _required_wheel() -> Path:
    matches = []
    pattern = re.compile(
        r"^\./vendor/(beamapp_inputs_v2-[^/\\\s]+-py3-none-any\.whl)$"
    )
    for raw_line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        match = pattern.match(raw_line.strip())
        if match:
            matches.append(VENDOR_ROOT / match.group(1))
    if len(matches) != 1:
        raise AssertionError(
            "requirements.txt must select exactly one vendored Inputs V2 wheel"
        )
    return matches[0]


def main() -> int:
    project = tomllib.loads(
        (PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    expected_version = project["version"]
    wheel = _required_wheel()
    if not wheel.is_file():
        raise AssertionError(f"required vendored wheel is missing: {wheel.name}")

    all_wheels = sorted(VENDOR_ROOT.glob("beamapp_inputs_v2-*.whl"))
    if all_wheels != [wheel]:
        raise AssertionError(
            "vendor must contain only the wheel selected by requirements.txt: "
            f"{[path.name for path in all_wheels]}"
        )

    source_files = {
        path.relative_to(SOURCE_ROOT).as_posix(): path.read_bytes()
        for path in SOURCE_ROOT.rglob("*.py")
        if path.is_file()
    }
    with zipfile.ZipFile(wheel) as archive:
        wheel_files = {
            name.removeprefix("inputs_v2/"): archive.read(name)
            for name in archive.namelist()
            if name.startswith("inputs_v2/") and name.endswith(".py")
        }
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise AssertionError("wheel must contain exactly one METADATA file")
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))

    if metadata["Name"] != project["name"]:
        raise AssertionError("wheel project name does not match pyproject.toml")
    if metadata["Version"] != expected_version:
        raise AssertionError(
            f"wheel version {metadata['Version']} does not match {expected_version}"
        )
    if wheel_files.keys() != source_files.keys():
        missing = sorted(source_files.keys() - wheel_files.keys())
        extra = sorted(wheel_files.keys() - source_files.keys())
        raise AssertionError(f"wheel/source file mismatch; missing={missing}, extra={extra}")
    changed = sorted(
        name for name, content in source_files.items() if wheel_files[name] != content
    )
    if changed:
        raise AssertionError(f"vendored wheel contains stale source files: {changed}")

    print(
        "verify_vendored_inputs_v2 PASS "
        f"version={expected_version} files={len(source_files)} wheel={wheel.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
