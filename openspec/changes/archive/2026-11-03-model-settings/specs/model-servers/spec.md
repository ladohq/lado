## ADDED Requirements

### Requirement: lado model-server add saves a server under a name

`lado model-server add <name> <address> [--key]` SHALL probe the address as `lado
model-server probe` does, print the probe's lines, and on a server LADO recognised save it
under the name with its address, its type and the APIs it proved, then print `Saved model
server "<name>".` and exit 0. The server's list of models SHALL NOT be saved.

#### Scenario: LM Studio on the human's machine
- **WHEN** the human runs `lado model-server add "LM Studio дома" localhost:1234` and LM
  Studio answers there with the models `qwen3-8b` and `gemma-3-12b`
- **THEN** it prints `http://localhost:1234 (added http://)`, `type: LM Studio`,
  `models: qwen3-8b, gemma-3-12b`, the CLIs and `Saved model server "LM Studio дома".`,
  and exits 0
- **AND** `lado model-server list` shows `LM Studio дома` with `http://localhost:1234`

### Requirement: A server that fails the probe is not saved

`lado model-server add` SHALL save nothing and exit 1 with the probe's line for an address
that does not answer, asks for a key, refuses the key or is no server LADO knows, and exit
2 for an address the probe does not take.

#### Scenario: An address that does not answer
- **WHEN** the human runs `lado model-server add lab http://127.0.0.1:<a closed port>`
- **THEN** it prints `http://127.0.0.1:<port> does not answer (connection refused)`, exits
  1, and no server `lab` is saved

#### Scenario: An unknown server
- **WHEN** the address is a web server that answers 404 to every request
- **THEN** it prints the unknown server's line, exits 1, and nothing is saved

### Requirement: A server's name

A server's name SHALL be one line of visible text of 1 to 64 characters; spaces and any
script SHALL be allowed. A name another saved server has, compared ignoring case, SHALL be
refused with `a model server "<its name>" is saved already; to change its address or key:
lado model-server add "<its name>" <address> [--key] --replace` and exit 1, before any
request is sent. Every command that takes a server's name SHALL find it ignoring case.

#### Scenario: A name taken in another case
- **WHEN** `LM Studio дома` is saved and the human runs `lado model-server add "lm studio
  ДОМА" localhost:1234`
- **THEN** it exits 1 with the line naming `LM Studio дома` and `--replace`, and sends no
  request

#### Scenario: A name with a line break
- **WHEN** the human gives a name that holds a line break, or an empty one, or one of 65
  characters
- **THEN** it exits 1 without sending a request

### Requirement: --replace changes a saved server's address or key

`lado model-server add <name> <address> [--key] --replace` SHALL probe the new address
and, on a server LADO recognised, replace the saved server's address, type and APIs, and
its key when `--key` is given; without `--key` the kept key SHALL be kept and sent with
the probe. The models that refer to the server SHALL keep referring to it. A failed probe
SHALL change nothing. `--replace` with a name no server has SHALL be refused with exit 1.

#### Scenario: LM Studio moved to another port
- **WHEN** `LM Studio дома` is saved at `http://localhost:1234` and the model `Локальная
  Qwen` refers to it, and the human runs `lado model-server add "LM Studio дома"
  localhost:1235 --replace`, where LM Studio answers
- **THEN** it prints `Replaced model server "LM Studio дома".`, the list shows
  `http://localhost:1235`, and `Локальная Qwen` still names `LM Studio дома`

#### Scenario: A new key for a gateway
- **WHEN** `work` is saved with a key and the human pipes a new key into `lado
  model-server add work https://gw.corp/llm --key --replace`, which the server takes
- **THEN** the server's key file holds the new key

#### Scenario: The new address does not answer
- **WHEN** the human replaces a server's address with one that does not answer
- **THEN** it exits 1, and the saved address and key are as before

### Requirement: A server's key is kept in its own file

A saved server's key SHALL be kept in the file `<LADO_HOME>/model-servers/<id>/key`, the
folders mode 700 and the file mode 600 whatever the umask, written whole by a rename,
refusing a symbolic link on the way. The key's value SHALL appear in no output, log, error
journal, `lado.db`, other file of `LADO_HOME`, or folder of LADO's or a project's secrets.
Removing the server SHALL remove its key file and folder.

#### Scenario: A key piped in
- **WHEN** the human runs `printf '%s' "$KEY" | lado model-server add work
  https://gw.corp/llm --key` and the server takes the key
- **THEN** `<LADO_HOME>/model-servers/<id>/key` holds the key with mode 600, its folder
  has mode 700, and neither the output, `lado.db`, the error journal nor any other file of
  `LADO_HOME` holds its value

#### Scenario: A server saved without a key
- **WHEN** the human adds a server without `--key`
- **THEN** it has no key file and `lado model-server list` says `no` under KEY

### Requirement: The key of add is read as the probe's

`--key` of `lado model-server add` SHALL read the key without echo on a terminal, else from
stdin; a key on the command line or an empty one SHALL be refused without echoing it,
without sending a request and without saving anything.

#### Scenario: A key on the command line
- **WHEN** the human runs `lado model-server add work https://gw.corp/llm --key s3cr3t`,
  or `--key -s3cr3t`, or adds a word the command does not take (`--help=s3cr3t`)
- **THEN** it exits 1 without sending a request, neither stream contains `s3cr3t`, and
  nothing is saved

### Requirement: lado model-server list shows the saved servers without asking them

`lado model-server list` SHALL print one line per saved server, sorted by name ignoring
case, under the header `NAME ADDRESS TYPE KEY CLIs`: its name, address, type, `yes` when its
key file is there and `no` otherwise, and the titles of the CLIs whose API it proved when
it was saved (`none` for none). It SHALL send no request. With no server saved it SHALL
print `No model servers. Add one: lado model-server add <name> <address> [--key]`.

#### Scenario: Two servers
- **WHEN** `LM Studio дома` (LM Studio, chat completions, no key) and `work`
  (OpenAI-compatible, chat completions and the Responses API, a key) are saved
- **THEN** the list shows `LM Studio дома  http://localhost:1234  LM Studio  no  Kilo CLI,
  OpenCode` and `work  https://gw.corp/llm  OpenAI-compatible  yes  Kilo CLI, OpenCode,
  Codex CLI`, and no request reaches either server

#### Scenario: None saved
- **WHEN** no server is saved
- **THEN** it prints `No model servers. Add one: lado model-server add <name> <address>
  [--key]` and exits 0

### Requirement: lado model-server remove refuses a server a model uses

`lado model-server remove <name>` SHALL remove the saved server and its key file, print
`Removed model server "<name>".` and exit 0. While a configured model refers to the
server it SHALL be refused, changing nothing, with `model server "<name>" is used by the
models <model>, <model>; remove them first: lado model remove <model>` and exit 1. A name no
server has SHALL be refused with exit 1.

#### Scenario: A server a model uses
- **WHEN** the model `Локальная Qwen` refers to `LM Studio дома` and the human runs `lado
  model-server remove "LM Studio дома"`
- **THEN** it exits 1 with the line naming `Локальная Qwen`, and the server and its key
  file stay

#### Scenario: A server no model uses
- **WHEN** no model refers to `work` and the human runs `lado model-server remove work`
- **THEN** the server is gone from the list, its folder under `<LADO_HOME>/model-servers/`
  is gone, and it exits 0

### Requirement: A key over plain http to a public address is warned about

When a key is sent over `http://` to a host that is neither `localhost`,
`host.docker.internal`, nor a loopback, private or link-local IP address, `lado
model-server probe` and `lado model-server add` SHALL print on stderr, before sending,
`lado: warning: the key goes to <host> over plain http://, unencrypted; use https:// if
the server has it`, and go on. A host name other than those two SHALL count as public:
LADO resolves no name for the rule.

#### Scenario: A gateway on the internet over http
- **WHEN** the human runs `lado model-server add ext http://llm.example.com --key` with a
  key piped in
- **THEN** stderr has the warning naming `llm.example.com`, and the server is probed

#### Scenario: A server in the human's network
- **WHEN** the address is `http://10.0.0.5:4000` or `http://192.168.1.10:11434` or
  `http://localhost:1234`, with a key
- **THEN** no warning is printed

#### Scenario: No key or https
- **WHEN** no key is given, or the address is `https://`
- **THEN** no warning is printed

### Requirement: The saved servers are kept in lado.db

The saved servers SHALL be kept in `lado.db` (from schema 38), each with an id that never
changes, its name, address, type and APIs; never its key. A `lado.db` of schema 37 SHALL be
upgraded by the migration with no server saved; `lado model-server probe` SHALL keep
neither migrating nor writing `lado.db`.

#### Scenario: Upgrading from schema 37
- **WHEN** a `lado.db` of schema 37 is upgraded
- **THEN** it is at schema 38 with no saved server and no configured model, and every
  session and agent is as before

#### Scenario: The probe leaves lado.db alone
- **WHEN** the human runs `lado model-server probe <address>` with a `lado.db` of schema 37
- **THEN** `lado.db` stays at schema 37

### Requirement: lado doctor checks the saved servers

When servers are saved, `lado doctor` SHALL print one line `Model servers` that probes all
of them at once with their keys: `OK` naming each server that answered with its type;
`WARN` naming each server that does not answer, asks for a key, refuses its key or is no
server LADO knows, with the probe's reason, each key file that is not a regular file or
has a mode other than 600. With no server saved it SHALL print no line.

#### Scenario: One server answers, one does not
- **WHEN** `LM Studio дома` answers and `work` does not
- **THEN** `lado doctor` prints `[WARN] Model servers:` naming `LM Studio дома` as
  answering and `work` with `does not answer (<why>)`, and its exit status is as without
  the line

#### Scenario: A key file with a loose mode
- **WHEN** the key file of `work` has mode 644
- **THEN** the line warns that the key file of `work` has mode 644, not 600

### Requirement: lado doctor names key folders of no server

`lado doctor` SHALL warn of each folder of `<LADO_HOME>/model-servers/` that is no saved
server's, as left over, in the `Model servers` line, also when no server is saved.

#### Scenario: A folder left by a rolled-back lado.db
- **WHEN** `<LADO_HOME>/model-servers/` holds a folder whose name is no saved server's id
- **THEN** the `Model servers` line warns of it as left over, naming its path

### Requirement: doctor's servers line keeps its exit status and lado.db

The `Model servers` line SHALL NOT change doctor's exit status, and `lado doctor` SHALL NOT
migrate `lado.db`: on another schema the line SHALL say the servers were not checked.

#### Scenario: lado.db at schema 37
- **WHEN** `lado doctor` runs with a `lado.db` of schema 37
- **THEN** the line says the model servers were not checked, and `lado.db` stays at 37

## MODIFIED Requirements

### Requirement: localhost in LADO's container

When LADO runs in its container and a `localhost`, `127.0.0.0/8` or `::1` address does
not answer, LADO SHALL add the line `LADO runs in a container, where localhost is the
container itself; a server on your machine: <command> <scheme>://host.docker.internal:<port><path>
(not tried)`, `<command>` being the command run without its address (`lado model-server
probe`, or `lado model-server add "<name>"` with its `--replace`). It SHALL NOT send a
request to any address but the one given.

#### Scenario: Ollama on the host, LADO in Docker
- **WHEN** `LADO_CONTAINER=1` and the human probes `localhost:11434`, which does not answer
- **THEN** it prints the hint with `lado model-server probe
  http://host.docker.internal:11434`, sends nothing to that address, and exits 1

#### Scenario: Outside the container
- **WHEN** `LADO_CONTAINER` is unset and `localhost:11434` does not answer
- **THEN** no hint is printed

#### Scenario: Adding LM Studio on the host, LADO in Docker
- **WHEN** `LADO_CONTAINER=1` and the human runs `lado model-server add "LM Studio дома"
  localhost:1234`, which does not answer
- **THEN** it prints the hint with `lado model-server add "LM Studio дома"
  http://host.docker.internal:1234`, sends nothing to that address, saves nothing, and
  exits 1

### Requirement: The server's key is asked and kept nowhere

`--key` of `lado model-server probe` SHALL read the key without echo on a terminal, else
from stdin, and send it as `Authorization: Bearer` and `x-api-key`. A key given on the
command line or an empty one SHALL be refused. The probe's key SHALL appear in no output,
log, error journal, file of `LADO_HOME` or `lado.db`; only `lado model-server add` keeps a
key, in the server's own key file.

#### Scenario: A key piped in
- **WHEN** the human runs `printf '%s' "$KEY" | lado model-server probe http://gw:4000 --key`
- **THEN** each request to the server carries the key, and neither the output nor any
  file of `LADO_HOME` holds its value

#### Scenario: A key on the command line
- **WHEN** the human runs `lado model-server probe http://gw:4000 --key s3cr3t`
- **THEN** it exits 1 without sending a request, and the line does not contain `s3cr3t`

#### Scenario: A dashed value or a word more on the command line
- **WHEN** the human runs `lado model-server probe http://gw:4000 --key -s3cr3t`, or adds
  a word the command does not take (`--key a s3cr3t`, `--help=s3cr3t`)
- **THEN** it exits 1 without sending a request, and neither stream contains `s3cr3t`

### Requirement: A server that asks for a key or refuses it

Any 401 or 403 among the answers SHALL exit 1: without a key with `<address> asks for a
key (<status>): run <command> <address> --key`, with one with `<address> refused the key
(<status>)`, where `<command>` is the command that was run with its address left out, as
for the container's hint.

#### Scenario: No key given
- **WHEN** the server answers `GET /v1/models` with 401 and no key was given
- **THEN** it prints `http://gw:4000 asks for a key (401): run lado model-server probe
  http://gw:4000 --key` and exits 1

#### Scenario: Adding a gateway without its key
- **WHEN** the human runs `lado model-server add work http://gw:4000` and the server
  answers 401
- **THEN** it prints `http://gw:4000 asks for a key (401): run lado model-server add "work"
  http://gw:4000 --key`, exits 1, and nothing is saved
