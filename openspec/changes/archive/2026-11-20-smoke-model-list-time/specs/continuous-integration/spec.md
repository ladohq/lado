## ADDED Requirements

### Requirement: The smoke gives a CLI's list of models a minute

Every smoke test SHALL give a CLI's list command 60 s (`base.MODEL_LIST_TIMEOUT`) instead of
the users' 15 s, and SHALL still fail when a session that should be checked starts with the
warning that LADO cannot check its model.

#### Scenario: A slow list on a loaded runner

- **WHEN** `kilo models` takes 20 s in the cell `smoke macos-latest kilo`
- **THEN** `test_the_session_s_model_reaches_the_cli[kilo]` starts its session with no warning
  about the model and passes

#### Scenario: A list that never answers

- **WHEN** `kilo models` does not answer within 60 s in a smoke test that starts a session with
  a model
- **THEN** the session starts with the warning that `kilo models` timed out after 60 s, and the
  test fails naming it

#### Scenario: Users keep their limit

- **WHEN** a user starts a session with a model outside the tests
- **THEN** the CLI's list command has 15 s, as before
