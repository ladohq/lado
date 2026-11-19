## ADDED Requirements

### Requirement: Check asks whether to trust an untrusted certificate

When Check finds the certificate not trusted, Sign-in SHALL show `⚠ The server's certificate
is not trusted.` with an ⓘ, `Signed by`, `Valid` and `SHA-256` of the offer, a line to confirm
the fingerprint with IT, and `Trust this server` (main) and `Don't trust`. Trust SHALL save it
through `PUT /api/git-servers/{host}/certificate` and check again.

#### Scenario: Trusted
- **WHEN** the human presses `Trust this server` and the server then works for `a.sample`
- **THEN** Sign-in says `Certificate trusted. Works: signed in as a.sample, may clone and
  push.`, and the panel shows the `Certificate` row

#### Scenario: Not trusted
- **WHEN** the human presses `Don't trust`
- **THEN** Sign-in says `Not trusted: LADO and agents cannot clone or push here over https.`
  with `Check again`, the closed row says `✕ check failed: certificate not trusted`, and
  nothing is saved

### Requirement: A changed certificate is asked in red

When Check finds a saved certificate no longer fits, Sign-in SHALL show `⚠ The server's
certificate has changed since you trusted it.` on the danger ground with a border, the saved
certificate as `Before`, the offer as `Now` with `Valid` and `SHA-256`, a bold warning not to
trust an unannounced change, and `Trust the new certificate` and `Keep the old one`.

#### Scenario: Keeping the old one
- **WHEN** the human presses `Keep the old one`
- **THEN** the saved certificate is unchanged and the line says the server cannot be reached
  with it, with `Check again`

### Requirement: Add asks whether to trust under Address

When the add form's address check finds the certificate not trusted, it SHALL show the same
question under Address; Trust SHALL keep the certificate in the form, check the address again
with it and save it with the server on Add; Don't trust SHALL offer the kind to save the
server without a check.

#### Scenario: A company server added
- **WHEN** the human types `gitlab.corp.example`, trusts the offer, pastes a token and adds
- **THEN** the server is saved with its certificate, and its panel shows the `Certificate` row

#### Scenario: Added without trust
- **WHEN** the human presses `Don't trust`, chooses GitLab and presses `Add without a check`
- **THEN** the server is saved without a certificate as `⚠ not checked`

### Requirement: A saved certificate has its own row

A server with a certificate SHALL show a `Certificate` row ⓘ after Commit author: `<name> ·
valid until <date>`, or `⚠ <name> · expired on <date>`, with `Remove`, which removes it at
once and leaves `Certificate removed.` with `Undo`; a server without one SHALL show no row.
An expired certificate SHALL make the closed row say `⚠ certificate expired`.

#### Scenario: Removed and undone
- **WHEN** the human presses `Remove` on the certificate row, then `Undo`
- **THEN** the same certificate is saved again and the row shows it

## MODIFIED Requirements

### Requirement: Check on the panel checks the server again

`Check` SHALL check the server as `lado git-server check` does, through `POST
/api/git-servers/{host}/check`, the button off and `Checking…` under Sign-in meanwhile, and
show the result there in one line with its way out at the end; a server that works SHALL be
a status, any other outcome an alert; the closed row's second line SHALL follow the result
for this visit.

#### Scenario: The lines of the outcomes
- **WHEN** a check ends
- **THEN** its line is one of `Works: signed in as <login>, may clone and push.`, `Works:
  <Kind>, signed in as <login>.` (a server that was not checked), `Works: signed in as
  <login>; the token's rights are not checked.`, `<Kind> refused the token: it expired or was
  revoked.`, `The token lacks <scopes>.` ⓘ, `⚠ No answer in 5 seconds.` (`⚠ No answer:
  <why>.` for another reason) ⓘ [Check again], the trust question, `It redirects to
  <target>: add that address instead.`, `It answers as <Kind>, not <saved Kind>: remove it
  and add it again.`, `It answers as neither GitHub nor GitLab.`; a `Works:` line has no `✓`
  before it

#### Scenario: An expired token
- **WHEN** the human presses `Check` on a GitLab server whose token the server refuses
- **THEN** `GitLab refused the token: it expired or was revoked.` shows under Sign-in with
  no button of its own, Sign-in's `Replace token` becomes its main button, and the closed row
  says `✕ check failed: token refused`

#### Scenario: An untrusted certificate
- **WHEN** the check finds the server's certificate not trusted
- **THEN** the trust question shows under Sign-in, and its ⓘ `About the certificate` says the
  authority is often the company's own and that trusting it changes nothing else on the
  computer

#### Scenario: A certificate trust cannot fix
- **WHEN** the server's certificate is issued for another host
- **THEN** the line is `The server's certificate is not issued for <host>: trusting it would
  not help. Ask the server's administrator.` with no question

#### Scenario: A server saved without a check now answers
- **WHEN** the human presses `Check` on a server that says `⚠ not checked` and it works,
  signed in as `a.sample`
- **THEN** the line says `Works: GitLab, signed in as a.sample.`, and the row says
  `signed in as a.sample` after the page is opened again

### Requirement: Remove asks first

`Remove server` at the foot of a server's panel SHALL ask in its place, `Remove <address>?`,
`Its token, commit author and certificate go too. This cannot be undone.`, with Remove server
and Cancel (the focus on Cancel); Remove server SHALL remove the server as `lado git-server
remove` does and leave `Removed <address>.` in its place, the focus on `+ Add server`.

#### Scenario: Removing a server
- **WHEN** the human removes `https://git.corp.example` and confirms
- **THEN** its row says `Removed https://git.corp.example.`, `lado git-server list` no longer
  shows it, and its token folder is gone
