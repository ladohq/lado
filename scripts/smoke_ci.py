"""One cell of LADO's smoke tests in CI: a provider's CLI on one system, no model.

    python scripts/smoke_ci.py run <provider> <out>
    python scripts/smoke_ci.py container <out>
    python scripts/smoke_ci.py needed <event> [<base> <head>]

`run` does one (system, provider) cell of ci.yml's job `smoke` or of the Windows probe's WSL
part: it installs the provider's CLI at its pin from npm into ~/.local (first on PATH from
then on) and checks that `<cli> --version` runs, in up to three attempts: npm drops an
optional dependency that failed to install (a CLI's native binary) and still exits 0.
After a failed attempt but the last it prints a GitHub `::warning::` naming the provider
and the attempt, uninstalls the package and installs again; after the third the cell is red
and runs no test. Then it runs `uv run pytest -m smoke -n0 -v -k <provider>`, as `make
test-smoke PROVIDER=<provider>` does. Its output goes to the terminal and to
`<out>/smoke-<provider>.log`. The cell passes only when pytest exits 0 and its last summary
line has a `passed` and no `skipped` (a missing CLI skips). A failing cell copies the
test's evidence into `<out>/evidence`.

`container` is a cell of ci.yml's job `container`: it installs nothing (LADO's image, which
`make docker` built before, has its own CLI) and runs `uv run pytest -m container -n0 -v`
into `<out>/container.log`, with `run`'s pass rule (the container tests skip without Docker
or the image) and evidence.

`needed` answers ci.yml's job `changes`: whether this run needs the smoke. It prints
`smoke=true` or `smoke=false` (a line for `$GITHUB_OUTPUT`) and, on stderr, the files it
went by. Outside a pull request (`<event>` is GitHub's event name) the smoke always runs.
On a pull request it is skipped only when `git diff --name-only <base>...<head>` names at
least one file and every one is on the skip list, `$SMOKE_SKIP`, one path per line (one
ending in `/` is a folder, another a file); ci.yml holds that list.

Standard library only: it imports nothing of LADO, and tests/test_smoke_ci.py compares it
with LADO.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Every provider's CLI: npm package, the version LADO is tested with (its provider's
# TESTED_VERSION; tests/test_smoke_ci.py keeps them the same, and keeps this list LADO's
# providers) and the command it installs. The one place a CLI's version is written for CI.
PINS = {
    "claude": ("@anthropic-ai/claude-code", "2.1.295", "claude"),
    "codex": ("@openai/codex", "0.162.0", "codex"),
    "opencode": ("opencode-ai", "1.18.35", "opencode"),
    "kilo": ("@kilocode/cli", "7.8.8", "kilo"),
}
# A cell's tries at installing its CLI (`run`).
ATTEMPTS = 3

# pytest's last line, e.g. `===== 1 failed, 2 passed in 10.00s (0:00:10) =====`.
SUMMARY = re.compile(r"^=+ .* in [0-9.]+s\b.*=+$")
USAGE = "usage: smoke_ci.py run <provider> <out> | container <out> | needed <event> [<base> <head>]"


def summary(log: str) -> str:
    """pytest's last summary line in a log, or ''."""
    lines = [line for line in log.splitlines() if SUMMARY.match(line.strip())]
    return lines[-1].strip() if lines else ""


def passed(line: str, code: int) -> bool:
    """A cell passes when pytest exited 0 and its summary has a pass and no skip."""
    return code == 0 and " passed" in line and " skipped" not in line


def install_once(install: list[str], command: str, env: dict) -> str:
    """One attempt: `npm install`, then the CLI's `--version`; what failed, or '' when both
    exited 0."""
    print("$", " ".join(install), flush=True)
    if subprocess.run(install, env=env).returncode != 0:
        return f"{install[-1]} did not install"
    cli = shutil.which(command, path=env["PATH"])
    if cli is None or subprocess.run([cli, "--version"], env=env).returncode != 0:
        return f"{command} --version failed after the install"
    return ""


def run(provider: str, out: Path) -> int:
    package, version, command = PINS[provider]
    env = dict(os.environ)
    local = Path(env["HOME"]) / ".local"
    env["PATH"] = f"{local / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    install = ["npm", "install", "-g", "--prefix", str(local), f"{package}@{version}"]
    uninstall = ["npm", "uninstall", "-g", "--prefix", str(local), package]
    for attempt in range(1, ATTEMPTS + 1):
        failed = install_once(install, command, env)
        if not failed:
            break
        if attempt == ATTEMPTS:
            print(failed, file=sys.stderr)
            return 1
        print(f"::warning::{provider}: attempt {attempt} of {ATTEMPTS}: {failed}; reinstalling")
        print("$", " ".join(uninstall), flush=True)
        # Not checked: the install that follows decides.
        subprocess.run(uninstall, env=env)
    tests = ["uv", "run", "pytest", "-m", "smoke", "-n0", "-v", "-k", provider]
    return cell(tests, out / f"smoke-{provider}.log", out, f"smoke {provider}", env)


def container(out: Path) -> int:
    """The container tests against the image `make docker` built (ci.yml's job
    `container`): no CLI to install, the image has its own."""
    tests = ["uv", "run", "pytest", "-m", "container", "-n0", "-v"]
    return cell(tests, out / "container.log", out, "container")


def cell(tests: list[str], log: Path, out: Path, name: str, env: dict | None = None) -> int:
    """Run one cell's pytest command: its output to the terminal and to `log`; 0 only by the
    pass rule; on red, the tests' evidence copied into `<out>/evidence`."""
    # Where a failing test keeps its evidence (tests/real_clis.py, EVIDENCE).
    evidence = Path(tempfile.gettempdir(), "lado-live-evidence")
    shutil.rmtree(evidence, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    print("$", " ".join(tests), flush=True)
    with (
        log.open("w") as kept,
        subprocess.Popen(
            tests, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        ) as pytest,
    ):
        for line in pytest.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            kept.write(line)
    code = pytest.returncode
    line = summary(log.read_text())
    if passed(line, code):
        return 0
    print(f"{name}: not passed (exit {code}): {line or 'no summary'}", file=sys.stderr)
    if evidence.is_dir():
        shutil.copytree(evidence, out / "evidence", dirs_exist_ok=True)
    return 1


def skip_list(text: str) -> list[str]:
    """The skip list from `$SMOKE_SKIP`: one path per line; an empty one is refused, as it
    is a broken ci.yml, not a list that skips nothing."""
    paths = [line.strip() for line in text.splitlines() if line.strip()]
    if not paths:
        raise ValueError("empty skip list ($SMOKE_SKIP)")
    return paths


def on_list(path: str, skip: list[str]) -> bool:
    return any(path.startswith(p) if p.endswith("/") else path == p for p in skip)


def needed(event: str, files: list[str], skip: list[str]) -> bool:
    """Whether a run needs the smoke: always but on a pull request whose every changed file
    is on the skip list (none changed: it runs)."""
    if event != "pull_request":
        return True
    return not files or not all(on_list(f, skip) for f in files)


def changed(base: str, head: str) -> list[str]:
    diff = subprocess.run(
        # --no-renames: a file moved from src/ into docs/ names src/ too.
        ["git", "diff", "--name-only", "--no-renames", f"{base}...{head}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return diff.stdout.splitlines()


def main_needed(argv: list[str]) -> int:
    event, refs = argv[0], argv[1:]
    if len(refs) != (2 if event == "pull_request" else 0):
        print(USAGE, file=sys.stderr)
        return 2
    try:
        skip = skip_list(os.environ.get("SMOKE_SKIP", ""))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    files = []
    if refs:
        try:
            files = changed(*refs)
        except subprocess.CalledProcessError as e:
            print(f"git diff failed: {e.stderr.strip()}", file=sys.stderr)
            return 1
        print("changed:", *files or ["nothing"], sep="\n  ", file=sys.stderr)
    print(f"smoke={str(needed(event, files, skip)).lower()}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "run":
        if argv[1] not in PINS:
            print(f"{argv[1]}: no provider (one of {', '.join(PINS)})", file=sys.stderr)
            return 2
        return run(argv[1], Path(argv[2]))
    if len(argv) == 2 and argv[0] == "container":
        return container(Path(argv[1]))
    if len(argv) >= 2 and argv[0] == "needed":
        return main_needed(argv[1:])
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
