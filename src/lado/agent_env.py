"""Where an agent's environment comes from.

An agent gets the environment of the user's login shell, as a new terminal sees it,
resolved anew for each launch: the same whichever process starts the agent (`lado start`,
the UI server) and whichever started LADO's tmux server. `LADO_AGENT_ENV=inherit` gives it
the environment of the process that starts it instead.

Over either go the variables of the outside folder `LADO_ENV_DIR` names (LADO's image sets
it to /run/secrets): one file per variable, read anew at each launch (`outside`). A file
it cannot take is named with why, never with its content, and not applied.

A tmux window starts with its server's environment, so the launch does not rely on it: the
window runs the module `lado.agent_env <file> <argv>` (`interpreter.run_module`), which
replaces its environment with the one in the file and runs the agent's command.
"""

import contextlib
import json
import os
import re
import select
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

from lado import interpreter, tmux

SOURCE_VAR = "LADO_AGENT_ENV"
SHELL, INHERIT = "shell", "inherit"
TIMEOUT = 10  # seconds the shell may take
SLOW = 2  # seconds above which `lado doctor` warns
STDERR_LINES = 5  # of the shell's stderr in an error

# What a new terminal starts the shell with; its startup files do the rest.
SHELL_BASE = ("HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "LANG", "SSH_AUTH_SOCK")
# The PATH a new terminal has before its shell starts (`base_path`). On macOS
# /etc/profile's path_helper builds the system PATH from any start; on Linux what logs
# the user in sets it: pam_env from /etc/environment, else the login default.
SHELL_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
ENVIRONMENT_FILE = Path("/etc/environment")
LINUX_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
# WSL: told by these files, never by variables. Its init also puts the Windows PATH in a
# new terminal's; agents do not get it (a Windows node.exe or git.exe found first breaks
# tools, and lookups through /mnt/c are slow), only WSL's own libraries.
WSL_INTEROP = Path("/proc/sys/fs/binfmt_misc/WSLInterop")
PROC_VERSION = Path("/proc/version")
WSL_LIB = Path("/usr/lib/wsl/lib")
# Not taken from the source: the tmux server of the caller, if any, and the source shell's
# own (an agent's working directory and depth are its window's).
EXCLUDED = ("TMUX", "TMUX_PANE")
SHELL_OWN = ("PWD", "OLDPWD", "SHLVL", "_")
# Set by tmux in the agent's window: kept over the resolved environment.
PANE_VARS = ("TERM", "TERM_PROGRAM", "TERM_PROGRAM_VERSION", "TMUX", "TMUX_PANE")

# The outside folder: one file per variable (Docker's /run/secrets form), laid over the
# source's environment at each launch; LADO's image sets it. A name the login shell must
# keep (its identity, PATH, tmux's) is reserved, and so is LADO's own namespace.
ENV_DIR_VAR = "LADO_ENV_DIR"
MAX_VALUE = 65536  # bytes of one file
VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
RESERVED = frozenset({"HOME", "USER", "LOGNAME", "SHELL", "PATH", *SHELL_OWN, *PANE_VARS})
RESERVED_PREFIX = "LADO_"
SUBFOLDER = "in a subfolder"

INHERIT_HINT = (
    f"set {SOURCE_VAR}={INHERIT} to give agents the environment of the process that starts them"
)
HINT = f"fix your shell's startup files, or {INHERIT_HINT}"
# What to do about a command not on the agents' PATH (an agent's CLI, a kit's expects).
PATH_ADVICE = (
    f"add its folder to PATH in your shell's startup files, or with {SOURCE_VAR}={INHERIT} to "
    "the PATH of the process that starts LADO"
)


class AgentEnvError(RuntimeError):
    pass


def source() -> str:
    value = os.environ.get(SOURCE_VAR) or SHELL
    if value not in (SHELL, INHERIT):
        raise AgentEnvError(f'{SOURCE_VAR}="{value}" is not known; use "{INHERIT}" or unset it')
    return value


def resolve() -> dict[str, str]:
    """The environment for an agent, before LADO's and its provider's variables: the
    login shell's (or the starting process's), then the outside folder's."""
    env = from_shell() if source() == SHELL else dict(os.environ)
    dropped = (*EXCLUDED, *SHELL_OWN)
    base = {k: v for k, v in tmux.without_agent_vars(env).items() if k not in dropped}
    return {**base, **outside().values}


class Outside(NamedTuple):
    """The variables of the outside folder, and one line per file (or the folder) not
    used, with why. No line holds a value."""

    folder: str
    values: dict[str, str]
    unused: list[str]


def outside(environ: Mapping[str, str] | None = None) -> Outside:
    """The folder `LADO_ENV_DIR` names, read now: a new file reaches the next launch.
    Unset, empty or missing: no layer and no line."""
    folder = (os.environ if environ is None else environ).get(ENV_DIR_VAR, "")
    if not folder:
        return Outside("", {}, [])
    where = f"variable folder {folder} ({ENV_DIR_VAR}) not used"
    if not os.path.isabs(folder):
        return Outside(folder, {}, [f"{where}: not an absolute path"])
    try:
        with os.scandir(folder) as found:
            entries = sorted(found, key=lambda entry: entry.name)
    except FileNotFoundError:
        return Outside(folder, {}, [])
    except NotADirectoryError:
        return Outside(folder, {}, [f"{where}: not a folder"])
    except OSError as exc:
        return Outside(folder, {}, [f"{where}: cannot be listed: {exc.strerror}"])
    values: dict[str, str] = {}
    unused: list[str] = []
    for entry in entries:
        if entry.name.startswith("."):
            continue  # Docker's and editors' own files
        reason, value = _take(entry)
        if reason:
            name = f"{entry.name}/" if reason == SUBFOLDER else entry.name
            unused.append(f"variable file {name} in {folder} not used: {reason}")
        else:
            values[entry.name] = value
    return Outside(folder, values, unused)


def _take(entry: os.DirEntry) -> tuple[str, str]:
    """("", value) for a file used, (why, "") for one not. Symbolic links are followed:
    Docker's and Kubernetes' secrets are such links."""
    try:
        if entry.is_dir():
            return SUBFOLDER, ""
        regular = entry.is_file()
    except OSError as exc:
        return f"cannot be read: {exc.strerror}", ""
    if not regular:
        return "not a regular file", ""
    if not VARIABLE_NAME.fullmatch(entry.name):
        return "not a variable name", ""
    if entry.name in RESERVED or entry.name.startswith(RESERVED_PREFIX):
        return "a reserved name", ""
    try:
        with open(entry.path, "rb") as file:
            data = file.read(MAX_VALUE + 1)
    except OSError as exc:
        return f"cannot be read: {exc.strerror}", ""
    if len(data) > MAX_VALUE:
        return "larger than 64 KiB", ""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "not UTF-8 text", ""
    if "\0" in text:
        return "not UTF-8 text", ""
    for end in ("\r\n", "\n"):
        if text.endswith(end):
            return "", text[: -len(end)]
    return "", text


def timed() -> tuple[dict[str, str], float]:
    """`resolve()` and the seconds it took."""
    began = time.monotonic()
    env = resolve()
    return env, time.monotonic() - began


class BasePath(NamedTuple):
    """The PATH the login shell starts from, where it came from (`path_helper`, the
    environment file, `default`), why the default was taken, and whether this is WSL."""

    path: str
    source: str
    reason: str
    wsl: bool


def base_path() -> BasePath:
    if sys.platform == "darwin":
        return BasePath(SHELL_PATH, "path_helper", "", False)
    path, reason = _environment_path()
    source = str(ENVIRONMENT_FILE) if path else "default"
    path = path or LINUX_PATH
    wsl = is_wsl()
    if wsl and WSL_LIB.is_dir():
        path = f"{path}:{WSL_LIB}"
    return BasePath(path, source, reason, wsl)


def _environment_path() -> tuple[str, str]:
    """The PATH of ENVIRONMENT_FILE in pam_env's simple form (`[export ]KEY=value`, the
    value maybe in double quotes, `#` comments, the last one wins), or "" and why not."""
    try:
        text = ENVIRONMENT_FILE.read_text(errors="replace")
    except FileNotFoundError:
        return "", f"no {ENVIRONMENT_FILE}"
    except OSError as exc:
        return "", f"cannot read {ENVIRONMENT_FILE}: {exc}"
    path = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        if sep and key == "PATH":
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
            path = value
    if not path:
        return "", f"no PATH in {ENVIRONMENT_FILE}"
    # pam_env expands nothing here; LADO's choice: a `$` is taken as a mistake.
    if "$" in path:
        return "", f"a `$` in the PATH of {ENVIRONMENT_FILE}"
    return path, ""


def is_wsl() -> bool:
    if WSL_INTEROP.exists():
        return True
    try:
        return "microsoft" in PROC_VERSION.read_text(errors="replace").lower()
    except OSError:
        return False


def dump_script() -> tuple[str, str, str]:
    """A shell command that prints the environment as JSON between two markers, and the
    markers. The command holds them only in halves, so a shell that echoes its commands
    does not print them."""
    tag = uuid.uuid4().hex
    begin, end = f"LADO-ENV-BEGIN-{tag}", f"LADO-ENV-END-{tag}"
    dump = "import json, os, sys; sys.stdout.write(json.dumps(dict(os.environ)))"
    # -I: the shell's PYTHONPATH or PYTHONHOME do not reach this Python.
    python = f"{shlex.quote(sys.executable)} -I -c {shlex.quote(dump)}"
    script = f"printf '%s%s' LADO-ENV-BEGIN- {tag}; {python}; printf '%s%s' LADO-ENV-END- {tag}"
    return script, begin, end


def from_shell() -> dict[str, str]:
    shell = os.environ.get("SHELL")
    if not shell:
        raise AgentEnvError(
            "$SHELL is not set: LADO takes the agents' environment from your login shell; "
            f"set SHELL, or {INHERIT_HINT}"
        )
    script, begin, end = dump_script()
    argv = [shell, "-ilc", script]
    base = {k: os.environ[k] for k in SHELL_BASE if k in os.environ}
    base.update(PATH=base_path().path, TERM="dumb")
    command = shlex.join(argv)
    # stderr goes to a file: a program the startup files leave running in the background
    # may keep the shell's outputs open, so neither is read to its end.
    with tempfile.TemporaryFile() as errors:
        try:
            process = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=errors,
                env=base,
                cwd=base.get("HOME"),
                # No controlling terminal: an interactive shell must not take the caller's.
                start_new_session=True,
            )
        except OSError as exc:
            raise AgentEnvError(
                f"cannot run your shell for the agents' environment: {exc}\n{HINT}"
            ) from exc
        deadline = time.monotonic() + TIMEOUT
        with process.stdout:
            fd = process.stdout.fileno()
            out = _read_until(fd, end.encode(), deadline)
            if out is None or not _drain_until_exit(process, fd, deadline):
                _kill(process)
                out = None
        errors.seek(0)
        err = errors.read()
    if out is None:
        raise AgentEnvError(
            f"your shell did not finish in {TIMEOUT:g} s: {command}{_tail(err)}\n{HINT}"
        )
    if process.returncode != 0:
        raise AgentEnvError(
            f"your shell failed with exit status {process.returncode}: {command}{_tail(err)}"
            f"\n{HINT}"
        )
    text = out.decode(errors="surrogateescape")
    start, stop = text.find(begin), text.find(end)
    if start < 0 or stop < start:
        raise AgentEnvError(f"your shell printed no environment: {command}{_tail(err)}\n{HINT}")
    try:
        return json.loads(text[start + len(begin) : stop])
    except ValueError as exc:
        raise AgentEnvError(
            f"cannot read the environment from your shell: {exc}: {command}"
        ) from exc


def _read_until(fd: int, end: bytes, deadline: float) -> bytes | None:
    """What `fd` gives until `end` or its end of file; None when the deadline comes first."""
    out = b""
    while end not in out:
        left = deadline - time.monotonic()
        if left <= 0 or not select.select([fd], [], [], left)[0]:
            return None
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        out += chunk
    return out


def _drain_until_exit(process: subprocess.Popen, fd: int, deadline: float) -> bool:
    """Wait for the shell to exit, reading and dropping what it still prints (so it is
    never stopped by a full or closed pipe); whether it exited before the deadline."""
    while process.poll() is None:
        left = deadline - time.monotonic()
        if left <= 0:
            return False
        if select.select([fd], [], [], min(left, 0.05))[0] and not os.read(fd, 65536):
            # End of file: the shell is ending, with nothing left running that holds it.
            try:
                process.wait(max(deadline - time.monotonic(), 0))
            except subprocess.TimeoutExpired:
                return False
    return True


def _kill(process: subprocess.Popen) -> None:
    """End the shell and what it started."""
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()


def _tail(err: bytes) -> str:
    lines = err.decode(errors="replace").strip().splitlines()[-STDERR_LINES:]
    return "".join(f"\n  {line}" for line in lines)


def command(file: Path, env: Mapping[str, str], argv: list[str]) -> list[str]:
    """The window's command that runs `argv` with exactly `env` (and tmux's own variables
    of the window). `env` goes into `file`, readable by the user only, until the window
    reads it. Fails when `argv[0]` is not on `env`'s PATH: the window would close at once."""
    path = env.get("PATH", os.defpath)
    if shutil.which(argv[0], path=path) is None:
        raise AgentEnvError(f"`{argv[0]}` is not on the agents' PATH ({path}): {PATH_ADVICE}")
    fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)  # the mode above is only for a new file
    with os.fdopen(fd, "w") as f:
        json.dump(dict(env), f)
    return interpreter.run_module("lado.agent_env", str(file), *argv)


def main(args: list[str]) -> None:
    file, *argv = args
    env = json.loads(Path(file).read_text())
    Path(file).unlink()  # it holds the user's keys
    env.update({k: os.environ[k] for k in PANE_VARS if k in os.environ})
    os.execvpe(argv[0], argv, env)


if __name__ == "__main__":
    main(sys.argv[1:])
