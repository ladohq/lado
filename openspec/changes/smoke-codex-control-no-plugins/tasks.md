## 1. The fix

- [ ] 1.1 `tests/smoke/test_smoke.py`, `test_a_codex_agent_gets_none_of_codex_s_own_subagents`,
  requirement "A Codex agent has none of Codex's own subagents", scenario "A model whose
  metadata turns the subagents on": the control `codex exec` runs as
  `["codex", "exec", "--skip-git-repo-check", "-c", "features.plugins=false", "hi"]`, with
  a comment saying why: Codex 0.162 syncs OpenAI's curated plugins catalogue at its start
  (`git ls-remote https://github.com/openai/plugins.git`, then a clone) in the background,
  `codex exec` ends before it, and the orphan outlived the test (LAD-175). The docstring's
  "a plain `codex exec`" says its plugins are off. Nothing else in the test changes; the
  assertion that the control gets `collaboration.wait_agent` stays.

## 2. Checks

- [ ] 2.1 `make lint`; `openspec validate smoke-codex-control-no-plugins --strict`;
  `openspec validate --specs --strict`.
- [ ] 2.2 The Codex smoke locally, where the real `codex` (0.162.0) is installed:
  `uv run pytest -m smoke -n0 "tests/smoke/test_smoke.py::test_a_codex_agent_gets_none_of_codex_s_own_subagents[codex]"`
  passes, its teardown names no process, and the control's tools still hold
  `collaboration.wait_agent`. Then the whole Codex smoke file once:
  `uv run pytest -m smoke -n0 tests/smoke/test_smoke.py -k codex`.
- [ ] 2.3 On the pull request: CI's smoke cells `smoke ubuntu-latest codex` and
  `smoke macos-latest codex` are green with no "processes left after the test" (the pull
  request changes `tests/smoke/`, which is off ci.yml's skip list, so the smoke runs).
