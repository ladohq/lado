## MODIFIED Requirements

### Requirement: The warning says where to act

The warning about a context SHALL say where to change it: the setting of a server of a known type, and
the section of `docs/install.md`. In the launch window the name `docs/install.md` SHALL be a link to that
section on GitHub, opening in a new tab; `lado start` SHALL print the same text with no link. Team's
summary SHALL name each warning of the chosen model in a few words of its own.

#### Scenario: A server of a known type

- **WHEN** the model too small is on LM Studio
- **THEN** the warning names `lms load --context-length`

#### Scenario: The link of the launch window

- **WHEN** the launch window shows the warning
- **THEN** `docs/install.md ↗` in it links to `docs/install.md#what-to-expect-of-a-small-model` on
  GitHub, and a warning about a key over http has no link

#### Scenario: The folded Advanced

- **WHEN** the chosen model is too small and its key goes over plain http
- **THEN** Team's summary, hidden, ends with `⚠ key over http, context too small`; with the
  context alone, `⚠ context too small`

### Requirement: A start on a public server with no known context is warned about

When the model an agent starts on is on a server outside the human's machine and network, by the hosts of the rule on a key over plain http and by a name with no dot or ending in `.local`, `.lan`, `.internal` or `.home.arpa`, and its context is not known, `lado start`, the start's warnings and the launch window SHALL warn, naming the model and the server and saying that compaction comes late and the output has no limit; the agent SHALL start. Team's summary SHALL name it `context unknown`.

#### Scenario: A provider that lists no context

- **WHEN** a session starts on a model of `https://llm.example.com` whose list gives no context
- **THEN** the warning names the model and the server, and the session starts

#### Scenario: A local server

- **WHEN** a session starts on a model of `http://192.168.1.10:1234` or `localhost` with no known context
- **THEN** no such warning is given

#### Scenario: A name of the human's network

- **WHEN** a session starts on a model of `http://mac-studio.local:1234`, `http://gpu-box:8000` or `http://ollama.lan:11434` with no known context
- **THEN** no such warning is given, and a key over plain http to that name is warned about as before

#### Scenario: The folded Advanced

- **WHEN** the chosen model is on such a server
- **THEN** Team's summary, hidden, ends with `⚠ context unknown`

#### Scenario: A known context

- **WHEN** the same server lists the model's context
- **THEN** no such warning is given
