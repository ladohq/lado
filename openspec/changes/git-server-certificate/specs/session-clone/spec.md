## ADDED Requirements

### Requirement: An untrusted certificate of a git server points to its check

git's refusal of a server's certificate (OpenSSL's and GnuTLS's words, a certificate of
another host too) SHALL be the kind `cert_untrusted`, `the certificate of <host> is not
trusted`. For a saved server's URL its hint SHALL be `Check the git server and trust its
certificate:` `lado git-server check <address>`, and its UI way out `Check <host> ↗`; for an
unsaved http(s) host, the hint to add it.

#### Scenario: A saved company server
- **WHEN** `https://gitlab.corp.example` is saved without a certificate and a clone of
  `https://gitlab.corp.example/team/app.git` fails with `SSL certificate problem: unable to
  get local issuer certificate`
- **THEN** the text is `cannot clone https://gitlab.corp.example/team/app.git: the
  certificate of gitlab.corp.example is not trusted (<git's line>)` with the hint `lado
  git-server check https://gitlab.corp.example`

#### Scenario: The window's note
- **WHEN** the same failure shows in the New session window
- **THEN** the note says `Check the git server and trust its certificate there.` and
  `Check gitlab.corp.example ↗` opens `/settings/git-servers?check=gitlab.corp.example`

#### Scenario: An unsaved host
- **WHEN** a clone of `https://git.lab.example/app.git`, no saved server's, fails the same way
- **THEN** the hint is `Add it as a git server with a token:` `lado git-server add
  https://git.lab.example --token`
