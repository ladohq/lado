# Releasing LADO

A minor release is first published as a release candidate (RC): a PyPI pre-release
`X.Y.0rcN` that the human installs on their own LADO and works with before anyone else
gets it. Users are never offered an RC: `pip install lado`, `uv tool install lado`,
`lado update`, the daily check and the System panel take final releases only. A LADO that
runs an RC is offered newer RCs and the final, and says it is a pre-release (`lado doctor`,
the System panel's `pre-release` pill).

## 1. When an RC is needed

- Every minor release, `X.Y.0`: the Release workflow refuses its final without an RC.
- A patch, `X.Y.Z` with Z > 0, at the human's choice: with an RC, the same rules hold;
  without one, it is released directly (section 5 without the RC).

## 2. The RC

1. `uv version X.Y.ZrcN` (N from 1), commit `Release candidate X.Y.ZrcN` on main, push.
   CHANGELOG.md is not touched: its `## X.Y.Z (unreleased)` stays until the final.
2. CI is green on that commit, the smoke on Linux and macOS with it.
3. The Windows probe on it is green: `gh workflow run windows-shell.yml --ref main -f
   runner=windows-latest` (the smoke included), then `gh run watch <id> --exit-status`.
4. `make test-live` locally for every provider, Claude Code with the human's yes.
5. Push the tag `vX.Y.ZrcN`. Its spelling is PEP 440's, no dash (`v0.37.0rc1`, never
   `v0.37.0-rc1`): the workflow compares the tag with `uv version --short`. The Release
   workflow publishes `X.Y.ZrcN` to PyPI as a pre-release.

## 3. The freeze

From the first RC to the final, only fixes for the RC are merged to main. Each fix is
released as the next RC (section 2 again, N + 1), and the human's LADO is offered it. Any
other merge makes the final impossible: the workflow's check finds code the last RC did
not have, and a new RC from main is needed. Nothing in LADO enforces the freeze; the check
in section 6 catches a mistake before it is published.

## 4. The manual checklist

The human, on the RC:

- A clean install in a home of its own: `LADO_HOME=$(mktemp -d) LADO_TMUX_SOCKET=lado-rc
  uvx --from lado==X.Y.ZrcN lado doctor`, then with the same variables `lado start` of a
  scratch repository and `lado stop`.
- The upgrade of the human's own LADO from the last final with a session running:
  `lado update X.Y.ZrcN`. The migration when the schema moved, the sessions resumed, the
  UI server back; `update.log` read.
- A session with the sdlc kit through one run to its first gate, answered in the UI.
- The UI: the chat, a gate's card, the System panel with its `pre-release` pill.
- Each line of CHANGELOG.md's `## X.Y.Z (unreleased)` tried once.
- Going back when needed: `lado update <last final>`; when the schema moved, after
  `lado stop --all` restore the backup `~/.lado/backups/lado.db.<last final>` by hand.

There is no fixed soak time: the final follows the human's "ok".

## 5. The final

1. `uv version X.Y.Z`, the date in place of `(unreleased)` in CHANGELOG.md's heading,
   commit `Release X.Y.Z` on main, push. CI is green on that commit.
2. Push the tag `vX.Y.Z`. The Release workflow checks it (section 6), then builds with
   `make dist` and publishes to PyPI.

The Windows probe and the live tests are not run again: the code is the last RC's, which
they ran on.

## 6. What the workflow refuses

Before it builds, the Release workflow runs `scripts/release_check.py <tag>` on a checkout
with every tag and the history. A tag that is no final `vX.Y.Z` (an RC) passes. A final
fails, and nothing is published, when:

- it is `vX.Y.0` and no `vX.Y.0rcN` tag exists: `vX.Y.0 needs a release candidate: tag
  vX.Y.0rc1 first`;
- it differs from its last RC (the highest N) in a file other than CHANGELOG.md,
  pyproject.toml and uv.lock: `vX.Y.Z differs from vX.Y.ZrcN in <path>`, one line per file;
- it changes a line of pyproject.toml or uv.lock that is not a `version = "..."` line:
  `vX.Y.Z changes a line of <path> that is not its version: <line>`.

There is no way round it: a refused final is fixed by a new RC of what main has now
(section 2), then the final again. Delete the refused tag first (`git push --delete origin
vX.Y.Z`, `git tag -d vX.Y.Z`); PyPI got nothing.
