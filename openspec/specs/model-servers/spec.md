# model-servers Specification

## Purpose
What a model server in the human's network is, from its address and, when it asks for one,
its key: its type, its models and the agent CLIs that can use it, proven by requests that
generate nothing, with one clear line for each way it can fail and the key kept nowhere.

## Requirements

### Requirement: lado model-server probe names a server's type, models and CLIs

`lado model-server probe <address>` SHALL print the server's address, its type (Ollama,
LM Studio, OpenAI-compatible or Anthropic-compatible), its models, the agent CLIs that can
use it with the API each uses, and each CLI that cannot with the API it lacks, and exit 0.
The CLIs SHALL come in LADO's one order of the agent CLIs (Claude Code, Codex CLI, Kilo CLI,
OpenCode), the order of Settings → Models. `lado model-server` alone SHALL print its help.
Nothing else in LADO SHALL change.

#### Scenario: An Ollama server that speaks two APIs
- **WHEN** the human runs `lado model-server probe http://192.168.1.10:11434` and the
  server is Ollama with the models `llama3.1:8b` and `qwen2.5-coder:7b`, answering chat
  completions and the Responses API but not the Anthropic Messages API
- **THEN** it prints `http://192.168.1.10:11434`, `type: Ollama`,
  `models: llama3.1:8b, qwen2.5-coder:7b`,
  `CLIs: Codex CLI (Responses API); Kilo CLI, OpenCode (chat completions)` and
  `not: Claude Code (no Anthropic Messages API)`, and exits 0

#### Scenario: A server every CLI can use
- **WHEN** the server answers all three APIs
- **THEN** the output has no `not:` line

### Requirement: The CLIs follow from the APIs a server proves

A CLI SHALL be named as able to use a server exactly when the server proved the API its
provider declares: chat completions for OpenCode and Kilo, the Responses API for Codex,
the Anthropic Messages API for Claude Code. The server's type SHALL NOT decide it.

#### Scenario: An OpenAI-compatible server with chat completions only
- **WHEN** the server lists its models in OpenAI's shape and answers only chat completions
- **THEN** `type: OpenAI-compatible`, the CLIs are Kilo CLI and OpenCode, and Codex CLI
  and Claude Code are under `not:`

#### Scenario: A server with the Responses API only
- **WHEN** the server answers only the Responses API
- **THEN** the CLIs are Codex CLI alone

#### Scenario: An Anthropic-compatible server
- **WHEN** the server lists its models in Anthropic's shape and answers only the Messages
  API
- **THEN** `type: Anthropic-compatible`, the CLIs are Claude Code alone

#### Scenario: A server that proves no API
- **WHEN** the server lists its models but answers none of the three APIs
- **THEN** it prints `CLIs: none` and every CLI under `not:`, and exits 0

### Requirement: An API is proven without generating

LADO SHALL prove each API with one POST whose body is `{}`: an answer 400 or 422 with a
JSON body proves it, any other answer does not. It SHALL send at most one request per
check to an address (the model list, the model list in Anthropic's way, Ollama's and LM
Studio's own endpoints, one per API, one control), each limited to 5 seconds, and none to
another path, port or host.

#### Scenario: The requests of one probe
- **WHEN** the human probes an address that answers
- **THEN** the server receives at most `GET /v1/models` twice (once without
  `anthropic-version` and once with it), `GET /api/version`, `GET /api/v0/models` and one
  `POST` with the body `{}` to each of `/v1/chat/completions`, `/v1/responses`,
  `/v1/messages` and `/v1/lado-no-such-api`

#### Scenario: An API missing
- **WHEN** the server answers `POST /v1/responses` with 404
- **THEN** the server is named as without the Responses API

### Requirement: A server that answers every POST alike proves no API

When the control `POST /v1/lado-no-such-api` answers 400 or 422 with a JSON body, no API
SHALL count as proven. A server whose type is otherwise unknown SHALL then be an unknown
server; one whose type is known SHALL print `APIs: cannot be told: <address> answers
<status> to any POST` and `CLIs: none`.

#### Scenario: A gateway that answers 400 to every path
- **WHEN** the server answers every request, `GET /v1/models` and the control included,
  with 400 and a JSON error
- **THEN** it prints `unknown server: <address> answered, but not as an OpenAI-compatible,
  Anthropic-compatible, Ollama or LM Studio server (GET /v1/models: 400; it answers 400 to
  any POST, so its APIs cannot be told)` and exits 1

#### Scenario: A server with a list that answers every POST alike
- **WHEN** the server lists its models in OpenAI's shape and answers every POST, the
  control included, with 400 and a JSON error
- **THEN** it prints `type: OpenAI-compatible`, its models, `APIs: cannot be told:
  <address> answers 400 to any POST` and `CLIs: none`, and exits 0

### Requirement: The server's type

LADO SHALL name a server Ollama when `GET /api/version` gives a version, LM Studio when
`GET /api/v0/models` gives a list, then by its model list asked without
`anthropic-version`: Anthropic-compatible in Anthropic's shape, else OpenAI-compatible;
with no such list, Anthropic-compatible when the list asked with `anthropic-version` has
Anthropic's shape; otherwise by the APIs it proved: the Messages API as
Anthropic-compatible, chat completions or the Responses API as OpenAI-compatible.

#### Scenario: LM Studio
- **WHEN** the server answers `GET /api/v0/models` with a list
- **THEN** it prints `type: LM Studio`

#### Scenario: A gateway that speaks both APIs
- **WHEN** the server (LiteLLM) lists its models in OpenAI's shape when asked without
  `anthropic-version` and in Anthropic's shape when asked with it, and proves all three APIs
- **THEN** it prints `type: OpenAI-compatible`, its models once each, and no `not:` line;
  `lado model-server add` saves it so and `lado model-server list` shows
  `OpenAI-compatible`

#### Scenario: An Anthropic API that lists its models only with its version header
- **WHEN** the server refuses `GET /v1/models` without `anthropic-version` with 400, lists
  `claude-x` in Anthropic's shape with it, and proves the Messages API
- **THEN** it prints `type: Anthropic-compatible` and `models: claude-x`

### Requirement: A server's models or no list

LADO SHALL take a server's models from `GET /v1/models` asked without `anthropic-version`;
when that gives no list, from the one asked with it when that is a list in Anthropic's
shape. A list it cannot read SHALL be no list with why, not a failure: `models: no list
(<why>)`, the why of the list asked without the header. An empty list SHALL print `models:
none`.

#### Scenario: A list that fails
- **WHEN** Ollama answers `GET /v1/models` with 500
- **THEN** it prints `models: no list (GET /v1/models: 500)` and the type and CLIs, and
  exits 0

#### Scenario: A list in another shape with the header
- **WHEN** the server lists `gpt-oss-20b` in OpenAI's shape without `anthropic-version` and
  `other` in Anthropic's shape with it
- **THEN** it prints `models: gpt-oss-20b`

### Requirement: The address as given, its scheme added visibly

An address without a scheme SHALL get `http://`, and the first line SHALL say
`(added http://)`. A trailing `/v1` and trailing `/` SHALL be dropped and any other path
kept. An address that is not `http` or `https`, or holds a user, a password, a query or a
fragment, SHALL be refused with exit 2.

#### Scenario: No scheme
- **WHEN** the human probes `localhost:11434/v1/`
- **THEN** the first line is `http://localhost:11434 (added http://)`

#### Scenario: A password in the address
- **WHEN** the human probes `http://me:pw@host:4000`
- **THEN** it exits 2 with a line that does not contain `pw`

#### Scenario: An address urllib itself refuses
- **WHEN** the human probes `http://u:pw@h＃x`, whose host holds a character that Unicode
  normalisation changes
- **THEN** it exits 2 with a fixed line that does not contain `pw`

### Requirement: An address that does not answer

An address that gives no HTTP answer to the model list within 5 seconds SHALL stop the
probe, with nothing more sent, and exit 1 with `<address> does not answer (<why>)`. A TLS
failure SHALL exit 1 with `<address>: TLS failed (<why>); a company's CA goes in the file
SSL_CERT_FILE names`.

#### Scenario: Nothing listens
- **WHEN** the human probes `http://127.0.0.1:<a closed port>`
- **THEN** it prints `http://127.0.0.1:<port> does not answer (connection refused)` and
  exits 1

#### Scenario: A server that hangs
- **WHEN** the server accepts the connection and never answers
- **THEN** within about 5 seconds it prints `does not answer (no answer in 5 s)` and exits 1

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

### Requirement: An unknown server

An address that answers but proves no type and no API SHALL exit 1 with `unknown server:
<address> answered, but not as an OpenAI-compatible, Anthropic-compatible, Ollama or LM
Studio server (GET /v1/models: <answer>)`. LADO SHALL follow no redirect: a redirect is
an answer that proves nothing.

#### Scenario: A web page
- **WHEN** the address is a web server that answers 404 to every request
- **THEN** it prints the unknown server's line with `GET /v1/models: 404` and exits 1

#### Scenario: A redirect
- **WHEN** the server answers every request with 301 to another host
- **THEN** no request reaches that host, and the line names `301 to <location>`

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
it was saved (`none` for none), in LADO's one order of the agent CLIs. It SHALL send no
request. With no server saved it SHALL print `No model servers. Add one: lado model-server
add <name> <address> [--key]`.

#### Scenario: Two servers
- **WHEN** `LM Studio дома` (LM Studio, chat completions, no key) and `work`
  (OpenAI-compatible, chat completions and the Responses API, a key) are saved
- **THEN** the list shows `LM Studio дома  http://localhost:1234  LM Studio  no  Kilo CLI,
  OpenCode` and `work  https://gw.corp/llm  OpenAI-compatible  yes  Codex CLI, Kilo CLI,
  OpenCode`, and no request reaches either server

#### Scenario: None saved
- **WHEN** no server is saved
- **THEN** it prints `No model servers. Add one: lado model-server add <name> <address>
  [--key]` and exits 0

### Requirement: lado model-server remove refuses a server a model uses

`lado model-server remove <name>` SHALL remove the saved server and its key file, print
`Removed model server "<name>".` and exit 0. While a configured model refers to the
server it SHALL be refused, changing nothing, with a line naming every model that refers
to it and one `lado model remove` for all of them, the hint `or remove them with it: lado
model-server remove "<name>" --with-models`, and exit 1. A name no server has SHALL be
refused with exit 1.

#### Scenario: A server a model uses
- **WHEN** the model `Локальная Qwen` refers to `LM Studio дома` and the human runs `lado
  model-server remove "LM Studio дома"`
- **THEN** it exits 1 with the line naming `Локальная Qwen` and the hint naming
  `--with-models`, and the server and its key file stay

#### Scenario: A server several models use
- **WHEN** the models `coder-codex`, `coder-oc` and `sp` refer to `lms` and the human runs
  `lado model-server remove lms`
- **THEN** it exits 1 with `model server "lms" is used by the models coder-codex, coder-oc,
  sp; remove them first: lado model remove "coder-codex" "coder-oc" "sp"`
- **AND** running that command and then `lado model-server remove lms` removes the server

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

### Requirement: The header of Anthropic's API goes with its requests only

The header `anthropic-version` SHALL go only with the POSTs and with the model list asked in
Anthropic's way; the model list, `GET /api/version` and `GET /api/v0/models` SHALL be asked
without it.

#### Scenario: The header of Anthropic's API
- **WHEN** the human probes an address that answers
- **THEN** every `POST` and one `GET /v1/models` carry `anthropic-version: 2023-06-01`, and
  the first `GET /v1/models`, `GET /api/version` and `GET /api/v0/models` carry no
  `anthropic-version`

### Requirement: Embeddings models are marked in a server's models

A model that `GET /api/v0/models` types `embeddings` SHALL be shown in the `models:` line
of `lado model-server probe` and `lado model-server add` as `<model> (embeddings)`. A
server that gives no type for a model SHALL show it as before.

#### Scenario: LM Studio with an embeddings model
- **WHEN** LM Studio lists `qwen3-8b` and `text-embedding-nomic-embed-text-v1.5` and types
  them `llm` and `embeddings` in `GET /api/v0/models`
- **THEN** it prints `models: qwen3-8b, text-embedding-nomic-embed-text-v1.5 (embeddings)`

#### Scenario: Ollama
- **WHEN** the server is Ollama
- **THEN** its models are shown without a mark

### Requirement: A server at the address of another is saved and named

`lado model-server add` SHALL save a server whose address is that of another saved server,
and print `same address as model server "<its name>"` for each such server, after the
probe's lines and before `Saved model server "<name>".` (or `Replaced …`), exit 0; with
`--replace` the server replaced SHALL NOT count, and a failed probe SHALL print no such
line.

#### Scenario: The same LM Studio under a second name
- **WHEN** `macpro` is saved at `http://10.73.10.235:1234` and the human runs `lado
  model-server add lms 10.73.10.235:1234/v1/`, where LM Studio answers
- **THEN** it prints the probe's lines, `same address as model server "macpro"` and `Saved
  model server "lms".`, exits 0, and `lado model-server list` shows both

#### Scenario: Replacing a server at its own address
- **WHEN** `lms` is saved at `http://h:1234` and the human runs `lado model-server add lms
  http://h:1234/ --key --replace` with a new key
- **THEN** it prints no `same address` line and `Replaced model server "lms".`

### Requirement: Two addresses of one server

Two addresses of servers SHALL be the same when, after the probe's normalisation (`http://`
added, `/v1` and `/` dropped at the end), their scheme, host ignoring case, port (80 for
`http`, 443 for `https` when none is given) and path are the same.

#### Scenario: Three spellings of one address
- **WHEN** a server is saved at `http://h:1234` and the human adds another at `h:1234/v1/`,
  at `http://H:1234/` or at `http://h:1234`
- **THEN** each prints `same address as model server "<the first's name>"`

#### Scenario: Another port or path
- **WHEN** a server is saved at `http://h:1234` and the human adds another at
  `http://h:1235` or at `http://h:1234/llm`
- **THEN** no `same address` line is printed

### Requirement: Why a server has no list is given only with no list

A probe SHALL give why a server has no list of models only when it has none: when the list
asked without `anthropic-version` fails and the one asked with it gives the models, the
probe SHALL have those models and no why. Every place that shows the why (`lado
model-server probe` and `add`, Settings → Models) SHALL show it only with no list.

#### Scenario: An Anthropic API that lists its models only with its version header
- **WHEN** the server refuses `GET /v1/models` without `anthropic-version` with 400 and
  lists `claude-x` in Anthropic's shape with it
- **THEN** the probe has the models `claude-x` and no why, and Settings → Models shows
  `claude-x` with no `no list` reason

#### Scenario: A list that fails both ways
- **WHEN** the server answers `GET /v1/models` with 500 with and without the header
- **THEN** the probe has no list and its why is `GET /v1/models: 500`

### Requirement: lado doctor names models their server no longer lists

For each saved server that answered with a list of models, the `Model servers` line of
`lado doctor` SHALL warn of each configured model on that server whose model the list
lacks: `model "<name>" (<model>) is not in <server>'s list of models`. A server with no
list or that does not answer SHALL name no model so.

#### Scenario: A model gone from LM Studio
- **WHEN** `Локальная Qwen` (`qwen3-8b`) refers to `LM Studio дома`, which answers and no
  longer lists `qwen3-8b`
- **THEN** `lado doctor` prints `[WARN] Model servers:` with `model "Локальная Qwen"
  (qwen3-8b) is not in LM Studio дома's list of models`, and its exit status is as without
  the line

### Requirement: lado model-server remove --with-models removes its models too

`lado model-server remove <name> --with-models` SHALL remove every configured model that
refers to the server, printing `Removed model "<model>".` for each, and after it
`<CLI title>'s default model is cleared.` for each agent CLI whose default was one of them,
then the server and its key file, in one transaction for the models, the defaults and the
server, and exit 0.

#### Scenario: A server with its models
- **WHEN** the models `coder-oc` and `sp` refer to `lms` and the human runs `lado
  model-server remove lms --with-models`
- **THEN** it prints `Removed model "coder-oc".`, `Removed model "sp".` and `Removed model
  server "lms".`, exits 0, and neither the models, the server nor its key folder is left

#### Scenario: A server with a default on it
- **WHEN** `coder-oc` on `lms` is OpenCode's default model and the human runs `lado
  model-server remove lms --with-models`
- **THEN** it prints `Removed model "coder-oc".`, `OpenCode's default model is cleared.` and
  `Removed model server "lms".`, and `lado model default` shows OpenCode with no default

### Requirement: A server's key reaches an agent only through its environment

The key of every server with a model ticked for an agent's CLI SHALL reach that agent only as a
variable of its launch, named in its config as `{env:…}`. It SHALL NOT be in a config file, config
content, `lado.db`, a log, a warning, a refusal or an API answer, nor in the environment of an
agent of a CLI with no model on that server.

#### Scenario: The key in the environment only
- **WHEN** an OpenCode agent starts with a model ticked on a server with a key
- **THEN** its config content has `{env:LADO_MODEL_KEY_<ID>}`, that variable has the key, and no file
  under `LADO_HOME` but the server's key file has it

#### Scenario: A worker of another CLI
- **WHEN** that session spawns a Claude worker
- **THEN** the worker's environment has no such variable

### Requirement: A key that cannot reach an agent stops only its own server

A key file that cannot be read, or a key holding `"`, `\` or a control character, which the CLIs
put into their config's text as it is, SHALL refuse the start of an agent on that server, and leave that server's models out
of another agent's config with a warning; neither SHALL show the key.

#### Scenario: Another server's key cannot be read
- **WHEN** the key file of a server other than the start model's cannot be read
- **THEN** the agent starts without that server's models, and the warnings name the server

#### Scenario: A key that would break the config
- **WHEN** the key of the start model's server holds `"`
- **THEN** the start is refused naming the server, with no part of the key, and no server is asked

### Requirement: lado doctor promises only what the probe saw

For a server its probe found, `lado doctor` SHALL say that it lists its models: the probe sends no
chat, so it cannot say that the server works.

#### Scenario: A server that fails every chat
- **WHEN** a server lists its models and answers each chat with an error
- **THEN** the line `Model servers` says `<server> lists its models (<type>)`

### Requirement: lado doctor names a default that cannot start

With a default model set, `lado doctor` SHALL print one line `Default models`: `OK`, or `WARN`
naming each default whose server's probe failed, with why, whose server's list lacks it, or whose
built-in name its CLI no longer lists, or that it cannot check as the agents' environment cannot be
read. It SHALL ask each server no more than the line `Model servers` did, and its exit status SHALL
be as without the line. With no default it SHALL print no line.

#### Scenario: A default on a silent server
- **WHEN** OpenCode's default is `Локальная Qwen` and `LM Studio дома` does not answer
- **THEN** `lado doctor` prints `[WARN] Default models:` naming OpenCode, the model and that the
  server does not answer

#### Scenario: A built-in default the list lost
- **WHEN** Codex CLI's default is `gpt-5.4-old` and its list no longer has it
- **THEN** the line names Codex CLI and that its list lacks the model
