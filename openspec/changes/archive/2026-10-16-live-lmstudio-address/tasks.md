## 1. The LM Studio config of the test

- [x] 1.1 `tests/local_models.py`: `write_lmstudio_config(provider, model, folder)` writes
  `<folder>/<provider>-config.json` with `opencode_config(model, f"{lmstudio_url()}/v1")`
  and returns `{CONFIG_VARIABLES[provider]: str(path)}`, as `write_endpoint_config` does
  for the endpoint. Check: `uv run pytest -n0 tests/test_local_models.py`.
- [x] 1.2 `tests/test_local_models.py`: for `kilo` and `opencode`, with
  `LADO_LIVE_LMSTUDIO_URL` unset and set to `http://127.0.0.1:9/`, the returned variable is
  the CLI's, the file's `model` is the given one and
  `provider.lmstudio.options.baseURL` is `http://127.0.0.1:1234/v1` and
  `http://127.0.0.1:9/v1`. Check: red once against a `write_lmstudio_config` that drops
  `/v1`, then green with `uv run pytest -n0 tests/test_local_models.py`.
- [x] 1.3 `tests/live/conftest.py`: the LM Studio branch of `live_provider` for OpenCode
  and Kilo sets the variables `write_lmstudio_config` returns, with no inline config left.
  Check: `make lint`, `uv run pytest -m live --collect-only -q tests/live` collects.

## 2. Checks

- [x] 2.1 `make lint` and `make test` green (counts in the build report).
- [x] 2.2 Live on LM Studio (`lms server start`; `lms load qwen/qwen3.5-35b-a3b
  --context-length 65536 -y`): `make test-live PROVIDER=kilo` and `make test-live
  PROVIDER=opencode` pass, no test skipped; LM Studio's log has no `Unexpected endpoint`
  for their requests. A skip is no pass: report it as not run. Never Claude Code's live
  test.
