Task: LAD-15

## Why

README's Update section is one dense paragraph written from LADO's inside: it retells the
installers (`uv tool install lado==X.Y.Z`, `pipx install --force`), the steps of
`self_update.run`, the database refusal of an older LADO and the mark of an update that
did not finish. A user who only wants to update reads all of it to find two facts: run
`lado update`, and what happens to running agents. It also never says that the web UI
updates LADO (the `live` button in the top bar, then **Update…** and **Restart and
update**; docs/design/ui.md, System panel), which the UI has done since 0.33.

The root cause: the section was the only place these details were written down for users,
so every detail landed there. The fix gives the details a place of their own
(docs/install.md, next to the install steps they continue) and keeps README to what a user
does and what to expect.

## What Changes

- README.md: the `## Update` section is rewritten to the text below (agreed with the human),
  in English as the whole README is.
- docs/install.md: a new section `## Update`, between "Your first session" and "Common
  problems", holds the details README no longer carries. The places in docs/install.md
  that say "later updates: `lado update`" (the Windows steps, Your first session, Without
  uv) link to it.
- CHANGELOG.md: one line under `## 0.36.0 (unreleased)`.

README's new section, as agreed (the developer may fix wording, not content):

````markdown
## Update

LADO tells you when a newer version is out: `lado ls` and `lado doctor` print
`LADO X.Y.Z is available: lado update`, and the web UI shows `↑ X.Y.Z` next to `live`
in its top bar.

**In the terminal**

```bash
lado update             # the latest version (lado update X.Y.Z for another one)
```

It shows what it will do and asks `Update? [y/N]` before it starts.

**In the web UI**

Click `live` in the top bar, then **Update…**. The window shows the same plan;
**Restart and update** starts it. The page waits while the server restarts, then says
how the update went.

**What happens to your work**

The update restarts your running sessions and the UI server. Runs, gates, branches and
worktrees stay; each agent starts a new conversation, and a busy agent loses its current
turn, so update while your agents are idle. If the new version does not start, LADO
puts back the one you had.

Installed with pip, from a git checkout or a git address? Then LADO cannot update
itself: `lado update` and the web UI show the commands to run by hand.

More (going back to an older version, an update that stops half way, the log):
[docs/install.md](docs/install.md#update).
````

docs/install.md's `## Update` holds, in plain words and short paragraphs:

- what `lado update` does, in order: shows the plan (versions, the installer's command,
  the sessions and the UI server it restarts) and asks; stops the running sessions and
  the UI server; backs up `lado.db` to `~/.lado/backups/`; installs exactly that version
  with the installer LADO came with (`uv tool install lado==X.Y.Z`, or `pipx install
  --force`); checks the installed version; starts the sessions and the server again;
- `--yes` skips the question, and without a terminal (a script) it is required;
- when it goes wrong: a new version that reports a wrong version, or a UI server that
  does not come up on it, is rolled back to the old version, `lado.db` restored only when
  its schema moved; everything the update said and ran is in `~/.lado/update.log`; if an
  update stops half way, `lado ls` names the sessions left stopped and the `lado start`
  that resumes each;
- going back to an older version: `lado update 0.20.0`, as far as that version accepts the
  database (an older LADO refuses a newer `lado.db` and says so);
- the check for a newer version: on PyPI, at most once a day, by `lado ls`, `lado doctor`
  and the web UI; `LADO_NO_UPDATE_CHECK=1` switches it off;
- installed otherwise (pip in a virtual environment, a working copy, a git address, also
  through uv tool or pipx): `lado update` and the web UI show the commands by hand (stop
  the sessions and the UI server, `pip install lado==X.Y.Z` into LADO's environment, start
  them again).

## Scope

- README.md's Update section; a new Update section in docs/install.md and the links to
  it there; CHANGELOG.md.

## Out of scope

- Any change to `lado update`, the update check or the UI's update panel: the task is
  about the text, and the behaviour it describes is as built (docs/design/ui.md, System
  panel; AGENTS.md, `self_update.py`).
- A screenshot of the UI's update window in README: README has no images, and the path
  in words (`live`, **Update…**, **Restart and update**) is enough. The human's decision.
- Rewriting README's other sections: not asked.

## Impact

- Docs only: README.md, docs/install.md, CHANGELOG.md. No code, API, schema or test
  change; no delta spec (no behaviour rule changes), archived with `--skip-specs`.
- Version: patch (docs only); the line goes under the unreleased 0.36.0 already open.
