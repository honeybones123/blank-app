from importlib import metadata, util
from pathlib import Path
import tomllib

from packaging.requirements import Requirement
from packaging.version import Version


ROOT = Path(__file__).resolve().parents[1]


def test_distribution_metadata_matches_runtime_contract() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    assert project["name"] == "beamapp-inputs-v2"
    assert project["version"] == "0.1.0"
    dependencies = {
        requirement.name: requirement
        for item in project["dependencies"]
        if (requirement := Requirement(item))
    }
    assert {"numpy", "plotly", "streamlit"} <= dependencies.keys()
    assert Version("1.61.1") in dependencies["streamlit"].specifier
    assert metadata.version("beamapp-inputs-v2") == project["version"]


def test_inputs_v2_is_discoverable_as_an_installed_package() -> None:
    spec = util.find_spec("inputs_v2")
    assert spec is not None
    assert tuple(spec.submodule_search_locations or ())
