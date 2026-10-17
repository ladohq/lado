## ADDED Requirements

### Requirement: The UI server's token is never empty

The UI server's token in `LADO_HOME/server-token` SHALL never be empty: a file whose
content is empty or whitespace only SHALL count as missing, so the next `lado server` or
`lado ui` makes a new token and writes it, and the link `lado ui` prints SHALL carry that
token.

#### Scenario: An empty token file gets a new token

- **WHEN** `LADO_HOME/server-token` exists and is empty (or holds only whitespace), and the
  server's token is asked for
- **THEN** a new token of at least 32 characters is made, written to `server-token` (owner
  only), and returned, and the next request for the token returns the same one

#### Scenario: A token file with a token is kept

- **WHEN** `LADO_HOME/server-token` holds a token, and the server's token is asked for
  without `--new-token`
- **THEN** that token is returned and the file is not rewritten

### Requirement: The token file is written atomically

The token SHALL be written to a temporary file in `LADO_HOME`, owner only, and moved over
`server-token` in one step, so a failed write never leaves an empty or partial
`server-token`; a failed write SHALL stop the command with an error naming the path and
the reason, and SHALL leave no temporary file behind.

#### Scenario: The disk is full while the token is written

- **WHEN** writing a new token fails (e.g. ENOSPC)
- **THEN** the command fails with `cannot write the UI server's token to <path>: <reason>`,
  `server-token` is as it was before (or still missing), and `LADO_HOME` holds no
  temporary file of the attempt

### Requirement: The server refuses an empty token

The UI server SHALL refuse an empty token in every place it takes one: an
`Authorization: Bearer` header with nothing after it, `?token=` with no value and an empty
cookie SHALL each be refused with 401, and a server SHALL NOT be built with an empty token
of its own.

#### Scenario: An empty Bearer token

- **WHEN** a request to `/api/sessions` carries `Authorization: Bearer ` with no token
- **THEN** the server answers 401

#### Scenario: A link with an empty token

- **WHEN** the browser opens `/?token=`
- **THEN** the server answers 401 and sets no cookie

#### Scenario: A server on an empty token

- **WHEN** the server's guard is made with an empty token
- **THEN** it raises an error instead of taking requests
