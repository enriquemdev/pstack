# Codex adapter

Invoke a skill as `$pstack-how` or explicitly ask to use `pstack-how`.
Use `$pstack-poteto-mode` for the routing entrypoint. It applies to the current
task only; do not assume Cursor custom modes or `/loop` exist.

- File operations: use the host file/shell tools, respecting its permissions.
- Task tracking: use a native plan tool if available, otherwise a compact checklist.
- GitHub: prefer connected GitHub tools, then an authenticated CLI. If CLI auth fails,
  report it; do not read tokens from caches. Attach any created PR using the host's
  artifact tool when available.
- History: use native chat read tools and Engram, scoped to the requested project.
- Verification: use the project's actual test/runtime harness and the available browser
  or device tools. Do not use Cursor control-ui/control-cli or Cursor cloud agents.
- Delegation: only after explicit human authorization, use native collaboration tools
  advertised in this session. Do not assume arbitrary model overrides or named personas
  are registered. If no delegation tool exists, stop that parallel operation or offer
  a clearly labeled sequential alternative; never simulate an independent worker.
- Skills installed here have `agents/openai.yaml` with implicit invocation disabled,
  preserving upstream's opt-in policy. Explicit references from another pstack skill
  remain usable. Prefer sibling `../pstack-<name>/SKILL.md` paths for internal routing.

Read `references/policy.md` before executing the skill. Do not modify global Codex
configuration, permissions or model settings as part of a task.
