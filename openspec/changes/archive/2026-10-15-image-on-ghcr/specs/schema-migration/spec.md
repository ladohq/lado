## MODIFIED Requirements

### Requirement: A failed migration says how to go back

When a step of the migration fails, LADO SHALL leave `lado.db` as it was (the migration is
one transaction), keep the error in its error journal, and exit 1 with one message on
stderr and no traceback: `lado: could not upgrade lado.db from schema <N> to <M>: <error>.
lado.db is unchanged; its backup is <path>.`, then the way back, and `Report it with lado
bug-report.` The way back SHALL be, in a container (`update.in_container`), `To go back,
run the image of the LADO version you ran before (ghcr.io/ladohq/lado:<that version>) on
the same home volume.`, and elsewhere `To go back, install the LADO you had before.`

#### Scenario: Outside a container
- **WHEN** a migration step fails while `lado ls` migrates `lado.db` from schema 27
- **THEN** `lado ls` exits 1, stderr has the message with `install the LADO you had
  before`, `lado.db` still has schema 27, `backups/lado.db.schema-27` exists, and
  `errors.jsonl` has the error

#### Scenario: In a container
- **WHEN** the same happens with `LADO_CONTAINER=1`
- **THEN** the message names `ghcr.io/ladohq/lado:<that version>` and the same home
  volume, and no `lado:previous`
