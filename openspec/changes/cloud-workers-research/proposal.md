Task: LAD-100

## Why

LADO runs every agent on the human's own machine. LAD-100 asked how agents could run in a
cloud instead, without tying LADO to one cloud, with any agent CLI, as an option next to
the local mode and never a requirement, and with a paid hosted offering kept possible for
later. The research is done (five reports, written in the design dialogue of LAD-100),
and the human approved its staged plan on 2026-10-18. This change saves the plan and the
research behind it in the repository, as the Docker research of LAD-52 was saved, so the
next tasks build on it. It builds nothing users get.

## What Changes

- `docs/research/cloud-workers.md` (new, English): the research report, the approved
  Russian summary (the session artifact `lad-100-research`, sections 1-5 and 7) in English,
  in this order:
  1. **Summary**: the five findings (the control plane / sandbox split the industry
     converged on; LADO has no owning process, so moving a whole session is cheap and a
     single remote worker is dear; OCI, the Docker API and the Kubernetes API as the
     portability layers; unchanged CLIs in tmux keep "any provider"; the paid variant is
     limited by terms, not by technology).
  2. **Options**: where to run (the table of targets with lock-in, self-hosting, fit for a
     long interactive session and the verdict), the portability layers, isolation.
  3. **Split points A-D**: the table (what runs where, what LADO must change, size), the
     answer to "what to run in the cloud", and the assets in the code to reuse.
  4. **Logins and money**: the matrix of CLIs by scenario (own cloud with own
     subscription; hosted with the user's subscription; hosted with the operator's keys)
     and its consequences (self-hosted first; BYOK for a paid service; one refreshing
     login per container; remote MCP over HTTP with a bearer header in all four CLIs).
  5. **Principles**: the five principles of the solution.
  6. **Risks**.
  7. **Sources**: the four reports under `docs/research/cloud-workers/`, one line each.
- `docs/research/cloud-workers-plan.md` (new, English): the living staged plan, updated
  after each step as `docker-install-plan.md` is:
  1. **Decisions taken** (2026-10-18): start with stage A as the continuation of the
     Docker work; the first targets are a Docker host over SSH and Kubernetes; a paid
     service only as BYOK; the plan lives in the repository; contacting the model
     providers (Anthropic, OpenAI) is left to the later stages of implementation; only the
     next task goes to the tracker, each on the human's yes.
  2. **How the work goes**: each step is a working delivery that leaves the local mode
     unchanged; the plan is revisited after each step.
  3. **Step 0 and stages A-E**, each item with its technical details (below).
  4. **Technical details**: the coupling table C1-C16 of report R1 (coupling, main code
     references, today, what breaks when an agent is remote, the seam, size), with the
     commit the references are taken at; a sketch of the execution backend interface
     below `providers/` (its verbs, tmux as the first implementation, a remote node and
     an ACP runtime as the next two, each backend saying loudly what it cannot do); the
     node protocol (hook forwarding to the control plane, MCP over HTTP with a per-agent
     token from `agents.instance`, the control plane as the only writer of `lado.db`,
     heartbeats, the terminal relay, a protocol version check modelled on
     `SchemaError`); the launch bundle (render and materialize); git for stage D
     (workspace and branch sync options); credentials and terms constraints per CLI.
  5. **Risks** and **Open questions**: an example on a Russian cloud; running step 0 as a
     separate session by brief; the legal questions of stage E (contacting providers,
     a lawyer), all marked "decide later".
- `docs/research/cloud-workers/` (new): the four intermediate reports, as they were
  written, with all their sources: `r1-lado-coupling.md`, `r2-prior-art.md`,
  `r3-cloud-survey.md`, `r4-credentials.md`. Changed only to drop local absolute paths
  (R1 names the machine's checkout path) and scratchpad paths.
- `ROADMAP.md`: one line under "Later (after stage 7)": cloud workers researched
  2026-10-18, the staged plan in `docs/research/cloud-workers-plan.md`.
- A Russian comment on LAD-100: the short result, the files, the pull request's link.

- `openspec/changes/cloud-workers-research/inputs/` (temporary): the session's artifacts
  as files, so the change can be built from another LADO installation (the human moves
  from the PyPI install to the Docker one, 2026-10-19): `lad-100-research.md` (the
  approved Russian summary, its line on `r5-references` removed), `r1-lado-coupling.md`
  (its local path already replaced by "the repository root"), `r2-prior-art.md`,
  `r3-cloud-survey.md`, `r4-credentials.md`. The build removes the folder once its
  content is in `docs/research/`.

## Scope

- Translating the approved summary into English and moving the plan's technical details
  from the reports into the plan document; no new research.
- Cleaning the four reports of local paths; keeping their content and sources.

## Out of scope

- Any code, API, schema or kit change: the human's decision, documentation only.
- A change of the living specs under `openspec/specs/`: no behaviour rule changes, so the
  change has no delta and is archived with `--skip-specs`.
- The fifth report (`r5-references`) and anything naming the projects it studied: the
  repository is public and those sources stay private; its lessons appear in the plan
  only as LADO's own design reasoning, without attribution.
- Tracker tasks for step 0 or stage A: each is created only on the human's separate yes.
- Contacting Anthropic, OpenAI or a lawyer: the human's decision (2026-10-18), left to
  the later stages of implementation.
- Merging before the 0.41.0 final: the release freeze (docs/release.md, sections 3 and 6)
  refuses a final that differs from its last RC in any file, documentation too. The pull
  request is merged only after the 0.41.0 final, or before v0.41.0rc1 is tagged, on the
  human's yes at merge_ok; the integrator checks the `v0.41.0rc*` tags right before.
- A CHANGELOG line: nothing users see changes (docs only, as LAD-52's research).
- Changes to docs/design/*.md or AGENTS.md: they describe what is built; the plan is not
  built yet.

## Acceptance criteria

- AC-1: `docs/research/cloud-workers.md` exists in English with the seven sections of
  What Changes in that order, and says what the approved summary says (no finding,
  number or verdict added or dropped, except the attribution to the private references).
- AC-2: `docs/research/cloud-workers-plan.md` exists in English with the five sections of
  What Changes; its stages and step 0 hold every item of the approved plan; its technical
  details hold the coupling table C1-C16, the backend interface sketch, the node
  protocol, the launch bundle, the git options for stage D and the credentials
  constraints, each pointing at the report it comes from.
- AC-3: `docs/research/cloud-workers/` holds r1-r4, each with its sources as written; none
  holds a path of this machine (a home folder under `/Users/`, a scratchpad or temp
  path); paths inside a container (`/home/lado`) are content and stay.
- AC-4: No committed file names the private reference projects, refers to them by their
  private nicknames, or holds content of `r5-references`.
- AC-5: `ROADMAP.md` has the one line linking the plan under "Later (after stage 7)".
- AC-6: LAD-100 has a Russian comment with the result, the files and the pull request's
  link; no tracker task is created.
- AC-7: Every relative link in the new documents resolves to a file of the repository.

## Impact

- Docs only: `docs/research/cloud-workers.md`, `docs/research/cloud-workers-plan.md`,
  `docs/research/cloud-workers/*.md` (new), one line of `ROADMAP.md`. No code, API, schema,
  spec or CHANGELOG change; no release bump (a patch-level change if released alone). The
  pull request touches only `docs/`, `openspec/` and a top-level Markdown file, so CI's
  smoke cells skip it.
