#!/usr/bin/env python3
"""Detect pstack-only updates and optionally prepare a draft review PR in this fork."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OWNER = "enriquemdev/pstack"
UPSTREAM = "cursor/plugins"


def run(*args):
    return subprocess.check_output(args, text=True, cwd=ROOT).strip()


def public_json(url):
    return json.loads(run("curl", "--fail", "--silent", "--show-error", "--location", url))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-pr", action="store_true")
    args = parser.parse_args()
    lock = json.loads((ROOT / "ports/pstack/upstream.lock").read_text())
    commit = public_json(f"https://api.github.com/repos/{UPSTREAM}/commits?path=pstack&per_page=1")[0]["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Unexpected upstream SHA")
    if commit == lock["commit"]:
        print(json.dumps({"changed": False, "commit": commit}))
        return
    version = public_json(f"https://raw.githubusercontent.com/{UPSTREAM}/{commit}/pstack/plugin.json")["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Unexpected upstream version")
    result = {"changed": True, "current": lock["version"], "candidate": version, "commit": commit}
    if not args.prepare_pr:
        print(json.dumps(result, indent=2)); return
    if run("gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner") != OWNER:
        raise ValueError("PR preparation is restricted to the personal fork")
    if run("git", "status", "--porcelain"):
        raise ValueError("Refusing to update a dirty working tree")
    branch = f"chore/pstack-sync-{commit[:12]}"
    prs = json.loads(run("gh", "pr", "list", "--repo", OWNER, "--head", branch,
                         "--state", "all", "--json", "url,state"))
    if prs:
        print(json.dumps({**result, "existing_pr": prs[0]})); return
    issues = json.loads(run("gh", "issue", "list", "--repo", OWNER, "--state", "all",
                            "--search", f'"{commit}" in:body', "--json", "number,body"))
    issue = next((i["number"] for i in issues if f"Upstream commit: `{commit}`" in i["body"]), None)
    if issue is None:
        for name, color in (("status:approved", "0e8a16"), ("type:chore", "ededed")):
            run("gh", "label", "create", name, "--repo", OWNER, "--color", color, "--force")
        issue_url = run("gh", "issue", "create", "--repo", OWNER,
                        "--title", f"chore(pstack): prepare upstream {version} review",
                        "--label", "status:approved,type:chore", "--body",
                        f"Upstream commit: `{commit}`\n\nApproved scope: prepare a review PR under the owner's maintenance setup. "
                        "This does not approve the upstream changes, lock refresh, merge, installation or permission changes.\n\n"
                        "Review the original changes, adapt affected recipes, refresh the lock explicitly, run tests and host checks.")
        issue = int(issue_url.rsplit("/", 1)[-1])
    labels = json.loads(run("gh", "issue", "view", str(issue), "--repo", OWNER, "--json", "labels"))["labels"]
    if "status:approved" not in {x["name"] for x in labels}:
        raise ValueError("Linked issue must authorize PR preparation")
    run("git", "fetch", "--no-tags", f"https://github.com/{UPSTREAM}.git", commit)
    run("git", "checkout", "-B", branch, "origin/main")
    run("git", "restore", "--source", commit, "--staged", "--worktree", "--", "pstack")
    if not run("git", "diff", "--cached", "--name-only"):
        print(json.dumps({**result, "same_pstack_tree": True})); return
    run("git", "-c", "user.name=github-actions[bot]", "-c",
        "user.email=41898282+github-actions[bot]@users.noreply.github.com", "commit",
        "-m", f"chore(pstack): stage upstream {version} for review")
    run("git", "push", "origin", f"HEAD:refs/heads/{branch}")
    url = run("gh", "pr", "create", "--repo", OWNER, "--head", branch, "--base", "main",
              "--draft", "--label", "type:chore", "--title", f"chore(pstack): review upstream {version}",
              "--body", f"Closes #{issue}\n\n## Why\nNew upstream pstack changes are available.\n\n"
              f"## Scope\nOnly original pstack files; no installation or automatic merge.\n\n"
              f"## Verification\nThe source fingerprint gate intentionally remains failing until human review.\n"
              f"Review recipes and run `python3 ports/pstack/pstack.py lock --commit {commit} --reviewed`, then the tests and host checks.\n\n"
              "- [ ] Source and adaptation reviewed\n- [ ] Deterministic tests\n- [ ] Codex host check\n- [ ] Antigravity host check\n")
    print(json.dumps({**result, "draft_pr": url}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as error:
        print(f"upstream check failed: {error}", file=sys.stderr)
        sys.exit(1)
