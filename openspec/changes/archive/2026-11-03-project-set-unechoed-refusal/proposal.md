Task: LAD-181

## Why

Symptom (found in the review of LAD-177, 2026-11-02; checked by hand on main 666e372b with
Python 3.13 and 3.10): `lado project set` prints a secret's value in argparse's error when
the value is given where argparse cannot take it, exit 2:

- `lado project set shop GH_TOKEN -s3cr3t --secret` (and `--secret -s3cr3t`, `--s -s3cr3t`,
  or a second word, `a b --secret`): `lado: error: unrecognized arguments: -s3cr3t`.
- `--secret=s3cr3t`: `argument --secret: ignored explicit argument 's3cr3t'` (with or
  without the dash).
- `--help=s3cr3t`, `--he=s3cr3t`, `-h=s3cr3t`: `argument -h/--help: ignored explicit
  argument 's3cr3t'`; on Python 3.10 `-hs3cr3t` too (3.13 prints the help there).

The value then sits in the terminal, its scrollback and any log of the output, which `lado
project set --secret` promises never to do. A value that argparse does take (`ghp_3
--secret`, `--secret -- -s3cr3t`) is refused unechoed (`cli._secret_value`).

Cause: argparse quotes the words it refuses. `value` is an optional positional
(`nargs="?"`), so a word that looks like an option never becomes it and is left over; the
top-level parser reports leftovers with `unrecognized arguments: <words>`. An explicit
argument given to a flag (`--secret=…`, `--help=…`) is quoted by the subparser's own
error. Neither path passes through LADO's code, so `_secret_value`'s refusal never runs.
The code is in main and in released versions.

Options weighed:

- A: refuse the dashed value only, by scanning argv for `project set` before parsing.
  Cheap, but a second parser of the same command line that drifts from argparse's own
  (prefixes, `=`, `--`), and the `--secret=…` and `--help=…` paths stay.
- B (taken): the parser of `lado project set` refuses unechoed, as `lado model-server probe`
  does on the epic branch (LAD-177): its own `error()` prints its usage and a fixed text,
  exit 1; `cli.main` parses with `parse_known_args` and sends leftovers of `project set` to
  that same `error()`. Every refusal argparse makes for the command takes the one path; the
  rest of the CLI keeps argparse's messages.
- C: drop argparse for `project set` and parse its few words by hand. Most control, but a
  hand parser beside argparse for one command, and its help and usage made by hand.

## What Changes

- Any refusal of the command line of `lado project set` by argparse (a word left over, an
  argument given to a flag, a missing id or name) prints the command's usage and one fixed
  text that names no word of the command line, exit 1, nothing read and nothing stored.
- `-h` and `--help` alone print the help as before; every other path is unchanged.
- docs/cli.md and CHANGELOG.md (0.45.0, Fixed) say so. A patch: a fix only.

## Scope

- The parser of `lado project set` and the leftover check of `cli.main`.
- A unit canary in `tests/test_cli.py`, run by CI on Python 3.10 and 3.13.

## Out of scope

- Other commands' argparse errors: no other command of main takes a secret on its command
  line; `lado model-server probe` (epic LAD-154) has its own fix already.
- The BACKLOG.md entry of this defect: it is only on the epic branch (LAD-177); whoever
  merges main into the epic removes it there, and folds probe's leftover branch into the
  mechanism of this change (design D3).
- The plain variable's refusal of a dashed value keeps no echo either: a value of a plain
  variable is no secret, but the command cannot tell `--secret` was meant when the words
  are refused, and the fixed text says how to give a dashed value (`--`).

## Impact

- `src/lado/cli.py`: a parser class for `project set`, `cli.main`'s parse.
- `tests/test_cli.py`; `docs/cli.md`; `CHANGELOG.md`.
- Spec: `projects` (one requirement added).
