# Connect your git server

This guide is for anyone who wants LADO's agents to work with their code on GitHub or
GitLab, also without knowing much about git servers. It goes step by step, from "I have an
account" to "the agents push there". The technical details (every command, every flag,
where LADO keeps what) are in [install.md](install.md#github-and-your-git-servers) and
[cli.md](cli.md); this guide links to them instead of repeating them.

## What this does

Your code lives on a **git server**: github.com, gitlab.com, or your company's own GitHub
Enterprise or GitLab. The agents need to download the code from it (*clone*) and send their
work back (*push*). For that the server wants to know who they are.

You make a **token** on the server once: a long password made for programs, which you can
switch off at any time. You give it to LADO in **Settings → Git servers**. From then on,
whenever an agent works on a repository from that server, LADO signs it in with your token.
LADO picks the server by the repository's address: a repository at
`https://gitlab.example.com/team/app` uses the server `https://gitlab.example.com`.

You do this once per server, not once per repository or per agent.

## 1. Make a token

Open the server in your browser, signed in as yourself, and make a token there. Give it a
name you will recognise (for example `LADO`) and an **expiry date you will remember**: when
it expires, the agents stop reaching the server until you replace it. The server shows the
token **only once**: copy it right away.

### GitHub (github.com or GitHub Enterprise)

- Where: `<address>/settings/tokens`, a **classic** token. For github.com that is
  https://github.com/settings/tokens.
- Which rights (GitHub calls them *scopes*) to tick:
  - `repo`: required, and enough for most work. It lets the agents clone, push and open
    pull requests.
  - `read:org`: only if you want it, when the agents work with pull requests of a
    repository that belongs to an organization.
  - `workflow`: only if you want it, when the agents should change files under
    `.github/workflows/` (GitHub's automation).
- A *fine-grained* token works too, but GitHub does not tell LADO what it allows, so
  **Check** cannot see its rights and says so (see the answers below).

### GitLab (gitlab.com or your company's)

- Where: `<address>/-/user_settings/personal_access_tokens`. For gitlab.com that is
  https://gitlab.com/-/user_settings/personal_access_tokens.
- Which rights (scopes) to tick:
  - `api`: the recommended one. It covers everything, including the agents opening
    *merge requests* (GitLab's word for pull requests).
  - Without merge requests, only clone and push: `read_api`, `read_repository` and
    `write_repository`, all three. LADO refuses a token without `read_api`, because it uses
    it to ask GitLab who the token belongs to. With such a token everything works but
    merge requests, and LADO says so in its answers (`glab cannot open merge requests: the
    token lacks api`).

## 2. Add the server

1. In LADO, open **Settings → Git servers** and press **+ Add server**.
2. In **Address**, type the server's address as you open it in a browser: `github.com`,
   `gitlab.com`, or your company's, such as `gitlab.example.com`.
   While you type, LADO asks the server what it is:
   - `GitLab answers.` or `GitHub answers.`: good, and a link to **its token page** appears
     if you still need a token.
   - `⚠ Plain http://: the token travels unencrypted.`: the address starts with `http://`.
     Anyone on the network between LADO and the server could read the token. Use the
     `https://` address if the server has one.
   - `⚠ The server's certificate is not trusted.` with a card: your company's server uses
     its own certificate. See [Your company's certificate](#your-companys-certificate).
   - No answer (for example `No answer in 5 seconds.`) and a choice of **Kind**: LADO cannot
     reach the server's API right now. If you know the server works, choose GitHub or GitLab
     and press **Add without a check**; you can check it later from its row.
3. Paste the token into **Token**.
4. Press **Add server**. LADO checks the token before it saves anything. When it works, the
   server's row opens with a line such as `✓ Saved: GitLab, signed in as <login>.`, where
   `<login>` is your user name on that server.

A token that lacks a right is saved with a warning instead, for example `⚠ The token lacks
write_repository: agents can clone but not push.`: make a token with the rights of step 1
and press **Replace token** in the server's row.

If the token is refused, the form says so under **Token** (for example `GitLab refused this
token: copy it whole or make a new one.`) and nothing is saved. Copy the token again, whole,
or make a new one.

Agents that are already running get the new server after they restart; new agents get it
right away.

## 3. Press Check

Open the server's row and press **Check** next to Sign-in. LADO asks the server whether the
saved token still works and shows one line with the answer. Do it after you add a server,
when something stops working, or when a token may have expired.

Each answer, what it means, and what to do (`<login>` is your user name, `<scopes>` the
missing rights):

| The line | What it means | What to do |
|---|---|---|
| `Works: signed in as <login>, may clone and push.` | Everything is fine. | Nothing. |
| `Works: GitLab, signed in as <login>.` (or `GitHub`) | The first check of a server that was added without a check: it works. | Nothing. |
| `Works: signed in as <login>, may clone and push; glab cannot open merge requests: the token lacks api.` | GitLab: the agents can clone and push, but cannot open merge requests: the token has no `api`. | If you want merge requests, make a token with `api` and press **Replace token**. |
| `Works: signed in as <login>; the token's rights are not checked.` | The token works, but the server does not say what it allows (a GitHub fine-grained token, or an older GitLab). | Nothing, if the agents can push. If they cannot, make a token as in step 1. |
| `GitHub refused the token: it expired or was revoked.` (or `GitLab`) | The token no longer works. | Make a new token and press **Replace token**. |
| `The token lacks <scopes>.` | A right the agents need is missing. The ⓘ says what it means, for example `Agents can clone but not push with it. Make one with the scope api.` | Make a token with the rights of step 1 and press **Replace token**. |
| `The token lacks read_api.` | GitLab: LADO cannot ask GitLab who you are with this token. The ⓘ says `LADO asks the server's API with it. Make one with the scope api.` | Make a token with `api` (or the three rights of step 1) and press **Replace token**. |
| `Its token file is missing.` | LADO cannot find the saved token. | Press **Replace token** and paste a token. |
| `⚠ No answer in 5 seconds.`, `⚠ No answer: the name is not found.`, `⚠ No answer: the connection is refused.` or `⚠ No answer: TLS failed (<why>).` | LADO did not reach the server. The ⓘ says `Check that LADO's computer reaches the server: the company VPN or proxy; with LADO in Docker, its container.` | Connect to your company's VPN if it needs one, then press **Check again**. |
| `⚠ The server's certificate is not trusted.` | Your company's server uses its own certificate. | See [Your company's certificate](#your-companys-certificate). |
| `⚠ The server's certificate has changed since you trusted it.` | The server shows another certificate than the one you trusted. | See [A changed certificate](#a-changed-certificate). |
| `The server's certificate is not issued for <host>: trusting it would not help. Ask the server's administrator.` | The certificate belongs to another address. | Ask whoever runs the server; check that you typed the right address. |
| `The server's certificate names its host only in the old Common Name field, which LADO refuses: ask the server's administrator to reissue it.` | The certificate is made in an old way LADO does not accept. | Ask whoever runs the server to issue a new one. |
| `The server's certificate expired on <date>: ask the server's administrator to renew it.` | The server's certificate is out of date. | Ask whoever runs the server to renew it. |
| `It redirects to <address>: add that address instead.` | The server sends LADO somewhere else, for example a sign-in page or a new address. | Remove the server and add the address the line names. |
| `It answers as GitHub, not GitLab: remove it and add it again.` (or the other way round) | The server was saved as the wrong kind. | Press **Remove server**, then add it again: LADO finds the kind itself. |
| `It answers as neither GitHub nor GitLab.` | The address is not a GitHub or GitLab LADO knows. | Check the address; it should be the one you open in a browser. |

When a check fails, the server's row says so even when it is closed, for example `✕ check
failed: token refused`.

**Replace token** works like adding: paste the new token, press **Save token**, and LADO
checks it before it saves it (`✓ Token replaced: signed in as <login>.`). If the new token
belongs to another user than before, the line says who it was before.

## Your company's certificate

A company's own server often has a certificate (the server's proof of identity) signed by
the company itself, not by an authority every computer knows. LADO then asks you, at
**Add server** or at **Check**: `⚠ The server's certificate is not trusted.` with a card
that asks whether to trust this server, showing:

- **Signed by** (or **Certificate**): who issued it, usually your company's name;
- **Valid**: from when to when it is valid;
- **SHA-256**: its fingerprint, a long code unique to this certificate.

**Compare the fingerprint with your IT department** before you trust it: the card says
`Trust it only if you expected this authority. In a company network your IT department can
confirm the fingerprint.` If it matches, press **Trust this server**. LADO and the agents'
git then trust this certificate for this server alone; nothing else on your computer
changes. LADO checks the server again right away and shows its answer after `Certificate
trusted.`

If you are not sure, press **Don't trust**. Nothing is trusted, and at **Check** the line
says `Not trusted: LADO and agents cannot clone or push here over https.` (at **Add
server**: `⚠ Not trusted, so LADO cannot ask the server. Choose its kind to save it without
a check.`). You can press **Check** later, once IT has confirmed the fingerprint.

### A changed certificate

Certificates are renewed from time to time. When the server shows another certificate than
the one you trusted, **Check** says `⚠ The server's certificate has changed since you
trusted it.` and the card shows **Before** and **Now**.

**If your IT department did not announce a new certificate, do not trust it**: someone may
be between LADO and the server. Ask IT first. Then:

- **Trust the new certificate** when IT confirms it;
- **Keep the old one** otherwise. The line then says `The saved certificate does not fit the
  server: LADO and agents cannot clone or push here over https.` until the server shows the
  old certificate again, or you trust the new one.

### A certificate file from IT

Your IT department may give you the company's root certificate as a file (a text file that
starts with `-----BEGIN CERTIFICATE-----`, often named `.pem` or `.crt`). You can give LADO
that file in the terminal instead of trusting the card:

- without Docker: `lado git-server certificate <address> <file>`;
- with LADO in Docker, from the folder of LADO's `compose.yaml`:
  `docker compose exec -T lado lado git-server certificate <address> - < <file>`
  (the `-` reads the file from the terminal's input, so the file can stay on your
  computer).

When you add the server in the terminal, `lado git-server add` takes the file too, with
`--certificate <file>`. The details: [cli.md](cli.md) (`lado git-server certificate`) and
[install.md](install.md#github-and-your-git-servers).

## The agents at work

Start a session on a repository whose address is on the saved server, or bring one in with
**Clone from URL**. The agents then clone and push with your token, with nothing more to
set up.

- Each agent is told which server its repository is on and which tool goes with it: `gh`
  for GitHub's pull requests, `glab` for GitLab's merge requests.
- Addresses that start with `git@` (ssh addresses, such as `git@github.com:team/app.git`)
  work too: for a saved server LADO takes them over https with its token.
- A repository on a server that is not saved gets no token: when its clone is refused,
  LADO says to add the server, with a link to Settings → Git servers.

## Commit author (optional)

Each server's row has **Commit author**: the name and email on the agents' commits to that
server's repositories. Press **Set author** to give one, for example a work email for your
company's server. Without one, the agents' commits carry your own git author, as everywhere
else. The terminal's way: [cli.md](cli.md) (`lado git-server author`).

## What LADO does not use

LADO signs the agents in with the token of Settings → Git servers, and only that. It does
not use:

- your own sign-in of GitHub's or GitLab's tools (`gh auth login`, `glab auth login`);
- a `GH_TOKEN` or `GITLAB_TOKEN` from outside: from your shell, a project's variables or
  the `secrets/` folder.

So a token you used before LADO does not reach the agents by accident, and you change the
agents' access in one place. If you used a GitHub login with an older version of LADO, it
was moved into Settings → Git servers once: see
[install.md](install.md#github-and-your-git-servers).

## With Docker or without

The steps are the same. The difference is what is installed:

- **In Docker**, LADO's image already has `gh` and `glab`.
- **Without Docker**, install them yourself: `gh` for GitHub, and `glab` 1.114.0 or newer
  for GitLab. Without them the agents' git still works, but they cannot open pull or merge
  requests. See [install.md](install.md#glab-is-not-on-the-agents-path-or-glab--is-older-than-11140).

## More

- [install.md, GitHub and your git servers](install.md#github-and-your-git-servers): the
  technical details of tokens, certificates and the move of an older GitHub login.
- [install.md, git over ssh](install.md#git-over-ssh): ssh addresses in Docker.
- [cli.md](cli.md): every `lado git-server` command and line, and what `lado doctor` says
  of each server.
