"""One cell of LADO's smoke tests in CI: a provider's CLI on one system, no model.

    python scripts/smoke_ci.py run <provider> <out>

`run` does one (system, provider) cell of ci.yml's job `smoke` or of the Windows probe's WSL
part: it installs the provider's CLI at its pin from npm into ~/.local (first on PATH from
then on), then runs `uv run pytest -m smoke -n0 -v -k <provider>`, as `make test-smoke
PROVIDER=<provider>` does. Its output goes to the terminal and to
`<out>/smoke-<provider>.log`. The cell passes only when pytest exits 0 and its last summary
line has a `passed` and no `skipped` (a missing CLI skips). A failing cell copies the
test's evidence into `<out>/evidence`.

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

# pytest's last line, e.g. `===== 1 failed, 2 passed in 10.00s (0:00:10) =====`.
SUMMARY = re.compile(r"^=+ .* in [0-9.]+s\b.*=+$")
USAGE = "usage: smoke_ci.py run <provider> <out>"


def summary(log: str) -> str:
    """pytest's last summary line in a log, or ''."""
    lines = [line for line in log.splitlines() if SUMMARY.match(line.strip())]
    return lines[-1].strip() if lines else ""


def passed(line: str, code: int) -> bool:
    """A cell passes when pytest exited 0 and its summary has a pass and no skip."""
    return code == 0 and " passed" in line and " skipped" not in line


def run(provider: str, out: Path) -> int:
    package, version, command = PINS[provider]
    env = dict(os.environ)
    local = Path(env["HOME"]) / ".local"
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
    # Where a failing test keeps its evidence (tests/real_clis.py, EVIDENCE).
    evidence = Path(tempfile.gettempdir(), "lado-live-evidence")
    shutil.rmtree(evidence, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    log = out / f"smoke-{provider}.log"
    tests = ["uv", "run", "pytest", "-m", "smoke", "-n0", "-v", "-k", provider]
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
    print(f"smoke {provider}: not passed (exit {code}): {line or 'no summary'}", file=sys.stderr)
    if evidence.is_dir():
        shutil.copytree(evidence, out / "evidence", dirs_exist_ok=True)
    return 1


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "run":
        if argv[1] not in PINS:
            print(f"{argv[1]}: no provider (one of {', '.join(PINS)})", file=sys.stderr)
            return 2
        return run(argv[1], Path(argv[2]))
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
