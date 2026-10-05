"""Upgrading LADO: which version PyPI has, how LADO was installed and the command that
installs another version; `lado update` (lado.cli) stops and resumes the sessions around it.

No tmux, providers or UI here. The release index is PyPI's JSON of the package
(`INDEX_URL`); `LADO_UPDATE_INDEX` names a local file of that format instead, for the tests.
"""

import contextlib
import datetime
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from lado import __version__, state

INDEX_URL = "https://pypi.org/pypi/lado/json"
INDEX_TIMEOUT = 10.0  # seconds `lado update` waits for PyPI
CHECK_TIMEOUT = 2.0  # seconds the daily check waits for PyPI
CHECK_EVERY = 86400  # seconds between two looks of the check

_VERSION = re.compile(
    r"v?(?P<release>\d+(?:\.\d+)*)"
    r"(?:(?P<pre>a|b|rc)(?P<pre_n>\d+))?"
    r"(?:\.post(?P<post>\d+))?"
    r"(?:\.dev(?P<dev>\d+))?"
)
_PRE = {"a": 0, "b": 1, "rc": 2}
_FINAL = 3  # after every pre-release of the same version


def _key(version: str) -> tuple | None:
    """The sort key of a version as PEP 440 orders the forms LADO publishes (X.Y.Z, aN, bN,
    rcN, .postN, .devN); None for one it cannot read."""
    found = _VERSION.fullmatch(version.strip().lower())
    if found is None:
        return None
    release = [int(part) for part in found["release"].split(".")]
    while len(release) > 1 and release[-1] == 0:
        release.pop()  # 1.0 is 1.0.0
    if found["pre"]:
        pre = (_PRE[found["pre"]], int(found["pre_n"]))
    elif found["dev"] and not found["post"]:
        pre = (-1, 0)  # 1.0.dev1 comes before 1.0a1
    else:
        pre = (_FINAL, 0)
    post = int(found["post"]) if found["post"] else -1
    dev = int(found["dev"]) if found["dev"] else float("inf")
    return (tuple(release), pre, post, dev)


def newer(version: str, than: str) -> bool:
    """Whether `version` comes after `than`; False when either cannot be read."""
    a, b = _key(version), _key(than)
    return a is not None and b is not None and a > b


def same(version: str, other: str) -> bool:
    a = _key(version)
    return a is not None and a == _key(other)


def prerelease(version: str) -> bool:
    found = _VERSION.fullmatch(version.strip().lower())
    return bool(found and (found["pre"] or found["dev"]))


@dataclass(frozen=True)
class Release:
    version: str
    date: str  # YYYY-MM-DD of its first upload


def fetch_index(timeout: float = INDEX_TIMEOUT) -> dict:
    """PyPI's JSON of the package, or of the file LADO_UPDATE_INDEX names. OSError (no
    network, timeout, HTTP error) or ValueError (not JSON) when it cannot be read."""
    local = os.environ.get("LADO_UPDATE_INDEX")
    if local:
        with open(local) as file:
            return json.load(file)
    with urllib.request.urlopen(INDEX_URL, timeout=timeout) as answer:
        return json.load(answer)


def _releases(data: dict) -> list[Release]:
    """The releases with files that are not all yanked."""
    found = []
    for version, files in (data.get("releases") or {}).items():
        files = [f for f in files if not f.get("yanked")]
        if not files or _key(version) is None:
            continue
        date = min(f.get("upload_time_iso_8601") or f.get("upload_time") or "" for f in files)
        found.append(Release(version, date[:10]))
    return found


def latest(data: dict) -> Release | None:
    """The newest release that is no pre-release."""
    stable = [r for r in _releases(data) if not prerelease(r.version)]
    return max(stable, key=lambda r: _key(r.version), default=None)


def release(data: dict, version: str) -> Release | None:
    """The release of `version` (a pre-release too), or None when PyPI has no such one."""
    return next((r for r in _releases(data) if same(r.version, version)), None)


@dataclass(frozen=True)
class Check:
    """What the latest look at the index found (update-check.json)."""

    current: str  # this LADO
    latest: str | None  # the latest release; None before a look found one
    checked_at: str  # ISO time of that look, UTC
    error: str | None  # why the latest look failed

    @property
    def available(self) -> str | None:
        """The latest release when it is newer than this LADO."""
        return self.latest if self.latest and newer(self.latest, self.current) else None


def cache_path() -> Path:
    return state.home() / "update-check.json"


def check(now: datetime.datetime | None = None) -> Check | None:
    """The latest release, looked up at most once per CHECK_EVERY seconds for every caller
    (`lado ls`, `lado doctor`, the UI server), at most CHECK_TIMEOUT seconds; a failure is
    kept in the cache too, so it is not tried again before then. None with
    LADO_NO_UPDATE_CHECK=1: no look and nothing to say."""
    if os.environ.get("LADO_NO_UPDATE_CHECK") == "1":
        return None
    now = now or datetime.datetime.now(datetime.timezone.utc)
    cached = _cached()
    if cached and _age(cached, now) < CHECK_EVERY:
        return Check(__version__, cached.get("latest"), cached["checked_at"], cached.get("error"))
    newest, error = cached.get("latest") if cached else None, None
    try:
        found = latest(fetch_index(CHECK_TIMEOUT))
        newest = found.version if found else None
    except (OSError, ValueError) as exc:
        error = f"cannot look up LADO's latest version: {exc}"
    checked = Check(__version__, newest, now.isoformat(timespec="seconds"), error)
    _write_cache(checked)
    return checked


def _cached() -> dict | None:
    try:
        cached = json.loads(cache_path().read_text())
    except (OSError, ValueError):
        return None
    return cached if isinstance(cached, dict) and "checked_at" in cached else None


def _age(cached: dict, now: datetime.datetime) -> float:
    try:
        return (now - datetime.datetime.fromisoformat(cached["checked_at"])).total_seconds()
    except (TypeError, ValueError):
        return float("inf")


def _write_cache(checked: Check) -> None:
    fields = {"checked_at": checked.checked_at, "latest": checked.latest, "error": checked.error}
    with contextlib.suppress(OSError):
        path = cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        written = path.with_suffix(f".{os.getpid()}.tmp")
        written.write_text(json.dumps(fields))
        written.replace(path)


@dataclass(frozen=True)
class Installer:
    """How this LADO was installed: the installer that installs another version of it in
    `prefix`, and the `lado` that is there afterwards."""

    kind: str  # "uv tool" or "pipx"
    prefix: Path
    _command: tuple[str, ...]  # the installer's argv up to the requirement
    requirement: str  # lado, with the install's extras
    _options: tuple[str, ...] = ()  # the install's own options, given again
    lost: list[str] = field(default_factory=list)  # what the command does not keep

    @property
    def binary(self) -> Path:
        """The `lado` of this install, never one found on PATH (a working copy, say)."""
        return self.prefix / "bin" / "lado"

    def command(self, version: str) -> list[str]:
        """The argv that installs exactly `version` (never `uv tool upgrade`, which keeps the
        version a receipt pins)."""
        if self.kind == TEST_INSTALLER:
            return [*self._command, version]
        return [*self._command, f"{self.requirement}=={version}", *self._options]


TEST_INSTALLER = "test installer"  # LADO_UPDATE_INSTALLER


def prefix() -> Path:
    """Where this LADO is installed: its interpreter's prefix, or LADO_UPDATE_PREFIX (tests)."""
    return Path(os.environ.get("LADO_UPDATE_PREFIX") or sys.prefix)


def installer(where: Path | None = None) -> Installer | None:
    """The installer of the LADO in `where` (default: this one's prefix): a uv tool
    (`uv-receipt.toml` there) or pipx (`pipx_metadata.json`); None for anything else (pip
    in a venv, a working copy). LADO_UPDATE_INSTALLER (tests) is the argv of an installer
    instead, given the version as its last argument."""
    where = where or prefix()
    test = os.environ.get("LADO_UPDATE_INSTALLER")
    if test:
        return Installer(TEST_INSTALLER, where, tuple(shlex.split(test)), "lado")
    if (where / "uv-receipt.toml").is_file():
        return _uv_tool(where)
    if (where / "pipx_metadata.json").is_file():
        return _pipx(where)
    return None


def _uv_tool(where: Path) -> Installer:
    with open(where / "uv-receipt.toml", "rb") as file:
        tool = tomllib.load(file).get("tool", {})
    requirement, options, lost = "lado", [], []
    if tool.get("python"):
        options += ["--python", str(tool["python"])]
    for req in tool.get("requirements", []):
        name = req.get("name", "")
        extras = f"[{','.join(req['extras'])}]" if req.get("extras") else ""
        if name == "lado":
            requirement = f"lado{extras}"
        elif set(req) <= {"name", "extras", "specifier", "marker"}:
            marker = f"; {req['marker']}" if req.get("marker") else ""
            options += ["--with", f"{name}{extras}{req.get('specifier', '')}{marker}"]
        else:
            lost.append(f"--with {name} (not from an index)")
    lost += [key for key in tool if key not in ("requirements", "entrypoints", "python")]
    return Installer("uv tool", where, ("uv", "tool", "install"), requirement, tuple(options), lost)


def _pipx(where: Path) -> Installer:
    metadata = json.loads((where / "pipx_metadata.json").read_text())
    main = metadata.get("main_package") or {}
    options = []
    if main.get("pip_args"):
        options.append(f"--pip-args={shlex.join(main['pip_args'])}")
    if main.get("suffix"):
        options += ["--suffix", main["suffix"]]
    # --force installs into the existing venv: its injected packages stay.
    return Installer("pipx", where, ("pipx", "install", "--force"), "lado", tuple(options))


def installed_version(binary: Path) -> str | None:
    """What `<binary> --version` says (`lado X.Y.Z`), or None when it does not run."""
    try:
        said = subprocess.run(
            [str(binary), "--version"], capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    found = re.fullmatch(r"lado (\S+)", said.stdout.strip())
    return found[1] if said.returncode == 0 and found else None


def pending_path() -> Path:
    return state.home() / "update.json"


@dataclass(frozen=True)
class Pending:
    """An update that did not finish (update.json): the sessions it stopped, by name, with
    their repos, and the UI server's host and port when one ran. Read only by the LADO
    version that runs: a mark, no exchange between versions."""

    sessions: dict[str, str]  # name -> repo
    server: tuple[str, int] | None


def write_pending(pending: Pending) -> None:
    path = pending_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = {"sessions": pending.sessions, "server": pending.server}
    path.write_text(json.dumps(fields))


def read_pending() -> Pending | None:
    try:
        fields = json.loads(pending_path().read_text())
        server = fields.get("server")
        return Pending(dict(fields["sessions"]), tuple(server) if server else None)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def clear_pending() -> None:
    pending_path().unlink(missing_ok=True)


def available_line(checked: Check | None) -> str | None:
    """`LADO X is available: lado update` when the check found a newer release."""
    if checked is None or checked.available is None:
        return None
    return f"LADO {checked.available} is available: lado update"
