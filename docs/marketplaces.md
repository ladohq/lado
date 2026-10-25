# Marketplaces guide

A marketplace is a list of kits: your team installs them by name instead of passing their
addresses around. This guide is for whoever keeps one: what a marketplace is, how to make
one, the `index.json` the web UI reads, the CI that builds it, and how to propose a kit to
the official marketplace. Installing and writing kits is in the
[Kits guide](kits.md).

- [1. What a marketplace is](#1-what-a-marketplace-is)
- [2. Make one](#2-make-one)
- [3. index.json](#3-indexjson)
- [4. The marketplace's CI](#4-the-marketplaces-ci)
- [5. Propose a kit to the official marketplace](#5-propose-a-kit-to-the-official-marketplace)

## 1. What a marketplace is

A git repository with a `marketplace.yaml` at its root: a list of kit names and the git
address of each kit's own repository. It holds no kits: versions, roles, skills and flows
come from the kits themselves, from their release tags.

The official marketplace, [ladohq/marketplace](https://github.com/ladohq/marketplace), is
always there as `official`; it can be disabled, never removed. Any other one you add
yourself.

Why a team makes its own:

- **One command for everyone.** Each member adds it once and then installs a kit by its
  name: `lado kits add <kit> -m <marketplace>`. Without `-m` LADO never looks in a
  marketplace, so a name always means the list you chose.
- **You decide what is in it.** It lists only the kits you put there; a pull request to
  `marketplace.yaml` is your review step. A kit from any marketplace but the official one
  shows what it would install and asks first (below).
- **Private is fine.** LADO clones it with your own git access, as it clones the kits, so
  it can live next to your code.
- **Nothing to host.** No server: a repository with one YAML file, and an optional CI job
  that keeps its `index.json` fresh.

## 2. Make one

1. Make a git repository your team can clone, on any git host.
2. Put a `marketplace.yaml` at its root that maps each kit's name to the git address of
   its repository:

   ```yaml
   kits:
     my-team: https://github.com/<owner>/my-team.git
     tracker-ours: git@git.example.com:tools/lado-kit-tracker.git
   ```

   The name must be the `name` in that kit's kit.yaml (`lado kits add` checks it) and is
   lowercase letters, digits, `-` or `_`, starting with a letter or digit. Each address is
   one kit's repository, with its kit.yaml at the root; LADO installs it by its release
   tags `vX.Y.Z` (the [Kits guide](kits.md#6-improve-and-version-a-kit) says how a kit is
   released).
3. Commit and push it to the repository's default branch: LADO reads that branch.

**A private repository** works as any other: LADO runs `git` with your own access (ssh
keys, a credential helper, and the variables of `LADO_ENV_DIR`'s folder, such as the
image's `/run/secrets/GH_TOKEN`). It never asks for a password; a clone git refuses is an
error that says so, with where to give a token. The same holds for the kits it lists.

**Your team adds it once** (a marketplace's name is lowercase letters, digits and `-`):

```bash
lado marketplaces add team https://github.com/<owner>/marketplace   # clones it, reads its list
lado kits add my-team -m team                                       # install a kit from it
lado kits add my-team@v1.2.0 -m team                                # a given version
lado marketplaces update team                                       # fetch its latest list
```

Or in the web UI: `lado ui`, then **Kits**; the Marketplaces block adds, updates, enables,
disables and removes them, and the Available tab lists their kits.

A kit from any marketplace but the official one (and from a git address) shows first what
it would install (address, version, commit, its MCP servers) and asks `Install? [y/N]`;
`--yes` skips the question, and without a terminal it is required. Removing a marketplace
(`lado marketplaces remove team`) leaves the kits installed from it; `lado kits` then shows
their source as `(marketplace team, removed)`.

LADO keeps a clone of each marketplace in `LADO_HOME/marketplaces/<name>/` and reads the
list from there: a kit added to `marketplace.yaml` shows up after `lado marketplaces
update`.

## 3. index.json

`marketplace.yaml` gives only names and addresses. What the web UI's Kits page shows of a
kit it has not installed (its Available tab: the latest version, description, roles,
skills, flows and MCP servers) comes from an `index.json` at the marketplace's root, so
the page needs no clone of each kit. It is optional: without it the page shows each kit's
name and address. LADO reads it from the marketplace's clone, never the network, so it is
as fresh as the latest `lado marketplaces update`.

Version 1:

```json
{
  "index": 1,
  "kits": {
    "sdlc": {
      "address": "https://github.com/ladohq/kit-sdlc.git",
      "latest": "v0.5.0",
      "commit": "4be21c0…",
      "lado": ">=0.30",
      "description": "Day-to-day development of a project whose tasks live in a task tracker.",
      "agents": {"analyst": "the first line of the role's description"},
      "skills": ["openspec-changes"],
      "flows": ["task"],
      "mcp": {"playwright": "npx @playwright/mcp"}
    }
  }
}
```

`latest` is the latest release (no pre-release) and `commit` its commit, `lado` the kit's
`dependencies.lado`, `agents` each role with the first line of its description, `skills`
the kit's own skills, `mcp` each MCP server's command on one line. Only `address` is
required, and it must be the one `marketplace.yaml` gives: an entry with another address
is not used, and the page names the problem. Keys LADO does not know, in an entry or at
the top, are passed over, so the CI may add some without a new version; a higher `index`
needs a newer LADO. `marketplace.yaml` stays the list of names and addresses: an entry of
a kit it does not list is left out.

## 4. The marketplace's CI

Write `index.json` with a CI job rather than by hand, so it follows the kits' releases.
What it does:

- For each kit in `marketplace.yaml`: its repository's latest release tag `vX.Y.Z` (no
  pre-release; `git ls-remote --tags`) and the commit that tag points to.
- A clone of the kit at that tag; the `name` in its kit.yaml must be the one in the list,
  and `lado kits check . --tag <tag>` must pass, as `lado kits add` would check it.
- The index fields read from the kit at that tag: kit.yaml's `description` and
  `dependencies.lado`, its roles with the first line of each description, its own skills,
  its flows and its MCP servers.
- `index.json` written, and committed when it changed: on each push to the default branch,
  and on a schedule, so new releases of the kits show up without a change to the list.
- On a pull request: only the kits it adds or changes are checked, so a broken kit
  elsewhere does not block it.

The official marketplace does exactly this: its
[scripts/](https://github.com/ladohq/marketplace/tree/main/scripts) and
[.github/workflows/](https://github.com/ladohq/marketplace/tree/main/.github/workflows)
are a working example to read. There a kit whose latest tag fails its check keeps its
previous entry, and the build fails so someone looks.

## 5. Propose a kit to the official marketplace

The rules are in [ladohq/marketplace's README](https://github.com/ladohq/marketplace#propose-a-kit),
which its CI checks against; in short:

- One kit per repository, with kit.yaml at its root.
- Each release a tag `vX.Y.Z` whose kit.yaml says that `version`; never move a published
  tag.
- `lado kits check . --tag vX.Y.Z` prints `OK` before you tag.
- A pull request that adds one line to its `marketplace.yaml` (`<name>: <git-url>`, the
  name as in kit.yaml) and one row to the README's table.
- A maintainer reviews the kit itself: its prompts steer agents and its MCP servers run
  code.

A listed kit that turns out vulnerable or malicious: report it privately, as its
[SECURITY.md](https://github.com/ladohq/marketplace/blob/main/SECURITY.md) says.
