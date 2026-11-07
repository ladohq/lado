## ADDED Requirements

### Requirement: The plan of an update to an older schema names model servers among the loss

The warning of the plan of an update to an older schema SHALL name saved model servers, models
and default models among what is lost.

#### Scenario: The loss names them
- **WHEN** `lado.db` has schema 39, `backups/lado.db.schema-35` exists, and the human runs
  `lado update 0.44.0`
- **THEN** the warning's list of what is lost has `model servers, models, default models`

### Requirement: The plan of an update to an older schema lists the keys that stay

The warning of the plan of an update to an older schema SHALL list each folder of
`<LADO_HOME>/model-servers/` that holds a key file and whose name is no server id of the copy
of `lado.db`, saying that these keys stay on disk until the human removes them. A copy with no
table of model servers has no server id. With no such folder the warning SHALL have no such
list. When the folder cannot be read, the list SHALL be `<LADO_HOME>/model-servers` itself.

#### Scenario: Back to a version without model servers
- **WHEN** `lado.db` has schema 39, the copy `backups/lado.db.schema-35` has no table of model
  servers, `<LADO_HOME>/model-servers/ed6044c73df5/key` exists, and the human runs
  `lado update 0.44.0`
- **THEN** stderr has `Model server keys stay on disk; remove them when you no longer need
  them:` and the line of `<LADO_HOME>/model-servers/ed6044c73df5`, before `Update? [y/N]`

#### Scenario: A server the copy still has
- **WHEN** the copy has the server `aaa` and not the server `bbb`, and the folders of both hold
  a key
- **THEN** the warning lists the folder of `bbb` and not the folder of `aaa`

#### Scenario: No key left behind
- **WHEN** `<LADO_HOME>/model-servers/` is missing, or holds only folders with no key file
- **THEN** the warning has no line about keys

#### Scenario: The folder cannot be read
- **WHEN** reading `<LADO_HOME>/model-servers/` fails with an error other than its absence
- **THEN** the plan still goes on to `Update? [y/N]`, and the warning lists
  `<LADO_HOME>/model-servers` under the line about keys
