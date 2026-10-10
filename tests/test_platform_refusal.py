import json
import subprocess
import sys

from lado import cli, console

# A fresh Python on "native Windows": termios, fcntl, pty and tty cannot be imported, and
# each attempt is recorded, as is how `lado` ended.
ON_WINDOWS = """
import json, sys
tried = []
class Posix:
    def find_spec(self, name, path=None, target=None):
        if name in ("termios", "fcntl", "pty", "tty"):
            tried.append(name)
            raise ModuleNotFoundError(f"No module named {name!r}")
sys.meta_path.insert(0, Posix())
for name in ("termios", "fcntl", "pty", "tty"):
    sys.modules.pop(name, None)
sys.platform = "win32"
from lado import console
code = console.main(sys.argv[1:])
print(json.dumps({"code": code, "tried": tried, "cli": "lado.cli" in sys.modules}))
"""


def _on_windows(*argv: str) -> tuple[dict, str]:
    done = subprocess.run(
        [sys.executable, "-c", ON_WINDOWS, *argv], capture_output=True, text=True, check=True
    )
    return json.loads(done.stdout), done.stderr


def test_native_windows_gets_one_line_pointing_to_wsl2_whatever_the_arguments():
    for argv in (["--version"], ["doctor"], []):
        ended, stderr = _on_windows(*argv)
        assert ended == {"code": 1, "tried": [], "cli": False}, argv
        assert stderr.splitlines() == [console.NATIVE_WINDOWS], argv
    assert "native Windows is not supported" in console.NATIVE_WINDOWS
    assert "WSL2" in console.NATIVE_WINDOWS


def test_another_platform_reaches_the_cli(monkeypatch):
    called = []
    monkeypatch.setattr(cli, "main", lambda argv=None: called.append(argv) or 7)
    assert console.main(["doctor"]) == 7
    assert called == [["doctor"]]


def test_the_console_script_is_the_entry_module():
    from importlib.metadata import entry_points

    (script,) = entry_points(group="console_scripts", name="lado")
    assert script.value == "lado.console:main"
