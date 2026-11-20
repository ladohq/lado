## Context

A saved git server (`lado.git_servers`) gives git, through `GIT_CONFIG_*` laid over an
agent's launch and each of LADO's own network git calls, an empty `credential.<origin>.helper`,
LADO's helper, ssh rewrites and, with an author, `includeIf` entries. Its token lives in
`<LADO_HOME>/git-servers/<id>/token`. A check (`git_servers.check`, `probe`) asks the
server's API through `model_servers.ask_all` with urllib's default context, so a server
signed by an authority the computer does not know fails as `cert_untrusted`, whose hint
today is to ask IT to change the computer's or the container's trust store.

Root cause: LADO has no trust of its own per server; the only trust is the computer's (in
Docker, the image's Debian bundle), which the human cannot change from LADO and which the
human declined to import from the host (#7489).

Options weighed (the human chose at #7483–#7487):

1. **Import the host's trusted authorities into the container** (installer exports them,
   compose mounts them, the entrypoint runs `update-ca-certificates`). Covers everything an
   agent does, but needs a new channel into the container, per-OS export code, and does
   nothing for a home server the host does not trust either. Declined.
2. **A certificate field (file) per server.** Exact, but the human must find a PEM file; the
   UI has no upload by the human's choice. Kept for the command line only.
3. **Trust on first use per server** (chosen): LADO fetches the chain, offers its root with
   its fingerprint, and saves it for that server alone. Works for a company and a home
   server alike, needs nothing outside LADO; its risk (a man in the middle at the first
   check) is met by the fingerprint, a loud "changed", and never turning TLS off.

Held against ROADMAP's coming stages: `glab` (next) takes the same file through its own
`ca_cert` per host, and `gh` later through a wrapper, so the file per server is the one
source both will read. Against AGENTS.md: the neutral core is kept (git and LADO's Python
only, no provider code; every provider's agents get it through git's own variables); one
source of truth (whether a server has a certificate is the file, not a column); no silent
drop (`gh` not getting it is said by doctor and the launch); only what is used (no option
to turn TLS off, no upload).

## Goals / Non-Goals

Goals: trust a server's certificate from Check and Add in the UI, or from a file on the
command line; git (LADO's and agents') and LADO's API requests trust it for
that server alone; a changed certificate is told apart; failures trust cannot fix are named.

Non-Goals: a question on the terminal (#7492), `gh`, `glab`, model servers, an agent's own https (curl, Node, MCP) to the
server, the host's or the image's trust store, turning TLS off.

## Decisions

### D1. The certificate is a file of the server's folder, no schema change

`<LADO_HOME>/git-servers/<id>/ca.pem`, written and removed by the same link-refusing writer
as the token (`project_secrets.write_at`/`remove_at`), mode 600. Its name and expiry are read
from the file when listed. No lado.db column: a column would be a second source that can
disagree with the file (a file removed by hand). The schema stays 43, so an update needs no
migration and a rollback none (D12). The token replacement (`save_locked` of a known host)
keeps the folder, so the certificate stays.

### D2. git gets `http.<address>/.sslCAInfo`

`_entries(server)` adds `(f"http.{server.address}/.sslCAInfo", str(ca_file))` when the file
exists at the time of the launch or the call. git matches `http.<url>.*` by the URL after
`insteadOf`, so the rewritten ssh addresses get it too; a trailing `/` keeps
`https://corp.ru/git` from matching `https://corp.ru/gitlab`. The value replaces git's bundle
for that URL only (curl's CAINFO): the server is trusted through this certificate alone,
consistent with D3. curl ≥ 7.68 with OpenSSL accepts an intermediate as the last authority,
so an offered intermediate works for git. LADO's own git calls (`agent_env.for_git`) get the
same entries; nothing else changes (no `GIT_SSL_CAINFO`, no `SSL_CERT_FILE`).

### D3. LADO's requests trust the server's certificate alone

`_ask_kinds` and `_rights` build their opener with an `ssl.SSLContext` made by
`ssl.create_default_context(cafile=ca_file)` (which loads no default authorities when a
file is given) with `VERIFY_X509_PARTIAL_CHAIN` set (Python < 3.13 lacks it by default), for
a server with a certificate; the default context otherwise. `model_servers.ask_all` gains a
`context` argument passed to `urllib.request.HTTPSHandler`. The add form's address check and
`add --certificate` use the certificate in hand the same way.

### D4. The chain is read from a bare TLS handshake

`git_certificates.chain(at)`: a TCP connection to the server's host and port (5 s), a
handshake with `CERT_NONE` and `check_hostname=False` and SNI set to the host, then the
unverified chain: `SSLSocket.get_unverified_chain()` on 3.13+, `sock._sslobj.
get_unverified_chain()` on 3.10–3.12 (present since 3.10; a unit test pins it on every CI
Python). Nothing is written to the socket after the handshake, so no request and no token
leaves. Only the DER bytes are kept.

### D5. The offer is the root, else the highest authority found

From the chain's top: when it is self-issued and its signature verifies with its own key
(`cryptography`'s `verify_directly_issued_by`), it is the offer. Otherwise LADO follows its
`Authority Information Access` `CA Issuers` URL (http or https, DER or PEM; a PKCS#7 bundle
is skipped), keeping a fetched certificate only when it issued the current one by signature,
up to 3 links, each cut at 5 s and 64 KB, with only `User-Agent: lado` and no redirect to
another scheme; a self-signed one ends the walk. When no root is found, the highest
certificate held is the offer, marked `intermediate`. A self-signed leaf is marked `own`.

### D6. An offer is made only when it works

Before offering, LADO connects again trusting the offer alone (D3's context, hostname
checked). Success → the offer. A verify error that trust cannot fix gives no offer:
`X509_V_ERR_HOSTNAME_MISMATCH` → `cert_name` (`not issued for <host>`, or `names its host
only in the old Common Name field` when the leaf has no subjectAltName);
`X509_V_ERR_CERT_HAS_EXPIRED` on the leaf → `cert_expired` with its date; any other →
today's `TLS failed (<why>)`. The offer's fields: subject (CN, else O, else the full name),
issuer's O, not before, not after, SHA-256 of its DER as colon hex, `own`/`intermediate`,
its PEM.

### D7. The check's outcomes

`git_servers.OUTCOMES` gains `cert_changed`, `cert_name`, `cert_expired`; `cert_untrusted`
now carries the offer. A server with a certificate whose handshake fails verification is
`cert_changed` when the new offer's fingerprint differs from every certificate in its
`ca.pem`, else told by D6. `Check` (the dataclass) gains `offer: Offer | None` and `before:
CertificateInfo | None`. The API's `GitServerChecked` and `GitServerCheck` (the address
check) gain `certificate_offer` (subject, issuer, valid from/until, sha256, own,
intermediate, pem) and `certificate_before`.

### D8. Trusting is a write of the offered PEM

`PUT /api/git-servers/{host}/certificate` `{pem}` checks the PEM (D10), saves it under the
lock, runs the check and answers it (`GitServerChecked`). `DELETE` removes it and answers the
removed PEM, which `Undo` puts back with the same `PUT`. The add body (`GitServerAdd`) gains
`certificate: str | None`. The PEM in the browser is the server's public certificate, not a
secret; the human's decision is the button, so the server takes the PEM it is sent after
checking that it is a certificate. Refusing calls nothing: nothing is remembered.

### D9. The command line shows the offer, never asks

`check` and `add` print, after the refusal line, the offer as three lines (`Signed by`,
`Valid`, `SHA-256`, and the `own`/`intermediate` note) and the hint `trust it in Settings →
Git servers (Check), or give its certificate: lado git-server certificate <address> <file>`
(`--certificate <file>` for `add`); exit 1, nothing saved. No `[y/N]` question: moved out by
the human (#7492). The human compares the printed fingerprint with the file IT gives.

### D10. A file's checks

At most 1 MB; parsed with `cryptography`'s `load_pem_x509_certificates`; refused when none
parses (`holds no certificate`) or all are past `not_valid_after` (`the certificate expired
on <date>`). The file is kept as LADO writes it again: the PEM of the parsed certificates,
nothing else from the file (no key, no text). `-` reads stdin.

### D11. `cryptography` becomes a direct dependency

The standard library parses no X.509 (the private `ssl._ssl._test_decode_cert` does not
verify a signature and is private). `cryptography` is installed already through `mcp`
(`pyjwt[crypto]`), so declaring it costs no size; it gives the parsing, the signature
check of D5 and the AIA extension. Imported only by `git_certificates`, loaded by a check, an
add and the listing, never by a launch's hot path but `ca.pem`'s existence (D2).

### D12. The way back

No schema change. A previous LADO reads no `ca.pem`: git for that host fails as before this
change (its certificate untrusted), the file stays unused; removing that server there
leaves its folder with the warning `could not remove …` (its `_remove_token` removes only the
token). After the update again, the file is used. Checked by a unit test of the previous
`_remove_token` behaviour (the folder with a `ca.pem` stays, with the warning) and an
integration test that a launch without `ca.pem` gets no `sslCAInfo`.

### D13. `gh` is named, not served

`gh` has no certificate per host and `SSL_CERT_FILE` for a whole agent would break other
programs (Codex trusts only that file). `runtime`'s launch notes and doctor's `gh` line name
each GitHub server with a certificate. Kept for a later task with a `gh` wrapper.

### D14. The UI

`GitServers.tsx`: a `TrustCard` (one component for Sign-in and Add): `warn` ground for
`cert_untrusted`, `danger` ground with a 2 px border for `cert_changed`; buttons `Trust this
server`/`Trust the new certificate` (`.primary`/`.danger`) and `Don't trust`/`Keep the old
one`. The fingerprint in mono, wrapping by character. A `Certificate` row after Commit
author when `GitServerInfo.certificate` is set (`{name, not_after, expired}`); the closed
row's second line gains `⚠ certificate expired` after `⚠ token missing` in priority. Focus:
after Trust → `Check`; after Don't trust → `Check again`; after Remove → `Undo`.

## Risks / Trade-offs

- A man in the middle at the first check is trusted if the human presses Trust: the
  fingerprint and the IT line are the mitigation; a later change is loud (D7).
- A self-signed leaf breaks at each renewal: the offer says so (`own`), and the next check
  asks again.
- An intermediate as the trusted authority: git (curl ≥ 7.68) and LADO's Python accept it;
  Node by default does not, but Node gets no certificate here at all.
- Apple's git on a Mac (LibreSSL curl) with an intermediate is not verified: the manual
  check runs on Docker; a Mac native run with a root authority is in the manual check.
- `get_unverified_chain` on 3.10–3.12 is a private method: pinned by a unit test per CI
  Python.
