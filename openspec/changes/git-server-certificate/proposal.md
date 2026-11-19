Task: LAD-301

## Why

A company's own GitLab or GitHub Enterprise often has a certificate signed by the company's
own authority, which LADO's computer, and LADO's container all the more, does not trust.
Today Check says `The server's certificate is not trusted` and tells the human to ask the IT
department to change the computer's (or the container's) trust store; `add` cannot save such
a server but unchecked, and every clone and push of it fails. LADO should let the human trust
such a server in LADO itself, for that server only, without touching the computer, the image
or anything else.

## What Changes

- **Check asks "Trust this server?".** When a check (Settings' Check or the add form's address
  check; the command line shows the same offer without asking) fails because the server's
  certificate is not trusted, LADO fetches the server's certificate chain by a TLS handshake
  alone (no request, no token), takes its root authority (the chain's top when it signed
  itself, else its issuer by the certificate's `CA Issuers` link, else the highest one it
  got), checks that the server is reached with it, and shows who signed it, its validity and
  its SHA-256 fingerprint with Trust this server / Don't trust. Trust saves it for this
  server and checks again; Don't trust saves and remembers nothing.
- **A changed certificate is told apart.** When a trusted certificate no longer fits, the
  check says the certificate changed, louder, with the old and the new one, and asks again.
- **Failures trust cannot fix are named, with no offer**: a certificate issued for another
  host, one naming its host only in the Common Name, an expired server certificate.
- **The certificate is part of the server's entry**: `<LADO_HOME>/git-servers/<id>/ca.pem`,
  as the token is kept. LADO's git and agents' git get `http.<address>/.sslCAInfo` through
  `GIT_CONFIG_*`, as the token and the author; LADO's own requests to the server's API trust
  it for that server alone. Docker and native alike; the image and compose are unchanged.
- **The command line takes a file from IT**: `lado git-server add <address> --token
  --certificate <file>`, and `lado git-server certificate <address> [<file>|-|--clear]`. `check` and
  `add` show the offer of an untrusted certificate and refuse, pointing to Settings or a file;
  they never ask (the human's answer to #7492).
  `lado git-server list` shows a certificate column.
- **Settings → Git servers** shows the trust question under Sign-in after Check and under
  Address in Add, a `Certificate` row on a server's panel when one is saved (its name, its
  expiry, Remove with Undo), and the removal question names the certificate. No file upload.
- **A failed clone points to the check.** A clone or listing of a saved server's URL that git
  refuses for an untrusted certificate says so, with `lado git-server check <address>` and,
  in the UI, `Check <host> ↗`, which opens the server's Check in Settings.
- **`lado doctor`** names an untrusted or changed certificate by the check's line, and for a
  GitHub server with a certificate, that `gh` does not get it.
- **An agent's launch** warns that `gh` does not get the certificate of a GitHub server
  that has one.
- `cryptography` becomes a direct dependency (it is installed already, through `mcp`).

Mockup: the run's `mockup-certificate.html` (§1–§13).

## Scope

`src/lado/git_certificates.py` (new: the chain, the root, the offer, the file's checks),
`src/lado/git_servers.py` (the check's outcomes, the probe's context, `variables`, the
certificate's file, removal), `src/lado/cli.py` (`--certificate`, `certificate`, the
offer's lines, `list`), `src/lado/clone.py` (the kind `cert_untrusted`),
`src/lado/doctor.py`, `src/lado/runtime.py` (the launch warning), `src/lado/server/app.py`
and `models.py` (the offer in the check answers, PUT/DELETE of a server's certificate, the
add body), `web/openapi.json`, `web/src/api.gen.ts`, `web/src/GitServers.tsx`,
`web/src/styles.css`, `pyproject.toml`, `uv.lock`, tests (unit, integration, vitest, UI
e2e), `docs/cli.md`, `docs/design/ui.md`, `docs/design/modules.md`, `docs/install.md`,
CHANGELOG.md.

## Out of scope

- `gh` with the certificate: `gh` reads no certificate per host, and `SSL_CERT_FILE` for a
  whole agent breaks its CLI's own connections; the human put it under Later (#7489). doctor
  and the launch say so for a GitHub server with a certificate.
- `glab`: a later task (it has `ca_cert` per host).
- The host's trusted certificates brought into the container: declined by the human (#7489),
  not kept under Later.
- A file upload or paste in the UI: declined by the human (#7489); a file goes in by the
  command line.
- Turning off the TLS check, anywhere: never (#7489).
- A refusal remembered: the next check asks again (#7489).
- A "Trust it? [y/N]" question on the terminal: moved out by the human (#7492) to keep the
  task near its size; the command line trusts a file only.
- The certificate for model servers, `NODE_EXTRA_CA_CERTS`, `SSL_CERT_FILE` or an agent's own
  https (curl, Node, MCP servers) to the git server: only git gets the certificate, as the
  task's frame says.
- An ssh key for a server: Later.
