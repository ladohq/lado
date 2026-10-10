"""One cell of LADO's live tests in GitHub Actions, and the scrub before every upload.

    python scripts/live_ci.py run <provider> <out>
    python scripts/live_ci.py scrub <dir>
    python scripts/live_ci.py providers

`run` does one (system, provider) cell of live.yml or of the Windows probe's WSL part: it
installs the provider's CLI at its pin from npm into ~/.local (first on PATH from then
on), then runs `uv run pytest -m live -n0 -v -k <provider>`, as `make test-live
PROVIDER=<provider>` does, nothing deselected. Its output goes to the terminal and to
`<out>/live-<provider>.log`. The cell passes only when pytest exits 0 and its last summary
line has a `passed` and no `skipped` (a missing CLI or login skips). A failing cell copies
the live tests' evidence into `<out>/evidence`.

Claude Code's cell reads the token of `claude setup-token` from LADO_LIVE_CLAUDE_TOKEN (a
repository secret): without it the cell is red, never a skip. The tests get it as
CLAUDE_CODE_OAUTH_TOKEN, never on argv, and it is never printed. A fresh CI home gets
`hasCompletedOnboarding` in ~/.claude.json, without which Claude Code shows its first-run
screens before any hook.

`scrub` deletes each file under <dir> that holds LADO_LIVE_CLAUDE_TOKEN's bytes and names
it. It fails closed: a file it cannot read or a folder it cannot walk exits 1, and the
workflows upload only after its success.

`providers` prints the cloud providers, the Windows probe's `all`.

Standard library only: on the Windows host it runs with `uv run --no-project`.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

# The cloud providers: npm package, the version LADO is tested with (its provider's
# TESTED_VERSION; tests/test_live_ci.py keeps them the same) and the CLI it installs.
# The one place a cloud CLI's version is written.
PINS = {
    "opencode": ("opencode-ai", "1.18.35", "opencode"),
    "kilo": ("@kilocode/cli", "7.8.8", "kilo"),
    "claude": ("@anthropic-ai/claude-code", "2.1.295", "claude"),
}
# The live providers that run only on a developer's machine: Codex's model is a local
# Ollama one, too big for a runner.
LOCAL_ONLY = {"codex"}

TOKEN = "LADO_LIVE_CLAUDE_TOKEN"
NO_TOKEN = f"{TOKEN} is not set: add the repository secret"
# pytest's last line, e.g. `===== 1 failed, 2 passed in 10.00s (0:00:10) =====`.
SUMMARY = re.compile(r"^=+ .* in [0-9.]+s\b.*=+$")
USAGE = "usage: live_ci.py run <provider> <out> | scrub <dir> | providers"


def summary(log: str) -> str:
    """pytest's last summary line in a log, or ''."""
    lines = [line for line in log.splitlines() if SUMMARY.match(line.strip())]
    return lines[-1].strip() if lines else ""


def passed(line: str, code: int) -> bool:
    """A cell passes when pytest exited 0 and its summary has a pass and no skip."""
    return code == 0 and " passed" in line and " skipped" not in line


def seed_onboarding(home: Path) -> None:
    """Mark Claude Code's onboarding done in a fresh home's ~/.claude.json; a config that
    has the key is left as it is."""
    config = home / ".claude.json"
    data = json.loads(config.read_text()) if config.exists() else {}
    if "hasCompletedOnboarding" in data:
        return
    data["hasCompletedOnboarding"] = True
    config.write_text(json.dumps(data, indent=2) + "\n")


def scrub(folder: Path, token: str) -> bool:
    """Delete each file under folder that holds the token and print its path; False when a
    file or folder could not be read (what it could read is scrubbed all the same)."""
    if not folder.is_dir():
        print(f"scrub: {folder}: no such folder", file=sys.stderr)
        return False
    errors = []

    def failed(error: OSError) -> None:
        errors.append(error)
        print(f"scrub: {error.filename}: {error.strerror}", file=sys.stderr)

    secret = token.encode()
    for root, _, files in os.walk(folder, onerror=failed):
        for name in files:
            path = Path(root, name)
            try:
                if secret and secret in path.read_bytes():
                    path.unlink()
                    print(f"{path.relative_to(folder).as_posix()}: held the token, deleted")
            except OSError as error:
                failed(error)
    return not errors


def run(provider: str, out: Path, environ: Mapping[str, str]) -> int:
    package, version, command = PINS[provider]
    env = dict(environ)
    token = env.pop(TOKEN, "")
    if provider == "claude":
        if not token:
            print(NO_TOKEN, file=sys.stderr)
            return 1
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    home = Path(env["HOME"])
    local = home / ".local"
    env["PATH"] = f"{local / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    install = ["npm", "install", "-g", "--prefix", str(local), f"{package}@{version}"]
    print("$", " ".join(install), flush=True)
    if subprocess.run(install, env=env).returncode != 0:
        print(f"{package}@{version} did not install", file=sys.stderr)
        return 1
    cli = shutil.which(command, path=env["PATH"])
    if cli is None or subprocess.run([cli, "--version"], env=env).returncode != 0:
        print(f"{command} --version failed after the install", file=sys.stderr)
        return 1
    if provider == "claude":
        seed_onboarding(home)
    # Where a failing live test keeps its evidence (tests/live/conftest.py, EVIDENCE).
    evidence = Path(tempfile.gettempdir(), "lado-live-evidence")
    shutil.rmtree(evidence, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    log = out / f"live-{provider}.log"
    tests = ["uv", "run", "pytest", "-m", "live", "-n0", "-v", "-k", provider]
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
    print(f"live {provider}: not passed (exit {code}): {line or 'no summary'}", file=sys.stderr)
    if evidence.is_dir():
        shutil.copytree(evidence, out / "evidence", dirs_exist_ok=True)
    return 1


def main(argv: list[str], environ: Mapping[str, str]) -> int:
    if len(argv) == 3 and argv[0] == "run":
        if argv[1] not in PINS:
            print(f"{argv[1]}: no cloud provider (one of {', '.join(PINS)})", file=sys.stderr)
            return 2
        return run(argv[1], Path(argv[2]), environ)
    if argv == ["providers"]:
        print(" ".join(PINS))
        return 0
    if len(argv) == 2 and argv[0] == "scrub":
        return 0 if scrub(Path(argv[1]), environ.get(TOKEN, "")) else 1
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ))
