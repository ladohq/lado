# Trusting a git server's certificate: design

Task: LAD-301. Change: `openspec/changes/git-server-certificate/` (proposal, deltas of
`git-servers`, `git-servers-page`, `session-clone`, `doctor`, and `design.md` with decisions
D1–D14). Mockup: the run's `mockup-certificate.html` (§1–§13), after the human's decisions
#7481–#7487 (relayed in #7489): the main path is Check → "Trust this server?" with the
certificate taken from the server; no file in the UI; `gh` later.

## What the human sees

### Settings → Git servers

- **Check, not trusted** (mockup §1): under Sign-in a `warn` card, role alert:
  `⚠ The server's certificate is not trusted.` ⓘ (`About the certificate`: "The server's
  certificate is signed by an authority LADO's computer does not know, often your company's
  own. If you trust it, LADO and agents' git trust it for this server only; nothing else on
  the computer changes."), then `Signed by <subject> · <issuer O>`, `Valid <from> to <until>`,
  `SHA-256 <AA:BB:…>`, the line `Trust it only if you expected this authority. In a company
  network your IT department can confirm the fingerprint.` and `Trust this server` (primary),
  `Don't trust`.
  - `own` (§5): `Certificate <host> · signed by itself`, line `This is the server's own
    certificate, not an authority: when the server renews it, LADO asks again.`
  - `intermediate` (§5): line `The server does not send its root authority, so LADO offers
    the highest one it got. Trust it only if you expected it.`
- **Trusted** (§2): `Certificate trusted. Works: signed in as <login>, may clone and push.`
  (or the check's other line after `Certificate trusted.`); the row `Certificate` ⓘ ("The
  authority you trusted for this server. LADO and agents' git trust it for this server
  only.") `<name> · valid until <date>` with `Remove`.
- **Don't trust** (§3): `Not trusted: LADO and agents cannot clone or push here over https.`
  [Check again]; the closed row `✕ check failed: certificate not trusted`.
- **Changed** (§4): `danger` card with a border: `⚠ The server's certificate has changed since
  you trusted it.` ⓘ, `Before <name> · <first 8 bytes of its fingerprint>…`, `Now <subject> ·
  <issuer O>`, `Valid`, `SHA-256`, bold `If your IT department did not announce a new
  certificate, do not trust it:` then `someone may be between LADO and the server.`, buttons
  `Trust the new certificate` (`.danger`), `Keep the old one` → `The saved certificate does
  not fit the server: LADO and agents cannot clone or push here over https.` [Check again].
- **Trust cannot fix** (§6), `bad` lines, no button: `The server's certificate is not issued
  for <host>: trusting it would not help. Ask the server's administrator.` · `The server's
  certificate names its host only in the old Common Name field, which LADO refuses: ask the
  server's administrator to reissue it.` · `The server's certificate expired on <date>: ask
  the server's administrator to renew it.`
- **Expired saved certificate** (§7): value `⚠ <name> · expired on <date>`; closed row
  `⚠ certificate expired`.
- **Remove** (§8): at once, `Certificate removed.` [Undo]; the row stays with value `None`
  until the panel closes, then is not shown.
- **Remove server** (§9): `Its token, commit author and certificate go too. This cannot be
  undone.`
- **Add** (§10–§12): the address check's card under Address (same texts); Trust → `GitLab
  answers.` and `Certificate: <name> · valid until <date>, trusted for this server.`; Don't
  trust → `⚠ Not trusted, so LADO cannot ask the server. Choose its kind to save it without a
  check.` with the Kind segments and `Add without a check`.

### The clone (§13)

`cannot clone <url>: the certificate of <host> is not trusted (<git's line>)`; hint `Check the
git server and trust its certificate:` `lado git-server check <address>`; UI note `Check the
git server and trust its certificate there.` `Check <host> ↗`.

### The command line

```
$ lado git-server check gitlab.corp.example
lado: the certificate of https://gitlab.corp.example is not trusted
  Signed by  Corp Root CA · Corp Example Ltd
  Valid      2021-03-01 to 2031-03-01
  SHA-256    3F:9A:…:A0
hint: trust it in Settings → Git servers (Check), or give its certificate: lado git-server certificate https://gitlab.corp.example <file>
```

Exit 1, nothing saved; `add` the same with `--certificate <file>` in the hint. Changed: `lado:
the certificate of <address> has changed since you trusted it`, `Before <name> · <fingerprint>`
before the offer. The command line never asks (#7492).

- `lado git-server add <address> --token [--kind …] [--certificate <file>]`.
- `lado git-server certificate <address> [<file>|-|--clear]`: set (prints `Trusted <name> for
  <address>.` and the check's line, exit 0 even when the check fails, with the check's line
  on stderr), show (`<name>, valid until <date>` or `No certificate: LADO trusts this
  computer's authorities for <address>.`), clear (`<address> is trusted by this computer's
  authorities again.`).
- `lado git-server list`: `ADDRESS KIND LOGIN TOKEN CERTIFICATE AUTHOR`, `until <date>` /
  `expired <date>` / `-`.

### doctor and the launch

- doctor: a server's `warn` line with the check's line and `trust it: lado git-server check
  <address>, or Check in Settings → Git servers`; `[info] gh: does not get the certificate of
  <address>: agents' gh cannot reach it; git can` per GitHub server with one.
- Launch notes: the same `gh` sentence, once per server.

## Tests per requirement (lowest layer that catches it)

| Requirement | Layer and test |
|---|---|
| git-servers: kept in its folder; token replaced keeps it; remove takes it (MODIFIED) | unit `tests/test_git_servers.py` (mode, rename, link refused, no lado.db write, replace keeps, remove with `ca.pem`) |
| file is checked; `certificate` command; `add --certificate`; `list` (MODIFIED) | unit `tests/test_cli_git_server.py`: not PEM, expired, > 1 MB, a chain, stdin `-`, `--clear`, show, no server, exit codes, list's column |
| git trusts it for that server alone | unit `test_git_servers.py` (`variables` has `http.<address>/.sslCAInfo` only with a file); integration `tests/integration/test_git_server_certificate.py`: local https git server under a test CA, **no** `GIT_SSL_CAINFO`/`SSL_CERT_FILE` in the test's processes — without the certificate LADO's clone fails with `cert_untrusted`; with it LADO's clone and the fake agent's clone, commit and push pass, an ssh address of the host too; another host under the same CA refused; `~/.gitconfig`, system config and `/etc/ssl` unchanged (hash before/after) |
| LADO's requests trust it alone | unit with `tests/fake_git_api.py` over TLS under two test CAs |
| offers an untrusted certificate (root, AIA, intermediate, own) | unit `tests/test_git_certificates.py` with chains made by `cryptography` in the test (root+intermediate+leaf; AIA served by a local http server; no AIA; self-signed leaf); real TLS server in-process |
| fetching sends no token | unit: the TLS server records every byte after the handshake (none); the AIA server records the request's headers (no `Authorization`, `PRIVATE-TOKEN`) |
| trusting saves nothing else / refusing remembers nothing | unit `test_git_servers.py` + `tests/test_server_git_servers.py` (PUT, DELETE, a second check offers again) |
| changed certificate | unit (saved CA A, server under CA B → `cert_changed` with `before`) |
| trust cannot fix (host, CN only, expired) | unit with made certificates |
| the command line shows an offer | unit `tests/test_cli_git_server.py` (the three lines, the hint, exit 1, nothing saved) |
| gh named at launch | unit `tests/test_runtime_git_servers.py` (launch notes) |
| doctor | unit `tests/test_doctor.py` (warn line and hint, gh info line, nothing saved) |
| session-clone: `cert_untrusted` | unit `tests/test_clone.py` (git's two lines, saved/unsaved host, server way); integration in `test_git_server_certificate.py` (real git's line); vitest `Launch.test.tsx` note |
| git-servers-page: trust card, changed card, Add, Certificate row, Remove/Undo, Remove server text | vitest `GitServers.test.tsx` (every state of the mockup); UI e2e `tests/ui/test_git_servers_certificate.py`: a real `lado server` and a local TLS fake API under a test CA (`make_ca_certificate`), no CA in the browser's or server's trust: Check → card → Don't trust → mark → Check → Trust → `Works`, Certificate row; Remove → Undo; Add with trust; screenshots at 1440 and 390 |
| upgrade and rollback (D12) | unit: the previous `_remove_token` flow leaves the folder with `ca.pem` and a warning; integration: a launch without `ca.pem` gets no `sslCAInfo` and git to that host fails as before |
| Python's private chain method | unit pinning `get_unverified_chain` on the running Python (CI 3.10 and 3.13) |

Regression run: `make lint`, `make test`, the changed integration files with `-m
integration`, `tests/ui/test_git_servers*.py` with `-m ui`, `make web`; CI the rest.

## Docs

- `docs/cli.md`: `git-server add --certificate`, `git-server certificate`, `list`'s column,
  `check`'s trust question and new outcomes, the clone's `cert_untrusted`, doctor's lines.
- `docs/design/ui.md` § Git servers: the trust card, the changed card, the Certificate row,
  Add's question, the Remove text.
- `docs/design/modules.md`: `git_certificates.py`; `git_servers.py`'s certificate.
- `docs/install.md`: one sentence: a company server's certificate is trusted from Check;
  "ask your IT department for the company's root certificate (.pem or .crt)" for the command.
- AGENTS.md: one line for `git_certificates.py` in Layout.
- CHANGELOG.md, 0.48.0 (unreleased), New: **Trust your company's git server.** one item.

Version: a feature and a CLI change → minor; 0.48.0 is unreleased already, so no new
heading.

## Manual check (the pull request carries it from the start)

On the human's machine, by an agent; steps with a token are **[человек]**.

1. Fresh clone in a temp folder, branch of the pull request; `env | grep -E
   '^(GIT_|GH_|LADO_|SSL_|COMPOSE_)'` and `unset` what an earlier check left;
   `git config --global --list --show-origin > before.txt 2>&1`.
2. A local https git server under a self-signed test CA (the steps make the CA with
   `openssl`, the server with `git http-backend` behind a small Python TLS server or the
   test's `fake_git_server.py`), host name `git.test` in a temp `LADO_HOME`.
3. `uv run lado git-server add https://git.test:8443 --token` without a certificate: the
   refusal with the CA's fingerprint (compare with `openssl x509 -fingerprint -sha256`),
   nothing saved; again with `--certificate <the CA file>` → saved, `GitLab, signed in as …`.
4. `uv run lado ui`; Settings → Git servers: Remove the certificate, Check → card, Don't trust
   → mark, Check → Trust → Works; Add a second address of another test server the same way
   through the add form's question.
5. `lado start --provider <CLI>` with a clone of the server's URL; the agent clones, commits
   and pushes (**[человек]** gives the token at step 3).
6. `git config --global --list --show-origin > after.txt 2>&1`; `diff before.txt after.txt`
   empty; no new file under `/etc/ssl` or the keychain.
7. The same in Docker (`make docker`, the container with its `LADO_HOME`), steps 3–5.

Every command is checked against this branch's code before the pull request.
