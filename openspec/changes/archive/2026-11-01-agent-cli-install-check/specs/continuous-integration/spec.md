## ADDED Requirements

### Requirement: A smoke cell retries an install whose CLI does not run

A smoke cell (`scripts/smoke_ci.py run <provider> <out>`) SHALL install its provider's
CLI in up to three attempts, an attempt being `npm install` of the pinned package and then
the CLI's `--version`, which succeeds only when both exit 0. After a failed attempt but
the last it SHALL print a GitHub warning annotation naming the provider and the attempt,
uninstall the package and try again. After the third failed attempt the cell SHALL fail
and run no test.

#### Scenario: npm dropped the CLI's binary once
- **WHEN** the first install exits 0 but the CLI's `--version` fails, and the second
  attempt works
- **THEN** the cell runs its smoke tests, and its log has one `::warning::` line for
  attempt 1 of 3 and one uninstall before the second install

#### Scenario: The install fails once
- **WHEN** the first `npm install` exits non-zero and the second attempt works
- **THEN** the cell runs its smoke tests after one warning and one uninstall

#### Scenario: The CLI never runs
- **WHEN** the CLI's `--version` fails after each of three installs
- **THEN** the cell fails with `<cli> --version failed after the install` and runs no
  test

#### Scenario: The install works at once
- **WHEN** the first attempt works
- **THEN** the cell installs once, uninstalls nothing and prints no warning
