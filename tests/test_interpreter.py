"""LADO's own processes never import from the agent's cwd (interpreter.run_module)."""

import os
import subprocess
import sys

import pytest

from lado import agent_env, interpreter, mcp_exec, providers

SHADOWED = 7  # the exit code of a shadowing module


def shadow(folder, *modules: str) -> None:
    """Modules in `folder` that, once imported, leave a marker and exit."""
    for module in modules:
        (folder / f"{module}.py").write_text(
            f"open({str(folder / 'SHADOWED')!r}, 'a').write({module!r})\n"
            f"raise SystemExit({SHADOWED})\n"
        )
    (folder / "lado").mkdir()
    (folder / "lado" / "__init__.py").write_text((folder / f"{modules[0]}.py").read_text())


def run(argv: list[str], cwd, **kwargs) -> subprocess.CompletedProcess:
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, **kwargs)
    assert not (cwd / "SHADOWED").exists(), (cwd / "SHADOWED").read_text()
    assert proc.returncode != SHADOWED, proc.stderr
    return proc


def test_lado_command_does_not_import_from_its_cwd(tmp_path):
    shadow(tmp_path, "json", "argparse")
    proc = run(providers.lado_command("--version"), tmp_path)
    assert proc.returncode == 0 and proc.stdout.startswith("lado "), proc.stderr


def test_the_window_command_does_not_import_from_its_cwd(tmp_path):
    shadow(tmp_path, "json")
    argv = agent_env.command(tmp_path / "env.json", {"PATH": "/usr/bin:/bin"}, ["true"])
    proc = run(argv, tmp_path, env={})
    assert proc.returncode == 0, proc.stderr


def test_the_mcp_secrets_wrapper_does_not_import_from_its_cwd(tmp_path):
    shadow(tmp_path, "base64", "json")
    argv = mcp_exec.wrap("db", ["true"], {"T": "${A}"})
    proc = run(argv, tmp_path, env={**os.environ, "A": "1"})
    assert proc.returncode == 0, proc.stderr


def test_the_module_gets_its_arguments_as_python_m_would(tmp_path):
    script = "import sys; print(sys.argv[1:]); print(__name__)"
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "show.py").write_text(script)
    argv = interpreter.run_module("pkg.show", "a", "-b")
    proc = subprocess.run(
        argv,
        cwd=tmp_path / "pkg",
        env={**os.environ, "PYTHONPATH": str(tmp_path)},  # the user's PYTHONPATH still counts
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout == "['a', '-b']\n__main__\n"
    assert argv[0] == sys.executable


@pytest.mark.skipif(sys.version_info < (3, 11), reason="PYTHONSAFEPATH is new in 3.11")
def test_with_pythonsafepath_no_other_entry_is_dropped(tmp_path):
    (tmp_path / "found.py").write_text("print('found')")
    argv = interpreter.run_module("found")
    env = {**os.environ, "PYTHONPATH": str(tmp_path), "PYTHONSAFEPATH": "1"}
    proc = subprocess.run(argv, cwd="/", env=env, capture_output=True, text=True, check=True)
    assert proc.stdout == "found\n"
