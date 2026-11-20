## MODIFIED Requirements

### Requirement: An ssh failure says how to check the key or the host key

Outside LADO's container the ssh kinds of failure SHALL be:

| Kind | Reason | Hint (sentence: command) |
|---|---|---|
| `ssh_denied` | `<host> refused this machine's ssh key` | `Check that this machine's ssh key is added to your account on <host>:` `ssh -T <user>@<host>` |
| `host_key` | `this machine does not know <host>'s ssh host key yet` | `Connect once in a terminal and accept the host key:` `ssh -T <user>@<host>` |

#### Scenario: An ssh key the host refuses
- **WHEN** git prints `git@github.com: Permission denied (publickey).`
- **THEN** the kind is `ssh_denied` with the hint `ssh -T git@github.com`

## ADDED Requirements

### Requirement: In LADO's container an ssh failure points at the git servers

In LADO's container both ssh kinds of an ssh address of the user `git` on port 22
(`git@<host>:`, `ssh://git@<host>[:22]/`) of a host with no saved git server SHALL say `LADO's container has no ssh key for <host>`, with the hint `Add it
as a git server with a token:` `lado git-server add https://<host> --token` and the UI's
way out `Add git server`: `Add <host> as a git server with a token: its git@ addresses
then go over https too.`

#### Scenario: github.com not saved
- **WHEN** in the container the clone of `git@github.com:acme/app.git` fails with
  `Permission denied (publickey)` or `Host key verification failed` and no github.com entry
  is saved
- **THEN** the reason is `LADO's container has no ssh key for github.com`, the hint is
  `lado git-server add https://github.com --token`, and Clone from URL shows `Add git
  server ↗` opening Settings → Git servers with `https://github.com` in Address

#### Scenario: Outside the container
- **WHEN** the same github.com failure happens outside LADO's container
- **THEN** the kind's reason and hint are those of the ssh kinds' table

### Requirement: In LADO's container another ssh address asks for https

In LADO's container both ssh kinds of any other ssh address (another user or none, a port
other than 22, a host with a saved git server, or saved servers LADO cannot read: lado.db
at another schema) SHALL say `LADO's container has no ssh: clone by the
repository's https address`, with no hint and no way out.

#### Scenario: Another ssh port
- **WHEN** in the container the clone of `ssh://git@git.example:2222/team/app.git` fails
  with `Permission denied (publickey)`
- **THEN** the reason is `LADO's container has no ssh: clone by the repository's https
  address`, with no hint and no way out
