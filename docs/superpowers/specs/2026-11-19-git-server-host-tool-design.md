# glab for the agents and the line about the repository's server: design

Task: LAD-303. Change: `openspec/changes/git-server-host-tool/` (proposal, deltas of
`git-servers`, `git-servers-page`, `doctor`, `container`, and `design.md` with decisions
D1–D11). No screen changes but the token hint's words (`scope api`), so no mockup. The human approved every recommendation of the dialogue (#7538): agents use no
glab login or GitLab variable from outside LADO, named by doctor; the line names a missing
or old tool to the agent; glab older than 1.114.0 is a loud line, no fallback; a missing tool
warns, never refuses; a GitLab token without `api` is named and the hint asks for `api`
(#7541).

## What the human and the agents see

### An agent's instructions

One line after the container's lines (or where they would be), when `origin` is on a saved
server (D4):

- `The repository's origin is on GitLab (gitlab.corp.example), a git server LADO signs you in
  to: use `glab` for its merge requests; it is logged in already.`
- `The repository's origin is on GitHub (github.com), a git server LADO signs you in to: use
  `gh` for its pull requests; it is logged in already.`
- The other four texts of D4 (missing, old, no token, `gh` without the certificate).

### The launch notes (to whoever starts the agent: `lado start`, spawn_worker's result, the UI)

- `glab is not on the agents' PATH: agents cannot open merge requests on
  https://gitlab.corp.example; install glab 1.114.0 or newer`
- `glab 1.80.0 is older than 1.114.0, which LADO needs to sign it in to
  https://gitlab.corp.example; update glab`
- for `gh` missing: `gh is not on the agents' PATH: agents cannot open pull requests on
  https://github.com; install gh` (no oldest version).

Only for the origin's server; the existing `gh does not get the certificate …` line stays.

### lado doctor

After the `git server` lines (and their `gh` certificate lines):

- `[ok  ] glab: glab 1.130.0 (206ebab4f)` — the first line of `--version`.
- `[warn] glab: not on the agents' PATH: agents cannot open merge requests on <addresses>`,
  hint `install glab 1.114.0 or newer`; `[warn] glab: glab 1.80.0 is older than 1.114.0,
  which LADO needs to sign it in`, hint `update glab`.
- The same for `gh` when a GitHub server is saved (`[ok  ] gh: gh version 2.x.y (…)`).
- `[warn] GitLab login outside LADO: GITLAB_TOKEN of your shell, GITLAB_TOKEN in
  /run/secrets set but not used: a GitLab takes its token from Settings → Git servers`;
  `[info] GitLab login outside LADO: the GitLab CLI's own login is not used by agents`.

The source names (`of your shell`, `in <folder>`, `of project <id>`) are
`github_takeover.unused`'s; that function is generalised to take the variable names.

### glab inside an agent

`glab auth status` in a repository of a saved GitLab:

```
gitlab.corp.example
  ✓ Logged in to gitlab.corp.example as ann (<agent config>/glab/config.yml)
  ✓ Git operations for gitlab.corp.example configured to use https protocol.
  ...
  ! No token found (checked config file, keyring, and environment variables).
```

The last line is glab's own (the token comes by header, D2); docs/install.md says so.

## The configuration written (D1)

```yaml
check_update: false
telemetry: false
git_protocol: https
no_prompt: true
hosts:
    "gitlab.corp.example":
        api_protocol: "https"
        ca_cert: "/home/lado/.lado/git-servers/<id>/ca.pem"
        custom_headers:
            - name: "PRIVATE-TOKEN"
              valueFromCommand: "/opt/uv/.../python3 -c '<LOADER>' lado.git_credential --home /home/lado/.lado --server <id> --user oauth2 --address https://gitlab.corp.example token"
    "git.example:8443":
        api_protocol: "https"
        subfolder: "gitlab"
        custom_headers: [...]
```

With no GitLab saved: the first four keys and `hosts: {}`.

## Tests per requirement

| Requirement | Layer | Test |
|---|---|---|
| Each kind … module of its own (modified) | unit | `tests/test_git_kinds.py`: `tool_oldest`, `changes` of each kind |
| Agents' glab is signed in | unit + integration | `test_git_servers.py::test_glab_config_*` (text, modes, rename, subfolder, two servers, no GitLab); `tests/integration/test_git_server_host_tool.py::test_glab_signed_in` (real glab when on PATH, else skipped) |
| glab reads the token at each call | unit | `test_git_credential.py::test_token_mode_*` (prints it, none → exit 1 and stderr, link refused) |
| glab trusts a certificate for that server alone | unit + container | `test_glab_config_ca_cert_only_with_file`; `tests/container/test_glab.py` |
| Agents get no GitLab variable | unit + integration | `test_agent_env.py::test_merge_drops_gitlab_variables`; integration: the fake agent's env has none |
| An agent is told its server and tool | unit + integration | `test_runtime_git_servers.py::test_tool_line_*` (five texts, no line); integration: the fake agent's prompt file holds the GitLab line, the github.com line, none for another host |
| A missing or old tool is warned | unit + integration | `test_runtime_git_servers.py::test_tool_warning_*`; integration with a fake `glab` script printing `glab 1.80.0 (x)` and with none on PATH |
| doctor checks the tool | unit | `test_doctor.py::test_host_tool_*` |
| doctor names the GitLab login outside LADO | unit | `test_doctor.py::test_gitlab_outside_*` (a layer, a project secret, a glab config with a token, with `use_keyring: true`, none) |
| The image carries glab | unit + container | `test_docker.py::test_glab_pin_*` (exact version, both SHA-256, own layer, ENV and profile); `tests/container/test_glab.py` (version, auth status against the fake server under a test CA, another host fails, configs unchanged, growth ≤ 60 MB) |
| A GitLab token without api (git-servers, doctor) | unit + UI | `test_git_servers.py::test_check_gitlab_without_api`, `test_doctor.py::test_gitlab_without_api_warns`, `test_cli_git_server.py`; `tests/ui/test_git_servers_section.py` (the hint `scope api`) |
| The check of a saved server, the add form's hint (modified) | unit + UI | the same; `web/src/GitServers.test.tsx` |
| (brief) a push through a saved server | live | `tests/live/test_live.py::test_an_agent_pushes_through_a_saved_git_server` for Claude Code and Codex |

Regression: `make lint`, `make test`, the changed integration files with `-m integration`,
`make test-container` (CI), `openspec validate --specs --strict` and the trial archive.

The live test: a `fake_git_server.Server` over TLS with a test CA, saved with `git_servers`
directly (`--kind gitlab`, its certificate as `ca.pem`), an empty repository on it as the
session repository's `origin`; the worker is asked to add a file, commit and `git push origin
HEAD`; the test checks the server's `requests` for a receive-pack carrying the token and the
ref on the server. Written, run on each RC (`make test-live`).

## Docs

- `docs/install.md`, Docker's "GitHub and your git servers": a GitLab paragraph — the token
  page (`/-/user_settings/personal_access_tokens`), the scope `api` (git alone
  needs `read_repository`, `write_repository`, `read_api`, but glab's merge requests need
  `api`), Check and its `the token lacks api` line; agents get `glab` signed in and are told to use it; `glab auth status`'s `No token
  found` line; a `GITLAB_TOKEN` or `glab auth login` is not used. In macOS and Linux: glab
  1.114.0 or newer must be installed by the human, doctor says when not.
- `docs/cli.md` (`lado doctor`'s new lines), `docs/design/agents.md` (the line in the
  instructions, `GLAB_CONFIG_DIR`, dropped variables), `docs/design/modules.md`
  (`git_servers`, `git_credential`, `git_kinds`), `docs/testing.md` (the new container and live
  tests), Dockerfile's header comment (glab), CHANGELOG 0.48.0 New: **glab for GitLab**, and
  **Agents know their repository's server**.

`api` vs `read_api` (the human's choice #7541, D11): creating a merge request needs `api`; a
token with `read_repository`, `write_repository`, `read_api` pushes, but `glab mr create`
gets 403. The kind's `scopes` text becomes `scope api` (the token page's hint in Settings and
the replace hints); a check of a token without `api` stays `ok` and says `Works: GitLab,
signed in as ann, may clone and push; glab cannot open merge requests: the token lacks api.`;
doctor makes that server's line `warn` with `replace it with a token with the scope api: lado
git-server add <address> --token`. docs/install.md says `api`.

## The manual check (into the pull request's description from the first push)

On the human's installation (Docker on Mac, the company's GitLab through VPN), handed to an
agent on that machine; steps with a token or a click are **[human]**, the agent never sees
the token.

0. A fresh clone into a temporary folder, the pull request's branch; `env | grep -E
   '^(GIT_|GH_|GITLAB_|GLAB_|LADO_|SSL_|COMPOSE_)'` and `unset` leftovers; `git config --global
   --list --show-origin > <tmp>/gitconfig.before 2>&1`; the same for `~/.config/glab-cli`
   (`ls -la`, no copy of a token).
1. Start the previous version's container, `docker compose exec lado lado ls`, then `ls
   …/lado.db` before updating to the RC image.
2. **[human]** Settings → Git servers → Add the company GitLab with a token (`api`) → Check
   is green.
3. **[human]** If the GitLab is signed by the company's authority: "Trust this server?" →
   Trust. If it is signed by a public authority, run the certificate steps of the previous
   change with a local https server and a test CA in Docker separately.
4. `lado start <git-url> --provider claude`: the agent's instructions hold the GitLab line
   (`docker compose exec lado lado log` / the agent's first answer when asked which tool it
   will use); the agent clones, commits with the server's author, pushes, and opens a merge
   request with `glab mr create`, choosing glab by the line alone.
5. The push goes over https: `GIT_SSH_COMMAND=false git push …` inside the agent's shell.
6. github.com works as before: a session on a github.com repository gets the `gh` line and
   `gh pr list` works.
7. Check with a revoked and with an expired token says `token refused`; a token with `api`
   only pushes over https.
8. `lado doctor` shows `[ok  ] glab: glab 1.130.0 …`; `git config --global --list
   --show-origin` equals the snapshot; `~/.config/glab-cli` unchanged.
