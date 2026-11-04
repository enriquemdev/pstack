# Claude Code port of the pstack dependencies

pstack has an official Claude Code plugin in `cursor/plugins`. It does not include
three skills that `poteto-mode` references, because they ship in `cursor-team-kit`,
which that marketplace does not publish for Claude Code. This port fills that gap.

| Skill | Invocation |
|---|---|
| `deslop` | `/cursor-team-kit:deslop` |
| `control-cli` | `/cursor-team-kit:control-cli` |
| `control-ui` | `/cursor-team-kit:control-ui` |

The rest of `cursor-team-kit` is not included.

## Fidelity

`build.py` copies the skills byte for byte from `cursor-team-kit/`. The build fails if
a skill uses a Cursor-specific name, using the term list of the official generator
(`scripts/generate-pstack-harness-trees.mjs`) plus any literal mention of Cursor. Only
the manifest is new: it moves from `.cursor-plugin/` to `.claude-plugin/` and its
description names the subset.

## Install

Install pstack from the official source, then this plugin from a clone of this repository:

```sh
claude plugin marketplace add cursor/plugins
claude plugin install pstack@cursor-plugins
claude plugin marketplace add ./ports/claude
claude plugin install cursor-team-kit@pstack-claude-ports
```

## Update

After `cursor-team-kit/` changes, run the following from the repository root:

```sh
python3 ports/claude/build.py
python3 -m unittest discover -s ports/claude/tests -v
claude plugin marketplace update pstack-claude-ports
claude plugin update cursor-team-kit@pstack-claude-ports
```

Claude Code detects an update through the manifest `version`, which comes from the
source. If the skills change without a new version, reinstall the plugin.
