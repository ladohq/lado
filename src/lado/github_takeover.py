"""The GitHub login agents used before github.com was a git server, taken over once into
the github.com entry (openspec capability `git-servers`), and the login outside LADO named
as not used (`unused`).

`run` is called by the UI server's start and before every launch of agents
(lado.runtime.agent_layers): with the takeover's record in lado.db (lado.state:
`github_takeover`) it returns at once. Otherwise it takes the token agents got: `GH_TOKEN`,
else `GITHUB_TOKEN`, of the highest layer of the agents' environment without a project
that sets it (lado.agent_env.layers), else what `gh auth token --hostname github.com` prints
in those layers (their GH_CONFIG_DIR kept: where that gh kept its login). It checks the
token on GitHub (lado.git_servers.probe), saves it as github.com (unchecked when GitHub
does not answer; not when GitHub refuses it) and records the outcome and the source in
words, never the token. An entry already saved is kept. Nothing outside LADO is changed.

A `gh` that fails for another reason than no login (a keychain closed to the process, more
than GH_WAIT seconds) records `pending` with why: the next start tries again, and `lado
doctor` says so. The record and the save are written under the git servers' lock, no
server being asked meanwhile, so two starts at once save once.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Mapping, Sequence
from typing import NamedTuple

from lado import agent_env, git_servers, state
from lado.git_kinds import github

TOKEN_NAMES = ("GH_TOKEN", "GITHUB_TOKEN")  # gh's order for github.com
GH_WAIT = 10  # seconds `gh auth token` may take
GH_LOGIN = "the GitHub CLI's login"
# gh's words when it holds no login for the host
NO_LOGIN = ("no oauth token", "not logged in")
SAVED, UNCHECKED, REFUSED, NONE, KEPT, PENDING = (
    "saved",
    "unchecked",
    "refused",
    "none",
    "kept",
    "pending",
)
SETTINGS = "Settings → Git servers"


class Found(NamedTuple):
    token: str
    source: str  # in words, e.g. "GH_TOKEN of your shell"


class Pending(Exception):
    """The GitHub CLI's login could not be read: why, one line."""


def _words(layer: int, name: str, folder: str) -> str:
    if layer == 0:
        return f"{name} of your shell"
    if layer == 1:
        return f"{name} in {folder}"
    return f"{name} of LADO's secrets"


def _found(layers: agent_env.Layers, folder: str) -> Found | None:
    """The token of the highest layer that sets GH_TOKEN, else GITHUB_TOKEN (the project's
    layer is none here)."""
    for name in TOKEN_NAMES:
        for index in (2, 1, 0):
            value = layers[index].get(name)
            if value:
                return Found(value, _words(index, name, folder))
    return None


def _gh_env(layers: agent_env.Layers) -> dict[str, str]:
    env = {k: v for layer in layers[:3] for k, v in layer.items()}
    config = env.get("GH_CONFIG_DIR")
    env = {k: v for k, v in env.items() if k not in agent_env.GITHUB_VARIABLES}
    if config:
        env["GH_CONFIG_DIR"] = config
    env["GH_PROMPT_DISABLED"] = "1"
    return env


def gh_token(env: Mapping[str, str]) -> str | None:
    """What `gh auth token --hostname github.com` prints in `env`; None for no gh or no
    login; Pending for any other failure."""
    gh = shutil.which("gh", path=env.get("PATH", ""))
    if gh is None:
        return None
    try:
        result = subprocess.run(
            [gh, "auth", "token", "--hostname", "github.com"],
            env=dict(env),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=GH_WAIT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise Pending(f"the GitHub CLI did not answer in {GH_WAIT} s") from None
    except OSError as exc:
        raise Pending(f"the GitHub CLI did not run: {exc.strerror or exc}") from None
    token = result.stdout.strip()
    if result.returncode == 0 and token:
        return token
    said = " ".join(result.stderr.split())
    if result.returncode == 0 or any(words in said.lower() for words in NO_LOGIN):
        return None
    raise Pending(said[:300] or f"the GitHub CLI failed with exit status {result.returncode}")


def unused(
    layers: agent_env.Layers | None,
    folder: str,
    projects: Mapping[str, Mapping[str, str]],
    names: Sequence[str] | None = None,
) -> list[str]:
    """Each variable of `names` (GitHub's, but GH_CONFIG_DIR, no login itself, which is
    left to `own_login`) a layer of the agents (`layers`, None when the shell could not be
    read) or a project's variables or secrets (`projects`, by id) sets, which no agent gets:
    `GH_TOKEN in <folder>`, `GH_TOKEN of your shell`, `GH_TOKEN of project <id>`; never a
    value."""
    if names is None:
        names = [n for n in agent_env.GITHUB_VARIABLES if n != "GH_CONFIG_DIR"]
    found = []
    for index, layer in enumerate(layers[:3] if layers else ()):
        found += [_words(index, n, folder) for n in names if layer.get(n)]
    for id, values in sorted(projects.items()):
        found += [f"{n} of project {id}" for n in names if n in values]
    return found


def own_login(layers: agent_env.Layers) -> bool:
    """Whether the GitHub CLI holds a login of its own in the agents' layers (no token
    variable of theirs, their GH_CONFIG_DIR): one agents no longer get."""
    try:
        return gh_token(_gh_env(layers)) is not None
    except Pending:
        return False


def _done(record: state.GithubTakeover | None) -> bool:
    return record is not None and record.outcome != PENDING


def _record(outcome: str, source: str | None, why: str | None = None) -> bool:
    """Record the outcome under the lock, held by the caller, unless another start did
    first: whether it was recorded."""
    if _done(state.github_takeover()):
        return False
    state.record_github_takeover(outcome, source, why)
    return True


def run(layers: agent_env.Layers | None = None, make: bool = True) -> str | None:
    """Take the GitHub login over once (see the module): the line to say, None for nothing
    to say (taken before, nothing found, an entry kept, pending, or the lock held by another
    change, which the next start retries). Not `make`: nothing while there is no lado.db,
    which a look of the UI never makes."""
    if not make and not (state.home_path() / "lado.db").exists():
        return None
    if _done(state.github_takeover()):
        return None
    at = git_servers.address(github.DOTCOM)
    try:
        with git_servers.locked():
            if state.git_server_by_host(at.key) is not None:
                _record(KEPT, None)
                return None
            if _done(state.github_takeover()):
                return None
        if layers is None:
            layers = agent_env.layers()
        env = _gh_env(layers)
        found = _found(layers, agent_env.outside().folder)
        try:
            if found is None:
                token = gh_token(env)
                found = Found(token, GH_LOGIN) if token else None
            if found is not None:
                # A git server needs a git that reads GIT_CONFIG_COUNT: no launch would go.
                try:
                    git_servers.check_git(env)
                except git_servers.Refused as exc:
                    raise Pending(str(exc)) from None
        except Pending as exc:
            with git_servers.locked():
                _record(PENDING, found.source if found else GH_LOGIN, str(exc))
            return None
        if found is None:
            with git_servers.locked():
                _record(NONE, None)
            return None
        try:
            git_servers.check_token(found.token)
            checked = git_servers.probe(at, found.token, github.KIND.name)
        except git_servers.Refused:
            with git_servers.locked():
                if not _record(REFUSED, found.source):
                    return None
            return f"GitHub refused the token of {found.source}: add github.com in {SETTINGS}."
        with git_servers.locked():
            if _done(state.github_takeover()):
                return None
            if state.git_server_by_host(at.key) is not None:
                _record(KEPT, None)
                return None
            git_servers.save_locked(at, checked, found.token)
            _record(SAVED if checked.login else UNCHECKED, found.source)
    except git_servers.Refused:  # the lock held past its wait, a token file not written
        return None
    signed = f"signed in as {checked.login}" if checked.login else "not checked yet"
    return f"LADO took your GitHub login ({found.source}) into {SETTINGS}: github.com, {signed}."
