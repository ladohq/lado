## ADDED Requirements

### Requirement: lado doctor checks the tool of each saved server's kind

`lado doctor` SHALL print, after the `git server` lines, one line per tool of the saved
servers' kinds, named by the tool: `ok` with its version on the agents' PATH, `warn` when it
is missing or older than its kind's oldest, with what to install. It SHALL never fail for it,
and print no such line with no saved server.

#### Scenario: glab in the image
- **WHEN** a GitLab server is saved and `glab` 1.130.0 is on the agents' PATH
- **THEN** doctor prints `[ok  ] glab: glab 1.130.0`

#### Scenario: glab missing
- **WHEN** a GitLab server is saved and no `glab` is on the agents' PATH
- **THEN** doctor prints `[warn] glab: not on the agents' PATH: agents cannot open merge
  requests on https://gitlab.corp.example` with the hint `install glab 1.114.0 or newer`,
  and the exit status does not change

#### Scenario: Only GitHub saved
- **WHEN** only github.com is saved
- **THEN** doctor prints a `gh` line and no `glab` line

### Requirement: lado doctor names the GitLab login outside LADO

`lado doctor` SHALL print `[warn] GitLab login outside LADO: <names> set but not used: a
GitLab takes its token from Settings → Git servers` while a layer or a project's secret sets
a dropped GitLab variable, never a value; `[warn]` that `OAUTH_TOKEN`, which agents keep,
reaches their glab while a layer or a project sets it; `[info]` that `glab`'s own login is not
used while the human's `glab` configuration holds a token or a keyring login; no line
otherwise.

#### Scenario: A token in the shell
- **WHEN** the login shell sets `GITLAB_TOKEN`
- **THEN** doctor prints `[warn] GitLab login outside LADO: GITLAB_TOKEN of your shell set
  but not used: a GitLab takes its token from Settings → Git servers`

#### Scenario: An OAuth token in the shell
- **WHEN** the login shell sets `OAUTH_TOKEN`
- **THEN** doctor prints `[warn] GitLab login outside LADO: OAUTH_TOKEN of your shell reaches
  agents: their glab sends it to a GitLab not in Settings → Git servers (gitlab.com by
  default)` with the hint `remove it from the agents' environment unless another tool needs
  it`

#### Scenario: glab logged in
- **WHEN** the human's `glab` configuration holds a token for `gitlab.com`
- **THEN** doctor prints `[info] GitLab login outside LADO: the GitLab CLI's own login is not
  used by agents`

#### Scenario: None
- **WHEN** no GitLab variable is set and the human's `glab` holds no login
- **THEN** doctor prints no `GitLab login outside LADO` line

### Requirement: lado doctor warns of a GitLab token without api

doctor's line of a saved GitLab whose check works but whose token lacks `api` SHALL be
`warn` with the check's line and the hint `replace it with a token with the scope api: lado
git-server add <address> --token`; the exit status SHALL not change.

#### Scenario: A token for git alone
- **WHEN** `https://gitlab.corp.example`'s token has `read_repository, write_repository,
  read_api`
- **THEN** doctor prints `[warn] git server https://gitlab.corp.example: Works: GitLab, signed
  in as a.sample, may clone and push; glab cannot open merge requests: the token lacks api.`
  with that hint
