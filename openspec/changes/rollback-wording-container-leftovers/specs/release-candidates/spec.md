## MODIFIED Requirements

### Requirement: rollback prints its plan and asks first

Before it changes anything `rollback` SHALL print its plan:
the sessions that run (not stopped in lado.db) and will be started again, whether the UI
server runs and will be started again, the final it installs, and whether lado.db will be
restored from the copy, which is when its schema (`PRAGMA user_version`) is newer than the
copy's, with what that loses (everything done on the RC) and, on a line
`- not started again, not in the copy: <names>`, the running sessions the copy lacks; and
it SHALL ask `Roll back? [y/N]`.

#### Scenario: Back to the final without a schema change
- **WHEN** lado.db's schema equals the copy's
- **THEN** the plan says lado.db is kept, and the rollback restores nothing

#### Scenario: A session started on the RC
- **WHEN** lado.db's schema is newer than the copy's, and sessions `app` and `web2` run,
  of which the copy has only `app`
- **THEN** the plan names `app` among the sessions started again and has the line
  `- not started again, not in the copy: web2`, before `Roll back? [y/N]`
