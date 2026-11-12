## Purpose
The test audit's tools: what they measure about each test (the lines it runs, its time,
whether it can fail), where they run, and when a batch of deleted tests counts as proven.

## ADDED Requirements

### Requirement: The audit runs apart from the working tree and the checks

`make test-audit` SHALL write everything it measures to a folder outside the repository
(`--out`, by default `<temp dir>/lado-test-audit`), SHALL mutate code only in a copy of the
repository, never in the working tree, and SHALL be part of neither `make check` nor CI.

#### Scenario: The working tree stays clean

- **WHEN** `make test-audit` runs its pseudo-tested and mutation commands to the end, or is
  interrupted in the middle
- **THEN** `git status` in the repository shows no change, and the mutants exist only in the copy

#### Scenario: Not in the checks

- **WHEN** `make check` or a CI run on a pull request runs
- **THEN** no command of the audit runs

### Requirement: Per-test coverage of the unit, integration and UI layers

The audit SHALL record, for each test of the unit, integration and UI layers, the lines of
`src/lado/` and `scripts/` that the test executed, also in the processes the test started (the
`lado` commands, `lado mcp`, the hooks, the UI server), each attributed to that test only.

#### Scenario: A line run by a hook belongs to its test

- **WHEN** an integration test starts a fake agent whose hook runs `lado.hooks.handle`
- **THEN** the lines of `handle` that ran are in that test's record and in no other test's

### Requirement: Subset candidates

The audit SHALL list as a candidate each test whose recorded lines are all among the lines of one
other test of the same layer, naming that other test; cases of one parametrized test function
SHALL NOT be compared with each other. A candidate is a proposal for the human, never a deletion.

#### Scenario: A test inside another

- **WHEN** test A of the unit layer ran lines 10–20 of `runs.py` and test B of the same layer ran
  lines 1–40
- **THEN** A is listed as a candidate with B named as the test that covers it

#### Scenario: Cases of one function

- **WHEN** two cases of one parametrized test function run the same lines
- **THEN** neither is listed as a candidate because of the other

### Requirement: Pseudo-tested functions of the core

The audit SHALL replace, one function at a time in the copy, the body of each function of
`runtime.py`, `hooks.py`, `state.py`, `runs.py` and `flows.py` with an empty return, run the tests
that executed that function, and list the function as pseudo-tested when none of them fails.

#### Scenario: A function no test checks

- **WHEN** tests execute a function but none of them fails after its body becomes an empty return
- **THEN** the report lists the function with the tests that executed it

#### Scenario: A function no test runs

- **WHEN** no test executed a function
- **THEN** the report lists it as not covered, apart from the pseudo-tested ones

### Requirement: The mutation proof of a deletion

A batch of deleted or moved tests SHALL count as proven only when, on each module whose lines a
deleted test executed, mutmut run before the batch (on its target branch) and after it finds no
mutant that was killed before and survives after; the batch's pull request SHALL carry both
results.

#### Scenario: A deletion that loses a check

- **WHEN** a batch deletes a test, and a mutant of `runs.py` that only this test killed survives
  after the batch
- **THEN** the proof fails and names the mutant and the deleted test that killed it

#### Scenario: A deletion that loses nothing

- **WHEN** every mutant of the touched modules killed before the batch is killed after it
- **THEN** the proof passes and prints each module's score before and after

#### Scenario: A mutation run stopped in the middle

- **WHEN** the mutation command is interrupted after mutmut checked some of the mutants
- **THEN** each module's result is still written, says that the run was stopped, marks the
  mutants not checked and leaves them out of the score, and the copy is removed

#### Scenario: A deleted test of no module

- **WHEN** a deleted test executed no line of `src/lado/` or `scripts/` (a test of a document)
- **THEN** the proof names it as resting on the checklist's rule, not on mutants

### Requirement: Durations and flakiness per layer

The audit SHALL report, for the unit, integration and UI layers, each test's duration and the
layer's total, and from CI's runs on `main` of the last 30 days each job's time and each job that
passed only on a rerun.

#### Scenario: The slowest tests

- **WHEN** the durations command runs on the unit layer
- **THEN** the report lists every test of 1 s or more with its time and the layer's wall time
