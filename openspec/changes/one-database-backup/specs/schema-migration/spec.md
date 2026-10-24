## MODIFIED Requirements

### Requirement: LADO backs lado.db up before it upgrades the schema

Before LADO upgrades `lado.db` to a newer schema, by any command that migrates it, it SHALL
copy `lado.db` by SQLite's backup API to `LADO_HOME/backups/lado.db.schema-<N>`, N the
schema version before the migration, and then remove every other `lado.db.schema-*` file
of that folder (one it cannot remove stays, and the migration goes on), leaving files of
other names as they are. It is the only copy LADO makes (capability update-database).

#### Scenario: The update's backup stays
- **WHEN** `backups/` holds `lado.db.0.38.0`, left by `lado update` of an earlier LADO,
  and `lado.db.schema-26`, and a command migrates `lado.db` from schema 27
- **THEN** `backups/` holds `lado.db.0.38.0` and `lado.db.schema-27`
