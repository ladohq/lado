## ADDED Requirements

### Requirement: A server's certificate is kept in its folder

A saved server's trusted certificate SHALL be kept in `<LADO_HOME>/git-servers/<id>/ca.pem`,
mode 600 in folders of mode 700, written whole by a rename, refusing a symbolic link on the
way, never in `lado.db`. Whether a server has one, its name and its expiry SHALL be read from
that file alone. Replacing a server's token SHALL keep it.

#### Scenario: Trusted from the check
- **WHEN** the human trusts the certificate a check of `https://gitlab.corp.example` offers
- **THEN** `<LADO_HOME>/git-servers/<id>/ca.pem` holds it with mode 600, and `lado.db` is
  unchanged

#### Scenario: A token replaced
- **WHEN** a server with a certificate gets a new token by `add` with the same address
- **THEN** its `ca.pem` is unchanged

### Requirement: A certificate file is checked before it is saved

A certificate given by file SHALL be refused, with nothing saved and its file name in the
line, when it is larger than 1 MB, holds no PEM certificate (`<file> holds no certificate`),
or every certificate in it has expired (`<file>: the certificate expired on <date>`). A file
of several certificates SHALL be kept whole.

#### Scenario: Not a certificate
- **WHEN** the human runs `lado git-server certificate gitlab.corp.example notes.txt` and
  `notes.txt` holds text
- **THEN** stderr has `lado: notes.txt holds no certificate`, nothing is saved, and the exit
  status is 1

#### Scenario: A chain
- **WHEN** the file holds an intermediate and a root certificate
- **THEN** both are saved

### Requirement: lado git-server certificate sets, shows and clears a server's certificate

`lado git-server certificate <address> <file>` (`-`: stdin) SHALL save the certificate of the
saved server of the address's host and port, then check the server and print the check's
line; `--clear` SHALL remove it; without either it SHALL print its name and expiry, or that
there is none. An address of no saved server SHALL exit 1; a file with `--clear` exit 2.

#### Scenario: Setting and showing
- **WHEN** the human runs `lado git-server certificate gitlab.corp.example corp-ca.pem`, then
  `lado git-server certificate gitlab.corp.example`
- **THEN** the first prints `Trusted Corp Root CA for https://gitlab.corp.example.` and the
  check's line, the second `Corp Root CA, valid until 2031-03-01`

#### Scenario: Clearing
- **WHEN** the human runs `lado git-server certificate gitlab.corp.example --clear`
- **THEN** its `ca.pem` is gone and the output says LADO trusts the computer's authorities
  for it again

### Requirement: add takes a certificate file

`lado git-server add <address> --token --certificate <file>` SHALL check the file as
`certificate` does before the token is asked, ask the server trusting it alone, and save it
with the server; a refusal SHALL save neither.

#### Scenario: A company server
- **WHEN** the human runs `lado git-server add gitlab.corp.example --token --certificate
  corp-ca.pem` and the server's certificate is signed by that authority
- **THEN** the output has `GitLab, signed in as a.sample`, and the server is saved with its
  `ca.pem`

### Requirement: git trusts a server's certificate for that server alone

For a saved server with a certificate, the `GIT_CONFIG_*` entries of agents and of LADO's
own git SHALL add `http.<address>/.sslCAInfo` naming its `ca.pem`, so git trusts it for that
server's address, its rewritten ssh addresses included, and nowhere else; no other config,
trust store or variable SHALL change.

#### Scenario: An agent pushes
- **WHEN** `https://git.test:8443`, signed by a test authority no process trusts, is saved
  with that authority's certificate, and an agent clones, commits and pushes there
- **THEN** both succeed, and `~/.gitconfig`, the system git config and the system trust store
  are unchanged

#### Scenario: Another server
- **WHEN** an agent clones from another https host signed by the same test authority
- **THEN** git refuses its certificate

### Requirement: LADO's requests to a server trust its certificate alone

A check or an `add` of a server with a certificate SHALL ask its API trusting that
certificate alone, as git does, accepting an intermediate as the last authority; a server
without one SHALL be asked trusting the computer's authorities, as before.

#### Scenario: The certificate of another authority
- **WHEN** a server's saved certificate did not sign the certificate it presents
- **THEN** the check does not pass, though the computer's authorities would trust it

### Requirement: A check offers an untrusted server's certificate to trust

When a check fails because the server's certificate is not trusted, LADO SHALL offer an
authority to trust: the top of the chain the server sent when it signed itself, else its
issuer by `CA Issuers` links, else the chain's top; only once a TLS connection trusting it
alone reaches the server. The offer SHALL name its subject, issuer, validity and SHA-256.

#### Scenario: A company authority
- **WHEN** the server sends its certificate signed by `Corp Root CA`, which signed itself
- **THEN** the offer names `Corp Root CA`, its validity and fingerprint, and nothing is saved

#### Scenario: Only an intermediate
- **WHEN** the server sends its certificate and `Corp Issuing CA 2`, which has no `CA Issuers`
  link
- **THEN** the offer is `Corp Issuing CA 2`, said to be the highest authority the server sent

#### Scenario: A self-signed server
- **WHEN** the server's certificate signed itself
- **THEN** the offer is that certificate, said to be the server's own

### Requirement: Fetching a server's certificates sends no token

The chain SHALL be read from a TLS handshake that sends no request; a `CA Issuers` link
SHALL be followed over http or https with no header but `User-Agent`, at most 3 links, each
cut at 5 seconds and 64 KB. No token SHALL reach any of them.

#### Scenario: An issuer link
- **WHEN** the server's intermediate links its issuer at `http://pki.corp.example/root.crt`
- **THEN** that address is asked once with no `Authorization` or `PRIVATE-TOKEN` header

### Requirement: Trusting saves nothing else and refusing remembers nothing

Trusting an offer SHALL save its certificate as the server's and check again; refusing it
SHALL save nothing and the next check SHALL offer it again. LADO SHALL never turn off the
TLS check.

#### Scenario: Refused, then checked again
- **WHEN** the human refuses the offer and checks the server again
- **THEN** the same offer is made, and the server has no `ca.pem`

### Requirement: A changed certificate is told apart

When a server with a certificate fails the check for its certificate, the check SHALL say
`the certificate of <address> has changed since you trusted it`, name the saved certificate
and offer the new one; keeping the old one SHALL change nothing.

#### Scenario: A new company authority
- **WHEN** `Corp Root CA` is saved and the server now presents a chain of `Corp Root CA G2`
- **THEN** the check says the certificate changed, names `Corp Root CA` as before and offers
  `Corp Root CA G2`

### Requirement: A certificate trust cannot fix gets no offer

When a connection trusting the offered authority still fails, the check SHALL make no offer
and say why: the certificate is not issued for the host; it names the host only in the
Common Name; it expired on a date; otherwise TLS failed with its reason.

#### Scenario: Another host's certificate
- **WHEN** the server presents a certificate for `other.corp.example`
- **THEN** stderr has `lado: the certificate of https://gitlab.corp.example is not issued for
  gitlab.corp.example: trusting it would not help`, and no offer

#### Scenario: A Common Name only
- **WHEN** a self-signed server certificate has no subjectAltName
- **THEN** the check says it names its host only in the old Common Name field, with no offer

### Requirement: The command line shows an offer and trusts only a file

`lado git-server check` and `add` SHALL, for an untrusted or changed certificate, print the
offer (`Signed by`, `Valid`, `SHA-256`) after the refusal and save nothing, with the hint
`trust it in Settings → Git servers (Check), or give its certificate: lado git-server
certificate <address> <file>` (`add`: `--certificate <file>`); they SHALL never ask.

#### Scenario: Not trusted on the command line
- **WHEN** `lado git-server check gitlab.corp.example` meets an untrusted certificate
- **THEN** stderr has the refusal, the offer's three lines and the hint, nothing is saved,
  and the exit status is 1

### Requirement: gh is named where it lacks a certificate

An agent's launch, while a GitHub server has a certificate, SHALL warn once per server that
`gh` does not get its certificate and so cannot reach it, while git can.

#### Scenario: GitHub Enterprise with a certificate
- **WHEN** `https://ghe.corp.example` (GitHub) has a certificate and an agent starts
- **THEN** the launch notes say `gh does not get the certificate of https://ghe.corp.example:
  agents' gh cannot reach it; git can`

## MODIFIED Requirements

### Requirement: lado git-server list shows the saved servers without asking them

`lado git-server list` SHALL print one row per saved server with its address, its kind,
the login seen when it was added (`not checked` for one saved with `--kind` unchecked),
whether its token file is there, its certificate's expiry (`-` for none) and, last, its
commit author (`-` for none), asking no server; with none saved it SHALL say how to add one.

#### Scenario: Two servers
- **WHEN** `https://gitlab.corp.ru` (GitLab, ivan.petrov) and `https://git.lan` (GitLab,
  saved with `--kind`) are saved
- **THEN** the rows show `GitLab  ivan.petrov  yes` and `GitLab  not checked  yes`

#### Scenario: None saved
- **WHEN** no server is saved
- **THEN** the output is `No git servers. Add one: lado git-server add <address> --token`

#### Scenario: A server with an author
- **WHEN** `https://gitlab.corp.ru` has the author `Ivan Petrov <ivan.petrov@corp.ru>` and
  `https://git.lan` none
- **THEN** the row of gitlab.corp.ru ends with `Ivan Petrov <ivan.petrov@corp.ru>` and the
  row of git.lan with `-`

#### Scenario: A server with a certificate
- **WHEN** `https://gitlab.corp.ru` has a certificate valid until 2031-03-01
- **THEN** its row shows `until 2031-03-01` before its author, and a server without one `-`

### Requirement: lado git-server remove removes a server and its token

`lado git-server remove <address>` SHALL find the server by the host and port of the
address, remove it from `lado.db` and remove its token file, its certificate and its folder,
and `<LADO_HOME>/git-servers/` itself once no server is left; an address that is no saved
server's SHALL be refused with exit 1. When the server is removed but a folder cannot be,
the command SHALL say `Removed` with a warning naming the folder, and exit 0.

#### Scenario: Removing a server
- **WHEN** the human runs `lado git-server remove gitlab.corp.ru`
- **THEN** the server is no longer listed and `<LADO_HOME>/git-servers/<id>/` is gone

#### Scenario: Removing a server with a certificate
- **WHEN** the server has a `ca.pem` and the human removes it
- **THEN** `<LADO_HOME>/git-servers/<id>/` is gone with it

#### Scenario: Removing the last server
- **WHEN** `https://gitlab.corp.ru` is the only saved server and the human removes it
- **THEN** `<LADO_HOME>/git-servers/` is gone too

#### Scenario: Removing one of two servers
- **WHEN** two servers are saved and the human removes one
- **THEN** `<LADO_HOME>/git-servers/` stays with the other server's folder

#### Scenario: A folder that cannot be removed
- **WHEN** the last server is removed and `<LADO_HOME>/git-servers/` holds a file of the
  human's
- **THEN** the server is no longer listed, the output says `Removed` with a warning naming
  `<LADO_HOME>/git-servers/`, and the exit status is 0

### Requirement: A check names each outcome in one line

A check SHALL tell these outcomes apart, each in one line with a hint where there is a way
out: the server works; the kind refuses the token; the token lacks a right agents need; the
server does not answer (the reasons of `add`); its certificate is not trusted, has changed,
or cannot be trusted; a redirect, with no request sent to its target; an answer of another
kind than the saved one; an answer of neither kind (`it answers as neither GitHub nor GitLab`).

#### Scenario: A token without the push right
- **WHEN** a GitLab token's scopes are `read_repository, read_api`
- **THEN** stderr has `lado: the token lacks write_repository: agents can clone but not push`
  with the hint naming the scopes a token needs and `lado git-server add <address> --token`;
  a token without `read_repository` too gets `…: agents can neither clone nor push`

#### Scenario: An untrusted certificate
- **WHEN** the TLS handshake fails because the server's certificate is signed by an authority
  this machine does not trust
- **THEN** stderr has `lado: the certificate of https://gitlab.corp.ru is not trusted` with
  the offer of its authority, not that the server does not answer

#### Scenario: A redirect
- **WHEN** `/api/v4/user` answers 302 to `https://sso.corp.ru/login`
- **THEN** stderr has `lado: it redirects to https://sso.corp.ru/login: add that address
  instead` and no request reaches `sso.corp.ru`

#### Scenario: Another kind
- **WHEN** a server saved as GitHub answers GitHub's path with 404 and GitLab's with a
  `username`
- **THEN** stderr has `lado: it answers as GitLab, not GitHub: remove it and add it again`,
  and the saved kind is unchanged

#### Scenario: No answer
- **WHEN** the server does not answer in 5 seconds
- **THEN** stderr has `lado: gitlab.corp.ru does not answer: it did not answer in 5 s`
  and the exit status is 1
