"""Kits: provider-neutral bundles of agent roles, skills and MCP servers.

A kit is a directory:

    kit.yaml            name, version, description, include (other kits), default_agent
    agents/<name>.md    YAML frontmatter + the role prompt
    skills/<name>/      a SKILL.md folder, always handled as a whole
    workflows/          reserved for flows; not loaded yet

Agents and skills are found in their folders; kit.yaml does not list them. Anything else in
the kit travels with it untouched. Kits are looked up by name in the project
(<repo>/.lado/kits), then in LADO_HOME/kits, then among the kits built into LADO; the first
hit wins. Several kits, with what they include, combine into one Environment.
"""

import dataclasses
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from lado import state
from lado.providers.base import McpServer

KIT_FILE = "kit.yaml"
DEFAULT_KIT = "default"
DEFAULT_ROLE = "worker"
BUILTIN = Path(__file__).with_name("builtin_kits")

KIT_KEYS = {"name", "version", "description", "include", "default_agent"}
AGENT_KEYS = {"name", "description", "supervisor", "skills", "mcp"}
MCP_KEYS = {"command", "env"}
WITHOUT_KINDS = ("agent", "skill", "mcp")

NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")
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
    include: list[str]
    default_agent: str | None
    agents: dict[str, AgentDef]
    skills: dict[str, Skill]

    @property
    def source(self) -> str:
        return f"{self.where}: {self.path}"


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
    kits: list[Kit]  # every kit taken in, included ones first
    agents: dict[str, AgentDef]
    skills: dict[str, Skill]
    default_agent: str | None
    without: list[str] = field(default_factory=list)

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
        if excluded["agent"]:
            raise KitError("an agent cannot be switched off for one agent; use skill: or mcp:")
        _check_known(excluded, self.skills, self._all_mcp(), set())
        agent = self.agents[name]
        wanted = list(self.skills) if agent.skills is None else agent.skills
        skills = {s: self.skills[s] for s in wanted if s in self.skills}
        skills = {s: v for s, v in skills.items() if s not in excluded["skill"]}
        mcp = {m: v for m, v in agent.mcp.items() if m not in excluded["mcp"]}
        return ResolvedAgent(agent, skills, mcp)

    def _all_mcp(self) -> set[str]:
        return {m for a in self.agents.values() for m in a.mcp}


def search_path(repo: str | Path | None) -> list[tuple[str, Path]]:
    """Where kits are looked up, in order."""
    dirs = [("user", state.home() / "kits"), ("built-in", BUILTIN)]
    return [("project", Path(repo) / ".lado" / "kits"), *dirs] if repo else dirs


def find(name: str, repo: str | Path | None) -> tuple[str, Path]:
    for where, base in search_path(repo):
        if (base / name / KIT_FILE).is_file():
            return where, base / name
    looked = ", ".join(str(base) for _, base in search_path(repo))
    raise KitError(f'kit "{name}" not found; looked in {looked}')


def available(repo: str | Path | None) -> list[tuple[str, str, Path, bool]]:
    """All kits on the search path: (name, where, path, shadowed by an earlier one)."""
    found, seen = [], set()
    for where, base in search_path(repo):
        if not base.is_dir():
            continue
        for path in sorted(base.iterdir()):
            if (path / KIT_FILE).is_file():
                found.append((path.name, where, path, path.name in seen))
                seen.add(path.name)
    return found


def load(path: str | Path, where: str = "path") -> Kit:
    """Read and validate the kit in `path`. Raises KitError listing every problem found."""
    path = Path(path).resolve()
    errors: list[str] = []
    meta = _yaml_file(path / KIT_FILE, errors)
    if not isinstance(meta, dict):
        if not errors:
            errors.append(f"{path / KIT_FILE}: expected a mapping")
        raise KitError("\n".join(errors))
    _unknown_keys(meta, KIT_KEYS, path / KIT_FILE, errors)
    name = meta.get("name")
    if not isinstance(name, str) or not NAME.fullmatch(name):
        errors.append(f"{path / KIT_FILE}: name must be lowercase letters, digits, - or _")
    elif name != path.name:
        errors.append(f'{path / KIT_FILE}: name "{name}" differs from the folder "{path.name}"')
    include = meta.get("include", [])
    if not _str_list(include):
        errors.append(f"{path / KIT_FILE}: include must be a list of kit names")
        include = []
    default_agent = meta.get("default_agent")
    if default_agent is not None and not isinstance(default_agent, str):
        errors.append(f"{path / KIT_FILE}: default_agent must be an agent name")
    kit_name = name if isinstance(name, str) else path.name
    skills = _load_skills(path, kit_name, errors)
    agents = _load_agents(path, kit_name, errors)
    if errors:
        raise KitError("\n".join(errors))
    return Kit(
        name=kit_name,
        path=path,
        where=where,
        version=str(meta.get("version", "")),
        description=str(meta.get("description", "")),
        include=list(include),
        default_agent=default_agent,
        agents=agents,
        skills=skills,
    )


def resolve(
    repo: str | Path | None, kits: Iterable[str | Kit], without: Iterable[str] = ()
) -> Environment:
    """Combine kits (names or loaded kits) and what they include into one environment, then
    switch off the `without` items ("agent:x", "skill:y", "mcp:z")."""
    taken: dict[Path, Kit] = {}

    def visit(kit: Kit, stack: list[str]) -> None:
        if kit.path in taken:
            return
        for name in kit.include:
            if name in stack:
                raise KitError(f"kits include each other: {' -> '.join([*stack, name])}")
            visit(load(*reversed(find(name, repo))), [*stack, name])
        taken[kit.path] = kit

    for item in kits:
        kit = item if isinstance(item, Kit) else load(*reversed(find(item, repo)))
        visit(kit, [kit.name])

    env_kits = list(taken.values())
    agents = _merge(env_kits, "agents", "agent")
    skills = _merge(env_kits, "skills", "skill")
    defaults = {k.default_agent: k for k in env_kits if k.default_agent}
    if len(defaults) > 1:
        sources = ", ".join(f'"{d}" ({k.source})' for d, k in defaults.items())
        raise KitError(f"kits set different default agents: {sources}")
    default_agent = next(iter(defaults), None)

    without = list(without)
    excluded = parse_without(without)
    _check_known(excluded, skills, {m for a in agents.values() for m in a.mcp}, set(agents))
    agents = {n: a for n, a in agents.items() if n not in excluded["agent"]}
    skills = {n: s for n, s in skills.items() if n not in excluded["skill"]}
    for agent in agents.values():
        for skill in agent.skills or []:
            if skill not in skills and skill not in excluded["skill"]:
                raise KitError(f'{agent.path}: skill "{skill}" is not in the kits')
        if excluded["mcp"]:
            mcp = {m: v for m, v in agent.mcp.items() if m not in excluded["mcp"]}
            agents[agent.name] = dataclasses.replace(agent, mcp=mcp)
    if default_agent and default_agent not in agents and default_agent not in excluded["agent"]:
        raise KitError(f'default_agent "{default_agent}" is not an agent of the kits')
    return Environment(env_kits, agents, skills, default_agent, without)


def parse_without(items: Iterable[str]) -> dict[str, set[str]]:
    excluded: dict[str, set[str]] = {kind: set() for kind in WITHOUT_KINDS}
    for item in items:
        kind, _, name = item.partition(":")
        if kind not in excluded or not name:
            raise KitError(f'"{item}": expected agent:<name>, skill:<name> or mcp:<name>')
        excluded[kind].add(name)
    return excluded


def lint(kit: Kit) -> list[str]:
    """Problems a kit can run with but should not have: paths that only work on one
    machine. Use ${KIT_DIR} or a relative path instead."""
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
    excluded: dict[str, set[str]], skills: Mapping, mcp: set[str], agents: set[str]
) -> None:
    known = {"agent": agents, "skill": set(skills), "mcp": mcp}
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
        skill_md = path / "SKILL.md"
        if not skill_md.is_file():
            errors.append(f"{path}: no SKILL.md")
            continue
        # SKILL.md is a standard format read by the agent CLIs: other keys are theirs.
        meta, _ = _frontmatter(skill_md.read_text(), skill_md, errors)
        if meta is None:
            continue
        name, description = meta.get("name"), meta.get("description")
        if name != path.name:
            errors.append(f'{skill_md}: name "{name}" differs from the folder "{path.name}"')
        elif not NAME.fullmatch(name):
            errors.append(f"{skill_md}: name must be lowercase letters, digits, - or _")
        elif not isinstance(description, str) or not description.strip():
            errors.append(f"{skill_md}: description is missing")
        else:
            skills[name] = Skill(name, description, path, kit_name)
    return skills


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


def _unknown_keys(meta: dict, allowed: set[str], path: Path, errors: list[str]) -> None:
    unknown = sorted(map(str, set(meta) - allowed))
    if unknown:
        errors.append(
            f"{path}: unknown keys {', '.join(unknown)}; allowed: {', '.join(sorted(allowed))}"
        )


def _str_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)
