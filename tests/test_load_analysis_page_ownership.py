from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DESIGN_PAGE = ROOT / "design_page_runtime.py"


class LoadAnalysisPageOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = DESIGN_PAGE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_load_analysis_summary_is_page_local(self) -> None:
        production_references: list[Path] = []
        for path in ROOT.rglob("*.py"):
            if "tests" in path.parts or path == DESIGN_PAGE:
                continue
            if "_render_calculation_check_summary" in path.read_text(
                encoding="utf-8", errors="ignore"
            ):
                production_references.append(path)

        self.assertEqual(production_references, [])
        self.assertEqual(self.source.count("_render_calculation_check_summary("), 2)

    def test_load_analysis_uses_unscaled_inputs_diagram_renderer(self) -> None:
        calls = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_render_section_2d_diagram_block_current"
        ]

        self.assertEqual(len(calls), 1)
        keywords = {keyword.arg: keyword.value for keyword in calls[0].keywords}
        self.assertIsInstance(keywords.get("compact"), ast.Constant)
        self.assertIs(keywords["compact"].value, True)
        self.assertNotIn("height_scale", keywords)

    def test_load_analysis_does_not_mirror_branch_actions_into_results(self) -> None:
        assigned_names = {
            target.id
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
            if isinstance(target, ast.Name)
        }
        self.assertNotIn("canonical_action_updates", assigned_names)

    def test_load_analysis_has_no_manual_inputs_action_fallback(self) -> None:
        forbidden_fragments = (
            "inputs_use_calculated_actions",
            "Manual design actions (inputs below)",
            "When disabled, demands follow manual actions entered on Inputs.",
            'set_shared("actions_source"',
            'set_shared("actions_mode"',
        )
        for fragment in forbidden_fragments:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, self.source)

        self.assertIn("ActionSource.LOAD_ANALYSIS", self.source)
        self.assertIn("include_design_brain=False", self.source)


if __name__ == "__main__":
    unittest.main()
