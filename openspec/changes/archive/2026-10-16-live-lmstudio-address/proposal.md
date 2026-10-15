Task: LAD-56

## Why

At 0.38.0rc1 every live test of Kilo and OpenCode on LM Studio failed (0 of 3), by a
defect of the tests, not of LADO. LM Studio's log says `Unexpected endpoint or method.
(POST /chat/completions). Returning 200 anyway.`: the CLIs post to LM Studio's root, not
to its OpenAI-compatible API under `/v1`.

Root cause: `tests/live/conftest.py` (`live_provider`, the LM Studio branch for OpenCode
and Kilo) passes `local_models.lmstudio_url()`, LM Studio's root without `/v1`, as the
base URL of `local_models.opencode_config`. Since commit 6a6a5f9 (live tests on a remote
endpoint) `opencode_config` takes the base URL as given, since a remote endpoint's
`LADO_LIVE_ENDPOINT` ends in `/v1` already; the LM Studio caller was not changed with it.
No unit test covers that caller: the conftest's branch builds the config inline, and
`tests/test_local_models.py` tests `opencode_config` only with a URL it gives itself.

## What Changes

- `tests/local_models.py` gets `write_lmstudio_config(provider, model, folder)`, the LM
  Studio counterpart of `write_endpoint_config`: it writes OpenCode's or Kilo's config file
  of the test in `folder` with the base URL `lmstudio_url() + "/v1"` and returns the
  variable to set (`OPENCODE_CONFIG` or `KILO_CONFIG`) with the file's path.
- `tests/live/conftest.py`'s LM Studio branch for OpenCode and Kilo calls it instead of
  building the config inline.
- `tests/test_local_models.py` pins it, with no model and no LM Studio: for both CLIs the
  file's `provider.lmstudio.options.baseURL` is `<LADO_LIVE_LMSTUDIO_URL>/v1` (the default
  and an overridden URL with a trailing `/`), the model is the one given, and the variable
  is the CLI's.
- Checked live: `make test-live PROVIDER=kilo` and `make test-live PROVIDER=opencode` pass
  on LM Studio (`local_models.MODEL`, free).
- No version bump and no CHANGELOG line: only tests change, nothing a user of LADO sees.

## Scope

- `tests/local_models.py`, `tests/live/conftest.py`, `tests/test_local_models.py`.

## Out of scope

- `opencode_config` appending `/v1` itself: a remote endpoint's URL ends in `/v1` by its
  contract (AGENTS.md, Live tests), so a second rule of who adds it would come back as
  this defect's twin; the URL stays the caller's.
- The Codex bridge (`Bridge.start`, `api_base: {upstream}/v1`): it adds `/v1` itself and
  works; changing it is no part of this defect.
- Claude Code's live test: paid, only with the human's yes; it does not use LM Studio.
- The Codex live test on LM Studio: not affected (it goes through the bridge).
- An integration or UI test: the defect is in the live tests' setup, which a unit test of
  `local_models` catches without a model.

## Impact

- Tests only. No product code, no API, CLI, MCP or schema change.
- `make test` runs the new unit test; CI runs it on every push.
