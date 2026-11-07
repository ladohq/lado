## MODIFIED Requirements

### Requirement: A provider's refusal reads in LADO's words

A turn of OpenCode, Kilo, or a Claude or Codex agent on a server that ends on a provider's 401, 402, 403 or 429 SHALL have as its error LADO's words with the status, then the server's text: `the model provider refused the key (401)`, `the model provider refused access (403)`, `the model provider asks for payment (402)`, `the model provider limits requests, or the quota is spent (429)`. The message's body SHALL hold the server's whole text.

#### Scenario: A wrong key on OpenCode
- **WHEN** a server answers 401 with `Incorrect API key provided`
- **THEN** the chat's line reads `turn of supervisor ended on an error: the model provider refused the key (401): Incorrect API key provided; it is idle`

#### Scenario: cloud.ru's refusal
- **WHEN** a server answers 401 with the plain text `{"message":"Invalid token"}`, which the CLI reports as `Unauthorized: Invalid token`
- **THEN** the line holds `the model provider refused the key (401)` and that text

#### Scenario: Another status
- **WHEN** a turn ends on an `APIError` of status 500
- **THEN** its line and body stay as the CLI gave them

#### Scenario: The kind in the statistics
- **WHEN** such a turn is counted by `lado stats`
- **THEN** its kind is LADO's words alone, with none of the server's text

### Requirement: Any other 4xx of a provider is a refusal too

Such a turn ending on any other 4xx but 408 SHALL read `the model provider refused the request (<status>)`, then the server's text, and a 400 whose text names an API key `the model provider refused the key (400)`. A server's refusal for the context SHALL keep LADO's words of a context too small, whatever its status.

#### Scenario: cloud.ru's wrong key
- **WHEN** a server answers 400 with `{"message":"invalid api key secret","code":"InvalidArgument"}`
- **THEN** on each CLI the line holds `the model provider refused the key (400)` and that text, and no resume is planned

#### Scenario: A request the model does not take
- **WHEN** a server answers 400 with `reasoning_effort='xhigh' is not supported`
- **THEN** the line holds `the model provider refused the request (400)` and that text

#### Scenario: A context too small
- **WHEN** a server answers 400 with `exceed_context_size_error`
- **THEN** the line holds LADO's words of a context too small

#### Scenario: A model the server does not have
- **WHEN** a server answers 404 to an agent of OpenCode, Kilo, Claude Code or Codex
- **THEN** the line holds `the model provider refused the request (404)`, then the server's text, or on Claude Code its own words, as its hook gets no text of the server

#### Scenario: A request too large
- **WHEN** a server answers 413 to a Claude agent
- **THEN** the line holds `the model provider refused the request (413)` and the server's body

#### Scenario: A request that took too long
- **WHEN** a turn ends on a 408
- **THEN** the error is as the CLI gave it, and a Claude agent's turn stays temporary

### Requirement: No repeat without end on a refusal

On a server that refuses every request with 401, 402, 403 or 429, each CLI SHALL end the turn by itself, and LADO SHALL add no request of its own to it. The repeats are the CLI's and limited in number; how long they take depends on the server's `Retry-After`, and until the turn ends the agent stays busy.

#### Scenario: A real CLI on a server that answers 429
- **WHEN** OpenCode, Kilo, Claude Code or Codex runs on a fake server that answers 429 to every request
- **THEN** the turn ends within its CLI's repeats, the agent is idle, and the server's count of requests stops growing

#### Scenario: A server that names a long wait
- **WHEN** a server answers 429 with a long `Retry-After` to an agent of OpenCode or Kilo
- **THEN** the CLI waits what the server names before each repeat, the agent is busy meanwhile, and `docs/install.md` says so

### Requirement: A server's key is in no error

Before an error's line or body is cut or kept, LADO SHALL replace in it the value of every variable of a server's key in the agent's environment, and in the session loop the kept key of the agent's server, with `***`. The key SHALL be in no line, body, event or log of LADO.

#### Scenario: A server that echoes the key
- **WHEN** a server's 401 repeats the key in its text
- **THEN** the chat's line, the message's body, `lado log` and `lado.db` hold `***` and not the key

#### Scenario: A key at the cut of the line
- **WHEN** the key stands where the line is cut short
- **THEN** no part of it stays in the line

#### Scenario: A Codex agent's refusal
- **WHEN** a server's 401 to a Codex agent repeats the key in its text
- **THEN** the chat's line, the message's body, `lado log` and `lado.db` hold `***` and not the key, though the session loop has no such variable

## ADDED Requirements

### Requirement: A Codex agent's failed turn is read from its journal

For a busy Codex agent on a server, the session loop SHALL read what is new in its session journal, and a `task_complete` with an `error` SHALL end the turn as a hook's end does, unless a later turn has begun. Each error SHALL be told once, also after a restart of the loop. A Codex agent on a built-in model SHALL have nothing read.

#### Scenario: A wrong key
- **WHEN** a server answers 401 `Missing Authentication header` to a Codex agent
- **THEN** within a few seconds of the turn's end the agent is idle, and the chat's line reads `turn of supervisor ended on an error: the model provider refused the key (401): Missing Authentication header; it is idle`

#### Scenario: A limit
- **WHEN** a server answers 429 to a Codex agent until Codex gives up
- **THEN** the line reads `the model provider limits requests, or the quota is spent (429)`, with no server's text, as Codex keeps none, and no resume is planned

#### Scenario: A bad request
- **WHEN** a server answers 400 with `{"error": {"message": "unknown model"}}`
- **THEN** the line reads `the model provider refused the request (400): unknown model`

#### Scenario: A server error
- **WHEN** a server answers 500 until Codex gives up
- **THEN** the turn is temporary, and LADO plans a resume

#### Scenario: The address
- **WHEN** Codex's error ends with `, url: https://user:pass@gw/v1/responses`
- **THEN** no line, body or event holds any of that

#### Scenario: A loop restarted
- **WHEN** the session loop restarts after it told an error
- **THEN** that error is not told again

#### Scenario: The next turn has begun
- **WHEN** a failed turn and a `task_started` after it stand in what the loop reads
- **THEN** the agent stays busy, and nothing is told

#### Scenario: A built-in model
- **WHEN** a Codex agent on OpenAI's model ends a turn on an API error
- **THEN** LADO reads no journal, and the agent stays as it does today
