## 1. The page's glab ending (AC-8)

- [x] 1.1 `src/lado/git_servers.py`, `check`: an `ok` whose `tool` rights are missing ends
  its `page` (both forms, `Works: signed in as …` and `Works: <Kind>, signed in as …`) with
  `; <tool_cannot(kind, tool)>` before the full stop, as `text` does. Test first in
  `tests/test_git_servers.py` beside the test of `text` (line ~879): the page line of a
  GitLab token with `read_repository, write_repository, read_api`, checked before and not;
  a token with `api` keeps `Works: signed in as …, may clone and push.`. Check: red, then
  green; `uv run pytest -n0 tests/test_git_servers.py`.
- [x] 1.2 `src/lado/server/models.py` `GitServerAdded` and `git_entries.add`: an optional
  field with the ending (`tool_cannot(...)` when `checked.tool_missing`, else null);
  `make web-types`, both generated files committed. Test in
  `tests/test_server_git_servers.py`: the add of that token answers with
  `glab cannot open merge requests: the token lacks api`, a token with `api` with null.
- [x] 1.3 `web/src/GitServers.tsx`: Add server's `✓ Saved: <Kind>, signed in as <login>.`
  and Replace token's `✓ Token replaced: signed in as <login>.` take `; <ending>` before
  the full stop when the answer has one; Check needs no change (it shows the server's
  sentence). Tests in `web/src/GitServers.test.tsx`: the three lines with and without the
  ending. Check: `make web`.
- [x] 1.4 `tests/ui/test_git_servers_section.py`: a fake GitLab whose token has
  `read_repository, write_repository, read_api` (a profile of `tests/fake_git_api.py`, as
  `answers_as` does): Add server shows the `✓ Saved:` line with the ending, Check the
  `Works:` line with it. Check: `uv run pytest -m ui tests/ui/test_git_servers_section.py`;
  a screenshot of each of the two lines as a run artifact in `build-report`, against
  `mockup-glab-line.html`.
- [x] 1.5 docs/design/ui.md, Settings → Git servers (Check, Replace token, Add server): the
  ending, in the words of the delta. Check: `grep -n "glab cannot" docs/design/ui.md`.

## 2. The guide (AC-1 to AC-7)

- [x] 2.1 Write `docs/git-servers.md`, "Connect your git server", with the ten sections of
  the proposal's What Changes, in plain words first and the details after. Every fact from
  the code, never from memory: the token pages and scopes from `src/lado/git_kinds/github.py`
  and `gitlab.py`, the form's and the rows' words from `web/src/GitServers.tsx`. No step
  numbers of any plan, no link into `docs/epics/`. Check: each command and label named is in
  the code or in `--help`.
- [x] 2.2 The Check section: every answer of the proposal's "Check's answers" (the glab
  ending included, as 1.1 makes it), its text as the page shows it, what it means, what to
  do. Check: each quoted text compared with `git_servers.check` / `_trust` /
  `_no_answer_page` and `GitServers.tsx` (`checkLine`, `TrustCard`, `NOT_TRUSTED`,
  `KEPT_OLD`), and the pull request's table "text in the guide ↔ place in the code"
  (file:line on the branch) written from that.
- [x] 2.3 The certificate section: the trust card's facts (Signed by or Certificate, Valid,
  SHA-256) and buttons, Don't trust, a changed certificate, a file from IT with
  `lado git-server certificate <address> <file>` (in Docker:
  `docker compose exec -T lado lado git-server certificate <address> - < <file>`, tried in
  the container, or the build report says it was not) and `--certificate` of `add`. Check:
  as 2.2. Done: the stdin form (`-`) tried with `lado git-server certificate` outside a
  container; the `docker compose exec -T` wrapper not tried (no Docker in the build's
  container), as the build report says.
- [x] 2.4 No second source: flags, files under `LADO_HOME`, `lado doctor`'s lines and the
  older GitHub login's move stay in docs/install.md and docs/cli.md, linked. Check: by
  reading the guide beside "GitHub and your git servers".
- [x] 2.5 docs/install.md: an item `[Connect your git server](git-servers.md)` in the
  contents list, and one sentence with the link at the top of "GitHub and your git
  servers".

## 3. Release notes

- [x] 3.1 CHANGELOG.md, under `## 0.48.0 (unreleased)`, by docs/release.md's rules: the
  guide (**A guide to connecting your git server**), and the git servers' line, or a fix
  line, saying the page tells when `glab` cannot open merge requests.

## 4. Tests and checks

- [x] 4.1 `tests/test_git_servers_guide.py`, `test_every_link_of_the_guide_resolves`: each
  relative link of `docs/git-servers.md` names an existing file, and each `#anchor` into a
  Markdown file is one of its headings (reuse `tests/test_docker.anchors`, or move it to a
  shared helper if importing it is awkward). Check: red with a broken link, green on the
  guide; `uv run pytest -n0 tests/test_git_servers_guide.py`.
- [x] 4.2 `test_the_guide_quotes_checks_answers_as_the_code_gives_them`: a list of the
  guide's quoted answers, each with its source file and its fixed fragments (the text
  without its `<…>` parts); each fragment is in the guide and in that source. Covers every
  row of the proposal's "Check's answers", the trust card's buttons and the two lines after
  them. Check: red after changing one fragment in the guide, green as written.
- [x] 4.3 `make lint`, `make test`, `make web`, the UI test of 1.4 green (counts in the build
  report).
- [x] 4.4 `openspec validate git-servers-guide --strict` and the trial archive green.

## 5. Manual check for the human (put these steps in the pull request's description)

- [ ] 5.1 The pull request's description carries, in English: open `docs/git-servers.md`
  on GitHub's preview of the branch; follow it with your own GitHub token (and a GitLab
  one, if you have it; one without `api` shows the glab ending) on a LADO of this branch;
  say whether every step and every answer of Check is clear to someone who does not know
  git servers (AC-9).
