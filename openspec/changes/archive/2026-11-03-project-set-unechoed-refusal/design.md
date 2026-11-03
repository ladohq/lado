## Context

`cli.main` builds one argparse tree and calls `parser.parse_args(argv)`. A subparser's own
refusal (an explicit argument to a flag, a missing positional) goes through that
subparser's `error()`; words no parser takes are collected and reported by the top-level
parser's `error()` as `unrecognized arguments: <words>`. Both quote argv. On the epic
branch, LAD-177 met the same for `lado model-server probe --key` and added a parser class
whose `error()` prints a fixed text, plus a `parse_known_args` branch in `main` for probe's
leftovers. This hotfix goes to main, where that code is not yet.

## Decisions

### D1. A parser class that refuses with a fixed text

`lado project set` is made by a subclass of `argparse.ArgumentParser` (passed with
`parser_class=` to `project.add_subparsers`, so `create`, `show`, … get it too, but only a
parser given a refusal text uses it; the others fall back to argparse's `error()`). Its
`error(message)` ignores `message`, prints its usage to stderr and exits 1 with
`lado: <text>`. The usage is argparse's own line (`usage: lado project set [-h] [--secret]
id name [value]`), which holds no word of argv. Why: every refusal argparse makes inside
the subparser (`--secret=…`, `--help=…`, `-hX` on 3.10, a missing id or name) takes one
path that cannot echo, without a second parser of argv (option A of the proposal) or a
hand parser (option C).

### D2. Leftovers go to the same `error()`

`cli.main` parses with `parser.parse_known_args(argv)`. When words are left over and the
chosen subcommand's parser refuses quietly (it put itself in its defaults, e.g.
`set_defaults(quiet_parser=project_set)`), `main` calls that parser's `error("")`;
otherwise `parser.error(f"unrecognized arguments: {' '.join(more)}")`, exactly what
`parse_args` says today, so every other command keeps its message and exit 2. Why: one
source of truth, the parser carries its own refusal for both paths; no list of
"secret-bearing commands" in `main` to drift.

### D3. Shape kept mergeable with the epic

The epic's probe has a `parse_known_args` branch of its own in `main`. When main is merged
into the epic, probe's parser takes D1's class with its text and D2's default, and its
special branch in `main` goes; its messages and exit 1 stay as the epic specifies. Named
here so the merge does not keep two mechanisms. The epic's BACKLOG.md entry "A project's
secret given on the command line with a leading `-` is printed" is removed in that merge.

### D4. The plain variable path refuses quietly too

The words are refused before `--secret` is known to be meant (`a -v --secret` vs `a -v`),
so the command cannot choose to echo for plain variables only. The fixed text tells how to
give a dashed value (`--`), which argparse's "unrecognized arguments" did not. Exit 1, as
every refusal of `lado project set` of LADO's own.

### D5. Tests: unit, both Pythons through CI

The defect is argparse's output inside one process: `main([...])` with `capsys`
(`tests/test_cli.py`) catches it, the lowest layer (AGENTS.md, Testing). CI runs the unit
suite on Python 3.10 and 3.13, which covers `-hX`'s difference. Each case also checks that
no file under `LADO_HOME` (the error journal included) holds the value and that stdin was
not read. No integration test: nothing crosses processes.

## Risks

- argparse's `exit_on_error=False` is not used: on 3.10 it does not cover every error path
  (unrecognized arguments still call `error()`), so overriding `error()` is the reliable
  hook on both versions.
- `parse_known_args` lets a subparser's leftovers through instead of failing inside
  `parse_args`: D2's else-branch keeps the old text and exit 2 for every other command; a
  test pins one (`lado project show shop extra` → `unrecognized arguments: extra`, exit 2).

## Version

A patch (fix only): CHANGELOG.md `## 0.45.0 (unreleased)`, Fixed.
