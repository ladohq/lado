## 1. Settings

- [x] 1.1 `.lado/tracker.yaml`: add `fields:` with `release:
  73563bdb-7110-43da-95e7-a60c01b07984` (the board's text sticker `Release`). Check:
  `yougile.py field LAD-119 release` prints `LAD-119: release not set` (or its value), not
  exit 3.
- [x] 1.2 `.lado/sdlc.md`: a section `## After the merge` between Tracker and Checks, with
  the parts "Into the base branch" (comment by the moved template, status `done`, label
  `waiting for release` and what removes it, field `release` = X.Y.Z of the
  `(unreleased)` heading on the target after the merge; without the heading «войдёт в
  следующий релиз» and the field untouched) and "Into an epic branch" (only the comment,
  first line «**Слит PR #<n> в эпик-ветку `<branch>`** — войдёт в релиз вместе с
  эпиком.», the rest of the template as is; the task stays in review), in the shape of
  kit-sdlc's `sdlc.example.md`.
- [x] 1.3 `.lado/sdlc.md`, Tracker: remove "Waiting for release label", "After a merge
  into the base branch …" and "Merge comment" (moved to 1.2); Component labels and
  Skipped issue types stay.
- [x] 1.4 `.lado/sdlc.md`, Extra instructions, Integrator: remove the rule "After a merge
  into the base branch, besides the merge comment …"; the other integrator rules stay.
  Check for 1.2–1.4: `grep -n "Waiting for release label\|as \*\*Tracker\*\* says"
  .lado/sdlc.md` finds nothing.

## 2. The release

- [x] 2.1 `docs/release.md`, section 5 (The final), step 3: each shipped task also gets
  the field `release` set to X.Y.Z (no change when it already holds it); a task not in
  the release keeps its label and field; "The merge sets that label (`.lado/sdlc.md`,
  Tracker)" reads "(`.lado/sdlc.md`, After the merge)", and the field's sticker is named
  in `.lado/tracker.yaml` too.

## 3. Regression

- [x] 3.1 `make lint`, `make test` (the docs and settings tests, e.g.
  `tests/test_agents_md.py`, stay green; numbers in the build report).
- [x] 3.2 `openspec validate release-field-on-tasks --strict` and `openspec validate
  --specs --strict`; `grep -rn "waiting for release\|Release" openspec/specs` finds no
  rule that contradicts `release-tracking`.
- [ ] 3.3 After the merge (integrator, not the build): LAD-119 shows the merge comment,
  `done`, the label `waiting for release` and `Release` = 0.42.1 (the CHANGELOG heading
  then); the integrator's note names each.
