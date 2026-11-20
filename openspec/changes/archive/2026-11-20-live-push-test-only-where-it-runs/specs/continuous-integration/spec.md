## MODIFIED Requirements

### Requirement: A live cell passes only with a pass and no skip

A live cell (`scripts/smoke_ci.py live <provider> <out>`) SHALL install its provider's CLI at
its pin as a smoke cell does, run that provider's live tests without
`tests/live/test_codex_login.py`, and pass only when pytest exits 0 and its summary has a pass
and no skip.

#### Scenario: The key is missing

- **WHEN** the environment gives no key and the live tests skip
- **THEN** the cell fails

#### Scenario: The image test skips

- **WHEN** `LADO_LIVE_IMAGE` is unset and the image test skips
- **THEN** the cell fails

#### Scenario: A test meant for some providers only

- **WHEN** a live test is meant for Claude Code and Codex only, as
  `test_an_agent_pushes_through_a_saved_git_server`
- **THEN** it is not collected for OpenCode and Kilo, and their cells pass with their other
  tests passed and none skipped
