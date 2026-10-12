# Port maintenance

- Preserve upstream `pstack/` files except in an explicitly scoped upstream-sync review.
- Keep common recipes in overrides/ and platform mechanics in adapters/; never edit dist/.
- New/changed upstream source must fail the fingerprint gate until reviewed. Never refresh
  upstream.lock automatically in CI or to silence a failing test.
- Use Conventional Commits without Co-Authored-By or other AI attribution trailers.
- No subagents unless explicitly requested by the human. Ask one question and stop.
- Tests run with `python3 -m unittest discover -s ports/pstack/tests -v` from the repo root.
- No third-party Python dependencies, credentials, global permission edits or native agent
  registrations are required. Never publish personal paths or transcripts in the fork.
- Keep backups outside skill discovery roots. Install/rollback must reject local edits and
  preserve unrelated skills. Model behavior is not proven by text assertions.
- New GitHub PRs must link an issue authorized for preparation and have one type:* label.
- Existing upstream attribution and license notices stay intact; the no-attribution rule
  concerns new commit trailers, not rewriting history or deleting legal notices.
