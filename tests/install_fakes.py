"""The host of docker/install.sh, faked for tests/test_install_sh.py: a PATH of its own with
the base tools the script needs (links to the real ones) and fake `docker`, `curl`, `git`,
`uname` and the other commands it may call, each a small Python script that logs its argv,
working folder and the `LADO_*`/`COMPOSE_*` of its environment to a JSON-lines file and
answers from the test's settings (a JSON file the test may change between runs).

A command left out of `Host(..., without=...)` is not on PATH at all, as on a computer that
lacks it. `sleep` answers at once, so no wait of the script is waited for real."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

# The base system's tools install.sh calls; each must be on the computer running the tests.
TOOLS = (
    "awk", "basename", "cat", "cp", "cut", "date", "dirname", "env", "grep", "head", "mkdir",
    "mv", "rm", "sed", "tail", "tr",
)  # fmt: skip

FAKES = (
    "docker", "curl", "git", "uname", "open", "xdg-open", "wslview", "cmd.exe", "scutil",
    "hostname", "nc", "systemctl", "sleep", "ip", "sudo",
)  # fmt: skip

# Every fake shares this body; NAME, SETTINGS, LOG and STATE are put before it.
BODY = r'''
import json, os, sys

args = sys.argv[1:]
settings = json.load(open(SETTINGS))
seen = {k: v for k, v in os.environ.items() if k.startswith(("LADO_", "COMPOSE_"))}
with open(LOG, "a") as log:
    log.write(json.dumps({"cmd": NAME, "args": args, "cwd": os.getcwd(), "env": seen}) + "\n")


def count(key):
    """How many times `key` was asked before, this time included."""
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    state[key] = state.get(key, 0) + 1
    json.dump(state, open(STATE, "w"))
    return state[key]


def answer(out="", err="", code=0):
    sys.stdout.write(out)
    sys.stderr.write(err)
    sys.exit(code)


s = settings
if NAME == "docker":
    if args[:2] == ["compose", "version"]:
        if s.get("no_compose"):
            answer(err="docker: 'compose' is not a docker command.\n", code=1)
        answer("Docker Compose version v2.30.0\n")
    if args[:1] == ["info"]:
        if count("info") <= s.get("info_fails", 0):
            answer(err=s.get("info_error", "Cannot connect to the Docker daemon\n"), code=1)
        answer("Server Version: 27.0.0\n")
    if args[:1] == ["ps"]:
        answer("".join(d + "\n" for d in s.get("ps_dirs", [])))
    if args[:1] == ["compose"]:
        rest = args[1:]
        if rest[:1] == ["up"]:
            answer(code=s.get("up_code", 0), err=s.get("up_error", ""))
        if rest[:1] == ["logs"]:
            answer("LOG LINE ONE\nLOG LINE TWO\n")
        if rest[:1] == ["exec"] and "ui" in rest:
            if count("ui") <= s.get("ui_fails", 0):
                answer(err="lado: no server\n", code=1)
            other = s.get("ui_other")
            answer(s.get("ui_link", "http://127.0.0.1:8765/?token=abc") + "\n",
                   f"From another machine: {other}\n" if other else "")
        if rest[:1] == ["exec"]:  # the health probe
            if count("health") <= s.get("health_fails", 0):
                answer(code=7)
            answer()
    answer()
if NAME == "curl":
    if s.get("curl_fails"):
        answer(err="curl: (22) The requested URL returned error: 404\n", code=22)
    out = args[args.index("-o") + 1]
    with open(out, "w") as f:
        f.write(s.get("compose_text", "name: lado\n"))
    answer()
if NAME == "git":
    key = {"user.name": "git_name", "user.email": "git_email"}.get(args[-1])
    if key and s.get(key):
        answer(s[key] + "\n")
    answer(code=1)
if NAME == "uname":
    if args == ["-r"]:
        answer(s.get("kernel", "6.8.0-generic") + "\n")
    answer(s.get("os", "Linux") + "\n")
if NAME == "open":
    if args[:1] == ["-a"] and not s.get("docker_desktop", True):
        answer(err="Unable to find application named 'Docker'\n", code=1)
    answer()
if NAME == "scutil":
    answer(s.get("local_host_name", "ann-mbp") + "\n")
if NAME == "hostname":
    if args == ["-I"]:
        answer(s.get("addresses", "192.168.1.23 172.17.0.1") + "\n")
    answer(s.get("hostname", "box") + "\n")
if NAME == "cmd.exe":
    if args[-1:] == ["hostname"]:
        answer(s.get("windows_name", "WINPC") + "\r\n")
    answer()
if NAME == "nc":
    answer(code=0 if int(args[-1]) in s.get("busy_ports", []) else 1)
if NAME == "systemctl":
    answer(code=0 if s.get("avahi") else 3)
answer()
'''


class Host:
    """A faked computer in `root`: its PATH (`bin`), home (`home`), the fakes' settings and
    their log. `run`'s env is the PATH and HOME with `env` added."""

    def __init__(self, root: Path, without: tuple[str, ...] = (), **settings):
        self.root, self.bin, self.home = root, root / "bin", root / "home"
        self.bin.mkdir(parents=True)
        self.home.mkdir()
        self.settings_path, self.log = root / "settings.json", root / "log.jsonl"
        self.state = root / "state.json"
        self.settings = {}
        self.set(**settings)
        for tool in TOOLS:
            found = shutil.which(tool)
            if found:
                os.symlink(found, self.bin / tool)
        for name in FAKES:
            if name in without:
                continue
            path = self.bin / name
            head = (
                f"#!{sys.executable}\nNAME = {name!r}\nSETTINGS = {str(self.settings_path)!r}\n"
                f"LOG = {str(self.log)!r}\nSTATE = {str(self.state)!r}\n"
            )
            path.write_text(head + BODY)
            path.chmod(0o755)

    def set(self, **settings) -> None:
        self.settings.update(settings)
        self.settings_path.write_text(json.dumps(self.settings))

    def env(self, **more: str) -> dict[str, str]:
        return {"PATH": str(self.bin), "HOME": str(self.home), "LANG": "C", **more}

    def calls(self, cmd: str | None = None) -> list[dict]:
        if not self.log.exists():
            return []
        found = [json.loads(line) for line in self.log.read_text().splitlines()]
        return [c for c in found if cmd is None or c["cmd"] == cmd]

    def compose_calls(self, sub: str) -> list[dict]:
        """The `docker compose <sub> ...` calls."""
        return [c for c in self.calls("docker") if c["args"][:2] == ["compose", sub]]


def on_tty(argv: list[str], env: dict, cwd: str, answers: list[list[str]]) -> dict:
    """`argv` with a pty as its controlling terminal (so /dev/tty is it): each [prompt,
    answer] answered once the prompt is seen since the last answer. Its exit code, the
    terminal's text (stdout and stderr together) and the prompts never seen. Run in a
    process of its own (`python install_fakes.py`), since forking a multi-threaded pytest
    worker may deadlock the child."""
    import pty
    import select
    import time

    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(cwd)
        os.execve(argv[0], argv, env)
    seen, since, pending = b"", b"", list(answers)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.5)
        if ready:
            try:
                chunk = os.read(fd, 4096)
            except OSError:  # the child closed the terminal
                break
            if not chunk:
                break
            seen, since = seen + chunk, since + chunk
        while pending and pending[0][0].encode() in since:
            since = b""
            os.write(fd, pending.pop(0)[1].encode() + b"\n")
    _, status = os.waitpid(pid, 0)
    text = seen.decode(errors="replace").replace("\r\n", "\n")
    return {"code": os.waitstatus_to_exitcode(status), "text": text, "pending": pending}


if __name__ == "__main__":
    given = json.loads(sys.stdin.read())
    print(json.dumps(on_tty(given["argv"], given["env"], given["cwd"], given["answers"])))
