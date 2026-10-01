"""Thin wrapper over the tmux CLI.

LADO runs its own tmux server (socket `lado`, or LADO_TMUX_SOCKET), so it never touches the
user's tmux sessions.
"""

import os
import subprocess
import time
import uuid

DEFAULT_SOCKET = "lado"
TIMEOUT = 10

# Set by Claude Code in its child processes. A `claude` started with them believes it is
# nested inside another Claude Code session, so the LADO tmux server must not inherit them.
_INHERITED_AGENT_VARS = ("CLAUDECODE", "CLAUDE_PID", "CLAUDE_EFFORT", "AI_AGENT")
_INHERITED_AGENT_PREFIXES = (
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_EXECPATH",
    "CLAUDE_CODE_MESSAGING_",
    "CLAUDE_CODE_SESSION_",
    "CLAUDE_CODE_CHILD_SESSION",
)


class TmuxError(RuntimeError):
    pass


def clean_env() -> dict[str, str]:
    return {
        k: v
        for k, v in os.environ.items()
        if k not in _INHERITED_AGENT_VARS and not k.startswith(_INHERITED_AGENT_PREFIXES)
    }


def socket() -> str:
    return os.environ.get("LADO_TMUX_SOCKET") or DEFAULT_SOCKET


def _arg(value: str) -> str:
    # tmux reads an argument ending in ";" as a command separator.
    return value[:-1] + "\\;" if value.endswith(";") else value


def run(*args: str, input: str | None = None) -> str:
    cmd = ["tmux", "-L", socket(), *(_arg(a) for a in args)]
    try:
        result = subprocess.run(
            cmd,
            input=input,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=clean_env(),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TmuxError(f"tmux timed out: {' '.join(args)}") from exc
    if result.returncode != 0:
        raise TmuxError(result.stderr.strip() or f"tmux failed: {' '.join(args)}")
    return result.stdout


def _env_args(env: dict[str, str]) -> list[str]:
    return [arg for k, v in env.items() for arg in ("-e", f"{k}={v}")]


def new_session(session: str, window: str, cwd: str, env: dict[str, str], cmd: list[str]) -> None:
    run("new-session", "-d", "-s", session, "-n", window, "-c", cwd, *_env_args(env), *cmd)


def new_window(session: str, window: str, cwd: str, env: dict[str, str], cmd: list[str]) -> None:
    run("new-window", "-d", "-t", f"{session}:", "-n", window, "-c", cwd, *_env_args(env), *cmd)


def has_session(session: str) -> bool:
    try:
        run("has-session", "-t", f"={session}")
    except TmuxError:
        return False
    return True


def kill_session(session: str) -> None:
    run("kill-session", "-t", f"={session}")


def kill_window(session: str, window: str) -> None:
    """Close the window and the program in it. A window that is already gone is fine."""
    try:
        names = run("list-windows", "-t", f"={session}", "-F", "#{window_name}").split()
    except TmuxError:
        return  # the session is gone
    if window in names:
        run("kill-window", "-t", f"={session}:={window}")


def send_text(session: str, window: str, text: str) -> None:
    """Type `text` into the program running in the window and press Enter.

    The text goes in as one bracketed paste, so newlines inside it do not submit early.
    """
    target = f"{session}:{window}"
    if run("display-message", "-p", "-t", target, "#{pane_in_mode}").strip() == "1":
        run("send-keys", "-t", target, "-X", "cancel")  # copy-mode swallows input
    buffer = f"lado-{uuid.uuid4().hex[:8]}"
    run("load-buffer", "-b", buffer, "-", input=text)
    run("paste-buffer", "-p", "-d", "-b", buffer, "-t", target)
    time.sleep(0.05)  # let the paste land before Enter, or Enter can end up inside it
    run("send-keys", "-t", target, "Enter")


def capture(session: str, window: str) -> str:
    return run("capture-pane", "-p", "-t", f"{session}:{window}")


def attach_argv(session: str) -> list[str]:
    return ["tmux", "-L", socket(), "attach-session", "-t", f"={session}"]
