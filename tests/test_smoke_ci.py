"""scripts/smoke_ci.py: one cell of the smoke tests in CI (ci.yml's job `smoke`, the
Windows probe)."""

import importlib.util
import os
import subprocess
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from agent_helpers import init_repo

from lado import providers
from lado.providers import claude, codex, kilo, opencode

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "smoke_ci.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smoke_ci = _load("smoke_ci", SCRIPT)


def test_the_script_imports_only_the_standard_library():
    """It imports nothing of LADO: the tests compare it with LADO."""
    code = (
        "import sys; sys.path.insert(0, 'scripts'); before = set(sys.modules); "
        "import smoke_ci; "
        "print('\\n'.join(sorted(m for m in set(sys.modules) - before)))"
    )
    loaded = subprocess.run(
        [sys.executable, "-I", "-c", code], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    stdlib = sys.stdlib_module_names
    assert [m for m in loaded if m.split(".")[0] not in stdlib and m != "smoke_ci"] == []


# One source of truth for the providers (AC-5).


def test_the_pins_are_exactly_lados_providers():
    assert sorted(smoke_ci.PINS) == sorted(providers.names())


@pytest.mark.parametrize(
    "provider, module",
    [("claude", claude), ("codex", codex), ("opencode", opencode), ("kilo", kilo)],
)
def test_each_pin_is_its_providers_tested_version(provider, module):
    _, version, _ = smoke_ci.PINS[provider]
    tested = module.TESTED_VERSION.split(".")
    # Compared by parts: 7.80.1 is no 7.8.
    assert version.split(".")[: len(tested)] == tested


def test_each_pins_command_is_its_providers_cli():
    for provider, (_, _, command) in smoke_ci.PINS.items():
        assert command == providers.get(provider).command


# The live cell (openspec change cloud-live-tests).


def test_redact_replaces_the_key_in_every_file(tmp_path):
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / "screen").write_bytes(b"KEY=s3cr3t\n")
    (tmp_path / "live-codex.log").write_bytes(b"s3cr3t s3cr3t")
    smoke_ci.redact(tmp_path, "s3cr3t")
    assert (tmp_path / "evidence" / "screen").read_bytes() == b"KEY=<redacted>\n"
    assert (tmp_path / "live-codex.log").read_bytes() == b"<redacted> <redacted>"


KEY = "sk-or-v1-0123456789abcdefE0123456789abcdef"


@pytest.mark.parametrize(
    "torn",
    [
        f"{KEY[:20]}\n{KEY[20:]}",  # tmux's wrap at the window's width
        f"{KEY[:20]}  \r\n  {KEY[20:]}",
        f"┃ {KEY[:20]} ┃\n┃ {KEY[20:30]} │\n┃ {KEY[30:]} ┃",  # a CLI's own wrap, in its frame
        f"E     {KEY[:20]}\nE     {KEY[20:]}",  # pytest's report of a failed wait
    ],
)
def test_redact_finds_a_key_torn_by_a_window(tmp_path, torn):
    (tmp_path / "screen").write_bytes(f"before {torn} after".encode())
    smoke_ci.redact(tmp_path, KEY)
    text = (tmp_path / "screen").read_text()
    assert "<redacted>" in text and text.endswith(" after")
    assert KEY[:12] not in text and KEY[-12:] not in text


def test_redact_keeps_what_only_looks_like_the_key(tmp_path):
    text = f"{KEY[:20]} and something else".encode()
    (tmp_path / "log").write_bytes(text)
    smoke_ci.redact(tmp_path, KEY)
    assert (tmp_path / "log").read_bytes() == text


def test_redact_leaves_a_link_and_what_it_points_at(tmp_path):
    outside = tmp_path / "outside"
    outside.write_bytes(b"s3cr3t")
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "link").symlink_to(outside)
    smoke_ci.redact(folder, "s3cr3t")
    assert outside.read_bytes() == b"s3cr3t"


def test_redact_without_a_key_changes_nothing(tmp_path):
    (tmp_path / "log").write_bytes(b"text")
    smoke_ci.redact(tmp_path, "")
    assert (tmp_path / "log").read_bytes() == b"text"


@pytest.fixture
def live_cell(monkeypatch):
    """`live` with its install replaced; `seen` holds each pytest command `cell` gets."""
    monkeypatch.setattr(smoke_ci, "install", lambda provider: dict(os.environ))
    monkeypatch.setenv("LADO_LIVE_API_KEY", "s3cr3t")
    return []


@pytest.mark.parametrize("code", [0, 1])
def test_a_live_cell_leaves_only_redacted_files_in_its_folder(
    code, tmp_path, monkeypatch, live_cell
):
    out = tmp_path / "out"

    def cell(tests, log, work, name, env=None, echo=True):
        live_cell.append(tests)
        assert not out.exists() or not any(out.iterdir())  # nothing there while it runs
        log.write_text("s3cr3t")
        (work / "evidence").mkdir()
        (work / "evidence" / "screen").write_text("s3cr3t")
        return code

    monkeypatch.setattr(smoke_ci, "cell", cell)
    assert smoke_ci.live("codex", out) == code
    assert live_cell[0][:4] == ["timeout", "--kill-after=30", "1500", "uv"]
    assert live_cell[0][4:] == [
        "run",
        "pytest",
        "-m",
        "live",
        "-n0",
        "-v",
        "-k",
        "codex",
        "--ignore=tests/live/test_codex_login.py",
    ]
    assert (out / "live-codex.log").read_text() == "<redacted>"
    assert (out / "evidence" / "screen").read_text() == "<redacted>"


def test_a_crash_during_the_tests_leaves_nothing_to_upload(tmp_path, monkeypatch, live_cell):
    out = tmp_path / "out"

    def cell(tests, log, work, name, env=None, echo=True):
        log.write_text("s3cr3t")
        raise OSError("killed")

    monkeypatch.setattr(smoke_ci, "cell", cell)
    with pytest.raises(OSError):
        smoke_ci.live("codex", out)
    assert not out.exists() or not any(out.iterdir())


def test_a_live_cell_whose_install_fails_is_red_and_runs_no_test(tmp_path, monkeypatch, live_cell):
    monkeypatch.setattr(smoke_ci, "install", lambda provider: None)
    monkeypatch.setattr(smoke_ci, "cell", lambda *args, **kwargs: pytest.fail("a test ran"))
    assert smoke_ci.live("codex", tmp_path / "out") == 1


@pytest.fixture
def stub_tests(tmp_path, monkeypatch):
    """The whole of `cell` in a live cell, on a stand-in for `timeout ... pytest`: the script
    given. Evidence goes under tmp_path; returns where."""

    def stub(script: str) -> Path:
        command = tmp_path / "bin" / "timeout"
        command.parent.mkdir()
        command.write_text(f"#!/bin/sh\n{script}\n")
        command.chmod(0o755)
        monkeypatch.setenv("PATH", f"{command.parent}{os.pathsep}{os.environ['PATH']}")
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
        return tmp_path / "lado-live-evidence"

    return stub


def test_a_live_cell_with_a_skip_is_red_and_keeps_its_log(tmp_path, live_cell, stub_tests):
    stub_tests("echo '====== 2 passed, 1 skipped in 9.00s ======'")
    assert smoke_ci.live("codex", tmp_path / "out") == 1
    assert "1 skipped" in (tmp_path / "out" / "live-codex.log").read_text()


def test_a_red_cell_with_a_dangling_link_keeps_its_log_and_evidence(
    tmp_path, live_cell, stub_tests
):
    """A Codex agent's auth.json links to a login the test has not: evidence keeps it so."""
    evidence = stub_tests("")
    (tmp_path / "bin" / "timeout").write_text(
        "#!/bin/sh\n"
        f"mkdir -p '{evidence}/agents/w1'\n"
        f"echo kept > '{evidence}/agents/w1/config.toml'\n"
        f"ln -s /nowhere/auth.json '{evidence}/agents/w1/auth.json'\n"
        "echo '====== 1 failed in 9.00s ======'\n"
        "exit 1\n"
    )
    assert smoke_ci.live("codex", tmp_path / "out") == 1
    assert "1 failed" in (tmp_path / "out" / "live-codex.log").read_text()
    kept = tmp_path / "out" / "evidence" / "agents" / "w1"
    assert (kept / "config.toml").read_text() == "kept\n"
    assert not (kept / "auth.json").is_symlink()


def test_evidence_that_cannot_be_copied_costs_a_cell_nothing_else(
    tmp_path, monkeypatch, live_cell, stub_tests, capsys
):
    evidence = tmp_path / "lado-live-evidence"
    stub_tests(f"mkdir -p '{evidence}'; echo '====== 1 failed in 9.00s ======'; exit 1")
    real = shutil.copytree

    def broken(source, *args, **kwargs):
        if Path(source) == evidence:
            raise shutil.Error([(str(evidence), "there", "no luck")])
        return real(source, *args, **kwargs)

    monkeypatch.setattr(shutil, "copytree", broken)
    assert smoke_ci.live("codex", tmp_path / "out") == 1
    assert "1 failed" in (tmp_path / "out" / "live-codex.log").read_text()
    assert "no luck" in capsys.readouterr().err


def test_a_torn_key_reaches_neither_the_folder_nor_the_job_s_log(
    tmp_path, monkeypatch, live_cell, stub_tests, capfd
):
    """The job's log is public too, and GitHub's mask needs the whole value."""
    monkeypatch.setenv("LADO_LIVE_API_KEY", KEY)
    evidence = stub_tests("")
    (tmp_path / "bin" / "timeout").write_text(
        "#!/bin/sh\n"
        f"echo 'E   {KEY[:20]}'\necho 'E   {KEY[20:]}'\n"
        f"mkdir -p '{evidence}/screens'\n"
        f"printf '{KEY[:20]}\\n{KEY[20:]}\\n' > '{evidence}/screens/w1.txt'\n"
        "echo '====== 1 failed in 9.00s ======'\n"
        "exit 1\n"
    )
    assert smoke_ci.live("codex", tmp_path / "out") == 1
    printed = capfd.readouterr()
    for text in (
        printed.out,
        printed.err,
        (tmp_path / "out" / "live-codex.log").read_text(),
        (tmp_path / "out" / "evidence" / "screens" / "w1.txt").read_text(),
    ):
        assert KEY[:20] not in text and KEY[20:] not in text
    assert "<redacted>" in printed.out and "1 failed" in printed.out


def test_an_unknown_provider_has_no_live_cell(capsys):
    assert smoke_ci.main(["live", "nobody", "out"]) == 2
    assert "nobody" in capsys.readouterr().err


# The pass rule (AC-6).


@pytest.mark.parametrize(
    "summary, code, passed",
    [
        ("============ 3 passed in 412.20s (0:06:52) ============", 0, True),
        ("====== 2 passed, 1 skipped in 300.00s (0:05:00) ======", 0, False),
        ("====== 3 skipped in 1.00s ======", 0, False),
        ("====== 3 deselected in 1.00s ======", 0, False),
        ("====== 1 failed, 2 passed in 600.00s ======", 1, False),
        ("============ 3 passed in 412.20s ============", 1, False),
        ("", 0, False),
    ],
)
def test_a_cell_passes_only_when_a_test_passed_none_skipped_and_pytest_exited_0(
    summary, code, passed
):
    assert smoke_ci.passed(summary, code) is passed


def test_the_summary_is_pytests_last_summary_line():
    log = (
        "tests/smoke/test_smoke.py::test_x[opencode] PASSED\n"
        "=========== short test summary info ===========\n"
        "========= 1 failed, 2 passed in 10.00s =========\n"
        "trailing noise\n"
    )
    assert smoke_ci.summary(log) == "========= 1 failed, 2 passed in 10.00s ========="
    assert smoke_ci.summary("no summary\n") == ""


# A cell's run, with npm, the CLI and uv stubbed on PATH.

# npm records its argv; an uninstall removes the CLIs. Its installs are counted: the first
# $NPM_FAILS_FIRST exit 1, and the first $CLI_BROKEN_FIRST leave a CLI that does not run, as
# when npm dropped the optional package with its binary; $NPM_FAILS fails them all.
NPM = """#!/bin/sh
printf 'npm %s\\n' "$*" >>"$CELL_RAN"
if [ "$1" = uninstall ]; then
  rm -f "$HOME/.local/bin/"*
  exit 0
fi
n=$(( $(cat "$CELL_RAN.installs" 2>/dev/null || echo 0) + 1 ))
echo "$n" >"$CELL_RAN.installs"
[ -n "$NPM_FAILS" ] && exit 1
[ "$n" -le "${NPM_FAILS_FIRST:-0}" ] && exit 1
mkdir -p "$HOME/.local/bin"
for cli in claude codex opencode kilo; do
  if [ "$n" -le "${CLI_BROKEN_FIRST:-0}" ]; then
    printf '#!/bin/sh\\necho Error: Missing optional dependency >&2\\nexit 1\\n' \\
      >"$HOME/.local/bin/$cli"
  else
    printf '#!/bin/sh\\necho %s 9.9.9\\n' "$cli" >"$HOME/.local/bin/$cli"
  fi
  chmod +x "$HOME/.local/bin/$cli"
done
"""
# uv stands in for `uv run pytest ...`: it records its argv, writes evidence as a failing
# smoke test would, prints the summary and exits with its code.
UV = """#!/bin/sh
printf 'uv %s\\n' "$*" >>"$CELL_RAN"
command -v opencode >>"$CELL_RAN"
if [ -n "$EVIDENCE_WRITES" ]; then
  mkdir -p "$TMPDIR/lado-live-evidence/20261010-test_w"
  echo "w1 never reported" >"$TMPDIR/lado-live-evidence/20261010-test_w/lado-log.txt"
fi
printf 'tests/smoke/test_smoke.py::t PASSED\\n%s\\n' "$SUMMARY"
exit "${CODE:-0}"
"""
PASSED = "============ 3 passed in 412.20s (0:06:52) ============"


def run_cell(tmp_path, provider, **env):
    """Run `smoke_ci.py run <provider> <out>` with the stubs: its process, out and the log of
    what it ran."""
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    for name, text in (("npm", NPM), ("uv", UV)):
        (stubs / name).write_text(text)
        (stubs / name).chmod(0o755)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    temp = tmp_path / "tmp"
    temp.mkdir(exist_ok=True)
    out = tmp_path / "out"
    full = {
        "PATH": f"{stubs}{os.pathsep}/usr/bin:/bin",
        "HOME": str(home),
        "TMPDIR": str(temp),
        "CELL_RAN": str(tmp_path / "ran"),
        "SUMMARY": PASSED,
        **env,
    }
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "run", provider, str(out)],
        env=full,
        capture_output=True,
        text=True,
        timeout=60,
    )
    ran = tmp_path / "ran"
    return done, out, ran.read_text() if ran.exists() else ""


def test_a_cell_installs_the_pinned_cli_then_runs_its_smoke_test(tmp_path):
    done, out, ran = run_cell(tmp_path, "opencode")
    assert done.returncode == 0, done.stdout + done.stderr
    package, version, _ = smoke_ci.PINS["opencode"]
    home = tmp_path / "home"
    assert f"npm install -g --prefix {home}/.local {package}@{version}\n" in ran
    # As `make test-smoke PROVIDER=opencode`, nothing deselected.
    assert "uv run pytest -m smoke -n0 -v -k opencode\n" in ran
    # The installed CLI is first on PATH for the tests.
    assert f"{home}/.local/bin/opencode\n" in ran
    assert "opencode 9.9.9" in done.stdout
    # The output goes to the terminal and to the cell's log.
    assert PASSED in done.stdout
    assert PASSED in (out / "smoke-opencode.log").read_text()
    assert not (out / "evidence").exists()


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_every_provider_has_a_cell(tmp_path, provider):
    done, _, ran = run_cell(tmp_path, provider)
    assert done.returncode == 0, done.stdout + done.stderr
    package, version, _ = smoke_ci.PINS[provider]
    assert f"{package}@{version}\n" in ran
    assert f"uv run pytest -m smoke -n0 -v -k {provider}\n" in ran


def test_a_cell_whose_install_fails_is_red_and_runs_no_test(tmp_path):
    done, _, ran = run_cell(tmp_path, "kilo", NPM_FAILS="1")
    assert done.returncode != 0
    assert "uv run" not in ran


# The install in up to three attempts: npm drops an optional package (a CLI's native binary)
# that failed to fetch and still exits 0.


def npm_calls(ran: str) -> list[str]:
    """What npm was asked to do, in order: `install` or `uninstall`."""
    return [line.split()[1] for line in ran.splitlines() if line.startswith("npm ")]


def warnings(done) -> list[str]:
    return [line for line in done.stdout.splitlines() if line.startswith("::warning::")]


@pytest.mark.parametrize("fails", [{"CLI_BROKEN_FIRST": "1"}, {"NPM_FAILS_FIRST": "1"}])
def test_an_install_that_failed_once_is_redone_and_the_cell_passes(tmp_path, fails):
    done, _, ran = run_cell(tmp_path, "codex", **fails)
    assert done.returncode == 0, done.stdout + done.stderr
    assert npm_calls(ran) == ["install", "uninstall", "install"]
    package, _, _ = smoke_ci.PINS["codex"]
    home = tmp_path / "home"
    assert f"npm uninstall -g --prefix {home}/.local {package}\n" in ran
    [warning] = warnings(done)
    assert warning.startswith("::warning::codex: attempt 1 of 3: "), warning
    assert warning.endswith("; reinstalling")
    assert "uv run pytest -m smoke -n0 -v -k codex\n" in ran


def test_a_cli_that_never_runs_is_red_after_three_installs(tmp_path):
    done, _, ran = run_cell(tmp_path, "codex", CLI_BROKEN_FIRST="3")
    assert done.returncode == 1
    assert npm_calls(ran) == ["install", "uninstall", "install", "uninstall", "install"]
    assert len(warnings(done)) == 2
    assert "codex --version failed after the install" in done.stderr
    assert "uv run" not in ran


def test_an_install_that_always_fails_is_red_after_three_installs(tmp_path):
    done, _, ran = run_cell(tmp_path, "kilo", NPM_FAILS="1")
    assert done.returncode == 1
    assert npm_calls(ran).count("install") == 3
    package, version, _ = smoke_ci.PINS["kilo"]
    assert f"{package}@{version} did not install" in done.stderr


def test_an_install_that_works_at_once_is_done_once_without_a_warning(tmp_path):
    done, _, ran = run_cell(tmp_path, "opencode")
    assert done.returncode == 0, done.stdout + done.stderr
    assert npm_calls(ran) == ["install"]
    assert warnings(done) == []


@pytest.mark.parametrize(
    "summary, code", [("====== 2 passed, 1 skipped in 3.00s ======", "0"), (PASSED, "1")]
)
def test_a_cell_is_red_unless_the_pass_rule_holds(tmp_path, summary, code):
    done, _, _ = run_cell(tmp_path, "kilo", SUMMARY=summary, CODE=code)
    assert done.returncode != 0


def test_a_failing_cell_keeps_its_evidence_in_out(tmp_path):
    done, out, _ = run_cell(
        tmp_path, "opencode", SUMMARY="=== 1 failed in 3.00s ===", CODE="1", EVIDENCE_WRITES="1"
    )
    assert done.returncode != 0
    kept = out / "evidence" / "20261010-test_w" / "lado-log.txt"
    assert kept.read_text() == "w1 never reported\n"


def test_evidence_of_an_earlier_run_is_cleared_first(tmp_path):
    stale = tmp_path / "tmp" / "lado-live-evidence" / "old"
    stale.mkdir(parents=True)
    done, out, _ = run_cell(tmp_path, "opencode", SUMMARY="=== 1 failed in 3.00s ===", CODE="1")
    assert done.returncode != 0
    assert not (out / "evidence" / "old").exists()


def test_an_unknown_provider_is_refused(tmp_path):
    done, _, ran = run_cell(tmp_path, "gemini")
    assert done.returncode != 0 and "gemini: no provider (one of " in done.stderr
    assert ran == ""


# The container cell (ci.yml's job `container`): the image's own CLI, nothing installed.


def run_container(tmp_path, *args, **env):
    """Run `smoke_ci.py container <out>` with the uv stub: its process, out and what it ran."""
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    (stubs / "uv").write_text(UV)
    (stubs / "uv").chmod(0o755)
    temp = tmp_path / "tmp"
    temp.mkdir(exist_ok=True)
    out = tmp_path / "out"
    full = {
        "PATH": f"{stubs}{os.pathsep}/usr/bin:/bin",
        "HOME": str(tmp_path),
        "TMPDIR": str(temp),
        "CELL_RAN": str(tmp_path / "ran"),
        "SUMMARY": PASSED,
        **env,
    }
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "container", *(args or (str(out),))],
        env=full,
        capture_output=True,
        text=True,
        timeout=60,
    )
    ran = tmp_path / "ran"
    return done, out, ran.read_text() if ran.exists() else ""


def test_the_container_cell_runs_the_container_tests_and_installs_nothing(tmp_path):
    done, out, ran = run_container(tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert ran.splitlines()[0] == "uv run pytest -m container -n0 -v"
    assert "npm" not in ran
    assert PASSED in (out / "container.log").read_text()


@pytest.mark.parametrize(
    "summary, code", [("====== 3 passed, 2 skipped in 3.00s ======", "0"), (PASSED, "1")]
)
def test_the_container_cell_is_red_unless_the_pass_rule_holds(tmp_path, summary, code):
    done, _, _ = run_container(tmp_path, SUMMARY=summary, CODE=code)
    assert done.returncode != 0
    assert "container: not passed" in done.stderr


def test_a_failing_container_cell_keeps_its_evidence(tmp_path):
    done, out, _ = run_container(
        tmp_path, SUMMARY="=== 1 failed in 3.00s ===", CODE="1", EVIDENCE_WRITES="1"
    )
    assert done.returncode != 0
    kept = out / "evidence" / "20261010-test_w" / "lado-log.txt"
    assert kept.read_text() == "w1 never reported\n"


@pytest.mark.parametrize("args", [[], ["a", "b"]])
def test_container_with_wrong_arguments_is_a_usage_error(tmp_path, args):
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "container", *args], capture_output=True, text=True
    )
    assert done.returncode == 2
    assert "container <out>" in done.stderr


# Whether a run needs the smoke (`needed`, ci.yml's job `changes`).

SKIP = "web/\ndocs/\ntests/ui/\nREADME.md\n"


@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch"])
def test_outside_a_pull_request_the_smoke_always_runs(event):
    assert smoke_ci.needed(event, [], smoke_ci.skip_list(SKIP)) is True
    assert smoke_ci.needed(event, ["docs/x.md"], smoke_ci.skip_list(SKIP)) is True


@pytest.mark.parametrize(
    "files, needed",
    [
        (["web/src/App.tsx", "docs/design/ui.md", "tests/ui/test_x.py"], False),
        (["README.md"], False),
        (["src/lado/runtime.py", "docs/design/ui.md"], True),
        (["NEW.md"], True),
        # An exact path is no folder prefix, and a folder takes only what is under it.
        (["README.md.orig"], True),
        (["webby/x"], True),
        (["tests/ui_helpers.py"], True),
        ([], True),
    ],
)
def test_a_pull_request_skips_the_smoke_only_when_every_file_is_on_the_list(files, needed):
    assert smoke_ci.needed("pull_request", files, smoke_ci.skip_list(SKIP)) is needed


@pytest.mark.parametrize("text", ["", "\n  \n"])
def test_an_empty_skip_list_is_refused(text):
    with pytest.raises(ValueError, match="empty skip list"):
        smoke_ci.skip_list(text)


def test_the_skip_list_takes_one_path_per_line_and_drops_blanks():
    assert smoke_ci.skip_list("  web/\n\nREADME.md  \n") == ["web/", "README.md"]


def git(repo, *args) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def run_needed(repo, *args, skip=SKIP):
    env = {**os.environ, "SMOKE_SKIP": skip}
    return subprocess.run(
        [sys.executable, str(SCRIPT), "needed", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture
def pr(tmp_path):
    """A repository; the test adds the base's and the pull request's commits."""
    return init_repo(tmp_path / "repo")


def commit(repo, path, text="y\n") -> str:
    file = repo / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text)
    git(repo, "add", path)
    git(repo, "commit", "-q", "-m", path)
    return git(repo, "rev-parse", "HEAD")


def test_needed_prints_false_for_a_docs_only_pull_request(pr):
    base = commit(pr, "README.md", "base\n")
    commit(pr, "docs/a.md")
    head = commit(pr, "web/src/b.tsx")
    done = run_needed(pr, "pull_request", base, head)
    assert done.returncode == 0, done.stderr
    assert done.stdout == "smoke=false\n"
    # It says why, on stderr: the files it went by.
    assert "docs/a.md" in done.stderr and "web/src/b.tsx" in done.stderr


def test_needed_prints_true_when_one_file_is_off_the_list(pr):
    base = commit(pr, "README.md", "base\n")
    commit(pr, "docs/a.md")
    head = commit(pr, "src/lado/x.py")
    done = run_needed(pr, "pull_request", base, head)
    assert done.returncode == 0, done.stderr
    assert done.stdout == "smoke=true\n"


def test_a_file_moved_from_code_into_docs_needs_the_smoke(pr):
    """A rename names both sides: the code it took away counts too."""
    commit(pr, "src/lado/x.py", "a\n" * 20)
    base = commit(pr, "README.md", "base\n")
    (pr / "docs").mkdir()
    git(pr, "mv", "src/lado/x.py", "docs/x.py")
    git(pr, "commit", "-q", "-m", "move")
    head = git(pr, "rev-parse", "HEAD")
    done = run_needed(pr, "pull_request", base, head)
    assert done.stdout == "smoke=true\n", done.stderr


def test_needed_diffs_from_the_merge_base(pr):
    """base...head: what main gained since the branch left it is not the pull request's."""
    git(pr, "checkout", "-q", "-b", "topic")
    head = commit(pr, "docs/a.md")
    git(pr, "checkout", "-q", "main")
    moved = commit(pr, "src/lado/x.py")
    done = run_needed(pr, "pull_request", moved, head)
    assert done.stdout == "smoke=false\n", done.stderr


def test_needed_outside_a_pull_request_needs_no_diff(pr):
    done = run_needed(pr, "push")
    assert done.returncode == 0, done.stderr
    assert done.stdout == "smoke=true\n"


def test_needed_fails_on_a_git_error_instead_of_answering(pr):
    done = run_needed(pr, "pull_request", "0" * 40, "1" * 40)
    assert done.returncode != 0
    assert done.stdout == ""


def test_needed_refuses_an_empty_list(pr):
    done = run_needed(pr, "push", skip="")
    assert done.returncode != 0
    assert "empty skip list" in done.stderr


@pytest.mark.parametrize("args", [[], ["pull_request"], ["pull_request", "a"], ["push", "a"]])
def test_needed_with_wrong_arguments_is_a_usage_error(pr, args):
    done = run_needed(pr, *args)
    assert done.returncode == 2
    assert "usage:" in done.stderr
