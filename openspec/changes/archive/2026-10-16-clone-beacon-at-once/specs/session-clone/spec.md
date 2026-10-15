## MODIFIED Requirements

### Requirement: The server runs a clone as a job its window keeps alive

The server SHALL offer `POST /api/remote-branches` (`{url}` → `RemoteInfo`), `GET
/api/clone-target?url=&path=` (`CloneTarget`, `path` defaulting to the default folder),
`POST /api/clones` (`{url, path, branch}` → `CloneJob`), `GET /api/clones/{id}`,
`DELETE /api/clones/{id}` and `POST /api/clones/{id}/cancel` (the same cancel, for a
beacon); the POSTs and the DELETE under `Guard.changes`, the GET behind the token. A
refusal SHALL be 400 `CloneRefused` (`message`, `kind`, `hint`), a second clone into the
same folder 409, an unknown job 404, never a 500. When the window's page goes away (tab
closed or reloaded) while its clone runs, the window SHALL cancel the clone at once with
`navigator.sendBeacon` to the cancel route, from the very change of the page that first
shows the clone running until the change that shows its end, and send no beacon after
that. A job no request asked about for
`clone.ABANDONED` seconds (150: longer than the minute a browser may leave between the
timers of a tab in the background) SHALL be cancelled as Cancel clone does; a finished
job SHALL be kept `clone.KEPT` seconds (60). A server that stops SHALL cancel its running
clones.

#### Scenario: A tab closed or reloaded during the clone
- **WHEN** a clone runs and its window's page goes away
- **THEN** the window's beacon cancels it at once and the temporary folder is removed

#### Scenario: A tab closed the moment the clone shows running
- **WHEN** the window's page goes away at the very change that first shows the clone
  running (Cancel clone)
- **THEN** the window's beacon cancels it, and a page that goes away at the change that
  shows the clone's end sends no beacon

#### Scenario: A window that went away
- **WHEN** a clone runs and nobody asks `GET /api/clones/{id}` for `ABANDONED` seconds
- **THEN** the server cancels it and removes the temporary folder

#### Scenario: Two clones into one folder
- **WHEN** `POST /api/clones` names a folder another running job clones into
- **THEN** it answers 409
