## 1. The test

- [x] 1.1 `tests/test_server_providers.py`, `test_a_saved_key_replaces_lados_token_and_beats_the_outside_folders`
  (unit): `monkeypatch.setattr(provider_check, "start", lambda: True)` before its first save;
  in place of the `[-1]` of the filtered list, `assert {argv[0] for argv, _ in
  cli_logins.calls} == {"claude"}` and `_, env = cli_logins.calls[-1]`; the comment loses its
  line about the other CLIs. The assertion on `env` stays as it is.
- [x] 1.2 The node id passes 20 times in a row with `-n0`; say so in `build-report`.
- [x] 1.3 `make lint` and `make test` green; report the tests as numbers.
