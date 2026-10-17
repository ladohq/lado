## 1. Tests first (red on main)

- [x] 1.1 `tests/test_server.py`, `test_an_empty_token_file_gets_a_new_token`: write `""`
  and then `"  \n"` to `state.home() / "server-token"`; `auth.token()` returns a token of at
  least 32 characters, the file holds it, its mode is 0600, and a second `auth.token()`
  returns the same. Check: red on main, `uv run pytest -n0 tests/test_server.py -k empty`.
- [x] 1.2 `test_a_failed_token_write_leaves_the_file_and_no_temporary_file`: with a token
  already in the file, make the write fail (monkeypatch `os.write`, or the file object's
  `write`, to raise `OSError(errno.ENOSPC, ...)`) and call `auth.token(new=True)`:
  `LadoError` whose text has `cannot write the UI server's token to` and the path; the file
  still holds the old token; `LADO_HOME` lists no other new file. Same with no file before:
  still no `server-token`. Check: red on main.
- [x] 1.3 `test_the_server_refuses_an_empty_token`: with the normal `client` fixture,
  `Authorization: Bearer ` (nothing after) on `/api/sessions` is 401; `/?token=` is 401 with
  no `set-cookie`; an empty cookie `lado_token_<PORT>=""` is 401. Check: green on main for
  a non-empty token (they guard `_valid`), and red on main for a guard built on `""`:
  add the case `auth.Guard("", PORT)` raises `ValueError`.

## 2. The fix

- [x] 2.1 `src/lado/server/auth.py`, `token()`: read the file when it exists; an empty or
  whitespace-only content counts as missing. A new token goes through a helper that writes
  it atomically: `tempfile.mkstemp(dir=<LADO_HOME>, prefix=".server-token.")` (0600),
  write, flush, `os.replace` over `token_path()`; on `OSError` remove the temporary file
  and raise `LadoError(f"cannot write the UI server's token to {path}: {error.strerror or
  error}")` from it. Drop the old `unlink` + `O_EXCL`. Update the module's docstring
  (empty file, atomic write). Check: 1.1 and 1.2 green.
- [x] 2.2 `Guard.__init__` raises `ValueError` on an empty token; `Guard._valid` returns
  false for an empty or missing given token. Check: 1.3 green.
- [x] 2.3 docs/design/ui.md, "Token": add that an empty file counts as missing and gets a
  new token, and that the file is written atomically (temporary file, then a rename).
- [x] 2.4 CHANGELOG.md, under `## 0.40.1 (unreleased)`: the UI server no longer lets
  anyone in when `LADO_HOME/server-token` is empty (left by a failed write, e.g. a full
  disk): an empty file gets a new token, the token is written atomically, and an empty
  token is always refused.

## 3. Checks

- [x] 3.1 `make lint`, `make test` green (counts in the build report);
  `openspec validate server-token-never-empty --strict` and
  `openspec validate --specs --strict` green.
- [x] 3.2 By hand: `LADO_HOME=$(mktemp -d)`; `: > "$LADO_HOME/server-token"`;
  `uv run lado server --port <free port>` in one shell; `uv run lado ui --no-open` prints a
  link with a non-empty token; `curl -s -o /dev/null -w '%{http_code}' -H 'Authorization:
  Bearer ' http://127.0.0.1:<port>/api/sessions` prints 401. Put these steps in the pull
  request's description.
