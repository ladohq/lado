## 1. The smoke's limit

- [ ] 1.1 By hand, before the fix: in `tests/smoke/conftest.py`'s `smoke_provider`, set
  `monkeypatch.setattr(base, "MODEL_LIST_TIMEOUT", 0.5)` and run
  `uv run pytest -m smoke -n0 -k "session_s_model_reaches_the_cli and kilo"`: it fails with
  `` `kilo models` timed out after 0.5 s `` (AC-2). Quote the failure in the build report.
- [ ] 1.2 `tests/smoke/conftest.py`: `smoke_provider` sets `base.MODEL_LIST_TIMEOUT` to 60 for
  every provider, with a one-line comment (the users' 15 s is too tight for a fresh CLI home
  beside two other workers on a CI runner, LAD-295) (AC-1). The same command as 1.1 passes;
  quote it.
- [ ] 1.3 `make test-smoke PROVIDER=kilo`, its exit status read (not piped) (AC-3).

## 2. Docs

- [ ] 2.1 `docs/testing.md`, the smoke paragraph: the smoke gives a CLI's list command 60 s, not
  the users' 15 s (`base.MODEL_LIST_TIMEOUT`), as a fresh home makes `kilo models` fetch its
  list on a runner shared by three workers. Check: read it.

## 3. Regression run

- [ ] 3.1 `make lint`, `make test`, `openspec validate smoke-model-list-time --strict`, the
  trial archive; CI of the pull request green, `smoke macos-latest kilo` on its first attempt
  (AC-4).
