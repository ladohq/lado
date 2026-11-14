## ADDED Requirements

### Requirement: A smoke cell runs its tests on three workers

A smoke cell (`scripts/smoke_ci.py run <provider> <out>`) SHALL run its provider's smoke
tests with `uv run pytest -m smoke -n 3 --dist worksteal -v -k <provider>`, on every system
it runs on, with the same pass rule as a serial run. `make test-smoke` SHALL keep running
the smoke tests serially (`-n0`).

#### Scenario: A cell in CI

- **WHEN** the cell `smoke macos-latest claude` runs
- **THEN** its tests run on three pytest-xdist workers, and a worker that ends its share
  takes tests still queued for another

#### Scenario: The same tests as before

- **WHEN** a pull request's run needs the smoke
- **THEN** each cell runs the same tests as a serial run, and passes only on pytest's exit
  0 with a test passed and none skipped

#### Scenario: Run by hand

- **WHEN** a person runs `make test-smoke PROVIDER=kilo`
- **THEN** the tests run one at a time
