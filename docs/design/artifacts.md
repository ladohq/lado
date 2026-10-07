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
  `artifact_records` (id, artifact, hash, size, media_type, author, run, state, visit,
  summary, created_at). Schema 21. Both are journaled (`changes`), so the UI's feed sees them.
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
  `content` (text) or `file` (a path relative to the agent's working folder, or absolute).
  The file is read by the agent's own `lado mcp` process, which always runs on the agent's
  machine, so the path is only how the bytes get in: it is never kept and never shown.
  `media_type` defaults to the file's extension, else `text/markdown` for content. Returns
  the full name, `created` or `unchanged`, size and media type.
- `read_artifact(name, from_line?, to_line?)`: a text artifact's latest content (media type
  `text/*`, `application/json`, `image/svg+xml`), at most 100 000 characters, a line range
  for a longer one; the result says the total lines when it is cut. A binary artifact gives
  its metadata and says it cannot be read as text.
- `list_artifacts(run?)`: the agent's scope (or a run's) with name, title, media type, size,
  author, time and the latest summary.

Limits: 25 MB per record; the limits above for names, titles and summaries; a write over a
limit is refused with the limit in the error.

## Attachments

- `send_message`, `ask_human` and `flow_advance` take `artifacts`: a list of names (bare or
  full). Each is resolved at the call to its latest record, and the message or note keeps
  that record (table `attachments`: message or note, artifact, record). A name not found
  refuses the whole call.
- The recipient's line says how many are attached: `[from <x>] <summary> (#<id>, <n> lines,
  <k> artifacts: call read_messages)`. `read_messages` gives each attachment's full name,
  title, media type and whether the artifact's content changed since (its latest record's
  hash differs from the attached one's).
- What the human approved at a gate is the record attached to the note before it, so a
  later rewrite of the artifact never changes what the gate showed.

## The human's side

- CLI: `lado artifacts <session> [--run RUN]` lists them; `lado artifacts <session> show
  <full-name>` prints a text artifact; `lado artifacts <session> get <full-name> [-o FILE]`
  writes its bytes.
- API (under `/api`, behind the same token and `Guard` as the rest): the session's
  artifacts, one artifact with its latest record, and a record's content
  (`Content-Type` from its media type, a sanitized `Content-Disposition` name, inline for
  the allow-list below, a download otherwise). Messages, notes and gates carry their
  attachments (artifact id, full name, title, media type, size, record id, `outdated`).
  The feed sends artifact changes as items like the other kinds.
- UI: the session's Artifacts tab (now a placeholder) lists the artifacts by scope; a
  viewer shows Markdown (as the chat does, no raw HTML), text and code, images, HTML in a
  sandboxed frame, and offers a download for every type. Attachments show as chips on
  messages, gate cards and notes; an attachment whose artifact changed since says so and
  opens the latest from there (changed: by hash, as above). The look is the UI part's design, from mockups.
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

A work state may name the artifacts its step must write: `produces: [design]`. An outcome
of that state (`flow_advance`) is refused until each has a record in the run's scope with
that state and the state's current visit number (no clocks are compared; a record written
unchanged counts); the refusal names each missing artifact by its full name and the
`write_artifact` call that writes it (the full name also for a lead's step, see Names and
scopes). The check fails closed: an error in it refuses. Gate states
take no `produces`. `flows.lint` checks the names' grammar. (Part 3 may refine this to
per-outcome requirements; it changes this section when it does.)

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
3. **Flows**: `produces`.
4. **Kit**: the lado-dev kit's flows write their design, report and review as artifacts
   (in the kit's repository).

Parts 2 and 3 may start before part 1 merges, against this contract, but merge after it.
Only one part at a time changes the schema: part 1 makes schema 21, part 2 the next one.

## Left out

- Showing records as versions, and a diff between them.
- The human uploading files for agents.
- Artifacts that outlive their session (a project's, a tracker task's): with projects
  (ROADMAP, Later).
- A retention policy, and images given to agents as images.
- Any other backend than the local one.
- Deleting one artifact, by an agent or the human: no real case yet; a mistaken one lives
  until `lado forget`.
