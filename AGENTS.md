# LADO: notes for coding agents

LADO (Layered Agent Delegation & Orchestration) runs teams of AI coding agents.
Current stage and next steps: [ROADMAP.md](ROADMAP.md).

## Commands

```bash
uv sync                 # create .venv and install dev tools
uv run lado --version   # run the CLI from the working copy
uv run pytest           # tests
uv run ruff format      # format
uv run ruff check       # lint (add --fix to autofix)
```

CI runs `ruff format --check`, `ruff check` and `pytest` on Python 3.10 and 3.13.

Release: `uv version <X.Y.Z>`, commit, then push tag `vX.Y.Z`. The Release workflow checks the
tag against the package version and publishes to PyPI.

## Layout

- `src/lado/`: the Python package; `cli.py` is the `lado` entry point, one module per command
  (`doctor.py`).
- `tests/`: pytest tests.
- `npm/`: placeholder npm package that only reserves the name. Leave it alone.

## Rules

- **Deliver fast.** Build only what the current roadmap stage needs.
- **Clean-room.** Ideas from other projects are welcome, but never copy their code, tests,
  prompt texts or file layout. Describe the behavior in your own words first, then write
  the implementation from scratch.
- **Tasks and bugs** go to the external task tracker, not to GitHub Issues.
- Python 3.10+. Standard library first; add a dependency only when it clearly saves work.
