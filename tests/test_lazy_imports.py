import subprocess
import sys
from importlib.metadata import version

import lado


def _modules_after(code: str) -> set[str]:
    """The modules a fresh LADO process has loaded after `code`."""
    shown = f"{code}; import sys; print(' '.join(sys.modules))"
    done = subprocess.run([sys.executable, "-c", shown], capture_output=True, text=True, check=True)
    return set(done.stdout.split())


def test_the_version_is_the_installed_package_s():
    assert lado.__version__ == version("lado")


def test_importing_lado_and_its_hooks_does_not_read_the_package_metadata():
    """Every hook process imports them: the metadata costs 15-20 ms each time."""
    assert "importlib.metadata" not in _modules_after("import lado")
    assert "importlib.metadata" not in _modules_after("import lado.hooks")


def test_the_cli_imports_what_only_some_commands_need_in_those_commands():
    loaded = _modules_after("import lado.cli")
    lazy = {"lado.doctor", "lado.update", "lado.self_update", "lado.server", "importlib.metadata"}
    assert lazy.isdisjoint(loaded)


def test_a_lado_command_that_does_not_show_the_version_does_not_read_it(tmp_path, monkeypatch):
    """`lado hook`, `lado mcp` and `lado loop` build the whole parser, `--version` too."""
    monkeypatch.setenv("LADO_HOME", str(tmp_path))
    run_loop = "from lado import cli; cli.main(['loop', 'no-such-session'])"
    assert "importlib.metadata" not in _modules_after(run_loop)
