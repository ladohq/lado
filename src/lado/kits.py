"""Kits: provider-neutral bundles of agent roles, skills and MCP servers.

A kit is a directory:

    kit.yaml            name, version, description, supervisor, dependencies
    agents/<name>.md    YAML frontmatter + the role prompt
    skills/<name>/      a SKILL.md folder, always handled as a whole
    flows/<name>.yaml   a flow (lado.flows)

Agents, skills and flows are found in their folders; kit.yaml does not list them. Anything else in
the kit travels with it untouched. A kit is identified by the name and version in kit.yaml.

A kit takes from outside only skill packs, never another kit: `dependencies.skills` maps a
pack's name to `<git address>@<tag or commit>`, or `{from: ..., folders: [...]}`, or a folder
relative to the kit's. A pack is SKILL.md folders (anywhere under skills/, or under its
`folders`) and no kit.yaml. A git pack is cloned once per version into the git cache
(lado.gitcache): load reads what is there and never uses the network, fetch clones the rest.
`dependencies.lado: ">=X.Y"` names the oldest LADO the kit runs with.

Kits are looked up by name in the project (<repo>/.lado/kits), then in LADO_HOME/kits, then
among the kits built into LADO; the first hit wins. LADO_HOME/kits holds what is installed:
folders, and links that `lado kits add` makes to a kit in the git cache or in a local folder.
A kit is one repository with kit.yaml at its root, installed by a version tag vX.Y.Z that
must agree with its kit.yaml `version` (required of every kit): plan_add and plan_update say
what an add or update would do (the clone made, nothing linked), install does it. Which tag
and commit a kit is at is its clone's (gitcache), kept nowhere else; which marketplace lists
it is read from the marketplaces' clones (lado.marketplaces.source_of).

`supervisor` in kit.yaml names the agent of the kit that leads a session; the name
"supervisor" is reserved for it. A flow state of that agent is the lead's step: it is read
as LEAD, so a run's snapshot gives it to the session's lead, whoever that is.

Several kits combine into one Environment for a session (resolve says in which order).
Exactly one kit with a supervisor: it leads; none or several: LADO's built-in supervisor
leads (the default kit's), and a kit supervisor that does not lead is no agent of the
session: its prompt and the skills it names, in its kit's versions, become the built-in
lead's skill lead-<kit> (Environment.lead_skills).
`--without kind:name@kit` switches a thing off in one kit before the kits combine, so two
kits with one name run together; `kind:name` switches it off in the whole session after.
Their roles, flows and own skills are one namespace: a name twice is an error that names
both ways out (KitError.switch_off). The skills of a kit's packs are its agents'
only, so two kits may take two versions of one pack; a kit without agents (by what it holds,
before --without) shares its packs with every agent of the session. Adding a first agent to
such a kit makes its packs private: the agents of other kits lose them, loudly only when
their `skills:` names one.
"""

import dataclasses
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from lado import __version__, flows, gitcache, marketplaces, state
from lado.flows import Flow
from lado.providers.base import McpServer

KIT_FILE = "kit.yaml"
DEFAULT_KIT = "default"
# The session's lead agent is named so, whichever kit's supervisor it is; a flow state of a
# kit's supervisor names it (lado.runs gives such a step to the lead).
LEAD = "supervisor"
BUILTIN = Path(__file__).with_name("builtin_kits")

KIT_KEYS = {"name", "version", "description", "supervisor", "dependencies"}
DEPENDENCY_KEYS = {"lado", "skills"}
PACK_KEYS = {"from", "folders"}
LADO_NEEDS = re.compile(r">=\s*(\d+)\.(\d+)(?:\.(\d+))?")
AGENT_KEYS = {"name", "description", "skills", "mcp"}
MCP_KEYS = {"command", "env"}
WITHOUT_KINDS = ("agent", "skill", "mcp", "flow")

NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")
SEMVER = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?")
VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
# A path that only works on one machine: ~/..., or /dir/... at the start of a word.
HARDCODED_PATH = re.compile(r"(?:^|(?<=[\s\"'`(=:,\[]))(~/|/[A-Za-z0-9._-]+/)[^\s\"'`)]*", re.M)


class KitError(RuntimeError):
    """`switch_off`: the --without items that would each resolve the problem, if any."""

    def __init__(self, message: str, switch_off: Iterable[str] = ()):
        super().__init__(message)
        self.switch_off = list(switch_off)


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path  # the skill's folder
    kit: str
    pack: str | None = None  # the pack of the kit's dependencies it comes from


@dataclass(frozen=True)
class Pack:
    """A skill pack a kit depends on (dependencies.skills): SKILL.md folders, no kit.yaml."""

    name: str
    address: str  # a git address, or a folder relative to the kit's
    ref: str | None  # the tag or commit of a git address
    folders: tuple[str, ...]  # where its skills are, inside it; empty: all of skills/
    path: Path | None  # its folder; None: a git pack not fetched yet
    skills: dict[str, Skill] | None  # None: not fetched yet

    @property
    def spec(self) -> str:
        return f"{self.address}@{self.ref}" if self.ref else self.address

    @property
    def label(self) -> str:
        return f"{self.name}@{self.ref}" if self.ref else self.name


@dataclass(frozen=True)
class McpDef:
    name: str
    command: list[str]  # may contain ${KIT_DIR}
    env: dict[str, str]  # may contain ${KIT_DIR} and ${ENV_VAR}
    kit_dir: Path


@dataclass(frozen=True)
class AgentDef:
    name: str
    description: str
    skills: list[str] | None  # None: all skills of the environment
    mcp: dict[str, McpDef]
    body: str  # the role prompt, ${KIT_DIR} substituted
    kit: str
    path: Path


@dataclass(frozen=True)
class Kit:
    name: str
    path: Path
    where: str  # project, user or built-in; "path" for a kit loaded from a path
    version: str
    description: str
    supervisor: str | None  # the agent of this kit that leads a session (kit.yaml)
    agents: dict[str, AgentDef]
    skills: dict[str, Skill]  # its own, in skills/
    flows: dict[str, Flow] = field(default_factory=dict)
    packs: dict[str, Pack] = field(default_factory=dict)  # dependencies.skills

    @property
    def source(self) -> str:
        """Where it is: its place on the search path, its address@ref when it is from the
        git cache, its folder."""
        origin = cached_origin(self.path)
        return f"{self.where}{f' {origin}' if origin else ''}: {self.path}"

    def unfetched(self) -> list[str]:
        """The packs not in the cache yet (fetch gets them)."""
        return [name for name, pack in self.packs.items() if pack.skills is None]


@dataclass(frozen=True)
class Found:
    """A kit on the search path, not loaded yet."""

    name: str
    where: str  # project, user or built-in
    path: Path  # the entry in its kits folder; a link in LADO_HOME/kits stays a link

    def load(self) -> Kit:
        if self.path.is_symlink() and not self.path.exists():
            raise KitError(
                f"{self.name}: broken link → {os.readlink(self.path)}; "
                f"run `lado kits remove {self.name}`"
            )
        return load(self.path, self.where)

    def link(self) -> str | None:
        """What a link in a kits folder leads to: address@ref of a kit from the git cache,
        else the folder."""
        if not self.path.is_symlink():
            return None
        target = self.path.resolve()
        return cached_origin(target) or str(target)


@dataclass(frozen=True)
class ResolvedAgent:
    """An agent of the environment with the session's and its own exclusions applied."""

    agent: AgentDef
    skills: dict[str, Skill]
    mcp: dict[str, McpDef]

    def mcp_servers(self, environ: Mapping[str, str] | None = None) -> dict[str, McpServer]:
        """The agent's MCP servers with ${ENV_VAR} in their env taken from `environ`."""
        environ = os.environ if environ is None else environ
        servers = {}
        for name, mcp in self.mcp.items():
            where = f'MCP server "{name}" of agent "{self.agent.name}" ({self.agent.path})'
            env = {k: _env_value(v, environ, f"{where}, env {k}") for k, v in mcp.env.items()}
            servers[name] = McpServer(list(mcp.command), env)
        return servers


@dataclass(frozen=True)
class LeadSkill:
    """What a kit's supervisor that does not lead hands to LADO's built-in one: its prompt
    as the skill lead-<kit>, with the skills its `skills:` names in its kit's versions."""

    kit: str
    description: str
    body: str  # the supervisor's prompt
    skills: dict[str, Skill]  # those it names, as its kit's agents see them
    listed: bool  # whether it has `skills:` at all (None gives none, with a warning)
    missing_mcp: list[str]  # its MCP servers: the lead does not get them

    @property
    def name(self) -> str:
        return lead_skill_name(self.kit)


def lead_skill_name(kit: str) -> str:
    return f"lead-{kit}"


@dataclass
class Environment:
    kits: list[Kit]  # every kit taken in, in the order given, before --without
    agents: dict[str, AgentDef]  # the worker roles
    shared: dict[str, Skill]  # every agent's: the kits' own skills, packs of kits without agents
    lead: AgentDef  # the session's lead: the one kit supervisor, else LADO's built-in one
    supervisors: dict[str, str] = field(default_factory=dict)  # kit -> its supervisor, in use
    without: list[str] = field(default_factory=list)
    flows: dict[str, Flow] = field(default_factory=dict)
    private: dict[str, dict[str, Skill]] = field(default_factory=dict)  # kit -> its packs' skills
    # kit -> its supervisor, when LADO's built-in one leads (not the default kit's, which is
    # that one); with the --without items applied. The source of lead_skills.
    kit_supervisors: dict[str, AgentDef] = field(default_factory=dict)

    def visible(self, agent: AgentDef) -> dict[str, Skill]:
        """The skills `agent` may have: the shared ones and its own kit's packs'."""
        return {**self.shared, **self.private.get(agent.kit, {})}

    def lead_skills(self) -> list[LeadSkill]:
        """The skill lead-<kit> of each kit supervisor that does not lead (kit_supervisors):
        none when a kit's supervisor leads."""
        found = []
        for kit, agent in self.kit_supervisors.items():
            visible = self.visible(agent)
            named = {s: visible[s] for s in agent.skills or [] if s in visible}
            description = (
                f"How kit {kit} wants its work led: read it before you take a task for its "
                f"roles or flows. {agent.description}"
            )
            listed = agent.skills is not None
            found.append(LeadSkill(kit, description, agent.body, named, listed, list(agent.mcp)))
        return found

    def all_skills(self) -> list[Skill]:
        """Every skill of the session, one per folder: a name may come twice, from two
        versions of a pack in two kits."""
        found = {s.path: s for s in self.shared.values()}
        for skills in self.private.values():
            for skill in skills.values():
                found.setdefault(skill.path, skill)
        return list(found.values())

    def flow(self, name: str) -> Flow:
        """Flow `name`, once every role it names is an agent of this environment (a step of
        LEAD is the lead's)."""
        found = self.flows.get(name)
        if found is None:
            raise KitError(f'no flow "{name}"; flows: {", ".join(self.flows) or "none"}')
        roles = ", ".join(self.agents) or "none"
        errors = [
            f'{found.path}: state "{s.name}": no role "{s.agent}" in this session; roles: {roles}'
            for s in found.states.values()
            if s.kind == flows.WORK and s.agent != LEAD and s.agent not in self.agents
        ]
        if errors:
            raise KitError("\n".join(errors))
        return found

    def lead_line(self) -> str:
        """Who leads the session, and why when it is LADO's built-in supervisor."""
        if len(self.supervisors) == 1:
            return f"lead: {self.lead.name} of kit {self.lead.kit}"
        if not self.supervisors:
            return "lead: LADO's built-in supervisor (no kit has a supervisor)"
        return (
            f"lead: LADO's built-in supervisor (kits {_and(list(self.supervisors))} each have "
            "a supervisor)"
        )

    @property
    def warnings(self) -> list[str]:
        """How the kits' supervisors are used when none of them leads, each with the way to
        make it the lead, and what their lead skills lack."""
        if len(self.supervisors) < 2:
            return []
        lead_skills = {s.kit: s for s in self.lead_skills()}
        found = []
        for kit in self.supervisors:
            others = " ".join(
                f"--without agent:{s}@{k}" for k, s in self.supervisors.items() if k != kit
            )
            skill = lead_skills.get(kit)
            if skill is None:
                # The default kit's: switching the others off keeps it the lead, so no hint;
                # each other kit's line says how to make that one the lead.
                found.append(
                    f"kit {kit}'s supervisor leads as LADO's built-in supervisor (several kits "
                    "have a supervisor)"
                )
                continue
            found.append(
                f"kit {kit}'s supervisor does not lead (several kits have a supervisor): its "
                f"prompt is the built-in supervisor's skill {skill.name}; to make it the lead, "
                f"switch the others off: {others}"
            )
            if not skill.listed:
                found.append(f"kit {kit}'s supervisor lists no skills: its lead skill carries none")
            if skill.missing_mcp:
                found.append(
                    f"MCP servers of kit {kit}'s supervisor ({', '.join(skill.missing_mcp)}) "
                    "are not available to the session's lead"
                )
        return found

    def roles(self) -> list[AgentDef]:
        """Agents the lead can start as workers."""
        return list(self.agents.values())

    def role(self, name: str | None) -> AgentDef:
        """Worker role `name`; None: the session's only one."""
        if name is None:
            if len(self.agents) == 1:
                return next(iter(self.agents.values()))
            if not self.agents:
                raise KitError("no worker roles in this session")
            raise KitError(
                f"role is required: this session has several worker roles: {', '.join(self.agents)}"
            )
        agent = self.agents.get(name)
        if agent is None:
            roles = ", ".join(self.agents) or "none"
            raise KitError(f'no worker role "{name}" in this session; roles: {roles}')
        return agent

    def resolve(self, name: str, without: Iterable[str] = ()) -> ResolvedAgent:
        """Agent `name` (a role or the lead) with its skills and MCP servers, minus `without`
        (skill: and mcp: items, on top of the session's; with @kit only what comes from that
        kit)."""
        excluded = parse_without(without)
        if excluded["agent"] or excluded["flow"]:
            raise KitError(
                "an agent or flow cannot be switched off for one agent; use skill: or mcp:"
            )
        by_name = {k.name: k for k in self.kits}
        plain = _check_at_kit(excluded, by_name)
        _check_known(plain, {s.name for s in self.all_skills()}, self._all_mcp(), set(), set())
        agent = self.lead if name == self.lead.name else self.agents[name]
        visible = self.visible(agent)
        wanted = list(visible) if agent.skills is None else agent.skills
        skills = {
            s: visible[s]
            for s in wanted
            if s in visible and not _off(excluded["skill"], s, visible[s].kit)
        }
        mcp = {m: v for m, v in agent.mcp.items() if not _off(excluded["mcp"], m, agent.kit)}
        return ResolvedAgent(agent, skills, mcp)

    def _all_mcp(self) -> set[str]:
        return {m for a in [*self.agents.values(), self.lead] for m in a.mcp}


def search_path(repo: str | Path | None) -> list[tuple[str, Path]]:
    """Where kits are looked up, in order: (where, folder)."""
    places = [("project", Path(repo) / ".lado" / "kits")] if repo else []
    return [*places, ("user", installed()), ("built-in", BUILTIN)]


def installed() -> Path:
    """LADO_HOME/kits: the kits installed for the user, folders or links (lado kits add)."""
    return state.home() / "kits"


def candidates(repo: str | Path | None) -> list[Found]:
    """Every kit on the search path, in lookup order; a name may come more than once."""
    return [found for where, base in search_path(repo) for found in _in_folder(base, where)]


def find(name: str, repo: str | Path | None) -> Found:
    for found in candidates(repo):
        if found.name == name:
            return found
    looked = ", ".join(str(base) for _, base in search_path(repo))
    hint = migration_hint()
    raise KitError("\n".join(filter(None, [f'kit "{name}" not found; looked in {looked}', hint])))


def available(repo: str | Path | None) -> list[tuple[Found, str | None]]:
    """All kits on the search path, each with where the kit that shadows it is (or None)."""
    winners: dict[str, Found] = {}
    listed = []
    for found in candidates(repo):
        winner = winners.setdefault(found.name, found)
        listed.append((found, None if winner is found else winner.where))
    return listed


@dataclass(frozen=True)
class Install:
    """What `lado kits add` or `update` would do (plan_add, plan_update); install does it.
    A plan has the kit in the git cache, loaded and fetched, but changes no link."""

    name: str
    address: str  # the git address, or the folder
    tag: str | None  # the version tag; None for a folder
    commit: str | None  # the commit the kit's clone is at; None for a folder
    source: str  # "official", "marketplace <name>", "git" or "folder"
    kit: Kit
    installed: str | None = None  # an update's: the tag or commit installed now
    needs_confirmation: bool = False  # an add not from the official marketplace or a folder
    new_mcp: tuple[str, ...] = ()  # an update's: MCP servers the installed version did not have
    warnings: tuple[str, ...] = ()  # a moved tag

    @property
    def mcp(self) -> dict[str, McpDef]:
        """The MCP servers the kit's agents start, by name."""
        return {name: mcp for a in self.kit.agents.values() for name, mcp in a.mcp.items()}


@dataclass(frozen=True)
class Outdated:
    """An installed kit against the versions its repository has now (outdated)."""

    name: str
    installed: str  # its tag or commit; '' when not from git
    latest: str | None = None  # the highest release
    pre: str | None = None  # a pre-release higher than the latest release
    note: str = ""  # why it was not checked; '' when it was
    warnings: tuple[str, ...] = ()  # a moved tag


def plan_add(spec: str, market: str | None = None, pre: bool = False) -> Install:
    """What adding a kit would do: a git address (`<address>[@vX.Y.Z]`), a folder, or with
    `market` a kit's name (`<kit>[@vX.Y.Z]`) in that marketplace. Without a tag it takes
    the latest release, with `pre` the latest version of all. Changes no link."""
    if market:
        name, _, ref = spec.partition("@")
        address = marketplaces.resolve(market, name)
        source = OFFICIAL if market == marketplaces.OFFICIAL else f"marketplace {market}"
        again = f"lado kits add {name}@{{tag}} -m {market}"
        plan = _plan_git(address, ref or None, pre, source, again, None)
        if plan.name != name:
            raise KitError(
                f'marketplace "{market}" lists "{name}" at {address}, but its kit is "{plan.name}"'
            )
    else:
        location, ref = gitcache.split_ref(spec)
        if gitcache.is_git(location):
            plan = _plan_git(location, ref, pre, "git", f"lado kits add {location}@{{tag}}", None)
        else:
            plan = _plan_folder(spec)
    link = installed() / plan.name
    if link.exists() or link.is_symlink():
        raise KitError(
            f'kit "{plan.name}" is installed already: {link}; `lado kits update {plan.name}` '
            f"or `lado kits remove {plan.name}` first"
        )
    return plan


def plan_update(name: str, tag: str | None = None, pre: bool = False) -> Install:
    """What moving kit `name`, installed from git, to `tag` (or its latest version) would
    do. Its address is its clone's; changes no link."""
    clone, address = _installed_clone(name)
    current = gitcache.ref(clone)
    old = _kit_or_none(installed() / name)
    plan = _plan_git(
        address,
        tag,
        pre,
        _source(address),
        f"lado kits update {name} {{tag}}",
        (current, clone),
    )
    if plan.name != name:
        raise KitError(f'{address}@{plan.tag}: the kit is named "{plan.name}", not "{name}"')
    before = set(_mcp_names(old)) if old else set()
    return dataclasses.replace(
        plan,
        installed=current,
        needs_confirmation=False,  # the human's decision: an update warns, never asks
        new_mcp=tuple(sorted(set(plan.mcp) - before)),
    )


def install(plan: Install) -> Kit:
    """Make the link LADO_HOME/kits/<name> lead to the plan's kit: a new one for an add,
    replaced in one step for an update (the old version stays in the cache)."""
    link = installed() / plan.name
    link.parent.mkdir(parents=True, exist_ok=True)
    if plan.installed is None:
        if link.exists() or link.is_symlink():
            raise KitError(f'kit "{plan.name}" is installed already: {link}')
        link.symlink_to(plan.kit.path, target_is_directory=True)
    else:
        temp = link.with_name(f".{plan.name}.new")
        temp.unlink(missing_ok=True)
        temp.symlink_to(plan.kit.path, target_is_directory=True)
        os.replace(temp, link)
    return dataclasses.replace(plan.kit, where="user")


def outdated() -> list[Outdated]:
    """Each kit in LADO_HOME/kits against the version tags of its repository now (the
    network, once per kit from git); the others say why they are not checked."""
    rows = []
    base = installed()
    entries = sorted(base.iterdir()) if base.is_dir() else []
    for link in entries:
        if link.name.startswith("."):
            continue
        name = link.name
        target = link.resolve()
        clone = gitcache.clone_root(target) if link.is_symlink() else None
        if link.is_symlink() and not link.exists():
            rows.append(Outdated(name, "", note=f"broken link; run `lado kits remove {name}`"))
        elif clone is None:
            rows.append(Outdated(name, "", note="local, not checked"))
        elif clone != target:
            rows.append(Outdated(name, gitcache.ref(clone), note=_multi_kit(name)))
        elif not gitcache.VERSION_TAG.fullmatch(current := gitcache.ref(clone)):
            rows.append(
                Outdated(
                    name,
                    current,
                    note=f"pinned to commit {current}; `lado kits update {name}` moves it to "
                    "a version tag",
                )
            )
        else:
            try:
                address = gitcache.address(clone)
                tags = gitcache.remote_tags(address)
            except gitcache.GitError as exc:
                rows.append(Outdated(name, current, note=f"cannot check: {exc}"))
                continue
            latest = gitcache.latest(tags)
            newest = gitcache.latest(tags, pre=True)
            rows.append(
                Outdated(
                    name,
                    current,
                    latest=latest,
                    pre=newest if newest != latest else None,
                    warnings=tuple(_moved(address, current, clone, tags)),
                )
            )
    return rows


OFFICIAL = "official"  # Install.source of a kit from the official marketplace


def _plan_git(
    address: str,
    ref: str | None,
    pre: bool,
    source: str,
    again: str,
    current: tuple[str, Path] | None,
) -> Install:
    """The plan for the kit at `address`: `ref` or the latest version tag (one look at the
    remote's tags), its clone in the cache, loaded, checked and fetched. `again` is the
    command that takes another tag ({tag}); `current` an update's installed ref and clone."""
    try:
        tags = gitcache.remote_tags(address)
    except gitcache.GitError as exc:
        raise KitError(str(exc)) from None
    tag = _pick(address, tags, ref, pre)
    cached = gitcache.clone_dir(address, tag).is_dir()
    clone = _cache(address, tag)
    warnings = []
    if current and gitcache.VERSION_TAG.fullmatch(current[0]):
        warnings += _moved(address, current[0], current[1], tags)
    if cached and not (current and current[0] == tag):
        warnings += _moved(address, tag, clone, tags)
    _check_root(clone, f"{address}@{tag}")
    need = _lado_needed(clone)
    if need:
        older = [t for t in gitcache.sorted_versions(tags) if pre or "-" not in t]
        older = older[: older.index(tag)] if tag in older else []
        hint = f", or add an older version: {again.format(tag=older[-1])}" if older else ""
        version = _yaml_file(clone / KIT_FILE, []).get("version")
        raise KitError(
            f"{_kit_name(clone)} {version} needs LADO {need}, this is {__version__}; "
            f"upgrade LADO{hint}"
        )
    kit = fetch(load(clone, "user", named_folder=False))
    if kit.version != tag[1:]:
        raise KitError(
            f"{address}@{tag}: kit.yaml says version {kit.version}; the tag and kit.yaml must agree"
        )
    return Install(
        name=kit.name,
        address=address,
        tag=tag,
        commit=_commit(clone),
        source=source,
        kit=kit,
        needs_confirmation=source != OFFICIAL,
        warnings=tuple(warnings),
    )


def _plan_folder(spec: str) -> Install:
    location, ref = gitcache.split_ref(spec)
    root = Path(spec).expanduser().resolve()  # a folder's name may have an @
    if ref and not root.is_dir():
        raise KitError(f"{location}: a local folder has no version; drop @{ref}")
    if not root.is_dir():
        if not re.search(r"[/\\~]", location) and not location.startswith("."):
            raise KitError(
                f'"{location}" is neither a git address nor a folder; for a kit of a '
                "marketplace add -m <marketplace> (lado marketplaces lists them)"
            )
        raise KitError(f"{location} is not a folder")
    _check_root(root, location)
    kit = fetch(load(root, "user", named_folder=False))
    return Install(kit.name, str(root), None, None, "folder", kit)


def _pick(address: str, tags: dict[str, str], ref: str | None, pre: bool) -> str:
    """The version tag to take: `ref`, which must be one, or the latest."""
    versions = gitcache.sorted_versions(tags)
    if ref:
        if not gitcache.VERSION_TAG.fullmatch(ref):
            raise KitError(
                f"{address}@{ref}: a kit is pinned by its version tag vX.Y.Z; to try an "
                "unreleased kit, tag a pre-release (vX.Y.Z-rc.1) or add its folder"
            )
        if ref not in tags:
            listed = ", ".join(versions) or "none"
            raise KitError(f"{address} has no tag {ref}; its versions: {listed}")
        return ref
    tag = gitcache.latest(tags, pre)
    if tag:
        return tag
    if versions:
        raise KitError(
            f"{address} has pre-releases only ({', '.join(versions)}): add --pre or @<tag>"
        )
    raise KitError(f"{address} has no version tags vX.Y.Z")


def _moved(address: str, tag: str, clone: Path, tags: dict[str, str]) -> list[str]:
    """A warning when the remote's `tag` points to another commit than `clone` is at."""
    remote = tags.get(tag)
    try:
        local = gitcache.commit(clone)
    except gitcache.GitError:
        return []  # a damaged clone is reported where it is read
    if remote is None or remote == local:
        return []
    return [
        f"tag {tag} of {address} now points to {remote}, installed {local}; the kit was "
        "changed under the same version"
    ]


def _installed_clone(name: str) -> tuple[Path, str]:
    """The clone in the git cache that the link of kit `name` leads to, and its address."""
    link = _installed_entry(name)
    if not link.is_symlink():
        raise KitError(f"{link}: {name} is a folder LADO did not install; nothing to update")
    target = link.resolve()
    clone = gitcache.clone_root(target)
    if clone is None:
        raise KitError(
            f"{name} links to the folder {target}: it is read in place, nothing to update"
        )
    if clone != target:
        raise KitError(f"{name}: {_multi_kit(name)}")
    try:
        return clone, gitcache.address(clone)
    except gitcache.GitError as exc:
        raise KitError(f"cannot read the clone {clone}: {exc}") from None


def multi_kit(name: str) -> str | None:
    """Why kit `name` in LADO_HOME/kits cannot be updated when it was installed from a
    repository's kits/<name>/ (older LADOs did that), else None."""
    link = installed() / name
    target = link.resolve()
    clone = gitcache.clone_root(target) if link.is_symlink() else None
    if clone is None or clone == target:
        return None
    return _multi_kit(name)


def _multi_kit(name: str) -> str:
    return (
        "installed from a multi-kit repository, no longer supported; "
        f"`lado kits remove {name}` and add it again"
    )


def _source(address: str) -> str:
    market = marketplaces.source_of(address)
    if market is None:
        return "git"
    return OFFICIAL if market == marketplaces.OFFICIAL else f"marketplace {market}"


def _kit_or_none(path: Path) -> Kit | None:
    try:
        return load(path, "user")
    except KitError:
        return None  # an older version LADO cannot read: each MCP server counts as new


def _mcp_names(kit: Kit) -> list[str]:
    return [name for agent in kit.agents.values() for name in agent.mcp]


def _commit(clone: Path) -> str:
    try:
        return gitcache.commit(clone)
    except gitcache.GitError as exc:
        raise KitError(f"cannot read the clone {clone}: {exc}") from None


def _lado_needed(path: Path) -> str | None:
    """`X.Y[.Z]` when the kit at `path` needs a newer LADO than this one, else None."""
    meta = _yaml_file(path / KIT_FILE, [])
    deps = meta.get("dependencies") if isinstance(meta, dict) else None
    need = deps.get("lado") if isinstance(deps, dict) else None
    match = LADO_NEEDS.fullmatch(need.strip()) if isinstance(need, str) else None
    if match and _too_old(match):
        return need.strip().removeprefix(">=").strip()
    return None


def _too_old(need: re.Match) -> bool:
    return _version(__version__) < tuple(int(n or 0) for n in need.groups())


def remove(name: str) -> Path:
    """Remove the link of kit `name` from LADO_HOME/kits; returns where it led. The folder
    it led to stays."""
    link = _installed_entry(name)
    if not link.is_symlink():
        raise KitError(f"{link}: not installed by LADO; delete {link} yourself")
    target = Path(os.readlink(link))
    link.unlink()
    return target


def _installed_entry(name: str) -> Path:
    link = installed() / name
    if not link.exists() and not link.is_symlink():
        raise KitError(f'no kit "{name}" in {installed()}')
    return link


def _cache(address: str, ref: str) -> Path:
    try:
        return gitcache.fetch_pinned(address, ref)
    except gitcache.GitError as exc:
        raise KitError(str(exc)) from None


def _check_root(root: Path, spec: str) -> None:
    """A kit to install has kit.yaml at the root of its repository or folder."""
    if (root / KIT_FILE).is_file():
        return
    if _in_folder_paths(root / "kits"):
        raise KitError(
            f"{spec}: kits in kits/<name>/ are no longer supported: a kit is one repository "
            "with kit.yaml at its root"
        )
    if _skill_dirs(root / "skills") or _skill_dirs(root):
        raise KitError(
            f"{spec} is a skill pack, not a kit: list it under dependencies.skills of a kit; "
            "a kit without agents shares its packs with the whole session"
        )
    raise KitError(f"no kit in {spec}: a kit has kit.yaml at its root")


def cached_origin(path: Path) -> str | None:
    """`<address>@<ref>` of the git cache's clone `path` is in, or None when it is not in
    the cache."""
    clone = gitcache.clone_root(path)
    if clone is None or not clone.is_dir():
        return None
    try:
        return f"{gitcache.address(clone)}@{gitcache.ref(clone)}"
    except gitcache.GitError:
        return None


def migration_hint() -> str | None:
    """What to do with LADO_HOME/sources.yaml of an older LADO, while it is there."""
    registry = state.home() / "sources.yaml"
    if not registry.exists():
        return None
    lines = [f"{registry} is no longer read: kits are installed with `lado kits add`."]
    try:
        entries = (yaml.safe_load(registry.read_text()) or {}).get("sources") or []
    except (yaml.YAMLError, AttributeError, OSError):
        entries = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or not isinstance(entry.get("location"), str):
            continue
        name, location, ref = entry.get("name"), entry["location"], entry.get("ref")
        git = entry.get("kind") == "git"
        folder = state.home() / "sources" / str(name) if git else Path(location)
        spec = f"{location}@{ref or '<tag or commit>'}" if git else location
        folders = entry.get("skills") or []
        value = f"{{from: {spec}, folders: [{', '.join(folders)}]}}" if folders else spec
        pack = f"list it under dependencies.skills of a kit ({name}: {value})"
        # What is not on disk is not guessed at.
        if not folder.is_dir() and not git:
            lines.append(f"  {name}: {location} is gone; nothing to move")
        elif not folder.is_dir():
            lines.append(
                f"  {name}: no clone in {folder}; with kits: lado kits add {spec}; "
                f"a skill pack: {pack}"
            )
        elif (folder / KIT_FILE).is_file() or (folder / "kits").is_dir():
            lines.append(f"  lado kits add {spec}")
        else:
            lines.append(f"  {name} is a skill pack: {pack}")
    lines.append(f"then delete {registry} and {state.home() / 'sources'}")
    return "\n".join(lines)


def _in_folder(base: Path, where: str) -> list[Found]:
    """The kits in a kits folder; a link whose folder is gone is there too (load says so)."""
    broken = (
        [p for p in base.iterdir() if p.is_symlink() and not p.exists()] if base.is_dir() else []
    )
    paths = sorted([*_in_folder_paths(base), *broken])
    return [Found(p.name, where, p) for p in paths]


def _in_folder_paths(base: Path) -> list[Path]:
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if (p / KIT_FILE).is_file())


def _kit_name(path: Path) -> str:
    """The name in a kit's kit.yaml, or its folder's name when it has none (load says why)."""
    meta = _yaml_file(path / KIT_FILE, [])
    name = meta.get("name") if isinstance(meta, dict) else None
    return name if isinstance(name, str) else path.name


def _stray_kit_file(root: Path) -> Path | None:
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        if KIT_FILE in files:
            return Path(folder, KIT_FILE)
    return None


def _skill_dirs(base: Path) -> list[Path]:
    """SKILL.md folders anywhere under `base`; a skill folder is not searched further."""
    found = []
    for folder, dirs, files in os.walk(base):
        if "SKILL.md" in files:
            found.append(Path(folder))
            dirs[:] = []
        else:
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
    return sorted(found)


def load(path: str | Path, where: str = "path", named_folder: bool = True) -> Kit:
    """Read and validate the kit in `path`. Raises KitError listing every problem found.
    Packs not in the git cache yet are left unfetched (fetch gets them); load never uses
    the network. `named_folder`: the kit is in a kits folder, where the name of its entry
    (a folder, or a link in LADO_HOME/kits) must be the kit's name."""
    entry = Path(path).absolute().name
    path = Path(path).resolve()
    errors: list[str] = []
    meta = _yaml_file(path / KIT_FILE, errors)
    if not isinstance(meta, dict):
        if not errors:
            errors.append(f"{path / KIT_FILE}: expected a mapping")
        raise KitError("\n".join(errors))
    _unknown_keys(meta, KIT_KEYS | {"include"}, path / KIT_FILE, errors)  # include: below
    name = meta.get("name")
    if not isinstance(name, str) or not NAME.fullmatch(name):
        errors.append(f"{path / KIT_FILE}: name must be lowercase letters, digits, - or _")
    elif named_folder and name != entry:
        errors.append(f'{path / KIT_FILE}: name "{name}" differs from the folder "{entry}"')
    version = meta.get("version")
    if version is None:
        errors.append(f"{path / KIT_FILE}: version is missing; add `version: X.Y.Z`")
    elif not SEMVER.fullmatch(str(version)):
        errors.append(f"{path / KIT_FILE}: version must be X.Y.Z or X.Y.Z-<prerelease>")
    if "include" in meta:
        errors.append(
            f"{path / KIT_FILE}: include is gone: a kit takes skill packs from "
            "dependencies.skills (<name>: <git-url>@<version>); a kit no longer includes "
            "another kit"
        )
    kit_name = name if isinstance(name, str) else path.name
    supervisor = meta.get("supervisor")
    if supervisor is not None and not isinstance(supervisor, str):
        errors.append(f"{path / KIT_FILE}: supervisor must be an agent name")
        supervisor = None
    skills = _load_skills(path, kit_name, errors)
    packs = _load_dependencies(meta.get("dependencies", {}), path, kit_name, errors)
    _check_unique(skills, packs, path / KIT_FILE, errors)
    agents = _load_agents(path, kit_name, errors)
    if supervisor is not None and supervisor not in agents:
        errors.append(
            f'{path / KIT_FILE}: supervisor "{supervisor}" is not an agent of kit "{kit_name}"'
        )
    if LEAD in agents and supervisor != LEAD:
        errors.append(
            f'{agents[LEAD].path}: agent name "{LEAD}" is reserved for the session\'s lead; '
            f"rename it, or make it the kit's lead with `supervisor: {LEAD}` in {KIT_FILE}"
        )
    kit_flows = _load_flows(path, kit_name, supervisor, errors)
    if errors:
        raise KitError("\n".join(errors))
    return Kit(
        name=kit_name,
        path=path,
        where=where,
        version=str(version),
        description=str(meta.get("description", "")),
        supervisor=supervisor,
        agents=agents,
        skills=skills,
        flows=kit_flows,
        packs=packs,
    )


def fetch(kit: Kit) -> Kit:
    """`kit` with every pack of its dependencies in the cache: the git packs not fetched yet
    are cloned (gitcache), then checked as load checks a pack that is there."""
    if not kit.unfetched():
        return kit
    errors: list[str] = []
    packs = dict(kit.packs)
    for name in kit.unfetched():
        where = f"{kit.path / KIT_FILE}: dependencies.skills.{name}"
        try:
            clone = gitcache.fetch_pinned(packs[name].address, packs[name].ref or "")
        except gitcache.GitError as exc:
            errors.append(f"{where}: {exc}")
            continue
        packs[name] = _fill_pack(packs[name], clone.resolve(), kit.name, where, errors)
    _check_unique(kit.skills, packs, kit.path / KIT_FILE, errors)
    if errors:
        raise KitError("\n".join(errors))
    return dataclasses.replace(kit, packs=packs)


def _load_dependencies(value: object, path: Path, kit_name: str, errors: list[str]) -> dict:
    file = path / KIT_FILE
    if not isinstance(value, dict):
        errors.append(f"{file}: dependencies must be a mapping")
        return {}
    _unknown_keys(value, DEPENDENCY_KEYS, f"{file}: dependencies", errors)
    need = value.get("lado")
    if need is not None:
        match = LADO_NEEDS.fullmatch(need.strip()) if isinstance(need, str) else None
        if not match:
            errors.append(f'{file}: dependencies.lado must be ">=X.Y" or ">=X.Y.Z"')
        elif _too_old(match):
            errors.append(
                f'{file}: kit "{kit_name}" needs LADO {need.strip()}, this is {__version__}; '
                "upgrade LADO"
            )
    entries = value.get("skills", {})
    if not isinstance(entries, dict):
        errors.append(
            f"{file}: dependencies.skills must map pack names to <address>@<ref> "
            "or {from, folders}"
        )
        return {}
    packs = {}
    for name, spec in entries.items():
        pack = _load_pack_entry(name, spec, path, kit_name, errors)
        if pack:
            packs[name] = pack
    return packs


def _load_pack_entry(
    name: object, spec: object, path: Path, kit_name: str, errors: list[str]
) -> Pack | None:
    """One entry of dependencies.skills; its skills when it is a local folder or in the cache."""
    file = path / KIT_FILE
    if not isinstance(name, str) or not NAME.fullmatch(name):
        errors.append(
            f'{file}: dependencies.skills: "{name}" is not a valid pack name '
            "(lowercase letters, digits, - or _)"
        )
        return None
    where = f"{file}: dependencies.skills.{name}"
    count = len(errors)
    folders: list[str] = []
    if isinstance(spec, dict):
        _unknown_keys(spec, PACK_KEYS, where, errors)
        folders = spec.get("folders", [])
        if not _str_list(folders):
            errors.append(f"{where}: folders must be a list of folders inside the pack")
            folders = []
        for folder in folders:
            if Path(folder).is_absolute() or ".." in Path(folder).parts or not Path(folder).parts:
                errors.append(f'{where}: "{folder}": folders are relative paths inside the pack')
        if "from" not in spec:
            errors.append(f"{where}: from is missing")
        spec = spec.get("from")
    if not isinstance(spec, str):
        if len(errors) == count:
            errors.append(f"{where}: expected <address>@<ref> or {{from, folders}}")
        return None
    if len(errors) > count:
        return None
    location, ref = gitcache.split_ref(spec)
    pack = Pack(name, location, ref, tuple(Path(f).as_posix() for f in folders), None, None)
    if gitcache.is_git(location):
        if not ref:
            errors.append(f"{where}: pin a version: {location}@<tag or commit>")
            return None
        clone = gitcache.clone_dir(location, ref)
        return (
            _fill_pack(pack, clone.resolve(), kit_name, where, errors) if clone.is_dir() else pack
        )
    if ref:
        errors.append(f"{where}: a local pack has no version; drop @{ref}")
        return None
    if Path(location).is_absolute() or location.startswith("~"):
        errors.append(f"{where}: a local pack is a path relative to the kit folder: {location}")
        return None
    folder = (path / location).resolve()
    clone = gitcache.clone_root(path)
    if clone and not _inside(folder, clone):
        errors.append(
            f"{where}: local pack outside the kit's repository works only on this machine; "
            "use <git-url>@<ref>"
        )
        return None
    if not folder.is_dir():
        errors.append(f"{where}: {folder} does not exist")
        return None
    return _fill_pack(pack, folder, kit_name, where, errors)


def _fill_pack(pack: Pack, folder: Path, kit_name: str, where: str, errors: list[str]) -> Pack:
    """`pack` read from `folder`: its skills."""
    stray = _stray_kit_file(folder)
    if stray:
        errors.append(f"{where}: {pack.spec} is a kit, not a skill pack ({stray})")
        return pack
    skills: dict[str, Skill] = {}
    for sub in pack.folders or ("skills",):
        if pack.folders and not (folder / sub).is_dir():
            errors.append(f"{where}: folder {folder / sub} does not exist")
            continue
        for skill_dir in _skill_dirs(folder / sub):
            skill = _load_skill(skill_dir, kit_name, errors, pack.name)
            if skill:
                _add_skill(skills, skill, where, errors)
    return dataclasses.replace(pack, path=folder, skills=skills)


def _check_unique(own: dict[str, Skill], packs: dict[str, Pack], file: Path, errors: list[str]):
    """One name is one skill folder in a kit: its own skills and its packs' together."""
    skills = dict(own)
    for pack in packs.values():
        for skill in (pack.skills or {}).values():
            _add_skill(skills, skill, str(file), errors)


def _add_skill(skills: dict[str, Skill], skill: Skill, where: str, errors: list[str]) -> None:
    other = skills.setdefault(skill.name, skill)
    if other.path != skill.path:
        errors.append(
            f'{where}: skill "{skill.name}" is in {other.path} and in {skill.path}; '
            "choose them with folders in dependencies.skills"
        )


def _inside(path: Path, folder: Path) -> bool:
    try:
        path.relative_to(folder)
    except ValueError:
        return False
    return True


def _version(text: str) -> tuple[int, ...]:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", text)
    return tuple(int(n) for n in match.groups()) if match else (0, 0, 0)


def resolve(
    repo: str | Path | None, kits: Iterable[str | Kit], without: Iterable[str] = ()
) -> Environment:
    """Combine kits into one environment. A kit is a name, looked up, loaded and fetched
    here, or a loaded kit, fetched already (fetch). In this order:

    1. the `without` items of one kit ("agent:x@k", "skill:y@k", "mcp:z@k", "flow:f@k")
       switch it off in that kit; "agent:x" of a kit's supervisor x is "agent:x@" its kit;
    2. the lead: the supervisor of the one kit that has one, else LADO's built-in supervisor;
    3. the kits' supervisors are no roles: one leads, the others are not in the session;
    4. the roles, flows and skills of the kits are combined: a name twice is an error;
    5. the other `without` items ("agent:x", ...) switch it off in the whole session."""
    taken: dict[Path, Kit] = {}
    for item in kits:
        kit = item if isinstance(item, Kit) else fetch(find(item, repo).load())
        if kit.unfetched():
            raise KitError(f'kit "{kit.name}": pack not fetched yet: {", ".join(kit.unfetched())}')
        taken.setdefault(kit.path, kit)
    env_kits = list(taken.values())
    without = list(without)
    excluded = parse_without(without)
    _supervisors_by_kit(excluded, env_kits)
    plain = _check_at_kit(excluded, {k.name: k for k in env_kits})
    trimmed = [_trim(kit, excluded) for kit in env_kits]

    supervisors = {k.name: k.supervisor for k in trimmed if k.supervisor}
    leading = [k for k in trimmed if k.supervisor]
    roles = [(k, {n: a for n, a in k.agents.items() if n != k.supervisor}) for k in trimmed]
    kit_supervisors: dict[str, AgentDef] = {}
    if len(leading) == 1:
        lead = leading[0].agents[leading[0].supervisor]
        # No role may take the lead's name.
        agents = _merge([(leading[0], {lead.name: lead}), *roles], "agent")
        del agents[lead.name]
    else:
        builtin = load(BUILTIN / DEFAULT_KIT, "built-in")
        lead = builtin.agents[builtin.supervisor]
        agents = _merge(roles, "agent")
        # The built-in default kit's supervisor is the lead itself.
        kit_supervisors = {
            k.name: k.agents[k.supervisor]
            for k in leading
            if k.agents[k.supervisor].path != lead.path
        }
    skills = _merge([(k, k.skills) for k in trimmed], "skill")
    # A kit without agents (by what it holds, before --without) shares its packs.
    had_agents = {k.name for k in env_kits if k.agents}
    owner = {name: kit for kit in trimmed for name in kit.skills}
    for kit in trimmed:
        for skill in [] if kit.name in had_agents else _pack_skills(kit).values():
            other = skills.setdefault(skill.name, skill)
            if other.path != skill.path:
                first = owner[skill.name].name
                raise _twice(
                    "skill", skill.name, (first, str(other.path)), (kit.name, str(skill.path))
                )
            owner.setdefault(skill.name, kit)
    private = {kit.name: _pack_skills(kit) for kit in trimmed if kit.name in had_agents}
    for kit_name, own in private.items():
        for skill in own.values():
            other = skills.get(skill.name)
            if other and other.path != skill.path:
                raise KitError(
                    f'skill "{skill.name}" comes from two folders for the agents of kit '
                    f'"{kit_name}": {other.path} and {skill.path}'
                )
    env_flows = _merge([(k, k.flows) for k in trimmed], "flow")

    mcp = {m for a in [*agents.values(), lead, *kit_supervisors.values()] for m in a.mcp}
    every_skill = {**{s: v for own in private.values() for s, v in own.items()}, **skills}
    _check_known(plain, every_skill, mcp, set(agents), set(env_flows))
    agents = {n: a for n, a in agents.items() if n not in plain["agent"]}
    skills = {n: s for n, s in skills.items() if n not in plain["skill"]}
    private = {
        k: {n: s for n, s in own.items() if n not in plain["skill"]} for k, own in private.items()
    }
    env_flows = {n: f for n, f in env_flows.items() if n not in plain["flow"]}
    # A skill an agent names that is switched off, in the session or in the kit it came
    # from, is no error.
    off_skills = {name for name, _ in excluded["skill"]}
    # A kit supervisor that does not lead is checked as if it led: its lead skill names them.
    for agent in [*agents.values(), lead, *kit_supervisors.values()]:
        visible = {**skills, **private.get(agent.kit, {})}
        for skill in agent.skills or []:
            if skill not in visible and skill not in off_skills:
                raise KitError(
                    f'{agent.path}: skill "{skill}" is not visible to agent "{agent.name}" '
                    f'(kit "{agent.kit}"): not a skill of the session\'s kits or of kit '
                    f'"{agent.kit}"\'s dependencies'
                )
    lead_visible = {**skills, **private.get(lead.kit, {})}
    for kit_name, agent in kit_supervisors.items():
        name = lead_skill_name(kit_name)
        if name in lead_visible:
            other = lead_visible[name]
            options = [f"skill:{name}", f"agent:{agent.name}@{kit_name}"]
            raise KitError(
                f'skill "{name}" of kit {other.kit} ({other.path}) has the name of the lead '
                f"skill of kit {kit_name}'s supervisor ({agent.path}), which LADO's built-in "
                f"supervisor gets; switch one off: --without {options[0]} or "
                f"--without {options[1]}",
                options,
            )
    if plain["mcp"]:
        agents = {n: _without_mcp(a, plain["mcp"]) for n, a in agents.items()}
        lead = _without_mcp(lead, plain["mcp"])
        kit_supervisors = {k: _without_mcp(a, plain["mcp"]) for k, a in kit_supervisors.items()}
    return Environment(
        env_kits, agents, skills, lead, supervisors, without, env_flows, private, kit_supervisors
    )


def _supervisors_by_kit(
    excluded: dict[str, set[tuple[str, str | None]]], session_kits: list[Kit]
) -> None:
    """Read agent:<name> that names a kit's supervisor as agent:<name>@<that kit>, as
    sessions of older LADOs stored it; a kit supervisor is no role to switch off after the
    kits combine. Several kits' supervisors of that name: an error with each way out."""
    for name, kit_name in sorted(excluded["agent"], key=lambda i: (i[1] or "", i[0])):
        owners = [k.name for k in session_kits if k.supervisor == name]
        if kit_name is not None or not owners:
            continue
        if len(owners) > 1:
            options = [f"agent:{name}@{k}" for k in owners]
            raise KitError(
                f"cannot switch off agent:{name}: it is the supervisor of kits {_and(owners)}; "
                f"use {' or '.join(f'--without {o}' for o in options)}",
                options,
            )
        excluded["agent"].add((name, owners[0]))
        # A role of that name in another kit is still switched off in the whole session.
        if not any(name in k.agents and k.supervisor != name for k in session_kits):
            excluded["agent"].discard((name, None))


def _trim(kit: Kit, excluded: dict[str, set[tuple[str, str | None]]]) -> Kit:
    """`kit` without the items switched off in it (kind:name@kit)."""

    def on(kind: str, name: str) -> bool:
        return (name, kit.name) not in excluded[kind]

    off_mcp = {name for name, k in excluded["mcp"] if k == kit.name}
    agents = {n: _without_mcp(a, off_mcp) for n, a in kit.agents.items() if on("agent", n)}
    packs = {
        n: dataclasses.replace(
            p, skills={s: v for s, v in (p.skills or {}).items() if on("skill", s)}
        )
        for n, p in kit.packs.items()
    }
    return dataclasses.replace(
        kit,
        supervisor=kit.supervisor if kit.supervisor in agents else None,
        agents=agents,
        skills={n: s for n, s in kit.skills.items() if on("skill", n)},
        flows={n: f for n, f in kit.flows.items() if on("flow", n)},
        packs=packs,
    )


def _without_mcp(agent: AgentDef, names: set[str]) -> AgentDef:
    if not names & set(agent.mcp):
        return agent
    return dataclasses.replace(agent, mcp={m: v for m, v in agent.mcp.items() if m not in names})


def _off(items: set[tuple[str, str | None]], name: str, kit: str) -> bool:
    """Whether `name` of `kit` is switched off by `items`: by name, or by name@kit."""
    return (name, None) in items or (name, kit) in items


def _pack_skills(kit: Kit) -> dict[str, Skill]:
    """The skills of a kit's packs (fetched)."""
    return {name: s for pack in kit.packs.values() for name, s in (pack.skills or {}).items()}


def parse_without(items: Iterable[str]) -> dict[str, set[tuple[str, str | None]]]:
    """kind -> {(name, kit)} of "kind:name" (kit None: the whole session) and
    "kind:name@kit" (that kit only)."""
    excluded: dict[str, set[tuple[str, str | None]]] = {kind: set() for kind in WITHOUT_KINDS}
    for item in items:
        kind, _, rest = item.partition(":")
        name, at, kit = rest.partition("@")
        if kind not in excluded or not name or (at and not kit):
            raise KitError(
                f'"{item}": expected agent:<name>, skill:<name>, mcp:<name> or flow:<name>, '
                "each optionally @<kit>"
            )
        excluded[kind].add((name, kit or None))
    return excluded


def _check_at_kit(
    excluded: dict[str, set[tuple[str, str | None]]], session_kits: dict[str, Kit]
) -> dict[str, set[str]]:
    """Check that each kind:name@kit item names a kit of the session and a thing it has;
    returns the items without @kit, kind -> names."""
    for kind, items in excluded.items():
        for name, kit_name in sorted(items, key=lambda i: (i[1] or "", i[0])):
            if kit_name is None:
                continue
            item = f"{kind}:{name}@{kit_name}"
            kit = session_kits.get(kit_name)
            if kit is None:
                raise KitError(
                    f"cannot switch off {item}: no kit {kit_name} in this session; "
                    f"kits: {', '.join(session_kits)}"
                )
            has = {
                "agent": list(kit.agents),
                "flow": list(kit.flows),
                "skill": [*kit.skills, *_pack_skills(kit)],
                "mcp": list(dict.fromkeys(m for a in kit.agents.values() for m in a.mcp)),
            }[kind]
            if name not in has:
                raise KitError(
                    f"cannot switch off {item}: kit {kit_name} has no {kind} {name}; "
                    f"it has: {', '.join(has) or 'none'}"
                )
    return {kind: {n for n, k in items if k is None} for kind, items in excluded.items()}


def _twice(what: str, name: str, first: tuple[str, str], second: tuple[str, str]) -> KitError:
    """The error for `name` in two kits, each given as (kit, where), with the two ways out."""
    options = [f"{what}:{name}@{first[0]}", f"{what}:{name}@{second[0]}"]
    return KitError(
        f'{what} "{name}" is defined by two kits: {first[0]} ({first[1]}) and '
        f"{second[0]} ({second[1]}); switch one off: --without {options[0]} or "
        f"--without {options[1]}",
        options,
    )


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def lint(kit: Kit) -> list[str]:
    """Problems a kit can run with but should not have: paths that only work on one
    machine (use ${KIT_DIR} or a relative path instead)."""
    problems = []
    for agent in kit.agents.values():
        raw = _frontmatter(agent.path.read_text(), agent.path, [])[1]
        problems += _hardcoded(raw, str(agent.path))
        for mcp in agent.mcp.values():
            where = f'{agent.path}: MCP server "{mcp.name}"'
            problems += _hardcoded(" ".join(mcp.command), f"{where} command")
            problems += _hardcoded(" ".join(mcp.env.values()), f"{where} env")
    for skill in kit.skills.values():
        skill_md = skill.path / "SKILL.md"
        problems += _hardcoded(skill_md.read_text(), str(skill_md))
    return problems


def warnings(kit: Kit) -> list[str]:
    """Doubts about a kit that do not stop it: a kit from the git cache whose version
    differs from the version tags on its clone's commit."""
    clone = gitcache.clone_root(kit.path)
    try:
        tags = gitcache.versions(clone) if clone and kit.version else []
    except gitcache.GitError as exc:
        return [f"{kit.name}: cannot read the version tags of {clone}: {exc}"]
    if tags and kit.version not in tags:
        return [
            f"{kit.name}: version {kit.version} in kit.yaml, but {cached_origin(kit.path)} "
            f"is at {', '.join('v' + t for t in tags)}"
        ]
    return []


def _hardcoded(text: str, where: str) -> list[str]:
    return [
        f'{where}: hardcoded path "{m.group(0)}"; use ${{KIT_DIR}} or a relative path'
        for m in HARDCODED_PATH.finditer(text)
    ]


def _merge(parts: list[tuple[Kit, dict]], what: str) -> dict:
    """The items of each (kit, items) in one namespace; a name twice is an error."""
    merged: dict = {}
    owner: dict[str, Kit] = {}
    for kit, items in parts:
        for name, item in items.items():
            if name in merged:
                first = owner[name]
                raise _twice(what, name, (first.name, first.source), (kit.name, kit.source))
            merged[name], owner[name] = item, kit
    return merged


def _check_known(
    excluded: dict[str, set[str]],
    skills: Iterable[str],
    mcp: set[str],
    agents: set[str],
    flow_names: set[str],
) -> None:
    known = {"agent": agents, "skill": set(skills), "mcp": mcp, "flow": flow_names}
    for kind, names in excluded.items():
        for name in sorted(names - known[kind]):
            have = ", ".join(sorted(known[kind])) or "none"
            raise KitError(f"cannot switch off {kind}:{name}: no such {kind}; there are: {have}")


def _load_skills(kit: Path, kit_name: str, errors: list[str]) -> dict[str, Skill]:
    skills = {}
    folder = kit / "skills"
    for path in sorted(folder.iterdir()) if folder.is_dir() else []:
        if not path.is_dir():
            errors.append(f"{path}: skills/ holds one folder per skill")
            continue
        skill = _load_skill(path, kit_name, errors)
        if skill:
            skills[skill.name] = skill
    return skills


def _load_skill(
    path: Path, kit_name: str, errors: list[str], pack: str | None = None
) -> Skill | None:
    skill_md = path / "SKILL.md"
    if not skill_md.is_file():
        errors.append(f"{path}: no SKILL.md")
        return None
    # SKILL.md is a standard format read by the agent CLIs: other keys are theirs.
    meta, _ = _frontmatter(skill_md.read_text(), skill_md, errors)
    if meta is None:
        return None
    name, description = meta.get("name"), meta.get("description")
    if name != path.name:
        errors.append(f'{skill_md}: name "{name}" differs from the folder "{path.name}"')
    elif not NAME.fullmatch(name):
        errors.append(f"{skill_md}: name must be lowercase letters, digits, - or _")
    elif not isinstance(description, str) or not description.strip():
        errors.append(f"{skill_md}: description is missing")
    else:
        return Skill(name, description, path, kit_name, pack)
    return None


def _load_agents(kit: Path, kit_name: str, errors: list[str]) -> dict[str, AgentDef]:
    agents = {}
    folder = kit / "agents"
    for path in sorted(folder.iterdir()) if folder.is_dir() else []:
        if path.suffix != ".md":
            errors.append(f"{path}: agents/ holds <name>.md files")
            continue
        agent = _load_agent(path, kit, kit_name, errors)
        if agent:
            agents[agent.name] = agent
    return agents


def _load_flows(
    kit: Path, kit_name: str, supervisor: str | None, errors: list[str]
) -> dict[str, Flow]:
    found = {}
    folder = kit / "flows"
    for path in sorted(folder.iterdir()) if folder.is_dir() else []:
        if path.suffix != ".yaml":
            errors.append(f"{path}: flows/ holds <name>.yaml files")
            continue
        count = len(errors)
        data = _yaml_file(path, errors)
        if len(errors) > count:
            continue
        data = _lead_steps(data, supervisor)
        flow = flows.parse(data, path.stem, kit_name, str(path), errors)
        if flow:
            found[flow.name] = flow
    return found


def _lead_steps(data: object, supervisor: str | None) -> object:
    """A flow's data with each state of the kit's supervisor given to the session's lead
    (LEAD), before it is parsed: the run's snapshot keeps the lead's name."""
    states = data.get("states") if isinstance(data, dict) else None
    if not supervisor or supervisor == LEAD or not isinstance(states, dict):
        return data
    return {
        **data,
        "states": {
            name: (
                {**raw, "agent": LEAD}
                if isinstance(raw, dict) and raw.get("agent") == supervisor
                else raw
            )
            for name, raw in states.items()
        },
    }


def _load_agent(path: Path, kit: Path, kit_name: str, errors: list[str]) -> AgentDef | None:
    count = len(errors)
    meta, body = _frontmatter(path.read_text(), path, errors)
    if meta is None:
        return None
    _unknown_keys(meta, AGENT_KEYS, path, errors)
    name = meta.get("name")
    if name != path.stem:
        errors.append(f'{path}: name "{name}" differs from the file name "{path.stem}"')
    description = meta.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append(f"{path}: description is missing")
    skills = meta.get("skills")
    if skills is not None and not _str_list(skills):
        errors.append(f"{path}: skills must be a list of skill names")
    mcp = _load_mcp(meta.get("mcp", {}), path, kit, errors)
    try:
        body = _substitute(body, {"KIT_DIR": str(kit)}, f"{path}", keep_unknown=True)
    except KitError as exc:
        errors.append(str(exc))
    if len(errors) > count:
        return None
    return AgentDef(name, description, skills, mcp, body.strip(), kit_name, path)


def _load_mcp(value: object, path: Path, kit: Path, errors: list[str]) -> dict[str, McpDef]:
    if not isinstance(value, dict):
        errors.append(f"{path}: mcp must map server names to {{command, env}}")
        return {}
    servers = {}
    for name, server in value.items():
        where = f'{path}: MCP server "{name}"'
        if name == "lado" or not isinstance(name, str) or not NAME.fullmatch(name):
            errors.append(f"{where}: invalid name (lowercase letters, digits, - or _; not lado)")
            continue
        if not isinstance(server, dict):
            errors.append(f"{where}: expected {{command, env}}")
            continue
        if set(server) - MCP_KEYS:
            keys = ", ".join(sorted(map(str, set(server) - MCP_KEYS)))
            errors.append(f"{where}: unknown keys {keys} (only stdio servers: command, env)")
            continue
        command, env = server.get("command"), server.get("env", {})
        if not _str_list(command) or not command:
            errors.append(f"{where}: command must be a non-empty list of strings")
            continue
        if not isinstance(env, dict) or not all(isinstance(v, str) for v in env.values()):
            errors.append(f"{where}: env must map names to strings")
            continue
        try:
            command = [_substitute(c, {"KIT_DIR": str(kit)}, f"{where} command") for c in command]
            env = {
                str(k): _substitute(v, {"KIT_DIR": str(kit)}, where, keep_unknown=True)
                for k, v in env.items()
            }
        except KitError as exc:
            errors.append(str(exc))
            continue
        servers[name] = McpDef(name, command, env, kit)
    return servers


def _substitute(text: str, values: dict[str, str], where: str, keep_unknown=False) -> str:
    """Replace ${NAME} with values[NAME]. Other variables stay (keep_unknown) or are errors.

    ${SKILL_DIR} is never set here: a skill is placed as a whole folder and the agent CLI
    tells the model where each skill lives.
    """

    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name in values:
            return values[name]
        if name == "SKILL_DIR":
            raise KitError(
                f"{where}: ${{SKILL_DIR}} is only meaningful inside a skill; "
                "the agent CLI tells the model each skill's folder"
            )
        if keep_unknown:
            return match.group(0)
        raise KitError(f"{where}: unknown variable ${{{name}}}; only ${{KIT_DIR}} is set here")

    return VARIABLE.sub(replace, text)


def _env_value(value: str, environ: Mapping[str, str], where: str) -> str:
    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in environ:
            raise KitError(f"{where}: environment variable {name} is not set")
        return environ[name]

    return VARIABLE.sub(replace, value)


def _frontmatter(text: str, path: Path, errors: list[str]) -> tuple[dict | None, str]:
    """Split "---\\n<yaml>\\n---\\n<body>" into the YAML mapping and the body."""
    match = re.match(r"---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)(.*)", text, re.S)
    if not match:
        errors.append(f"{path}: must start with YAML frontmatter between --- lines")
        return None, text
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        errors.append(f"{path}: invalid YAML frontmatter: {exc}")
        return None, match.group(2)
    if not isinstance(meta, dict):
        errors.append(f"{path}: frontmatter must be a mapping")
        return None, match.group(2)
    return meta, match.group(2)


def _yaml_file(path: Path, errors: list[str]) -> object:
    try:
        return yaml.safe_load(path.read_text())
    except OSError as exc:
        errors.append(f"{path}: {exc.strerror}")
    except yaml.YAMLError as exc:
        errors.append(f"{path}: invalid YAML: {exc}")
    return None


def _unknown_keys(meta: dict, allowed: set[str], path: Path | str, errors: list[str]) -> None:
    unknown = sorted(map(str, set(meta) - allowed))
    if unknown:
        errors.append(
            f"{path}: unknown keys {', '.join(unknown)}; allowed: {', '.join(sorted(allowed))}"
        )


def _str_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)
