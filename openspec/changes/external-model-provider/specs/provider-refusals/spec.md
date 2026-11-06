## Purpose
What the human reads when a model provider refuses an agent's request, and that neither LADO nor a CLI repeats it without end nor shows the key.

## ADDED Requirements

### Requirement: A provider's refusal reads in LADO's words

A turn of OpenCode, Kilo or a Claude agent on a server that ends on a provider's 401, 402, 403 or 429 SHALL have as its error LADO's words with the status, then the server's text: `the model provider refused the key (401)`, `the model provider refused access (403)`, `the model provider asks for payment (402)`, `the model provider limits requests, or the quota is spent (429)`. The message's body SHALL hold the server's whole text.

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

### Requirement: A Claude agent's refusal is read from its last message

For a Claude agent on a server, LADO SHALL read the status and the text of a failed turn from `last_assistant_message` of `StopFailure`, in Claude Code's forms `API Error: 402 <text>` and `API Error: Request rejected (429) · <text>`. A message in no such form SHALL leave the error as the hook's kind. A Claude agent on a built-in model SHALL keep its words as before.

#### Scenario: Quota on a server
- **WHEN** a Claude agent on a server ends a turn with `rate_limit` and the message `API Error: Request rejected (429) · You exceeded your current quota`
- **THEN** the line reads `the model provider limits requests, or the quota is spent (429): You exceeded your current quota`

#### Scenario: A built-in model
- **WHEN** a Claude agent on Claude Code's own login ends a turn with `rate_limit`
- **THEN** the error is as before

#### Scenario: A form LADO does not know
- **WHEN** the message of a turn ended with `server_error` holds no such form
- **THEN** the error is the kind, and the turn stays temporary

### Requirement: A refusal is never a temporary error

A turn that ended on a status of those four SHALL NOT be temporary, whatever kind the CLI gives it: LADO SHALL plan no resume, and SHALL tell the lead, or the human for the supervisor's turn, at once.

#### Scenario: 402 on Claude Code
- **WHEN** Claude Code reports `unknown` with the message `API Error: 402 Insufficient credits`
- **THEN** no resume is planned, and the lead hears of it at that turn's end

#### Scenario: A rate limit on the supervisor
- **WHEN** the supervisor's turn ends on a 429
- **THEN** the human sees the line, the supervisor is idle, and no request follows from LADO

### Requirement: No repeat without end on a refusal

On a server that refuses every request with 401, 402, 403 or 429, each CLI SHALL end the turn by itself, and LADO SHALL add no request of its own to it. The repeats are the CLI's and limited in number; how long they take depends on the server's `Retry-After`, and until the turn ends the agent stays busy.

#### Scenario: A real CLI on a server that answers 429
- **WHEN** OpenCode, Kilo or Claude Code runs on a fake server that answers 429 to every request
- **THEN** the turn ends within its CLI's repeats, the agent is idle, and the server's count of requests stops growing

#### Scenario: A server that names a long wait
- **WHEN** a server answers 429 with a long `Retry-After` to an agent of OpenCode or Kilo
- **THEN** the CLI waits what the server names before each repeat, the agent is busy meanwhile, and `docs/install.md` says so

### Requirement: A server's key is in no error

Before an error's line or body is cut or kept, LADO SHALL replace in it the value of every variable of a server's key in the agent's environment with `***`. The key SHALL be in no line, body, event or log of LADO.

#### Scenario: A server that echoes the key
- **WHEN** a server's 401 repeats the key in its text
- **THEN** the chat's line, the message's body, `lado log` and `lado.db` hold `***` and not the key

#### Scenario: A key at the cut of the line
- **WHEN** the key stands where the line is cut short
- **THEN** no part of it stays in the line
