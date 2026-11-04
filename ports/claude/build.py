#!/usr/bin/env python3
"""Generate the Claude Code tree for the cursor-team-kit skills that pstack needs.

Skills are copied byte for byte. A skill that uses a Cursor-specific name stops the
build, because it would need an adapter this port does not have.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

PORT = Path(__file__).resolve().parent
ROOT = PORT.parents[1]
SOURCE = ROOT / "cursor-team-kit"
OUTPUT = PORT / "cursor-team-kit"
SKILLS = ("control-cli", "control-ui", "deslop")
DESCRIPTION = (
    "Claude Code subset of Cursor Team Kit: the deslop, control-cli and control-ui "
    "skills that pstack references, copied unchanged."
)
MANIFEST_FIELDS = ("name", "version", "author", "homepage", "repository", "license", "keywords")

# Same terms as cursor/plugins scripts/generate-pstack-harness-trees.mjs, plus any
# literal mention of Cursor.
CURSOR_TERMS = {
    "Task": r"`Task`|\bTask (tool|subagent|call)",
    "AskQuestion": r"AskQuestion",
    "todolist": r"(?i)\btodo ?list\b",
    "generalPurpose": r"generalPurpose",
    "poteto-agent": r"poteto-agent",
    "comment-sicko": r"comment-sicko",
    "readonly": r"readonly: (true|false)|readonly/Ask",
    "environment": r'environment: "(cloud|local)"',
    "cloud_base_branch": r"cloud_base_branch",
    "run_in_background": r"run_in_background",
    "resume": r"`resume`",
    "file_attachments": r"file_attachments",
    "claude-model": r"\bclaude-[a-z]+-\d",
    "grok-model": r"\bgrok-\d",
    "gpt-model": r"\bgpt-\d",
    "inherit-parent": r"inherit-parent",
    "models-rule": r"pstack-models\.mdc",
    "cursor-paths": r"\.cursor|\.mdc\b",
    "agent-transcripts": r"agent-transcripts",
    "cursor-only": r"Bugbot|[Cc]loud [Aa]gent|built-in PR tool",
    "cursor": r"(?i)\bcursor\b",
}


def cursor_terms(text):
    return sorted(name for name, pattern in CURSOR_TERMS.items() if re.search(pattern, text))


def manifest():
    source = json.loads((SOURCE / ".cursor-plugin/plugin.json").read_text())
    data = {field: source[field] for field in MANIFEST_FIELDS}
    data["description"] = DESCRIPTION
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def render(target):
    for skill in SKILLS:
        directory = SOURCE / "skills" / skill
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            found = cursor_terms(path.read_text())
            if found:
                raise ValueError(f"{path.relative_to(ROOT)} uses Cursor names: {', '.join(found)}")
        shutil.copytree(directory, target / "skills" / skill)
    shutil.copy2(SOURCE / "LICENSE", target / "LICENSE")
    (target / ".claude-plugin").mkdir()
    (target / ".claude-plugin/plugin.json").write_text(manifest())


def inventory(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the tree is out of date")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "tree"
        fresh.mkdir()
        render(fresh)
        if args.check:
            if not OUTPUT.exists() or inventory(fresh) != inventory(OUTPUT):
                print("ports/claude/cursor-team-kit is out of date. Run ports/claude/build.py.")
                return 1
            print("ports/claude/cursor-team-kit is up to date.")
            return 0
        if OUTPUT.exists():
            shutil.rmtree(OUTPUT)
        shutil.copytree(fresh, OUTPUT)
    print(f"{len(SKILLS)} skills copied to {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValueError as error:
        print(f"FAIL {error}", file=sys.stderr)
        sys.exit(1)
