Task: LAD-97

## Why

An empty `LADO_HOME/server-token` makes the UI server's token the empty string, and the
server then lets anyone in: `Authorization: Bearer ` (nothing after it) gets 200, `/?token=`
answers 303 and sets the cookie, and `lado ui` prints a link `?token=` with no value. Found
by hand while checking PR #93 (LAD-93); main has it too.

Symptom: a server started on an empty token file accepts an empty token.

Root cause, in `src/lado/server/auth.py`:

1. `token()` creates the file (`O_CREAT | O_EXCL`) and only then writes the token into it.
   When the write fails (ENOSPC: the disk is full; a kill between the two steps) an empty
   file stays behind.
2. On the next start `path.exists()` is true, `read_text().strip()` gives `""`, and that is
   the token: nothing checks that it is not empty.
3. `Guard._valid` compares the given string with the token by `compare_digest`, and `""`
   equals `""`.

Options weighed (long-term cost):

- A. Only make `Guard` refuse an empty token: closes the hole, but the server then refuses
  every request, and the human is stuck until they find `lado server --new-token`; the
  empty file is still made by a failed write. Cheap now, a support question later.
- B. (chosen) Treat an empty file as no file and make a new token, write the token
  atomically (a temporary file in `LADO_HOME`, then `os.replace`), and make `Guard` refuse
  an empty token, both given and its own. Three small guards in the one module that checks
  tokens; nothing to maintain afterwards. Holds against the roadmap: `auth.py` stays the
  only place that checks who may call the server, and a real login replacing it later
  replaces these lines too.
- C. Check the token's shape (length, alphabet) and replace any token that fails it:
  discards a token a human wrote into the file on purpose, a rule no one asked for
  ("only what is used").

## What Changes

- `auth.token()`: a file whose content is empty or whitespace only counts as missing, and a
  new token is made and written (the human sees nothing but a new token; any old cookie was
  for the empty one and fails anyway).
- `auth.token()` writes the token atomically: into a temporary file in `LADO_HOME`, owner
  only (0600), then `os.replace` over `server-token`. A failed write leaves the old file
  as it was (or none), removes the temporary file, and raises `LadoError` naming the path
  and the reason (`cannot write the UI server's token to <path>: <reason>`), so
  `lado server` stops with that line instead of a traceback, and `lado ui` too.
- `Guard` refuses an empty token: `Guard("", port)` raises `ValueError` (a programming
  error, never reached through `token()`), and `_valid` returns false for an empty given
  token, so `Bearer ` and `?token=` are 401 whatever the token.
- A new living spec `ui-server-token` holds these rules.
- docs/design/ui.md, "Token": one sentence that an empty file is replaced by a new token and
  that the file is written atomically.
- CHANGELOG.md: a line under `## 0.40.1 (unreleased)`.

## Scope

- `src/lado/server/auth.py`, `tests/test_server.py`, docs/design/ui.md, CHANGELOG.md, the
  delta of `ui-server-token`.

## Out of scope

- A token file emptied by hand while the server runs: the server keeps its token in memory,
  so `lado ui` makes a new one and prints a link the running server refuses (401) until
  `lado server stop` and a new start. Only an outside hand gets the file there once the
  write is atomic; a restart fixes it.
- Checking the token's shape (option C): it would throw away a token a human set on
  purpose; no one asked for it.
- Two processes making the first token at the same moment: `lado server` makes it under the
  server's lock before `lado ui` can reach the server; unchanged by this change (the old
  code had the same window).
- A real login and TLS: a later roadmap stage replaces this module whole.

## Impact

- Product code: `auth.py` only. No API, MCP, CLI option or schema change. A patch release
  (0.40.1).
- Users: a server whose token file was left empty gets a new token on its next start; the
  old link with an empty token no longer opens the UI, `lado ui` prints a working one.
- Neutral core: the server's token has nothing to do with agent CLIs; every provider is the
  same.
- Test layer: unit (`tests/test_server.py`), the lowest that catches it: `token()` and
  `Guard` are pure functions of a file and a request, the FastAPI `TestClient` covers the
  HTTP answers; no process boundary is crossed.
