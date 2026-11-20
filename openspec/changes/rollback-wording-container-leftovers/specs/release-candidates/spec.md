## ADDED Requirements

### Requirement: rollback's plan names the sessions it does not start again

When lado.db will be restored, `rollback`'s plan SHALL name the running sessions the copy
lacks on one line `- not started again, not in the copy: <names>`, before
`Roll back? [y/N]`: `rollback` stops every session before `lado update <final>`, so the
update's own warning names none.

#### Scenario: A session started on the RC
- **WHEN** lado.db's schema is newer than the copy's, and sessions `app` and `web2` run,
  of which the copy has only `app`
- **THEN** the plan names `app` among the sessions started again and has the line
  `- not started again, not in the copy: web2`, before `Roll back? [y/N]`
