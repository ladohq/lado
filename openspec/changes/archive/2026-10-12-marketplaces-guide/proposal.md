Task: LAD-20

## Why

A team that has written its own kits has no document that tells it how to list them for
everyone: README's `## Kits` says only "Publish a kit in a marketplace", and what a
marketplace author needs (`marketplace.yaml`, the `index.json` format, the CI that builds
it, how to propose a kit to the official marketplace) is either in `docs/kits.md`'s "Share
your kit", where LAD-16 parked the `index.json` format for kit users, or only in the
official marketplace's own repository (github.com/ladohq/marketplace). The root cause: the
Kits guide is written for kit users and kit authors, and marketplace authors were left for
this task (LAD-16, Out of scope).

## What Changes

- README.md: a new section `## Marketplaces`, right after `## Kits`: why a team or company
  wants its own marketplace, short, with no YAML or JSON, linking `docs/marketplaces.md`.
  Approved text below.
- A new guide, `docs/marketplaces.md` ("Marketplaces guide"), for marketplace authors.
- `docs/kits.md`, section 7 "Share your kit": the `marketplace.yaml` example and the
  `index.json` format move to the new guide; the section keeps its steps and links it.
- Pointers to the `index.json` format follow it: AGENTS.md (`marketplaces.py`'s line) and
  docs/design/ui.md (Kits, Available).
- CHANGELOG.md: one line under `## 0.36.0 (unreleased)`.

## README's Marketplaces section (approved text)

```markdown
## Marketplaces

**Your team's own list of kits.** A marketplace is a git repository that names the kits
your team trusts, so everyone installs them by name instead of passing addresses around.

- **One command for everyone.** `lado marketplaces add team <git-url>` once, then
  `lado kits add <kit> -m team`; the UI's Kits page lists its kits with their roles,
  flows and versions.
- **You decide what is in it.** Only the kits you reviewed are listed; a pull request to
  the list is your review step.
- **Private is fine.** LADO clones it with your own git access, so it can live next to
  your code.
- **Nothing to host.** No server: a repository with one YAML file, and an optional CI job
  that keeps its index fresh.

How to make one, its index and how to propose a kit to the official marketplace:
**[Marketplaces guide](docs/marketplaces.md)**.
```

The developer may fix wording, never add a claim the code does not back.

## Scope

`docs/marketplaces.md`, sections in this order:

1. **What a marketplace is**: a git repository with `marketplace.yaml` at its root, a list
   of kit names and the git address of each kit's own repository; it holds no kits. The
   official one (github.com/ladohq/marketplace) is always there and can only be disabled.
   Why a team makes its own (the points of README's section, with the facts behind them).
2. **Make one**: the repository; `marketplace.yaml` (`kits:` name -> git address; the name
   is the kit's `name` in its kit.yaml and matches `[a-z0-9][a-z0-9_-]*`; one kit per
   repository, installed by its release tags `vX.Y.Z`); a private repository works with
   the user's own git access (ssh keys or a credential helper; LADO never asks for a
   password, a refused clone is an error); how the team adds and uses it (`lado
   marketplaces add <name> <git-url>`, `lado kits add <kit> -m <name>`, `lado marketplaces
   update`, the UI's Kits page); that a kit from any marketplace but the official one
   shows its plan and asks `Install? [y/N]` (`--yes`); that removing a marketplace leaves
   its installed kits.
3. **`index.json`**: what it is for (the UI's Available list without cloning each kit),
   optional (without it the page shows names and addresses), read from the marketplace's
   clone, never the network; format version 1 moved from `docs/kits.md` as it is, with its
   rules (only `address` required and equal to `marketplace.yaml`'s; unknown keys passed
   over; a higher `index` needs a newer LADO; an entry of a kit the list does not name is
   left out).
4. **The marketplace's CI**: what it does, in words: for each listed kit its latest release
   tag (no pre-release) and that tag's commit, `lado kits check . --tag <tag>` on a clone
   of it and its kit.yaml `name` equal to the list's, then the index fields read from the
   kit at that tag, `index.json` written and committed when it changed; on a pull request,
   check only the kits it adds or changes. The official marketplace's `scripts/` and
   `.github/workflows/` linked as a working example, not copied.
5. **Propose a kit to the official marketplace**: a short list of what it takes (one kit
   per repository with kit.yaml at its root; `version` equal to the tag; `lado kits check
   . --tag vX.Y.Z` prints OK; a pull request adding one line to `marketplace.yaml` and one
   row to its README's table; a maintainer reviews the kit, as its prompts steer agents and
   its MCP servers run code), linking that repository's README as the source of the rules
   and its SECURITY.md for reporting a listed kit.

`docs/kits.md`, section 7: steps 1 and 2 stay; step 3 says a marketplace lists the kit by
name and links `docs/marketplaces.md`; the `marketplace.yaml` example and the whole
`index.json` part leave. Every other link to `docs/kits.md` for the format points at the
new guide.

## Out of scope

- A ready CI workflow or index builder in LADO's docs or code: it would be a second copy
  of the official marketplace's scripts to keep in step (the human's decision, option (a)).
- A LICENSE for github.com/ladohq/marketplace, so its scripts may be copied: another
  repository; the human did not ask for a task now.
- A command in LADO that builds `index.json`: no kit or marketplace needs it yet (Only what
  is used).
- Changing the official marketplace's README rules: the guide links them.
- Any code change: none is needed.

## Acceptance criteria

- AC-1: README has `## Marketplaces` right after `## Kits`, with the approved text (wording
  fixes only), no YAML or JSON, linking `docs/marketplaces.md`.
- AC-2: `docs/marketplaces.md` has the five sections of Scope, in that order.
- AC-3: The `index.json` format 1 and the `marketplace.yaml` example are in
  `docs/marketplaces.md` and no longer in `docs/kits.md`; `docs/kits.md`'s section 7 links
  the new guide.
- AC-4: Every fact the guide states agrees with the code (`marketplaces.py`: `NAME`,
  `KIT_NAME`, `INDEX_VERSION`, `add`, `index`; `kits.py`: `needs_confirmation`;
  `gitcache.py`: `GIT_TERMINAL_PROMPT=0`) and with github.com/ladohq/marketplace's README
  and CI as they are; every command it names exists in `lado marketplaces --help` or
  `lado kits --help`.
- AC-5: Every relative link in README.md, docs/kits.md and docs/marketplaces.md resolves,
  anchors included; AGENTS.md and docs/design/ui.md point at docs/marketplaces.md for the
  format.
- AC-6: CHANGELOG.md has one line for the guide under `## 0.36.0 (unreleased)`.

## Impact

- Docs only: README.md, docs/marketplaces.md (new), docs/kits.md, AGENTS.md,
  docs/design/ui.md, CHANGELOG.md. No code, API, schema or spec change: a patch release
  (the next version is already 0.36.0 for other changes).

## Decisions for the record

- Scale tweak: docs only, the shape of LAD-16's Kits guide; no delta spec, archived with
  `--skip-specs`.
- The proposal rules of the official marketplace are summarised and linked, not copied:
  its README is checked by its CI, one source of truth.
- The `index.json` format is written once, in docs/marketplaces.md; `marketplaces.py`'s
  docstring keeps its copy for code readers, as before.
