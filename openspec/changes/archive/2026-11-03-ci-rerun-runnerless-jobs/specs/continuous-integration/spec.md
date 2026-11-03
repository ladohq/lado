## ADDED Requirements

### Requirement: A run whose jobs got no runner is rerun once

When a CI run completes with `failure` on its first attempt, the workflow
`.github/workflows/ci-rerun.yml` SHALL rerun the run's failed jobs once if and only if
every job that did not succeed, `ci-ok` aside, was cancelled without a runner with
GitHub's annotation "was not acquired by Runner", and no newer CI run of the same pull
request exists; it SHALL print why it reruns or does not.

#### Scenario: A macOS cell got no runner on main

- **WHEN** a push to `main` ends with the smoke cell `smoke macos-latest opencode`
  cancelled with no step, no runner and the annotation "was not acquired by Runner", every
  other job but `ci-ok` succeeded
- **THEN** the run's failed jobs are rerun once and the run's second attempt decides
  `ci-ok`

#### Scenario: A real failure beside a runner-less cell

- **WHEN** a run has a cell cancelled without a runner and a unit job that failed
- **THEN** nothing is rerun

#### Scenario: The second attempt fails the same way

- **WHEN** the rerun attempt again has a cell that got no runner
- **THEN** nothing is rerun; the run stays red for the Review trap's manual reruns

#### Scenario: A superseded run

- **WHEN** a pull request's run was cancelled because a newer push started a new run
- **THEN** nothing is rerun

#### Scenario: A newer run of the same pull request

- **WHEN** a pull request's run failed only by a runner-less cell, and a newer CI run of
  that pull request exists
- **THEN** nothing is rerun, so the newer run is not cancelled by the old one's rerun

### Requirement: The rerun workflow runs no code of the pull request

The workflow `.github/workflows/ci-rerun.yml` MUST NOT check out or run a pull request's
code, and SHALL hold no permission beyond `actions: write`, `checks: read` and
`contents: read`.

#### Scenario: A pull request changes the rerun script

- **WHEN** a pull request changes `scripts/ci_rerun.py` and its CI run fails
- **THEN** the rerun workflow runs the script of `main`, not the pull request's
