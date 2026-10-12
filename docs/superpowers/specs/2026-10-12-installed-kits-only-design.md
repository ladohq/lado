# Installed kits only: design

Task: LAD-22. Change: `openspec/changes/installed-kits-only/`.

## Problem

A kit can live in a session's repository (`<repo>/.lado/kits/<name>/`) and win over an
installed or built-in kit of the same name. The kits a human can use therefore depend on
the folder:

- the New session window asks for the kit list again for every folder and cannot offer
  the kits of that folder before it is chosen (a later task loads the list once);
- a session started on a cloned repository (LAD-6) would start the MCP servers of that
  repository's kits without any question, while installing a kit from git shows what it
  starts and asks first;
- every consumer of the kit list carries a "project kit shadows it" exception.

Root cause: the kit lookup takes the session's folder as an input.

## What the user sees after the change

- `lado kits` lists the installed kits, then the built-in ones, the same in every folder;
  `--repo` is refused as an unknown argument.
- `lado start <repo> --kit team` with `team` only in `<repo>/.lado/kits` is refused:
  `kit "team" not found; looked in the installed kits in …/lado.db, …/builtin_kits`.
  A stopped session that used such a kit fails the same way on resume.
- To use a kit folder, the user installs it once: `lado kits add <folder>`; LADO reads it
  in place, so edits show in the next agent (docs/kits.md, "Develop it from a folder").
- The New session window is not changed (another task, the human's decision): it still
  asks for the kit list per folder, and gets the installed and built-in kits every time.
- `lado kits remove` and the Kits page's remove dialog name every session that uses the
  kit.
- CHANGELOG (0.36.0) says project kits are no longer read and how to install a folder.

## Options

| Option | Long-term cost | Verdict |
|---|---|---|
| Remove project kits | none added; a parameter, an option and an exception go | chosen (the task) |
| Keep them, ask before their MCP servers start | a confirmation path in core, CLI and UI that LAD-6 and LAD-7 must carry; the Launch list still per folder | no |
| Keep them behind an opt-in | two lookups to test and document | no: no kit in use relies on them |

## Design

The technical decisions are D1–D12 in `openspec/changes/installed-kits-only/design.md`:
the lookup loses its `repo` parameter (D1); shadowing remains only installed over built-in
(D2); `Found.where` is `user` or `built-in` and the broken-link handling that only served
project folders goes (D3); the CLI (D4) and the API (D5) follow, the web UI's sources stay as they are (D6);
`kit_users` counts every session (D7); tests install folder kits with one helper (D9).

## Test layers

| Requirement | Layer | Tests |
|---|---|---|
| Kits come only from the installed and the built-in ones | unit; integration for a real start | `tests/test_kits.py`, `tests/test_cli.py`, `tests/integration/test_session_start.py` |
| The kit list does not depend on a folder | unit (CLI, API) | `tests/test_cli.py`, `tests/test_server_launch.py` |
| A kit's users are every session that names it | unit | `tests/test_runtime.py`, `tests/test_server_kits.py` (remove-preview) |

Everything else is a regression run: the unit suite, the changed integration and UI files,
and CI's full `make check` with the smoke. The live test changes are written, not run.

## Version

Minor (CLI and API change); it lands in 0.36.0, already the unreleased minor.
