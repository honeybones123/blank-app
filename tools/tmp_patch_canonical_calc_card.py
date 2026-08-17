from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]

widgets = ROOT / "widgets_helpers.py"
source = widgets.read_text(encoding="utf-8-sig")

old_sig = """    jump_uid=None,\n    accent: str | None = None,\n):\n"""
new_sig = """    jump_uid=None,\n    accent: str | None = None,\n    render_policy: str = \"lazy\",\n):\n"""
if source.count(old_sig) != 1:
    raise SystemExit("canonical calc-card signature changed unexpectedly")
source = source.replace(old_sig, new_sig, 1)

old_expander = """    expander = st.expander(\n        label,\n        expanded=bool(is_expanded),\n        key=open_key,\n        on_change=\"rerun\",\n    )\n"""
new_expander = """    policy = str(render_policy or \"lazy\").strip().lower()\n    mount_closed_body = policy in {\"mounted\", \"eager\", \"client_mounted\"} and diagram_fn is None\n    expander = st.expander(\n        label,\n        expanded=bool(is_expanded),\n        key=open_key,\n        on_change=\"ignore\" if mount_closed_body else \"rerun\",\n    )\n"""
if source.count(old_expander) != 1:
    raise SystemExit("canonical calc-card expander block changed unexpectedly")
source = source.replace(old_expander, new_expander, 1)

old_gate = """        if not expander.open:\n            return\n\n        if diagram_fn:\n"""
new_gate = """        if not expander.open and not mount_closed_body:\n            return\n\n        if diagram_fn:\n"""
if source.count(old_gate) != 1:
    raise SystemExit("canonical calc-card body gate changed unexpectedly")
source = source.replace(old_gate, new_gate, 1)

css_anchor = """div[data-testid=\"stExpander\"] details:has(span.step-fail) > summary {\n  border-left-color: #dc3545 !important;\n  background: rgba(220,53,69,0.10) !important;\n}\n</style>\n"""
css_replacement = """div[data-testid=\"stExpander\"] details:has(span.step-fail) > summary {\n  border-left-color: #dc3545 !important;\n  background: rgba(220,53,69,0.10) !important;\n}\n\n/* Keep the open calculation body visually connected to its semantic header. */\ndiv[data-testid=\"stVerticalBlock\"]:has(\n  > div[data-testid=\"stElementContainer\"] [data-calc-uid]\n) div[data-testid=\"stExpander\"] details[open]:has(span.step-neutral) > div {\n  box-shadow: inset 4px 0 0 #1f77b4 !important;\n  background: rgba(31,119,180,0.018) !important;\n}\ndiv[data-testid=\"stVerticalBlock\"]:has(\n  > div[data-testid=\"stElementContainer\"] [data-calc-uid]\n) div[data-testid=\"stExpander\"] details[open]:has(span.step-pass) > div {\n  box-shadow: inset 4px 0 0 #28a745 !important;\n  background: rgba(40,167,69,0.018) !important;\n}\ndiv[data-testid=\"stVerticalBlock\"]:has(\n  > div[data-testid=\"stElementContainer\"] [data-calc-uid]\n) div[data-testid=\"stExpander\"] details[open]:has(span.step-fail) > div {\n  box-shadow: inset 4px 0 0 #dc3545 !important;\n  background: rgba(220,53,69,0.018) !important;\n}\n</style>\n"""
if source.count(css_anchor) != 1:
    raise SystemExit("shared calc-card CSS anchor changed unexpectedly")
source = source.replace(css_anchor, css_replacement, 1)
widgets.write_text(source, encoding="utf-8")

bending = ROOT / "bending_tabs.py"
bsrc = bending.read_text(encoding="utf-8-sig")
tree = ast.parse(bsrc)
lines = bsrc.splitlines()
insertions = []
for node in ast.walk(tree):
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        continue
    if node.func.id != "step_expander_calcbox":
        continue
    keywords = {kw.arg: kw for kw in node.keywords if kw.arg}
    if "render_policy" in keywords or "diagram_fn" in keywords:
        continue
    end_index = int(node.end_lineno) - 1
    closing = lines[end_index]
    indent = closing[: len(closing) - len(closing.lstrip())]
    insertions.append((end_index, indent + '    render_policy="mounted",'))
for index, text in sorted(insertions, reverse=True):
    lines.insert(index, text)
bending.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(f"Mounted light Bending cards: {len(insertions)}")
