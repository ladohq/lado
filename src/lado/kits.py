"""Kits: provider-neutral bundles of agent roles, skills and MCP servers.

A kit is a directory:

    kit.yaml            name, version, description, include (other kits), default_agent
    agents/<name>.md    YAML frontmatter + the role prompt
    skills/<name>/      a SKILL.md folder, always handled as a whole
    flows/<name>.yaml   a flow (lado.flows)

Agents, skills and flows are found in their folders; kit.yaml does not list them. Anything else in
the kit travels with it untouched. A kit is identified by the name and version in kit.yaml.

Kits are looked up by name in the project (<repo>/.lado/kits), then in LADO_HOME/kits, then
in the registered sources (lado.sources) in the order they were added, then among the kits
built into LADO; the first hit wins. A source holds kits in kits/<name>/, or one kit at its
root, or is a skill pack: no kit.yaml, only SKILL.md folders anywhere under skills/ (or under
the folders the source names). A skill pack is a kit named after the source, with skills and
no agents. Several kits, with what
they include, combine into one Environment.
"""

import dataclasses
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from lado import __version__, flows, gitcache, sources, state
from lado.flows import Flow
from lado.providers.base import McpServer

KIT_FILE = "kit.yaml"
DEFAULT_KIT = "default"
DEFAULT_ROLE = "worker"
BUILTIN = Path(__file__).with_name("builtin_kits")

KIT_KEYS = {"name", "version", "description", "dependencies", "default_agent"}
DEPENDENCY_KEYS = {"lado", "skills"}
PACK_KEYS = {"from", "folders"}
LADO_NEEDS = re.compile(r">=\s*(\d+)\.(\d+)(?:\.(\d+))?")
AGENT_KEYS = {"name", "description", "supervisor", "skills", "mcp"}
MCP_KEYS = {"command", "env"}
WITHOUT_KINDS = ("agent", "skill", "mcp", "flow")

NAME = sources.NAME
SEMVER = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?")
VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
# A path that only works on one machine: ~/..., or /dir/... at the start of a word.
HARDCODED_PATH = re.compile(r"(?:^|(?<=[\s\"'`(=:,\[]))(~/|/[A-Za-z0-9._-]+/)[^\s\"'`)]*", re.M)


class KitError(RuntimeError):
    pass


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
    supervisor: bool
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
    default_agent: str | None
    agents: dict[str, AgentDef]
    skills: dict[str, Skill]  # its own, in skills/
    origin: sources.Source | None = None  # the source the kit was found in
    pack: bool = False  # a skill pack: SKILL.md folders without a kit.yaml
    flows: dict[str, Flow] = field(default_factory=dict)
    packs: dict[str, Pack] = field(default_factory=dict)  # dependencies.skills

    @property
    def source(self) -> str:
        revision = self.origin.revision() if self.origin else None
        return f"{self.where}{f' @ {revision}' if revision else ''}: {self.path}"

    def unfetched(self) -> list[str]:
        """The packs not in the cache yet (fetch gets them)."""
        return [name for name, pack in self.packs.items() if pack.skills is None]


@dataclass(frozen=True)
class Found:
    """A kit on the search path, not loaded yet."""

    name: str
    where: str  # project, user, source <name> or built-in
    path: Path
    origin: sources.Source | None = None
    pack: bool = False
    named_folder: bool = True  # in a kits folder, where the folder name is the kit name

    def load(self) -> Kit:
        if self.pack:
            return _load_pack(self)
        return load(self.path, self.where, self.named_folder, self.origin)


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


@dataclass
class Environment:
    kits: list[Kit]  # every kit taken in, in the order given
    agents: dict[str, AgentDef]
    shared: dict[str, Skill]  # every agent's: the kits' own skills, packs of kits without agents
    default_agent: str | None
    without: list[str] = field(default_factory=list)
    flows: dict[str, Flow] = field(default_factory=dict)
    private: dict[str, dict[str, Skill]] = field(default_factory=dict)  # kit -> its packs' skills

    def visible(self, agent: AgentDef) -> dict[str, Skill]:
        """The skills `agent` may have: the shared ones and its own kit's packs'."""
        return {**self.shared, **self.private.get(agent.kit, {})}

    def all_skills(self) -> dict[str, Skill]:
        found = dict(self.shared)
        for skills in self.private.values():
            for name, skill in skills.items():
                found.setdefault(name, skill)
        return found

    def flow(self, name: str) -> Flow:
        """Flow `name`, once every role it names is an agent of this environment."""
        found = self.flows.get(name)
        if found is None:
            raise KitError(f'no flow "{name}"; flows: {", ".join(self.flows) or "none"}')
        roles = ", ".join(self.agents) or "none"
        errors = [
            f'{found.path}: state "{s.name}": no role "{s.agent}" in this session; roles: {roles}'
            for s in found.states.values()
            if s.kind == flows.WORK and s.agent not in self.agents
        ]
        if errors:
            raise KitError("\n".join(errors))
        return found

    def supervisor(self) -> AgentDef:
        found = [a for a in self.agents.values() if a.supervisor]
        if not found:
            raise KitError("no agent with `supervisor: true` in the kits")
        if len(found) > 1:
            names = ", ".join(f"{a.name} ({a.kit})" for a in found)
            raise KitError(
                f"more than one agent with `supervisor: true`: {names}; "
                "switch all but one off with --without agent:<name>"
            )
        return found[0]

    def roles(self) -> list[AgentDef]:
        """Agents a supervisor can start as workers."""
        return [a for a in self.agents.values() if not a.supervisor]

    def worker_role(self, role: str | None) -> AgentDef:
        name = role or self.default_agent or DEFAULT_ROLE
        agent = self.agents.get(name)
        if agent is None or agent.supervisor:
            roles = ", ".join(a.name for a in self.roles()) or "none"
            raise KitError(f'no worker role "{name}" in this session; roles: {roles}')
        return agent

    def resolve(self, name: str, without: Iterable[str] = ()) -> ResolvedAgent:
        """Agent `name` with its skills and MCP servers, minus `without` (skill: and mcp:
        items, on top of the session's)."""
        excluded = parse_without(without)
        if excluded["agent"] or excluded["flow"]:
            raise KitError(
                "an agent or flow cannot be switched off for one agent; use skill: or mcp:"
            )
        _check_known(excluded, self.all_skills(), self._all_mcp(), set(), set())
        agent = self.agents[name]
        visible = self.visible(agent)
        wanted = list(visible) if agent.skills is None else agent.skills
        skills = {s: visible[s] for s in wanted if s in visible and s not in excluded["skill"]}
        mcp = {m: v for m, v in agent.mcp.items() if m not in excluded["mcp"]}
        return ResolvedAgent(agent, skills, mcp)

    def _all_mcp(self) -> set[str]:
        return {m for a in self.agents.values() for m in a.mcp}


def search_path(repo: str | Path | None) -> list[tuple[str, Path, sources.Source | None]]:
    """Where kits are looked up, in order: (where, folder, the source if it is one)."""
    places = [("project", Path(repo) / ".lado" / "kits", None)] if repo else []
    places.append(("user", state.home() / "kits", None))
    places += [(f"source {s.name}", s.path(), s) for s in _registered()]
    return [*places, ("built-in", BUILTIN, None)]


def candidates(repo: str | Path | None) -> list[Found]:
    """Every kit on the search path, in lookup order; a name may come more than once."""
    found = []
    for where, base, origin in search_path(repo):
        found += in_source(origin) if origin else _in_folder(base, where)
    return found


def find(name: str, repo: str | Path | None) -> Found:
    for found in candidates(repo):
        if found.name == name:
            return found
    looked = ", ".join(str(base) for _, base, _ in search_path(repo))
    raise KitError(f'kit "{name}" not found; looked in {looked}')


def available(repo: str | Path | None) -> list[tuple[Found, str | None]]:
    """All kits on the search path, each with where the kit that shadows it is (or None)."""
    winners: dict[str, Found] = {}
    listed = []
    for found in candidates(repo):
        winner = winners.setdefault(found.name, found)
        listed.append((found, None if winner is found else winner.where))
    return listed


def in_source(origin: sources.Source) -> list[Found]:
    """The kits of a source: kits/<name>/, one kit at its root, or a skill pack."""
    root, where = origin.path(), f"source {origin.name}"
    if not root.is_dir():
        raise KitError(
            f'source "{origin.name}": {root} does not exist; '
            f"run `lado sources update {origin.name}` or `lado sources remove {origin.name}`"
        )
    found = []
    if (root / KIT_FILE).is_file():
        found.append(Found(_kit_name(root), where, root, origin, named_folder=False))
    elif (root / "kits").is_dir() and _skill_dirs(root / "skills"):
        raise KitError(f"{root / 'skills'}: skills of a source with kits belong in a kit")
    found += _in_folder(root / "kits", where, origin)
    if found and origin.skills:
        raise KitError(
            f'source "{origin.name}" has kits; skills folders ({", ".join(origin.skills)}) '
            "only choose the skills of a skill pack"
        )
    if not found:
        stray = _stray_kit_file(root)
        if stray:
            raise KitError(f"{stray}: a source keeps kits in kits/<name>/ or one kit at its root")
        if _pack_skill_dirs(root, origin):
            found.append(Found(origin.name, where, root, origin, pack=True))
    seen: dict[str, Found] = {}
    for kit in found:
        if kit.name in seen:
            raise KitError(
                f'source "{origin.name}" has two kits named "{kit.name}": '
                f"{seen[kit.name].path} and {kit.path}"
            )
        seen[kit.name] = kit
    return found


def _registered() -> list[sources.Source]:
    try:
        return sources.registered()
    except sources.SourceError as exc:
        raise KitError(str(exc)) from None


def _in_folder(base: Path, where: str, origin: sources.Source | None = None) -> list[Found]:
    if not base.is_dir():
        return []
    paths = sorted(p for p in base.iterdir() if (p / KIT_FILE).is_file())
    return [Found(p.name, where, p, origin) for p in paths]


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


def _pack_skill_dirs(root: Path, origin: sources.Source) -> list[Path]:
    """The skill folders of a skill pack: under skills/, or under the source's skills folders."""
    if not origin.skills:
        return _skill_dirs(root / "skills")
    found = []
    for folder in origin.skills:
        if not (root / folder).is_dir():
            raise KitError(f'source "{origin.name}": skills folder {root / folder} does not exist')
        found += _skill_dirs(root / folder)
    return found


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


def load(
    path: str | Path,
    where: str = "path",
    named_folder: bool = True,
    origin: sources.Source | None = None,
) -> Kit:
    """Read and validate the kit in `path`. Raises KitError listing every problem found.
    `named_folder`: the folder's name must be the kit's name (it is in a kits folder)."""
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
    elif named_folder and name != path.name:
        errors.append(f'{path / KIT_FILE}: name "{name}" differs from the folder "{path.name}"')
    version = meta.get("version")
    if version is not None and not SEMVER.fullmatch(str(version)):
        errors.append(f"{path / KIT_FILE}: version must be X.Y.Z or X.Y.Z-<prerelease>")
    if "include" in meta:
        errors.append(
            f"{path / KIT_FILE}: include is gone: a kit takes skill packs from "
            "dependencies.skills (<name>: <git-url>@<version>); a kit no longer includes "
            "another kit"
        )
    default_agent = meta.get("default_agent")
    if default_agent is not None and not isinstance(default_agent, str):
        errors.append(f"{path / KIT_FILE}: default_agent must be an agent name")
    kit_name = name if isinstance(name, str) else path.name
    skills = _load_skills(path, kit_name, errors)
    packs = _load_dependencies(meta.get("dependencies", {}), path, kit_name, errors)
    _check_unique(skills, packs, path / KIT_FILE, errors)
    agents = _load_agents(path, kit_name, errors)
    kit_flows = _load_flows(path, kit_name, errors)
    if errors:
        raise KitError("\n".join(errors))
    return Kit(
        name=kit_name,
        path=path,
        where=where,
        version="" if version is None else str(version),
        description=str(meta.get("description", "")),
        default_agent=default_agent,
        agents=agents,
        skills=skills,
        origin=origin,
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
        elif _version(__version__) < tuple(int(n or 0) for n in match.groups()):
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


def _load_pack(found: Found) -> Kit:
    errors: list[str] = []
    skills: dict[str, Skill] = {}
    root = found.path.resolve()
    for path in _pack_skill_dirs(root, found.origin):
        skill = _load_skill(path, found.name, errors)
        if skill and skill.name in skills:
            errors.append(
                f'{path}: skill "{skill.name}" is also in {skills[skill.name].path}; '
                "choose the folders to use with `lado sources add --skills <folder>`"
            )
        elif skill:
            skills[skill.name] = skill
    if errors:
        raise KitError("\n".join(errors))
    return Kit(
        name=found.name,
        path=root,
        where=found.where,
        version="",
        description=f"skill pack, {len(skills)} skills",
        include=[],
        default_agent=None,
        agents={},
        skills=skills,
        origin=found.origin,
        pack=True,
    )


def resolve(
    repo: str | Path | None, kits: Iterable[str | Kit], without: Iterable[str] = ()
) -> Environment:
    """Combine kits into one environment, then switch off the `without` items ("agent:x",
    "skill:y", "mcp:z", "flow:f"). A kit is a name, looked up, loaded and fetched here, or a
    loaded kit, fetched already (fetch)."""
    taken: dict[Path, Kit] = {}
    for item in kits:
        kit = item if isinstance(item, Kit) else fetch(find(item, repo).load())
        if kit.unfetched():
            raise KitError(f'kit "{kit.name}": pack not fetched yet: {", ".join(kit.unfetched())}')
        taken.setdefault(kit.path, kit)

    env_kits = list(taken.values())
    agents = _merge(env_kits, "agents", "agent")
    skills = _merge(env_kits, "skills", "skill")
    # A kit without agents (by what it holds, before --without) shares its packs.
    owner = {name: kit for kit in env_kits for name in kit.skills}
    for kit in env_kits:
        for skill in [] if kit.agents else _pack_skills(kit).values():
            other = skills.setdefault(skill.name, skill)
            if other.path != skill.path:
                raise KitError(
                    f'skill "{skill.name}" is defined by two kits: {owner[skill.name].name} '
                    f"({other.path}) and {kit.name} ({skill.path})"
                )
            owner.setdefault(skill.name, kit)
    private = {kit.name: _pack_skills(kit) for kit in env_kits if kit.agents}
    for kit_name, own in private.items():
        for skill in own.values():
            other = skills.get(skill.name)
            if other and other.path != skill.path:
                raise KitError(
                    f'skill "{skill.name}" comes from two folders for the agents of kit '
                    f'"{kit_name}": {other.path} and {skill.path}'
                )
    env_flows = _merge(env_kits, "flows", "flow")
    defaults = {k.default_agent: k for k in env_kits if k.default_agent}
    if len(defaults) > 1:
        sources = ", ".join(f'"{d}" ({k.source})' for d, k in defaults.items())
        raise KitError(f"kits set different default agents: {sources}")
    default_agent = next(iter(defaults), None)

    without = list(without)
    excluded = parse_without(without)
    mcp = {m for a in agents.values() for m in a.mcp}
    every_skill = {**{s: v for own in private.values() for s, v in own.items()}, **skills}
    _check_known(excluded, every_skill, mcp, set(agents), set(env_flows))
    agents = {n: a for n, a in agents.items() if n not in excluded["agent"]}
    skills = {n: s for n, s in skills.items() if n not in excluded["skill"]}
    private = {
        k: {n: s for n, s in own.items() if n not in excluded["skill"]}
        for k, own in private.items()
    }
    env_flows = {n: f for n, f in env_flows.items() if n not in excluded["flow"]}
    for agent in agents.values():
        visible = {**skills, **private.get(agent.kit, {})}
        for skill in agent.skills or []:
            if skill not in visible and skill not in excluded["skill"]:
                raise KitError(
                    f'{agent.path}: skill "{skill}" is not visible to agent "{agent.name}" '
                    f'(kit "{agent.kit}"): not a skill of the session\'s kits or of kit '
                    f'"{agent.kit}"\'s dependencies'
                )
        if excluded["mcp"]:
            mcp = {m: v for m, v in agent.mcp.items() if m not in excluded["mcp"]}
            agents[agent.name] = dataclasses.replace(agent, mcp=mcp)
    if default_agent and default_agent not in agents and default_agent not in excluded["agent"]:
        raise KitError(f'default_agent "{default_agent}" is not an agent of the kits')
    return Environment(env_kits, agents, skills, default_agent, without, env_flows, private)


def _pack_skills(kit: Kit) -> dict[str, Skill]:
    """The skills of a kit's packs (fetched)."""
    return {name: s for pack in kit.packs.values() for name, s in (pack.skills or {}).items()}


def parse_without(items: Iterable[str]) -> dict[str, set[str]]:
    excluded: dict[str, set[str]] = {kind: set() for kind in WITHOUT_KINDS}
    for item in items:
        kind, _, name = item.partition(":")
        if kind not in excluded or not name:
            raise KitError(
                f'"{item}": expected agent:<name>, skill:<name>, mcp:<name> or flow:<name>'
            )
        excluded[kind].add(name)
    return excluded


def lint(kit: Kit) -> list[str]:
    """Problems a kit can run with but should not have: paths that only work on one
    machine (use ${KIT_DIR} or a relative path instead), a missing version."""
    problems = []
    if not kit.version and not kit.pack:
        problems.append(f"{kit.path / KIT_FILE}: version is missing; use X.Y.Z")
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
    """Doubts about a kit that do not stop it: its version differs from the source's."""
    tags = kit.origin.versions() if kit.origin and kit.version else []
    if tags and kit.version not in tags:
        return [
            f"{kit.name}: version {kit.version} in kit.yaml, but {kit.origin.name} is at "
            f"{', '.join('v' + t for t in tags)} ({kit.origin.describe()})"
        ]
    return []


def _hardcoded(text: str, where: str) -> list[str]:
    return [
        f'{where}: hardcoded path "{m.group(0)}"; use ${{KIT_DIR}} or a relative path'
        for m in HARDCODED_PATH.finditer(text)
    ]


def _merge(kits: list[Kit], attr: str, what: str) -> dict:
    merged: dict = {}
    owner: dict[str, Kit] = {}
    for kit in kits:
        for name, item in getattr(kit, attr).items():
            if name in merged:
                raise KitError(
                    f'{what} "{name}" is defined by two kits: '
                    f"{owner[name].name} ({owner[name].source}) and {kit.name} ({kit.source})"
                )
            merged[name], owner[name] = item, kit
    return merged


def _check_known(
    excluded: dict[str, set[str]],
    skills: Mapping,
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


def _load_flows(kit: Path, kit_name: str, errors: list[str]) -> dict[str, Flow]:
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
        flow = flows.parse(data, path.stem, kit_name, str(path), errors)
        if flow:
            found[flow.name] = flow
    return found


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
    supervisor = meta.get("supervisor", False)
    if not isinstance(supervisor, bool):
        errors.append(f"{path}: supervisor must be true or false")
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
    return AgentDef(name, description, supervisor, skills, mcp, body.strip(), kit_name, path)


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
