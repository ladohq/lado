# LAD-166 codex-shared-login: review report

Pull request #189 `feature/lad-166-codex-shared-login` → `main`. Scale: full; it also
closes LAD-152. Head reviewed last: `f371fa24` (= the remote head, `origin/main` `7831c65c` merged in). Every Codex agent's
`auth.json` is a link to the user's Codex login file (or a file of its own with
`OPENAI_API_KEY`), so one login serves all agents; Codex's sheet asks how the human pays
(sign-in code, access token, API key) and offers Log out; a model that needs a login
refuses a start or waits for it; the agent's config trusts its repository and the
repository's hooks, and switches Codex's plugins off. `providers/`, `runtime.py` and
`tests/live/` changed: the live test of the shared login was run by the developer on a
real ChatGPT account.

## Rounds

- **Round 1** (`a3e4c687..b888e23d`): a local pass in breadth and external 1 of 2 (Claude
  Code GitHub Action). F3 important, F1, F2, F8 minor; F4-F7 refuted.
- **Round 2** (`b888e23d..cde86bbb`): a local precision pass over the fixes; external 2
  of 2: no blocking findings, one nit (F9).
- **Round 3** (`cde86bbb..3f4dc45d`), after the human's no at `merge_ok` (the live test
  failed): the live test fixed, LADO's code unchanged. A running Codex keeps its login in
  memory, so each agent now starts on a stale file and must refresh through its link; the
  inode, the links and `codex login status` are checked after each. F10 minor.
- **Round 4** (`3f4dc45d..6112431a`), after the first archive failed strict validation
  (three modified requirements over 500 characters): the requirements cut to their rule,
  the details moved to scenarios, the container's Codex login made a requirement of its
  own. Meaning checked against the old text; no new findings; no external round: the cap
  of 2 was used.
- **Round 5** (`6112431a..f371fa24`), after the merge of `origin/main` (LAD-158,
  agent-cli-install-check) conflicted in `openspec/specs/container/spec.md`: the archive
  `de53f68f` checked (the change moved unchanged, the deltas in the living specs, the
  removed requirement gone), and the merge keeps both new requirements whole ("The headers
  say how Codex logs in", "The image's build runs each agent CLI it installs" with its
  three scenarios). No new findings; no external round.

External rounds used: 2 of 2. The external reviewer is of the same model family, so its
"no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F3 | important | `needs_login` crashed on a user's Codex config of odd types (Traceback in `lado doctor`, the refusal, the login wait) | fixed in `cde86bbb` (`_as_table`), with tests |
| F1 | minor | A link LADO could not make warned "it starts all the same", while an agent on OpenAI's model then waits for its login | fixed in `cde86bbb` |
| F8 | minor | Uneven wrapping in `login_wait.py`'s docstring | fixed in `cde86bbb` |
| F2 | minor | `provider_check._row` reads `capabilities.needs_login` | declined: a placeholder row of the unknown state, no visible effect |
| F9 | minor | external nit: a comment that `name` is a string | declined: the reviewer called it optional |
| F10 | minor | A 136-character line in `docs/testing.md` | declined: Markdown layout only |
| F4 | — | external: any repository's hooks are trusted without asking | refuted: the human's decision (#2163), as Claude's `.mcp.json` (LAD-163) |
| F5-F7 | — | external: the link without `user-codex-home`, a dangling link, a Log out fallback in ChoiceSheet | refuted against the code and the spec |

## Checks

- On `f371fa24`: `make lint` green; `make test` 4689 passed, 7 skipped;
  `tests/test_docker.py` 101 passed, 1 skipped; `openspec validate --specs --strict`
  53/53; CI 23/23 with `ci-ok`, integration, UI, container and the smoke of every CLI.
- On `6112431a`: `openspec validate codex-shared-login --strict` valid.
- On `cde86bbb` (LADO's code unchanged since): `make test` 4680 passed, 7 skipped;
  integration `test_provider_logins` 11 passed.
- Live: `tests/live/test_codex_login.py` 1 passed on `3f4dc45d`, by the developer's report
  only.

## Residual risk

- The live run is confirmed by the developer's report alone.
- The external reviewer did not read `docker/Dockerfile` and `docker/compose.yaml`; only
  their comments changed, read locally and checked by `test_docker.py`.
- The screenshots were taken with the fake agent.
- For the human: `OPENAI_API_KEY` wins over the ChatGPT login (the approved spec), so a key
  put in `secrets/` for OpenCode or Kilo makes Codex agents pay per use too; any
  repository's hooks, a cloned one too, run without asking (F4).
