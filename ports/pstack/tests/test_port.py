import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PORT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pstack", PORT / "pstack.py")
pstack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pstack)
spec_log = importlib.util.spec_from_file_location("decision_log", PORT / "log.py")
log = importlib.util.module_from_spec(spec_log)
spec_log.loader.exec_module(log)


class PortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundles = {host: pstack.build(host) for host in pstack.HOSTS}

    def test_covers_all_52_skills_and_23_playbooks(self):
        _, recipes, names, playbooks = pstack.check_source()
        self.assertEqual(len(names), 52)
        self.assertEqual(len(recipes), 28)
        self.assertEqual(len(playbooks), 23)
        for bundle in self.bundles.values():
            self.assertEqual(len(pstack.validate(bundle)["skills"]), 52)

    def test_deterministic_build(self):
        before = pstack.inventory(self.bundles["codex"])
        pstack.build("codex")
        self.assertEqual(before, pstack.inventory(self.bundles["codex"]))

    def test_source_drift_is_rejected(self):
        original = pstack.inventory
        def changed(source=pstack.SOURCE):
            values = original(source)
            values["new-unreviewed-file.md"] = "changed"
            return values
        with patch.object(pstack, "inventory", changed):
            with self.assertRaisesRegex(ValueError, "Unreviewed"):
                pstack.check_source()

    def test_no_cursor_runtime_dependencies_in_active_payload(self):
        forbidden = ("pstack-models.mdc", "subagent_type:", "run_in_background:",
                     "~/.cursor", "cursor-team-kit", "grok-4.7", "claude-opus-5-5", "origin pr")
        for bundle in self.bundles.values():
            for path in bundle.rglob("*.md"):
                if path.name == "host.md":
                    continue  # explicit documentation of unsupported host APIs
                for token in forbidden:
                    self.assertNotIn(token, path.read_text(), str(path))

    def test_codex_invocation_is_explicit_only(self):
        for skill in (self.bundles["codex"] / "skills").iterdir():
            self.assertEqual((skill / "agents/openai.yaml").read_text(),
                             "policy:\n  allow_implicit_invocation: false\n")

    def test_permissions_are_present_in_every_skill(self):
        for bundle in self.bundles.values():
            for skill in (bundle / "skills").iterdir():
                self.assertIn("references/policy.md", (skill / "SKILL.md").read_text())
                policy = (skill / "references/policy.md").read_text()
                self.assertIn("Do not use subagents unless", policy)
                self.assertIn("After asking, stop and wait", policy)
                self.assertIn("Never add Co-Authored-By", policy)
                self.assertIn("not permission to publish", policy)

    def test_principle_overrides_do_not_bypass_checkpoints(self):
        path = self.bundles["codex"] / "skills/pstack-principle-never-block-on-the-human/SKILL.md"
        self.assertIn("Never bypass a requested checkpoint", path.read_text())

    def test_dry_run_does_not_create_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "skills"
            result = pstack.install(self.bundles["codex"], destination)
            self.assertEqual(result["count"], 52)
            self.assertFalse(destination.exists())

    def test_install_update_and_rollback_preserve_unrelated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "skills"
            destination.mkdir()
            untouched = destination / "existing-skill"
            untouched.mkdir(); (untouched / "SKILL.md").write_text("keep me")
            first = pstack.install(self.bundles["codex"], destination, True)
            second = pstack.install(self.bundles["codex"], destination, True)
            self.assertEqual(len(list(destination.glob("pstack-*/SKILL.md"))), 52)
            pstack.rollback(second["backup"], True)
            self.assertEqual(len(list(destination.glob("pstack-*/SKILL.md"))), 52)
            pstack.rollback(first["backup"], True)
            self.assertEqual(list(destination.glob("pstack-*/SKILL.md")), [])
            self.assertEqual((untouched / "SKILL.md").read_text(), "keep me")

    def test_unmanaged_collision_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)
            existing = destination / "pstack-how"
            existing.mkdir(); (existing / "SKILL.md").write_text("custom")
            with self.assertRaisesRegex(ValueError, "Unmanaged collision"):
                pstack.install(self.bundles["codex"], destination, True)
            self.assertEqual((existing / "SKILL.md").read_text(), "custom")
            self.assertEqual(len(list(destination.glob("pstack-*"))), 1)

    def test_local_edits_block_update_and_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)
            result = pstack.install(self.bundles["codex"], destination, True)
            path = destination / "pstack-how/SKILL.md"
            path.write_text(path.read_text() + "local edit")
            with self.assertRaisesRegex(ValueError, "Locally modified"):
                pstack.install(self.bundles["codex"], destination, True)
            with self.assertRaisesRegex(ValueError, "local edits"):
                pstack.rollback(result["backup"], True)
            self.assertTrue(path.read_text().endswith("local edit"))

    def test_injected_install_failure_restores_previous_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)
            pstack.install(self.bundles["codex"], destination, True)
            before = pstack.inventory(destination)
            real_copy = pstack.shutil.copytree
            failed = False
            def failure(src, dst, *args, **kwargs):
                nonlocal failed
                if str(src).startswith(str(self.bundles["codex"])) and not failed:
                    failed = True
                    raise OSError("injected copy failure")
                return real_copy(src, dst, *args, **kwargs)
            with patch.object(pstack.shutil, "copytree", failure):
                with self.assertRaisesRegex(OSError, "injected"):
                    pstack.install(self.bundles["codex"], destination, True)
            after = pstack.inventory(destination)
            # Backups are intentionally retained; active files must be identical.
            active = lambda values: {k: v for k, v in values.items() if not k.startswith(".pstack-backups/")}
            self.assertEqual(active(before), active(after))

    def test_tampered_bundle_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            pstack.shutil.copytree(self.bundles["codex"], bundle)
            (bundle / "skills/pstack-how/SKILL.md").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "integrity"):
                pstack.install(bundle, Path(tmp) / "skills", True)
            self.assertFalse((Path(tmp) / "skills/pstack-how").exists())

    def test_destination_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"; target.mkdir()
            link = Path(tmp) / "skills"; link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink"):
                pstack.install(self.bundles["codex"], link, True)

    def test_decision_log_sanitizes_and_appends(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decisions.tsv"
            log.append(path, "phase", " =SUM(1)", "why\nsecond", "proof\tvalue", "result")
            log.append(path, "phase", "decision", "why", "proof", "result")
            lines = path.read_text().splitlines()
            self.assertEqual(len(lines), 3)
            self.assertIn("' =SUM(1)", lines[1])
            self.assertEqual(len(lines[1].split("\t")), 6)


if __name__ == "__main__":
    unittest.main()
