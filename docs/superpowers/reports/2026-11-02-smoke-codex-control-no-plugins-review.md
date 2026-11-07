# LAD-175 smoke-codex-control-no-plugins: review report

Pull request #204 `hotfix/lad-175-smoke-codex-plugins` → `main`. Scale: hotfix, review
depth: precision. Head reviewed: `be790b8f` (= the remote head). The control `codex exec`
of the smoke test `test_a_codex_agent_gets_none_of_codex_s_own_subagents` runs with
`-c features.plugins=false`, so it starts no background sync of Codex's curated plugins
catalogue (`git ls-remote https://github.com/openai/plugins.git`) that outlived the test;
the living spec `codex-agent-turns` says so in its scenario "A model whose metadata turns
the subagents on". Only tests and openspec changed.

## Rounds

- **Round 1** (`228a1de2..be790b8f`): local precision with a check against the spec, and
  external 1 of 1 (Claude Code GitHub Action), which read every file of the diff
  (`proposal.md` in part: its why, cause and options). No blocking or important findings.

External rounds used: 1 of 1 (the hotfix cap). The external reviewer is of the same model
family, so its "no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| N1 | — | external: one CI sample without the leak proves little; if "processes left" returns, look for other background network work of Codex | dropped: a second CI sample (run 41521506385) was green on both Codex smoke cells, and the manual check below shows the mechanism gone |
| N2 | — | external: "none of LADO's config" is worded precisely | dropped: the reviewer itself called it no defect |

## Checks

- `openspec validate smoke-codex-control-no-plugins --strict` valid; tasks 4/4.
- Manual check with codex-cli 0.162.0: a plain `codex exec` with the smoke's user config
  leaves `CODEX_HOME/.tmp/plugins` (the catalogue cloned); with
  `-c features.plugins=false` no `.tmp` at all.
- CI run 41518779635 (head `68f2010a`): all green; the Codex smoke on Linux and macOS
  8 passed each, no "processes left".
- CI run 41521506385 (head `be790b8f`): attempt 1 lost two macOS cells (claude, opencode)
  to GitHub not assigning a runner; rerun of the failed jobs green, `ci-ok` success. The
  Codex smoke green on both systems again.
- Not run locally: `make lint`, `make test`, the integration tests (no LADO code changed;
  CI ran them green); `make test-smoke` as a whole (excluded by the settings; CI ran it).

## Residual risk

- The flake depended on GitHub's latency, so CI's proof is statistical (two green samples
  per system); the manual check shows deterministically that with the flag Codex starts no
  catalogue sync. Other background network work a future Codex adds at start would be
  named by the teardown.
