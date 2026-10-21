Task: LAD-119

## Why

The release a task ships in should show on its card, in the board's text sticker
`Release`, not only in the merge comment. kit-sdlc 0.6.0 (LAD-118) made the integrator do
after a merge exactly what the project's `.lado/sdlc.md` says in its section **After the
merge**, and nothing else; tracker-yougile 0.5.0 (LAD-113) can write a text sticker with
`field`. LADO's `.lado/sdlc.md` has no such section yet: its rules for a merged task (the
`waiting for release` label, the status `done`, the comment's template) still sit in
**Tracker**, which kit-sdlc 0.6.0 no longer acts on, only names. Until this change, a
merge into main leaves the task as it was.

Root cause: the project's settings were written for kit-sdlc before 0.6.0, and the board
had no text sticker for the release (the human created `Release` at this design).

Options weighed:

1. **Move the rules into After the merge and add the field** (chosen): the kit stays
   neutral, the project's words live in one place, and the release overwrites the field
   with the version it ships. Cost: one more tracker write per merge and per shipped task.
2. **Keep the rules in Tracker and the extra instruction for the integrator**: kit-sdlc
   0.6.0 ignores them; it would need a per-project override of the kit, the second source
   of truth AGENTS.md forbids.
3. **The version in the comment only**: what is done today; the card shows no release, and
   a minor that turns a planned patch into another version leaves a wrong number in the
   comment with nothing to correct.

## What Changes

- **`.lado/sdlc.md`, a new section After the merge** (between Tracker and Checks):
  - into the base branch: the merge comment by the current template (`**Слит PR #<n>** —
    войдёт в релиз <X.Y.Z>.`, X.Y.Z from CHANGELOG.md's `## X.Y.Z (unreleased)` heading
    on the target after the merge), the status `done`, the label `waiting for release`,
    the field `release` set to X.Y.Z; without such a heading the comment says «войдёт в
    следующий релиз» and the field is not touched;
  - into an epic branch: only a comment, by the same template with the first line
    `**Слит PR #<n> в эпик-ветку `<branch>`** — войдёт в релиз вместе с эпиком.`; the task
    stays in review.
- **`.lado/sdlc.md`, Tracker**: the lines "Waiting for release label", "After a merge
  into the base branch …" and "Merge comment" go; the label's meaning (it stays until the
  release that ships the task removes it) moves to After the merge.
- **`.lado/sdlc.md`, Extra instructions, Integrator**: the rule "After a merge into the
  base branch, besides the merge comment and the waiting-for-release label, move the
  task to the status `done` …" goes: After the merge says it, and kit-sdlc 0.6.0 does
  only what that section says.
- **`.lado/tracker.yaml`**: `fields: release: 73563bdb-7110-43da-95e7-a60c01b07984`, the
  board Development's text sticker `Release`.
- **`docs/release.md`, The final, step 3**: each task the release ships also gets the
  field `release` set to X.Y.Z (unchanged when it already holds it), so a task merged
  before this change, or one whose planned patch became a minor, shows the version it
  shipped in; a task not in the release keeps its label and its field.

## Scope

`.lado/sdlc.md`, `.lado/tracker.yaml`, `docs/release.md`, the new capability spec
`release-tracking`. No change to LADO itself (`src/`, `web/`), its CLI, UI, API or schema.
Version: patch at most (settings and docs); no CHANGELOG.md line, as users of LADO see
nothing.

## Out of scope

- A check on the board polygon (LAD-118's "how to check"): it tests kit-sdlc, already
  released; this change is checked by its own merge, where the integrator runs the new
  section on LAD-119 and its `Release` sticker gets 0.42.1.
- Release candidates writing the field: an RC ships no task as final; the field holds the
  final release only.
- Updating kit-sdlc in other sessions of the project: this session already runs 0.6.0;
  a session started with an older kit is the human's to restart, not a file of the repo.
- Filling the field on tasks already released: the next final writes it on the tasks it
  ships; older ones keep their comment.

## Impact

- `.lado/sdlc.md`, `.lado/tracker.yaml`, `docs/release.md`.
- New capability spec `release-tracking`.
- The tracker: after each merge into main the task's `Release` sticker holds the coming
  version; after each final release, the shipped one.
