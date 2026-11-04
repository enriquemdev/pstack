import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PORT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("claude_port", PORT / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class ClaudePortTests(unittest.TestCase):
    def test_tree_is_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            fresh = Path(tmp) / "tree"
            fresh.mkdir()
            build.render(fresh)
            self.assertEqual(build.inventory(fresh), build.inventory(build.OUTPUT))

    def test_skills_match_the_source_byte_for_byte(self):
        for skill in build.SKILLS:
            source = build.inventory(build.SOURCE / "skills" / skill)
            ported = build.inventory(build.OUTPUT / "skills" / skill)
            self.assertEqual(source, ported, skill)

    def test_ships_exactly_the_three_skills_pstack_references(self):
        names = sorted(p.name for p in (build.OUTPUT / "skills").iterdir())
        self.assertEqual(names, ["control-cli", "control-ui", "deslop"])

    def test_cursor_names_are_detected(self):
        self.assertEqual(build.cursor_terms("Read ~/.cursor/rules/x.mdc"), ["cursor", "cursor-paths"])
        self.assertEqual(build.cursor_terms("Use the Task tool"), ["Task"])
        self.assertEqual(build.cursor_terms("Check the diff against main"), [])

    def test_manifest_keeps_the_source_identity(self):
        data = json.loads((build.OUTPUT / ".claude-plugin/plugin.json").read_text())
        source = json.loads((build.SOURCE / ".cursor-plugin/plugin.json").read_text())
        self.assertEqual(data["name"], "cursor-team-kit")
        self.assertEqual(data["version"], source["version"])
        self.assertEqual(data["author"], source["author"])
        self.assertEqual(data["license"], source["license"])

    def test_marketplace_points_at_the_tree(self):
        data = json.loads((PORT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual([p["source"] for p in data["plugins"]], ["./cursor-team-kit"])


if __name__ == "__main__":
    unittest.main()
