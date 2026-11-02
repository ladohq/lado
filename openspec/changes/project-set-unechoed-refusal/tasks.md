## 1. The failing tests

- [x] 1.1 `tests/test_cli.py`: requirement "lado project set refuses its command line
  without repeating it", parametrized over its scenarios: `-s3cr3t --secret`, `--secret
  -s3cr3t`, `--s -s3cr3t`, `--secret=s3cr3t`, `--secret=-s3cr3t`, `--help=s3cr3t`,
  `--he=s3cr3t`, `-h=s3cr3t`, `-hs3cr3t` (on 3.13 it may print the help: then exit 0 and the
  value is not in the output either), `ghp a1 --secret`, and a missing name (`project set
  shop`). For each: `main([...])` raises `SystemExit(1)` (or returns 1), stderr is the
  usage line and the fixed text, stdout empty, the value appears in neither, stdin is not
  read (the existing `Stdin` helper), the project has no new secret or variable, and no
  file under `LADO_HOME` holds the value. Fails before 2.1. Run:
  `uv run pytest -n0 tests/test_cli.py -k unechoed`.
- [x] 1.2 `tests/test_cli.py`: scenario "A plain variable's dashed value without --"
  (`FLAGS -v` refused with the fixed text; `FLAGS -- -v` sets it); "Help alone"
  (`project set --help` exits 0 with the help); another command keeps argparse's message:
  `project show shop extra` exits 2 with `unrecognized arguments: extra`.

## 2. The fix

- [x] 2.1 `src/lado/cli.py`: the parser class and its fixed text (design D1), given to
  `project.add_subparsers(parser_class=…)`, the text on `project set` only; `main` parses
  with `parse_known_args` and sends leftovers to the quiet parser in the defaults, else to
  `parser.error("unrecognized arguments: …")` (D2). 1.1 and 1.2 pass.
- [x] 2.2 `make lint` and `make test` green.

## 3. Docs

- [x] 3.1 `docs/cli.md`, the paragraph of `lado project set`: a refusal of its command line
  prints its usage and a fixed text naming none of its words, exit 1.
- [x] 3.2 `CHANGELOG.md`, `## 0.45.0 (unreleased)`, Fixed: a bold title and at most three
  lines in the user's words (a secret typed with a leading `-` or as `--secret=…` is no
  longer printed in the error).
- [x] 3.3 `openspec validate project-set-unechoed-refusal --strict` passes.
