#!/usr/bin/env python3
"""Dependency-free, review-gated pstack builder and reversible installer."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import fcntl

PORT = Path(__file__).resolve().parent
ROOT = PORT.parents[1]
SOURCE = ROOT / "pstack"
DIST = PORT / "dist"
HOSTS = ("codex", "antigravity")
VERSION = "0.1.0"


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(source=SOURCE):
    if any(p.is_symlink() for p in source.rglob("*")):
        raise ValueError("Upstream symlinks require a separate review")
    return {str(p.relative_to(source)): digest(p)
            for p in sorted(source.rglob("*")) if p.is_file()}


def source_skills():
    return sorted(p.parent.name for p in (SOURCE / "skills").glob("*/SKILL.md"))


def body(path):
    text = path.read_text()
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError(f"Invalid manifest: {path}")
    return text.split("\n---\n", 1)[1].strip() + "\n"


def check_source():
    lock = read_json(PORT / "upstream.lock")
    if inventory() != lock["files"]:
        raise ValueError("Unreviewed upstream changes: review source and refresh upstream.lock explicitly")
    recipes = read_json(PORT / "overrides/recipes.json")
    names = source_skills()
    expected = set(recipes) | {n for n in names if n.startswith("principle-")}
    if set(names) != expected:
        raise ValueError("Skill coverage changed; add/remove adaptations before release")
    playbooks = read_json(PORT / "overrides/playbooks.json")
    actual = {p.stem for p in (SOURCE / "skills/poteto-mode/playbooks").glob("*.md")}
    if set(playbooks) != actual:
        raise ValueError("Playbook coverage changed; review adaptations before release")
    return lock, recipes, names, playbooks


def adapted_principle(name):
    if name == "principle-never-block-on-the-human":
        return "# Bounded initiative\n\nWork without unnecessary interruptions inside the human's authorized scope.\nA reversible action is not automatically authorized. Ask at most one question\nand stop after asking. Never bypass a requested checkpoint. External writes,\npermission changes, deletion and publication require applicable authorization.\n"
    if name == "principle-guard-the-context-window":
        return "# Protect the context window\n\nSearch narrowly, read relevant regions and keep evidence summaries compact.\nDo not create subagents merely because a payload is large. Use authorized native\nworkers only when the human explicitly requests them; otherwise process bounded\nslices sequentially. Preserve source pointers and do not hide validation gaps.\n"
    text = body(SOURCE / "skills" / name / "SKILL.md")
    return re.sub(r"\]\(\.\./([a-z0-9-]+)/", r"](../pstack-\1/", text)


def build(host, output=None):
    if host not in HOSTS:
        raise ValueError("Unknown host")
    lock, recipes, names, playbooks = check_source()
    output = Path(output or DIST / host)
    output.parent.mkdir(parents=True, exist_ok=True)
    catalog = [{"name": "pstack-" + n, "upstream": n,
                "kind": "principle" if n.startswith("principle-") else "workflow"}
               for n in names]
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        staging = Path(tmp) / "bundle"
        for name in names:
            skill = staging / "skills" / ("pstack-" + name)
            refs = skill / "references"
            refs.mkdir(parents=True)
            instructions = adapted_principle(name) if name.startswith("principle-") else (
                "# " + name + "\n\n" + "\n".join(f"{i}. {step}" for i, step in enumerate(recipes[name], 1)) + "\n")
            first = (recipes.get(name) or [instructions.split("\n\n", 1)[-1]])[0].split("\n")[0]
            description = f"Opt-in pstack {name}: " + first[:260]
            url = f"https://github.com/cursor/plugins/blob/{lock['commit']}/pstack/skills/{name}/SKILL.md"
            content = (f"---\nname: pstack-{name}\ndescription: {json.dumps(description)}\n---\n\n"
                       "Read [runtime contract](references/policy.md) and [host adapter](references/host.md) first.\n"
                       "Activate only on an explicit human pstack request or routing from an already invoked pstack skill.\n"
                       "The runtime contract applies to every step. Other skills live in sibling pstack-* folders.\n\n"
                       + instructions + f"\nOriginal methodology: [poteto's source]({url}).\n"
                       "This is a reviewed functional port, not an identical copy of the original runtime.\n")
            (skill / "SKILL.md").write_text(content)
            shutil.copy2(PORT / "policy.md", refs / "policy.md")
            shutil.copy2(PORT / "adapters" / (host + ".md"), refs / "host.md")
            shutil.copy2(SOURCE / "LICENSE", skill / "LICENSE")
            write_json(refs / "catalog.json", catalog)
            if name == "poteto-mode":
                write_json(refs / "playbooks.json", playbooks)
                (refs / "principles.md").write_text("# Principles\n\n" + "\n".join(
                    f"- [{n}](../../pstack-{n}/SKILL.md)" for n in names if n.startswith("principle-")) + "\n")
            if name == "show-me-your-work":
                (skill / "scripts").mkdir()
                shutil.copy2(PORT / "log.py", skill / "scripts/log.py")
            if host == "codex":
                (skill / "agents").mkdir()
                (skill / "agents/openai.yaml").write_text("policy:\n  allow_implicit_invocation: false\n")
        manifest = {"port_version": VERSION, "host": host,
                    "upstream_version": lock["version"], "upstream_commit": lock["commit"],
                    "skills": catalog, "files": inventory(staging)}
        write_json(staging / "manifest.json", manifest)
        if output.exists():
            if output.is_symlink() or output.parent.resolve() != DIST.resolve():
                raise ValueError("Refusing to replace a non-managed output directory")
            shutil.rmtree(output)
        shutil.move(str(staging), output)
    return output


def validate(bundle):
    bundle = Path(bundle)
    manifest = read_json(bundle / "manifest.json")
    actual = inventory(bundle)
    actual.pop("manifest.json", None)
    if actual != manifest["files"]:
        raise ValueError("Bundle integrity mismatch")
    names = [x["name"] for x in manifest["skills"]]
    for name in names:
        path = bundle / "skills" / name / "SKILL.md"
        text = path.read_text()
        if not re.fullmatch(r"[a-z0-9-]{1,64}", name) or f"name: {name}\n" not in text:
            raise ValueError(f"Invalid skill name: {name}")
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if not link.startswith("https://") and not (path.parent / link.split("#")[0]).exists():
                raise ValueError(f"Broken link in {name}: {link}")
    return manifest


def default_destination(surface):
    home = Path.home()
    paths = {"codex": home / ".codex/skills", "antigravity": home / ".gemini/config/skills",
             "antigravity-cli": home / ".gemini/antigravity-cli/skills",
             "antigravity-ide": home / ".gemini/antigravity/skills"}
    return paths[surface]


def install(bundle, destination, apply=False):
    destination = Path(destination).expanduser().absolute()
    if destination.is_symlink():
        raise ValueError("Refusing to install through a destination symlink")
    if not apply:
        return _install(bundle, destination, False)
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / ".pstack-install.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _install(bundle, destination, True)


def _install(bundle, destination, apply=False):
    bundle, destination = Path(bundle), Path(destination).expanduser().absolute()
    manifest = validate(bundle)
    marker = destination / ".pstack-install.json"
    old = read_json(marker) if marker.exists() else {"owned": [], "files": {}}
    names = [x["name"] for x in manifest["skills"]]
    owned = set(old["owned"])
    if any(not re.fullmatch(r"pstack-[a-z0-9-]{1,57}", n) for n in owned):
        raise ValueError("Invalid installation ownership record")
    for name in names:
        target = destination / name
        if target.is_symlink() or (target.exists() and name not in owned):
            raise ValueError(f"Unmanaged collision, nothing changed: {target}")
    for name in owned:
        target = destination / name
        if not target.exists() or target.is_symlink() or inventory(target) != old["files"].get(name):
            raise ValueError(f"Locally modified skill, nothing changed: {target}")
    plan = {"destination": str(destination), "count": len(names), "apply": apply,
            "upstream_version": manifest["upstream_version"], "port_version": VERSION}
    if not apply:
        return plan
    destination.mkdir(parents=True, exist_ok=True)
    # Keep old SKILL.md files outside discovery roots to avoid duplicate skills.
    backups = destination.parent / ".pstack-backups" / destination.name
    backups.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix="install-", dir=backups))
    changes = sorted(owned | set(names))
    record = {"destination": str(destination), "changed": changes,
              "present": [n for n in changes if (destination / n).exists()],
              "marker": marker.exists()}
    write_json(backup / "rollback.json", record)
    if marker.exists():
        shutil.copy2(marker, backup / marker.name)
    for name in record["present"]:
        shutil.copytree(destination / name, backup / name)
    try:
        for name in changes:
            target = destination / name
            if target.exists():
                shutil.rmtree(target)
            if name in names:
                shutil.copytree(bundle / "skills" / name, target)
        state = {"host": manifest["host"], "port_version": VERSION,
                 "upstream_commit": manifest["upstream_commit"], "owned": names,
                 "files": {n: inventory(destination / n) for n in names},
                 "backup": str(backup)}
        write_json(marker, state)
    except Exception:
        restore_record(backup, record)
        raise
    return {**plan, "backup": str(backup)}


def restore_record(backup, record):
    destination = Path(record["destination"])
    marker = destination / ".pstack-install.json"
    for name in record["changed"]:
        target = destination / name
        if target.exists():
            shutil.rmtree(target)
        if name in record["present"]:
            shutil.copytree(backup / name, target)
    if record["marker"]:
        shutil.copy2(backup / marker.name, marker)
    elif marker.exists():
        marker.unlink()


def rollback(backup, apply=False):
    backup = Path(backup).absolute()
    record = read_json(backup / "rollback.json")
    destination = Path(record["destination"])
    if backup.parent != destination.parent / ".pstack-backups" / destination.name:
        raise ValueError("Invalid backup location")
    names = record["changed"]
    if any(not re.fullmatch(r"pstack-[a-z0-9-]+", n) for n in names):
        raise ValueError("Invalid rollback ownership")
    marker = destination / ".pstack-install.json"
    current = read_json(marker) if marker.exists() else {}
    if current and current.get("backup") != str(backup):
        raise ValueError("Not the current installation backup")
    for name in names:
        target = destination / name
        if target.is_symlink():
            raise ValueError("Refusing rollback through a symlink")
        if current and target.exists() and inventory(target) != current["files"].get(name):
            raise ValueError("Refusing to remove local edits; preserve them first")
    if apply:
        with (destination / ".pstack-install.lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            restore_record(backup, record)
    return {"destination": str(destination), "restored": len(names), "apply": apply}


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def lock_source(commit, reviewed=False):
    if not reviewed or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("A full commit SHA and --reviewed are required")
    # This command acknowledges review; it never fetches or rewrites the source tree.
    if git("diff", "--name-only", commit, "--", "pstack"):
        raise ValueError("pstack working tree does not match the selected upstream commit")
    version = read_json(SOURCE / "plugin.json")["version"]
    write_json(PORT / "upstream.lock", {"repository": "cursor/plugins", "commit": commit,
               "version": version, "files": inventory()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    b = commands.add_parser("build"); b.add_argument("--host", choices=HOSTS, required=True)
    v = commands.add_parser("validate"); v.add_argument("bundle", type=Path)
    i = commands.add_parser("install"); i.add_argument("--surface", required=True,
            choices=("codex", "antigravity", "antigravity-cli", "antigravity-ide"))
    i.add_argument("--destination", type=Path); i.add_argument("--apply", action="store_true")
    r = commands.add_parser("rollback"); r.add_argument("backup", type=Path); r.add_argument("--apply", action="store_true")
    l = commands.add_parser("lock"); l.add_argument("--commit", required=True); l.add_argument("--reviewed", action="store_true")
    commands.add_parser("check-source")
    args = parser.parse_args()
    if args.command == "build":
        result = {"bundle": str(build(args.host))}
    elif args.command == "validate":
        m = validate(args.bundle); result = {"host": m["host"], "skills": len(m["skills"]), "integrity": "verified"}
    elif args.command == "install":
        host = "codex" if args.surface == "codex" else "antigravity"
        result = install(DIST / host, args.destination or default_destination(args.surface), args.apply)
    elif args.command == "rollback":
        result = rollback(args.backup, args.apply)
    elif args.command == "lock":
        lock_source(args.commit, args.reviewed); result = {"reviewed_commit": args.commit}
    else:
        lock, _, names, _ = check_source(); result = {"version": lock["version"], "skills": len(names)}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        print(f"pstack: {error}", file=sys.stderr)
        sys.exit(1)
