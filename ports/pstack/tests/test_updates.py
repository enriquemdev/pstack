import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

PORT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_upstream", PORT / "check_upstream.py")
updates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updates)
PIN = json.loads((PORT / "upstream.lock").read_text())["commit"]
CANDIDATE = "a" * 40


class UpdateTests(unittest.TestCase):
    def invoke(self, prepare, api, fake_run):
        args = ["check_upstream.py"] + (["--prepare-pr"] if prepare else [])
        output = io.StringIO()
        with patch("sys.argv", args), patch.object(updates, "public_json", side_effect=api), \
             patch.object(updates, "run", side_effect=fake_run), contextlib.redirect_stdout(output):
            updates.main()
        return json.loads(output.getvalue())

    def test_unchanged_is_quiet_and_never_writes(self):
        def fail(*args):
            self.fail("No write/CLI command should run when unchanged")
        result = self.invoke(True, [[{"sha": PIN}]], fail)
        self.assertFalse(result["changed"])

    def test_detection_only_never_creates_branch_or_issue(self):
        result = self.invoke(False, [[{"sha": CANDIDATE}], {"version": "0.15.21"}],
                             lambda *args: self.fail("CLI mutation in detection-only mode"))
        self.assertEqual(result["candidate"], "0.15.21")

    def test_invalid_sha_is_rejected_before_cli(self):
        with self.assertRaisesRegex(ValueError, "SHA"):
            self.invoke(True, [[{"sha": "../main; echo unsafe"}]], lambda *args: self.fail())

    def test_dirty_checkout_blocks_preparation(self):
        def run(*args):
            return updates.OWNER if args[:3] == ("gh", "repo", "view") else " M local.txt"
        with self.assertRaisesRegex(ValueError, "dirty"):
            self.invoke(True, [[{"sha": CANDIDATE}], {"version": "0.15.21"}], run)

    def test_existing_pr_is_idempotent(self):
        def run(*args):
            if args[:3] == ("gh", "repo", "view"): return updates.OWNER
            if args[:3] == ("git", "status", "--porcelain"): return ""
            if args[:3] == ("gh", "pr", "list"): return '[{"url":"existing","state":"OPEN"}]'
            self.fail("Unexpected mutation after finding an existing PR")
        result = self.invoke(True, [[{"sha": CANDIDATE}], {"version": "0.15.21"}], run)
        self.assertEqual(result["existing_pr"]["url"], "existing")

    def test_retry_reuses_pushed_branch_and_does_not_refresh_lock(self):
        calls = []
        def run(*args):
            calls.append(args)
            if args[:3] == ("gh", "repo", "view"): return updates.OWNER
            if args[:2] == ("git", "status"): return ""
            if args[:3] == ("gh", "pr", "list"): return "[]"
            if args[:3] == ("gh", "issue", "list"):
                return json.dumps([{"number": 7, "body": f"Upstream commit: `{CANDIDATE}`"}])
            if args[:3] == ("gh", "issue", "view"):
                return '{"labels":[{"name":"status:approved"}]}'
            if args[:2] == ("git", "ls-remote"): return "existing branch"
            if args[:3] == ("gh", "pr", "create"): return "https://github.com/enriquemdev/pstack/pull/7"
            self.fail(f"Unexpected command {args}")
        before = (PORT / "upstream.lock").read_bytes()
        result = self.invoke(True, [[{"sha": CANDIDATE}], {"version": "0.15.21"}], run)
        self.assertTrue(result["draft_pr"].endswith("/7"))
        self.assertEqual(before, (PORT / "upstream.lock").read_bytes())
        self.assertFalse(any(c[:2] == ("git", "push") for c in calls))
        create = next(c for c in calls if c[:3] == ("gh", "pr", "create"))
        self.assertIn("--draft", create)
        self.assertIn("Closes #7", create[create.index("--body") + 1])


if __name__ == "__main__":
    unittest.main()
