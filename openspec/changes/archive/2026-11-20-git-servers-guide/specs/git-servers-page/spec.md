## ADDED Requirements

### Requirement: The page says a GitLab token without api leaves glab without merge requests

Check, Add server and Replace token SHALL end the line of a GitLab server whose token works
for git without `api` with `; glab cannot open merge requests: the token lacks api` before
its full stop, as `lado git-server check` and `add` do, the line keeping its ok tone, place
and buttons; other tokens and GitHub SHALL keep their lines.

#### Scenario: Check of a token for git alone
- **WHEN** the human presses `Check` on `https://gitlab.corp.example`, checked before, whose
  token's scopes are `read_repository, write_repository, read_api`, signed in as `ann`
- **THEN** the line under Sign-in is `Works: signed in as ann, may clone and push; glab
  cannot open merge requests: the token lacks api.`, a status

#### Scenario: First check of a server saved without a check
- **WHEN** the server was saved without a check and its check now finds the same token
- **THEN** the line is `Works: GitLab, signed in as ann; glab cannot open merge requests: the
  token lacks api.`

#### Scenario: Add server with a token for git alone
- **WHEN** the human adds `https://gitlab.corp.example` with that token
- **THEN** the new server's panel starts with `✓ Saved: GitLab, signed in as ann; glab cannot
  open merge requests: the token lacks api.`

#### Scenario: Replace token with a token for git alone
- **WHEN** the human replaces the server's token with that token
- **THEN** the line under Sign-in is `✓ Token replaced: signed in as ann; glab cannot open
  merge requests: the token lacks api.`

#### Scenario: A token with api
- **WHEN** the token's scopes are `api`
- **THEN** Check says `Works: signed in as ann, may clone and push.` and Add server
  `✓ Saved: GitLab, signed in as ann.`, as before

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
  and add it again.`, `It answers as neither GitHub nor GitLab.`; a `Works:` line of a GitLab
  token without `api` ends with `; glab cannot open merge requests: the token lacks api.`; a
  `Works:` line has no `✓` before it

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
