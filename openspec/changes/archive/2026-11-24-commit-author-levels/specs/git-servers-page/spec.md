## ADDED Requirements

### Requirement: LADO's author has a block above the servers

Settings → Git servers SHALL show, above Servers, a block `Commit author` ⓘ with one row
`LADO's author`: the author with `Edit` and `Remove` when set; else the author of git's own
config with `· from git on this computer` and `Set author`; else `⚠ Nobody: agents cannot
commit` with `Set author` as the main button. The form, its refusals and the result lines
SHALL be those of a server's author, through `PUT` and `DELETE /api/git-author`.

#### Scenario: Not set, git knows the human
- **WHEN** LADO has no author and git's own config names `Ann Lee <ann@example.com>`
- **THEN** the row reads `Ann Lee <ann@example.com> · from git on this computer` with `Set
  author`

#### Scenario: Nobody
- **WHEN** neither LADO nor git has an author
- **THEN** the row reads `⚠ Nobody: agents cannot commit` and `Set author` is the main button

#### Scenario: Setting it
- **WHEN** the human presses `Set author`, types `Ann Lee` and `ann@example.com` and presses
  Save author
- **THEN** the form closes, `✓ Author saved.` shows, the row reads `Ann Lee
  <ann@example.com>` with `Edit` and `Remove`, the focus on `Edit`

#### Scenario: Removing it and Undo
- **WHEN** the human presses `Remove LADO's author`, then `Undo`
- **THEN** first `✓ Author removed.` with `Undo` shows and the row falls back to git's own
  author or nobody; then the author is set again and `✓ Author saved.` shows

### Requirement: The page names the variables that win over every author

When the agents' environment holds any of `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`,
`GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL`, the row of LADO's author SHALL carry the warning
`⚠ The agents' environment sets <the names>: these sign their commits instead of any author
here.`, naming the variables, never their values.

#### Scenario: A variable from the login shell
- **WHEN** the agents' login shell exports `GIT_AUTHOR_NAME` and `GIT_AUTHOR_EMAIL`
- **THEN** the warning names `GIT_AUTHOR_NAME and GIT_AUTHOR_EMAIL`

### Requirement: The page opens LADO's author form from its address

`/settings/git-servers?author` SHALL open LADO's author form, Name focused, once the page is
read, and drop `?author` from the address; saved from there, the line SHALL read `✓ Author
saved. Go back to the New session tab: it checks again by itself.`

#### Scenario: From the New session window's link
- **WHEN** the page opens at `/settings/git-servers?author` and the human saves an author
- **THEN** the form was open with Name focused, the address has no `?author`, and the line
  says to go back to the New session tab

## MODIFIED Requirements

### Requirement: A server's commit author is set and removed on its row

A server's panel without an author SHALL show a minor line `Commit author:` with the author
in effect and its source, or `none yet`, and `Set one for this server` ⓘ, which opens the
author form under it (set as `lado git-server author` does, refusals under Name or Email;
done: `✓ Author saved.`, the focus on `Edit`). A set author SHALL have its full row with
`Edit` and `Remove`, which clears it at once; a closed row with one SHALL show `commits as
<name> <<email>>`.

#### Scenario: Setting an author
- **WHEN** the human presses `Set one for this server` on `https://gitlab.corp.example`, types
  `Ivan Petrov` and `ivan.petrov@corp.example` and presses Save author
- **THEN** the form closes, `✓ Author saved.` shows, the row's value is `Ivan Petrov
  <ivan.petrov@corp.example>`, and `lado git-server list` prints the same author

#### Scenario: The minor line
- **WHEN** a server has no author and LADO's author is `Ann Lee <ann@example.com>`
- **THEN** its panel reads `Commit author: Ann Lee <ann@example.com> (LADO's) · Set one for
  this server`, or with `(from git on this computer)` when only git's own config names her

#### Scenario: A wrong email
- **WHEN** the human types `ivan.petrov` in Email and
  presses Save author
- **THEN** `not an email address: name@host` shows under Email and nothing is saved

#### Scenario: Removing it
- **WHEN** the human presses `Remove` on the commit author of a server with one, while LADO's
  author is `Ann Lee <ann@example.com>`
- **THEN** the panel shows the minor line `Commit author: Ann Lee <ann@example.com> (LADO's)`,
  and `lado git-server list` prints `-` for its author

### Requirement: A server's panel has Sign-in, Commit author and Remove server

An open panel SHALL show Sign-in (`Signed in as <login>`, `⚠ Not checked` or `⚠ Token
missing`, with `Check` and `Replace token`, or `Replace token` alone as the main button when
the token is missing), Commit author (`<name> <<email>>` with `Edit` and `Remove`, or the
minor line with `Set one for this server`) and a foot with `Remove server`. Each button's
accessible name SHALL carry the address (`Check <address>`, `Replace the token of
<address>`, `Set a commit author for <address>`).

#### Scenario: An open server
- **WHEN** the human presses the row of `https://gitlab.corp.example` (GitLab, `a.sample`,
  author `Sample Name <sample.name@corp.example.com>`)
- **THEN** its panel shows `Signed in as a.sample` with `Check` and `Replace token`, `Sample
  Name <sample.name@corp.example.com>` with `Edit` and `Remove`, and `Remove server`

#### Scenario: A missing token
- **WHEN** the server's token file is missing
- **THEN** the closed row says `⚠ token missing`, and the open panel's Sign-in offers
  `Replace token` alone, as its main button
