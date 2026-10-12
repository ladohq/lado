Task: LAD-16

## Why

Kits are what makes LADO more than a single agent CLI: a team's roles, skills, tools and way
of working, packed once and reused on every project. Yet README's `## Kits` section is a
reference of about 160 lines (kit.yaml keys, `--without` forms, `expects`, MCP secrets, the
marketplace's `index.json`) that tells a newcomer how before it tells them why, and there is
no other document for kits: the flow format exists only in `src/lado/flows.py`'s docstring.

README is also out of date around kits: "Planned" lists artifacts and "Task trackers
(YouGile, Jira) as kits", both of which work now (`tracker-jira-server` in the official
marketplace, `tracker-yougile` at github.com/ladohq/kit-tracker-yougile), and it says LADO
refuses a read-only agent on Codex CLI, which it no longer does (AGENTS.md, Read-only roles).

## What Changes

- README's `## Kits` becomes a short pitch (about 25 lines): what a kit is in one line, its
  benefits, two commands to start, a link to the guide. No formats, flags or YAML.
- A new guide, `docs/kits.md` ("Kits guide"), holds every detail README had about kits and
  what it lacked: find and install a kit, use kits in a session, create a kit (with
  `kit-builder` or by hand), the flow format, improve and version a kit, share it,
  marketplaces from a kit user's side, troubleshooting.
- README's "What works now" and "Planned" agree with the code: artifacts and tracker kits
  (Jira Server, YouGile) move to what works; their "Planned" items go.

## README's Kits section (approved text)

```markdown
## Kits

**A kit is a team you can install.** Roles, skills, tools and the way of working that
made one project go well, packed into a git repository, so the next project starts
where the last one ended instead of from a blank prompt.

- **Start with a team that already knows the job.** `sdlc` takes your tracker's tasks
  from design to a merged pull request, with you approving the design and the merge.
- **Mix and match.** Combine a process kit with a tracker kit (`sdlc` +
  `tracker-jira-server`), and switch off any role, skill, flow or tool per session.
- **Any agent CLI.** One kit runs on Claude Code, Codex, Kilo and OpenCode alike.
- **Versioned like code.** A kit is a release `vX.Y.Z` with pinned skill packs: the team
  behaves the same tomorrow, and `lado kits update` moves it on when you choose.
- **Build your own by talking.** The `kit-builder` kit interviews you about your process,
  writes the kit, and a critic checks it before you tag it.
- **Share it.** Publish a kit in a marketplace, and your team installs it with one command.

```bash
lado kits add sdlc -m official                     # a kit of the official marketplace
lado kits add tracker-jira-server -m official
lado start . --kit sdlc --kit tracker-jira-server  # a session with that team
```

Or open `lado ui`, then Kits. Everything else (finding and installing kits, writing one,
releasing new versions, combining them in a session, marketplaces) is in the
**[Kits guide](docs/kits.md)**.
```

The developer may fix wording, never add a claim the code does not back.

## Scope

- README: the `## Kits` section above; "What works now" (the Kits bullet links the guide;
  artifacts and tracker kits listed as working); "Planned" (the artifacts and task-tracker
  items removed).
- `docs/kits.md`, sections in this order:
  1. **What a kit is**: a git repository or folder with `kit.yaml`, `agents/<role>.md`,
     `skills/<name>/SKILL.md`, `flows/<name>.yaml`; a folder tree; the kits shipped with
     LADO (`default`) and those of the official marketplace (`sdlc`, `tracker-jira-server`,
     `kit-builder`).
  2. **Find and install a kit**: the official marketplace, `lado kits add` (git address,
     `@vX.Y.Z`, `--pre`, a folder, `-m`), the `Install? [y/N]` plan and `--yes`,
     `lado kits`, `outdated`, `update`, `remove`; the UI's Kits page;
     `lado marketplaces` (list, add, update, enable, disable, remove) from a user's side.
  3. **Use kits in a session**: `--kit` (several), who leads (one kit supervisor, else the
     built-in one with `lead-<kit>` skills), `--without kind:name[@kit]`, shared names,
     `spawn_worker(role=...)`, `lado kits show`.
  4. **Create a kit**: with `kit-builder` (its flows `create`, `improve`, `evaluate`) or by
     hand: every key of `kit.yaml` (`name`, `version`, `description`, `supervisor`,
     `dependencies.lado`, `dependencies.skills`, `expects.skills`, `expects.commands`); a
     role's frontmatter (`name`, `description`, `skills`, `mcp`, `read_only`) and its
     prompt; skills; MCP servers with `${KIT_DIR}` and `${NAME}` secrets; read-only roles
     as they work today on each provider (Codex included, with its launch warning);
     developing from a folder (`lado kits add ./my-kit`).
  5. **Flows**: the format in full (work, gate and end states; `agent`, `do`, `outcomes`,
     `max_visits`, `produces`, `reads`; approval and choice gates; `start`), a short
     example, how the human answers a gate, what `lado kits check` lints.
  6. **Improve and version a kit**: tags `vX.Y.Z` and pre-releases, `version` in kit.yaml,
     `dependencies.lado`, pinned skill packs, `lado kits check . --tag` in the kit's CI,
     what users see (`outdated`, `update`, the moved-tag warning).
  7. **Share your kit**: publish the repository, add it to a marketplace's
     `marketplace.yaml`; the marketplace's `index.json` (format 1, moved from README as it
     is) until LAD-20 moves it to `docs/marketplaces.md`.
  8. **Troubleshooting**: a tag that disagrees with `version`, a kit that needs a newer
     LADO, a missing expected skill or command, a name in two kits.
- `docs/install.md` and other docs that point at README's Kits section point at the guide.
- CHANGELOG.md: one line.

## Out of scope

- README's `## Marketplaces` section and `docs/marketplaces.md` for marketplace authors
  (marketplace.yaml, index.json, the marketplace's CI, proposing a kit to the official
  one): LAD-20, the human's decision to keep this task on kits.
- `lado-dev` in README or the guide: it is to be removed soon (the human's decision).
- Adding `tracker-yougile` to the official marketplace: a change of the marketplace's
  repository, not of LADO.
- Claims the code does not back (numbers, speed-ups, planned features) in README: the
  human's decision; caveats go to the guide.
- Any code change: none is needed.

## Acceptance criteria

- AC-1: README's `## Kits` is at most about 30 lines, holds no YAML or JSON and no flag
  reference, names no `lado-dev`, and links `docs/kits.md`.
- AC-2: Every fact README's old Kits section held is in `docs/kits.md` (kit.yaml keys,
  versions and tags, `lado kits` commands, marketplaces, `index.json` format 1, who leads,
  `lead-<kit>`, read-only roles, `--without`, `expects.skills`, `expects.commands`, shared
  names, MCP servers and `${NAME}`).
- AC-3: `docs/kits.md` has the eight sections of Scope, in that order, and documents the
  flow format in full.
- AC-4: README's "Planned" no longer lists artifacts or task-tracker kits; "What works now"
  lists artifacts and tracker kits for Jira Server and YouGile.
- AC-5: No text says LADO refuses a read-only agent on Codex CLI.
- AC-6: Every command and key the guide names exists in the code (`lado kits --help`,
  `lado marketplaces --help`, `kits.KIT_KEYS`, `kits.AGENT_KEYS`, `flows.py`), and every
  relative link in README and the guide resolves.

## Impact

- Docs only: README.md, docs/kits.md (new), docs/install.md if it links the section,
  CHANGELOG.md. No code, API, schema or spec change: a patch release.
