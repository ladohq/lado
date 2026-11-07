Task: LAD-235

## Why

`lado update <older version>` goes back to the migration's copy of `lado.db`. A way back from
0.45.0 to 0.44.0 drops every saved model server, model and default model with the database,
and the key of each server stays on disk as `~/.lado/model-servers/<id>/key`. The warning and
`docs/install.md` list only "sessions, runs, gates, messages, projects", and the older LADO
knows nothing of that folder, so its `lado doctor` says nothing either.

Root cause: both texts were written before the model server store existed, and nothing ties
the list of what is lost to what `lado.db` holds. The store keeps keys outside `lado.db` by
design (requirement "A server's key is kept in its own file"), so restoring the database
cannot take a key with it, and the older LADO cannot remove what it does not know.

A user who goes back is not told that their servers go, and a key to a paid provider stays in
a folder nothing names until they upgrade again. For projects' secrets LADO already names
exactly this case in `docs/install.md`.

Options weighed:

- A (taken): the warning names what is lost and each key folder the copy has no server for;
  the documentation says how to remove them. Costs one read of the copy the plan already opens
  and one line of output, and tells the user where they decide.
- B: the documentation alone names the keys. Less code, but the user who reads only the
  warning keeps a paid key unknowingly; the human chose A (question #4718).
- C: the way back removes the keys. Rejected: it destroys something the user may want when
  they upgrade again, and it is a change of the rollback's mechanics, out of this task's frame.

## What Changes

- The plan's warning lists saved model servers, models and default models among what is lost.
- The plan's warning names each folder under `model-servers/` that holds a key and whose server
  the copy of `lado.db` lacks, and says they stay on disk until removed by hand. With no such
  folder there is no such line.
- `docs/install.md`: the list in "Going back to an older version", its "What stays" paragraph,
  and "Go back to the version before" in the Docker section say that the keys stay and how to
  remove them.
- CHANGELOG.md: **Set models in Settings** comes down to three lines, and one item says what
  going back now tells.
- The comment over `LOSES_TOOLS` in `providers/codex.py` names `tests/live_models.py`, which
  replaced the `tests/local_models.py` it names now.
- `make test-live` runs once on the epic's code on OpenCode, Kilo, Codex and Claude Code, and
  its result is reported. This changes no file.

## Scope

- The warning of `lado update` to an older schema, and its unit tests.
- The three places of `docs/install.md`, the two CHANGELOG items and the comment above.
- The live run and its report, on the models of `.github/workflows/live.yml`.

## Out of scope

- Removing keys in the way back: the older LADO does not know them, and the mechanics of the
  way back do not change in this task.
- A repeat of the real way back on its own `LADO_HOME`: the readiness check ran it.
- A schema change or a new dependency: neither is needed.
- **The card that waits for you**, also over three lines in CHANGELOG.md: it is not this
  epic's item.
- The UI: its update offers only newer versions, so it shows no such warning.

## Impact

- `src/lado/self_update.py`: `Restore`, `_way_back`, `print_plan`.
- `src/lado/providers/codex.py`: a comment.
- `tests/test_self_update.py`, `docs/install.md`, `CHANGELOG.md`.
- Capability `update-database`: two added requirements.
- No version bump: the change ships under the existing `## 0.45.0 (unreleased)`. Alone it
  would be a patch.
