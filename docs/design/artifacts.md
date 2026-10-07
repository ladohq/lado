# Artifacts

Design of LADO's artifacts (ROADMAP.md, stage 7), decided with the human 2026-10-07, task
feature/artifacts. This file is the contract the parts below are built against: each part
is its own run, may run in its own session, and changes this file when it changes the
contract.

## Why

An agent's result today is a file on the machine the agent runs on (a worktree, `/tmp`), a
message body (at most 8000 characters) or a flow note. When LADO runs on a remote server,
the human reaches the UI but not that machine's disk, so the results an agent leaves in
files are out of reach. The root cause is that a result has no identity apart from a path
on one disk. Artifacts give it one: a name in a session, kept by LADO and shown by LADO.

## What an artifact is

- An **artifact** is a named document of a session: a design, plan, review, report, an
  image, an HTML mockup, any file. It has an opaque id, a name, a scope, a title (optional,
  one line, at most 200 characters) and its records.
- A **record** is one write of its content: opaque id, content (bytes), media type, size,
  SHA-256 of the content, the agent who wrote it, the run, the run's state and that
  state's visit number (`runs.visits[state]`) it was written in (when it was), the time,
  and an optional one-line summary of what changed (at most 200 characters). Records never
  change once written.
- Agents and the human see an artifact as one document: its **latest record**. Record ids
  are not in the agents' tools and the UI has no version list. They exist so that an
  attachment keeps exactly what was attached (below) and a flow can tell what was written
  during a step.
- Every write makes a new record, also one with the same content as the latest: the write
  then says `unchanged`, and the content is not stored again (records refer to content by
  its hash). So a step that writes its artifact again unchanged still counts as having
  written it (Flows). The media type may change between records.

### Names and scopes

- A name is 1-64 characters of `a-z`, `0-9`, `-`, `_` and `.`, starting with a letter or a
  digit (no `/`, no spaces, no upper case). Examples: `design`, `review`, `plan-v2`,
  `mockup.html`.
- An artifact belongs to its session and to one **scope** in it: a flow run (its name, e.g.
  `feature/artifacts`), or the session itself. A name is unique in its scope.
- An artifact's **full name** is `<run>/<name>` in a run's scope, `<name>` in the session's.
  It is parsed by its last `/`, since run names hold a `/`.
- A bare name means: for a worker of a flow run, its run's scope; for any other agent (the
  supervisor, a worker of no run), the session's scope. The supervisor may lead several
  runs at once, so LADO never guesses its "current" run: in a step of its own (a state
  whose agent is the lead) it writes and attaches a run's artifacts by their full name,
  `<run>/<name>`, and its instructions say so. Any agent may use a full name to
  reach another run's artifact. There is no fallback from one scope to another: a bare name
  that is not in the agent's scope is not found, and the error says which full name was
  looked up.
- A worker of a run cannot address the session's scope in this version (no real use yet).
- Reading and writing are different rights (the human's decision, 2026-10-07). Any agent
  reads any artifact of its session by its full name. A worker of a run writes only to its
  run's scope, a worker of no run only to the session's, the supervisor to the session's
  and to any open run's; nobody writes to a run that ended or was cancelled. A refusal names
  the scope the agent may write to. Why: a flow's `produces` (Flows) must not count another
  agent's write, and a right is easier to widen later than to narrow.

## Storage behind one interface

`lado/artifacts.py` is the only module the rest of LADO calls for artifacts (MCP tools,
CLI, runs, the UI server, `lado forget`, `lado doctor`). It checks names, scopes and
limits, resolves bare and full names, and calls the store. Nothing else touches the store
or its tables.

The store is a Python protocol at the level of artifacts, not of bytes:

- `write(session, scope, name, data, media_type, *, author, run, state, visit, summary,
  title)`: the new record, and whether its content equals the previous one's
  (`unchanged`).
- `latest(session, scope, name)`: the artifact and its latest record, or none.
- `artifact(artifact_id)`: an artifact by its id with its latest record, or none (the UI's
  page and feed; `artifacts.of_artifact` checks that it is the session's).
- `record(record_id)`: a record's metadata; `content(record_id)`: its bytes.
- `list(session, scope=None)`: the session's artifacts (or one scope's) with their latest
  records.
- `remove_session(session)`: everything of a session.
- `usage()`: what the store holds and its unreferenced content, for `lado doctor`.

Why at this level: a later backend (a separate service) then owns names, records and
content alike, and LADO keeps only opaque ids in its own tables (attachments). An interface
for bytes alone would leave the metadata in `lado.db` and need a sync between the two,
which is most of the work such a move costs.

The store is chosen in one place, `artifacts.store()`. There is one backend now, with no
setting to choose it (only what is used).

### The local backend

- Metadata in `lado.db`: tables `artifacts` (id, session, scope, name, title, created_at,
  created_by; unique `(session, scope, name)`, scope `''` for the session's) and
  `artifact_records` (id, artifact, session, seq, hash, size, media_type, author, run,
  state, visit, summary, created_at; unique `(artifact, seq)`, the latest record has the
  highest `seq`; the session is the artifact's, kept with the record as every journaled
  table keeps its own). Schema 21. Both are journaled (`changes`), so the UI's feed sees
  them. Their SQL is in `state.py`, as all of LADO's; only `artifacts_local.py` calls it.
- LADO's own table `attachments` (message or note, position, artifact, record) keeps the
  store's ids as opaque values, with no foreign key to the store's tables; it goes with its
  message or note. Not journaled: attachments are written with their message or note and
  never change, so the feed's item of the message or note carries them.
- No foreign key from `artifacts` to `sessions`: `lado forget` calls the store's
  `remove_session` before it deletes the session's rows, as any backend needs it, so a
  forget that fails in between can be run again and a new session of the same name never
  sees the old one's artifacts.
- Content in files, by hash: `LADO_HOME/artifacts/<first two hex>/<sha256>`, written to a
  temporary file in the same folder, fsynced and renamed, then the record row is written.
  Equal content is stored once: a writer that finds the file there sets its modification
  time to now instead of writing it. Its bytes never change.
- A crash between the file and the row leaves a file no record refers to (an orphan); see
  Lifecycle. A file is removed only when no record refers to it and its modification time
  is more than an hour old, so a removal never takes the file of a write in progress (one
  that found the file there and is about to insert its row). A writer whose file a removal
  took all the same (its time update finds no file, or the file is gone once its row is
  in) writes the file again: it has the bytes.

### Moving to another backend later

What a separate service would take: a new class with the same protocol, chosen in
`artifacts.store()`; the UI feed's changes of artifacts from that service as well as
`lado.db`'s journal: `server/feed.py`'s `Source` is one source with one integer position
today, so two sources need a merged or composite position, a real part of the cost;
`remove_session` and `usage` against the service; and a namespace for each LADO
installation, since a session's name is unique only in its own `LADO_HOME`. Agents' tools, the CLI, the API, the UI and the attachments
(opaque ids) stay as they are.

## How agents use them

MCP tools for every agent (`mcp_server.py`), so every provider has them:

- `write_artifact(name, content | file, media_type?, summary?, title?)`: exactly one of
  `content` (text) or `file` (a path relative to the folder LADO started the agent in, its
  worktree or the supervisor's repo, `agents.cwd`; or absolute). The file is read by the
  agent's own `lado mcp` process, which always runs on the agent's machine, so the path is
  only how the bytes get in: it is never kept and never shown. `media_type` is the one
  given, else by the file's extension, else by the name's, else `text/markdown` for content
  and `application/octet-stream` for a file; extensions map by one table in `artifacts.py`
  (`EXTENSIONS`, no system `mimetypes`), where code and text are `text/*`. Returns `{name`
  (full), `status` (`created` | `unchanged`), `size, media_type}`.
- `read_artifact(name, from_line?, to_line?)`: a text artifact's latest content (media type
  `text/*`, `application/json`, `image/svg+xml`), UTF-8 with invalid bytes replaced, at
  most 100 000 characters of whole lines (one longer line is cut), a line range for a
  longer one: `{name, media_type, size, lines` (the total), `from_line, to_line, content,
  cut}`. A binary artifact gives `{name, media_type, size, binary: true, note: "cannot be
  read as text"}`.
- `list_artifacts(run?)`: the scope a bare name means for the agent, or `run`'s: `{name`
  (full), `title, media_type, size, author, time, summary}` each, as of its latest record.

Limits: 25 MB per record; the limits above for names, titles and summaries; a write over a
limit is refused with the limit in the error.

## Attachments

- `send_message`, `ask_human` and `flow_advance` take `artifacts`: a list of names (bare or
  full). Each is resolved at the call to its latest record, and the message or note keeps
  that record (table `attachments`: message or note, artifact, record). A name not found
  refuses the whole call.
- The recipient's line says how many are attached: `[from <x>] <summary> (#<id>, <n> lines,
  <k> artifacts: call read_messages)`, or `(#<id>, <k> artifacts: call read_messages)` for
  a message with no body. A message with artifacts and no body is one to read like one with
  a body (`state.TO_READ`, the one condition): `read_messages` returns it and marks it
  read, and `lado stop` and `finish_worker` drop it unread and count it. `read_messages`
  gives each attachment's full name, title, media type, size and whether the artifact's
  content `changed` since (its latest record's hash differs from the attached one's).
- A flow step's text names the artifacts of a needed note and of the previous step's note
  on a line below it, `Artifacts: <full name>[ (changed since)], ...`; `lado answer` prints
  the same line under the note that led to the gate.
- The human attaches nothing in this version (`write_as_human` takes no artifacts).
- What the human approved at a gate is the record attached to the note before it, so a
  later rewrite of the artifact never changes what the gate showed. A gate keeps the id of
  that note (`gates.note_id`, schema 22, written after the note in the same transaction);
  a gate's attachments are that note's, found only by that id, also for a closed gate
  after its run moved on (`runs.gate_attachments`, `lado answer`, the API's `GateInfo`);
  a gate that keeps none (one from before schema 22) has none.
- `artifacts.attached` is the one builder of attachments (each one's artifact and record),
  for `read_messages`, the steps' and `lado answer`'s lines and the API; whether one
  changed since is looked up only when asked (`with_changed`: the agents' and the CLI's
  side), since the UI compares the hashes itself.

## The human's side

- CLI, the verb first as in `lado kits`, also for a stopped session: `lado artifacts list
  <session> [--run RUN]` lists them (full name, media type, size, author, time, title);
  `lado artifacts show <session> <full-name>` prints a text artifact (a binary one is
  refused with the `get` that writes it); `lado artifacts get <session> <full-name> [-o
  FILE]` writes its bytes, to stdout without `-o` (refused for a binary artifact when stdout
  is a terminal). `lado artifacts` alone prints its help.
- API (under `/api`, behind the same token and `Guard` as the rest; a session's only, an
  unknown one or another session's id is 404; through `artifacts.py` only:
  `of_session`, `of_artifact`, `of_record`, `content`):
  - `GET /api/sessions/{name}/artifacts`: the session's artifacts (`ArtifactInfo`: id,
    session, scope, name, full name, title and `latest`, its latest record as a
    `RecordInfo`: id, media type, size, hash, author, run, state, summary, time);
  - `GET /api/sessions/{name}/artifacts/{id}`: one artifact with its latest record;
  - `GET /api/sessions/{name}/records/{record}`: a record with its artifact as it is now;
  - `GET /api/sessions/{name}/records/{record}/content[?download=1]`: its bytes,
    `Content-Type` from its media type (`; charset=utf-8` for `text/*`), the headers of
    one function, `server/app.py`'s `_content_headers`: the sandbox and nosniff below,
    inline for the allow-list below, else and with `download=1` a download
    (`Content-Disposition: attachment`), the file's name the artifact's with no `/`, `\`,
    quote or control character, and the extension of its media type
    (`artifacts.PREFERRED_EXTENSION`, one per type) only when its own is not that type's
    (`mockup.html` stays). A 200 is `Cache-Control: private, max-age=31536000, immutable`
    (a record never changes); content missing from the store is a 500 with the core's
    error and `no-store`.
  Messages, notes and gates carry their attachments (`AttachmentInfo`: artifact id, record
  id, full name, name, scope, title, media type, size and the attached record's `hash`). The
  UI says an attachment changed since when its hash differs from its artifact's latest
  (`web/src/artifacts.ts`, `changed`, the UI's one comparison; `unknown` while the
  session's artifacts are not loaded); `read_messages` gets `changed` from the core. An
  open gate's `reads` are the full names of the artifacts it reads but those its note
  carries (`runs.gate_reads`), names only: the UI takes each one's latest record from the
  feed's artifacts (Flows, below). The feed sends an artifact's `ArtifactInfo` as its item,
  also when a new record is written.
- UI (docs/design/ui.md, Artifacts): the session's Artifacts tab is a table of its
  artifacts, newest first, with filters by scope and type and a search; a row opens the
  artifact's page (`/sessions/<name>/artifacts/<id>`, `?record=<id>` for a record that
  is not the latest). A viewer shows Markdown (as the chat does, no raw HTML), text and
  code with line numbers, images, HTML in a sandboxed frame, and offers a download for
  every type. Attachments show as chips on messages, gate cards and notes; a chip opens
  the attached record in a panel over the page (`?view=<record>`), with Open in Artifacts
  tab; an attachment whose artifact changed since says so and opens the latest from
  there (changed: by hash, as above).
- Every response with an artifact's content carries `Content-Security-Policy: sandbox`
  and `X-Content-Type-Options: nosniff`; only `text/html` gets `sandbox allow-scripts`.
  The media type is the agent's word, so content is served inline only for an allow-list:
  `text/plain`, `text/markdown`, `text/html`, raster images and `image/svg+xml` (under the
  same sandbox); every other type is a download (`Content-Disposition: attachment`). A
  sandboxed response runs in an opaque origin, so a script in it (an HTML mockup, an SVG)
  cannot send the UI's cookie with a request of its own or act as the human, also when
  opened in a tab of its own.
- HTML is shown in an `<iframe sandbox="allow-scripts">`, never with `allow-same-origin`:
  mockups work, the page cannot reach the UI.

## Flows

A work state may name the artifacts its step must write: `produces: [design]`. It holds
for the state, whatever the outcome (the human's decision, 2026-10-08; one per outcome
waits for a real case). Every outcome of that state (`flow_advance`) is refused until the
latest record of each, in the run's scope, has that state and the state's current visit
number (no clocks are compared; a record written unchanged counts). While the run is in a
visit, every write to its scope is of that visit, so the latest record is the one to
count; a writer that read the run before it entered the state writes a record of the
state before, and the step is refused until it writes again (fail closed, no harm). The
refusal names each missing artifact as the caller writes it, with the `write_artifact`
call: bare for a run's worker, `<run>/<name>` for the lead (Names and scopes). The check
fails closed: an error of the store refuses and nothing is reported; any other error is a
bug and is not hidden. The author is not checked: a record of any agent that may write to
the run's scope counts (the run's workers, the supervisor; Names and scopes).

The counted records are attached to the step's note by themselves, first, then the
`artifacts` the agent named, each artifact once; so the gate after the step and the next
step show them with the note. The step's text names them as its agent writes
them (`This step must write: ...`); `flow_status` names them by their full names, which
work for any agent. `lado flow-set`, a gate's answer and a loop limit's `continue` report
no step and check nothing; since every entry into a state counts a visit, a record of an
earlier visit never counts after them.

Gate and end states take no `produces`. `flows.parse` checks the names' grammar
(`flows.ARTIFACT_NAME`, which `artifacts.NAME` is) and that each is named once: a flow
that breaks it does not load.

A step's inputs are artifacts too, in the same names (the human's decision, 2026-10-08): a
work or gate state may name the run's artifacts it reads, `reads: [design]`. A step's text
gives, after the previous step's note, a line per name with the artifact's latest record
as the step is told (its name as the agent writes it, title and summary, and
`read_artifact`; `no record yet`), never its content; a record attached to the previous
step's note is named only there. On a later visit of its state, a step is shown the records
of its own `produces` so far; naming one of its own `produces` in `reads` does not load. A
gate shows the human the note that led to it in full with its artifacts, then a line (a
chip in the UI) per artifact it reads, except those that note carries. The gate shows the
latest record in the store, also one written while it is open (writing to the run's scope
is allowed while it waits): that is what the human approves. In the UI a write shows at
once (the feed's artifacts), and the note's chip of an artifact written since says
`changed since`; `lado answer` reads the records at each show. Each name of `reads` must
be one some state of the flow produces, and `lado kits check` fails on one that no state
before the reading one produces (`flows.lint`). That is a rule of what is used today: once
a run has artifacts no step writes (a run's addendum, a task's context from a tracker),
`reads` takes them as well.

`needs` (LADO 0.26 and older: states whose latest notes a step got) is gone: a flow with it
does not load, with the way out (`needs was replaced by reads (artifact names) in LADO
0.27`); an open run whose snapshot has it shows that as its problem and only `flow_cancel`
moves it; schema 23 drops it from the snapshots of ended and cancelled runs.

Artifact or note (the human's decision, 2026-10-08): an artifact is a step's result, a
document read later (a design, a review, a report); it is always there, so its state names
it in `produces`, and no step writes an empty one just in case. A note is the short message
about the step to whoever acts next: the verdict, the questions for the human, what changed;
with no questions the note says so or says nothing. Questions are a note, not an artifact.
What a step writes only sometimes (a mockup, a log) it attaches with `flow_advance`'s
`artifacts` when it is there; `produces` names only what is required. A human's comment at
a gate reaches the next step only, as its note; instructions that last a run wait for a
run's addendum (BACKLOG.md).

## Lifecycle

- An artifact lives as long as its session: `lado stop` keeps it, `lado forget` removes the
  session's artifacts, records and attachments, then the content files no record refers to
  any more whose modification time is more than an hour old (the local backend's rule);
  newer ones go at a later `lado forget`.
- Orphans (content files with no record, from a crash) older than one hour are removed by
  `lado forget`; `lado doctor` shows the store's size and its orphans. There is no
  background process and no retention policy.

## Parts, in order of merge

1. **Core**: schema 21, `artifacts.py`, the store protocol and the local backend, the three
   MCP tools, attachments on `send_message`, `ask_human` and `flow_advance` with
   `read_messages`, the CLI, `lado forget` and `lado doctor`, the lead's instructions on
   full names. Its integration test (fake agent): `write_artifact(file=...)` is read by
   the agent's `lado mcp` in the agent's working folder.
2. **UI**: the API, the feed, the Artifacts tab and its viewer, attachments on messages,
   notes and gates (with the gate keeping the id of the note before it, BACKLOG.md "A gate
   shows a needed note twice ..."), its update of docs/design/ui.md. Starts from mockups.
3. **Flows**: `produces`, then (run feature/flow-inputs, schema 23) `reads` in place of
   `needs` and the rule of artifact or note (Flows). An open run's task cannot be amended
   (BACKLOG.md): not here, but a run of its own right after part 4, an addendum
   `<run>/addendum` the human approves.
4. **Kit**: the lado-dev and kit-builder kits' flows write their design, report and review
   as artifacts and read them with `reads` (in the kits' repositories), after
   feature/flow-inputs merges and before the release of LADO 0.27.

Parts 2 and 3 may start before part 1 merges, against this contract, but merge after it.
Only one part at a time changes the schema: part 1 made schema 21, part 2 schema 22, part 3
schema 23.

## Left out

- Showing records as versions, and a diff between them.
- The human uploading files for agents.
- Artifacts that outlive their session (a project's, a tracker task's): with projects
  (ROADMAP, Later).
- A retention policy, and images given to agents as images.
- Any other backend than the local one.
- Deleting one artifact, by an agent or the human: no real case yet; a mistaken one lives
  until `lado forget`.
