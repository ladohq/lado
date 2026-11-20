## MODIFIED Requirements

### Requirement: Each kind of git server is a module of its own

Each kind of server SHALL be a module of its own that names its API request, how it tells
its answer and a refused token, the user name git sends with the token (`oauth2` for
GitLab, `x-access-token` for GitHub), its host tool (`glab`, `gh`), the oldest version of
that tool LADO signs in (`glab` 1.114.0, none for `gh`), its word for a change request
(`merge requests`, `pull requests`) and its token page; the list of kinds SHALL be the one
place that names them.

#### Scenario: The kinds of --kind
- **WHEN** the human runs `lado git-server add --help`
- **THEN** `--kind` offers `github` and `gitlab`, the names of the kind modules

#### Scenario: The line takes the kind's words
- **WHEN** a kind's module names another tool or word
- **THEN** the agents' line and the launch's warning use them, with no other change

### Requirement: lado git-server check checks a saved server again

`lado git-server check <address>` SHALL ask the saved server of the address's host and
port with its saved token as `add` does, judge the answers by its saved kind, and print one
line of what it found, storing nothing but the login of a passing check. Exit status SHALL be 0 when
the server works; 1 for any other outcome, for an address that is no saved server's and for
a missing token file, with no request sent for those two; 2 for an address it does not take.

#### Scenario: A server that works
- **WHEN** `https://gitlab.corp.ru` is saved as GitLab and the human runs
  `lado git-server check gitlab.corp.ru`, and the server answers `/api/v4/user` with
  `{"username": "ivan.petrov"}` and the token's own information with the scope
  `api`
- **THEN** stdout is `Works: GitLab, signed in as ivan.petrov, may clone and push.` and the
  exit status is 0

#### Scenario: An expired token
- **WHEN** `https://gitlab.corp.ru` is saved as GitLab and the server answers the saved token
  with its own 401: `{"message": "401 Unauthorized"}`, or `{"error": "invalid_token",
  "error_description": …}` for a revoked or expired token
- **THEN** stderr has `lado: GitLab refused the token: it expired or was revoked` and the hint
  `replace it: lado git-server add https://gitlab.corp.ru --token`, and the exit status is 1

#### Scenario: A revoked GitHub token
- **WHEN** `https://ghe.corp.ru` is saved as GitHub and the server answers the saved token
  with GitHub's 401 `{"message": "Bad credentials", "documentation_url": …}`
- **THEN** stderr has `lado: GitHub refused the token: it expired or was revoked` and the hint
  `replace it: lado git-server add https://ghe.corp.ru --token`, and the exit status is 1

#### Scenario: No such server
- **WHEN** no server is saved for `git.lan` and the human runs `lado git-server check git.lan`
- **THEN** stderr has `lado: https://git.lan is no saved git server` with the hint
  `see them: lado git-server list`, no request is sent, and the exit status is 1

#### Scenario: The token file is missing
- **WHEN** the server's token file is gone from `LADO_HOME`
- **THEN** no request is sent, stderr says its token file is missing with the hint
  `replace it: lado git-server add https://gitlab.corp.ru --token`, and the exit status is 1

## ADDED Requirements

### Requirement: Agents' glab is signed in to the saved GitLab servers

An agent's launch SHALL set `GLAB_CONFIG_DIR` to a folder of the agent's own and write there
`config.yml` (mode 600, whole by a rename) with one host entry per saved GitLab server: its
host and port, its scheme as `api_protocol`, its path as `subfolder`, and a `PRIVATE-TOKEN`
header from LADO's helper; `git_protocol` https, update check and statistics off. The token
SHALL NOT be written there.

#### Scenario: glab on a saved GitLab
- **WHEN** `https://gitlab.corp.example` is saved with its token and an agent runs `glab auth
  status` in a repository there
- **THEN** it says logged in as the token's user, without `glab auth login`, and the file
  holds no token

#### Scenario: Two GitLab servers
- **WHEN** two GitLab servers are saved and an agent runs `glab api user` on each
- **THEN** each request carries its own server's token

#### Scenario: The human's glab
- **WHEN** the human's own `glab` is logged in to `gitlab.com` outside LADO
- **THEN** an agent's `glab auth status` does not show that login, and the human's `glab`
  configuration is unchanged

### Requirement: glab reads the token at each call

The header's command SHALL be LADO's helper with LADO's own Python, given the server's id and
LADO_HOME only; it SHALL print the token of the server's token file and nothing else, and
with no token it can read SHALL print nothing to stdout, a line saying so to stderr, and exit
non-zero.

#### Scenario: A token replaced
- **WHEN** the human replaces a GitLab server's token while an agent runs
- **THEN** that agent's next `glab` call carries the new token

#### Scenario: A server removed
- **WHEN** the server is removed while an agent runs
- **THEN** that agent's next `glab` call carries no token

### Requirement: glab trusts a server's certificate for that server alone

A saved GitLab server with a certificate SHALL get `ca_cert` naming its `ca.pem` in its own
host entry only; no variable SHALL set an authority for the agent's whole `glab`.

#### Scenario: Under the company's authority
- **WHEN** `https://gitlab.corp.example` is signed by a test authority and saved with it, and
  an agent runs `glab api user`
- **THEN** the request succeeds

#### Scenario: Another host
- **WHEN** another server under the same authority is not saved with it
- **THEN** an agent's `glab` call to it outside a repository of a saved server fails on the
  certificate, and one by its whole URL from such a repository, which glab sends with that
  server's certificate, carries no token

### Requirement: Agents get no GitLab variable from outside LADO

An agent's launch SHALL drop `GITLAB_TOKEN`, `GITLAB_ACCESS_TOKEN`, `GITLAB_HOST`,
`GITLAB_URI`, `GL_HOST`, `GLAB_CONFIG_DIR`, `GITLAB_API_HOST` and `GITLAB_REPO` from every
layer (login shell, outside folder, project), so `glab` reaches a GitLab only through a saved
server.

#### Scenario: A token in the shell
- **WHEN** the login shell sets `GITLAB_TOKEN` and no GitLab server is saved
- **THEN** an agent's environment has no `GITLAB_TOKEN`, and its `glab auth status` says it
  is not logged in

#### Scenario: Another host in the shell
- **WHEN** two GitLab servers are saved and the login shell sets `GITLAB_API_HOST` and
  `GITLAB_REPO` to a third host, which the agents' trust store accepts
- **THEN** an agent's `glab api user` reaches each saved server with its own token, and no
  request reaches the third host

### Requirement: An agent is told its repository's server and tool

When the session repository's `origin` is on a saved server, each agent's instructions SHALL
carry one line naming the server's kind and host, its tool and word from the kind, and that
the tool is logged in, or why not: not on the agents' PATH, older than the kind's oldest, no
token, or `gh` without the server's certificate. Another remote SHALL get no line.

#### Scenario: GitLab
- **WHEN** the origin is on the saved `https://gitlab.corp.example` and `glab` 1.130.0 is on
  the agents' PATH
- **THEN** the instructions say ``The repository's origin is on GitLab (gitlab.corp.example),
  a git server LADO signs you in to: use `glab` for its merge requests; it is logged in
  already.``

#### Scenario: GitHub
- **WHEN** the origin is on github.com, saved with its token
- **THEN** the line names GitHub (github.com), `gh` and pull requests

#### Scenario: Not a saved server
- **WHEN** the origin's host is not saved, or the repository has no origin
- **THEN** the instructions have no such line

#### Scenario: glab missing
- **WHEN** the origin is on a saved GitLab and no `glab` is on the agents' PATH
- **THEN** the line says ``its tool `glab` is not installed here, so you cannot open its
  merge requests; tell the human``

### Requirement: A missing or old host tool is warned at the launch

An agent's launch SHALL warn, and still start the agent, when the tool of the origin's saved
server is not on the agents' PATH, or is older than its kind's oldest version, naming the
tool, the server and what to install; a launch whose origin is on no saved server SHALL NOT
run the tool.

#### Scenario: No glab outside Docker
- **WHEN** the origin is on the saved `https://gitlab.corp.example` and `glab` is not on the
  agents' PATH
- **THEN** the launch notes say `glab is not on the agents' PATH: agents cannot open merge
  requests on https://gitlab.corp.example; install glab 1.114.0 or newer`, and the agent
  starts

#### Scenario: An old glab
- **WHEN** `glab` 1.80.0 is on the agents' PATH
- **THEN** the launch notes say `glab 1.80.0 is older than 1.114.0, which LADO needs to sign
  it in to https://gitlab.corp.example; update glab`

### Requirement: A GitLab token without api is said to leave glab without merge requests

A check, and an `add` the server answers, of a GitLab whose token's told rights do not grant
`api` SHALL still work for git and say `glab cannot open merge requests: the token lacks api`
at the end of its line (the check's before its full stop); GitLab's token hint SHALL ask for
the scope `api`.

#### Scenario: A token for git alone
- **WHEN** a GitLab token's scopes are `read_repository, write_repository, read_api`
- **THEN** the check says `Works: GitLab, signed in as ann, may clone and push; glab cannot
  open merge requests: the token lacks api.` and the exit status is 0

#### Scenario: A token with api
- **WHEN** the scopes are `api`
- **THEN** the check says `Works: GitLab, signed in as ann, may clone and push.`
