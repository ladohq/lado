import subprocess
import sys

from lado import __version__, state
from lado.cli import main


def test_version_flag_prints_version():
    result = subprocess.run(
        [sys.executable, "-m", "lado.cli", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == f"lado {__version__}"


def test_start_with_provider_and_ls_shows_it(repo, fake_tmux, capsys):
    assert main(["start", str(repo), "--name", "s", "--provider", "kilo", "--no-attach"]) == 0
    assert state.get_session("s").provider == "kilo"
    main(["ls"])
    assert "supervisor   supervisor kilo" in capsys.readouterr().out


def test_start_with_unknown_provider_fails(repo, fake_tmux, capsys):
    assert main(["start", str(repo), "--provider", "nope", "--no-attach"]) == 1
    assert 'unknown provider "nope"; known: claude, kilo' in capsys.readouterr().err


def _kit(repo, name, body="---\nname: rev\ndescription: reviews\n---\nReview.\n"):
    kit = repo / ".lado" / "kits" / name
    (kit / "agents").mkdir(parents=True)
    (kit / "kit.yaml").write_text(f"name: {name}\ndescription: about {name}\ninclude: [default]\n")
    (kit / "agents" / "rev.md").write_text(body)
    return kit


def test_start_with_kits_and_without(repo, fake_tmux):
    _kit(repo, "team")
    args = ["start", str(repo), "--name", "s", "--kit", "team", "--without", "agent:rev"]
    assert main([*args, "--no-attach"]) == 0
    sess = state.get_session("s")
    assert (sess.kits, sess.without) == (["team"], ["agent:rev"])


def test_start_with_bad_kit_fails(repo, fake_tmux, capsys):
    assert main(["start", str(repo), "--kit", "nope", "--no-attach"]) == 1
    assert 'lado: kit "nope" not found' in capsys.readouterr().err


def test_kits_lists_with_sources(repo, capsys, monkeypatch):
    kit = _kit(repo, "team")
    monkeypatch.chdir(repo)
    assert main(["kits"]) == 0
    out = capsys.readouterr().out
    assert f"team             project   {kit.resolve()}" in out
    assert "about team" in out
    assert "default          built-in" in out


def test_kits_show(repo, capsys):
    kit = _kit(repo, "team")
    assert main(["kits", "--repo", str(repo), "show", "team", "--without", "agent:worker"]) == 0
    out = capsys.readouterr().out
    assert f"team   (project: {kit.resolve()})" in out
    assert f"rev  from team: {kit.resolve()}/agents/rev.md" in out
    assert "supervisor  [supervisor]  from default" in out
    assert "  worker" not in out
    assert "Switched off: agent:worker" in out


def test_kits_check(repo, capsys, monkeypatch):
    kit = _kit(repo, "team")
    assert main(["kits", "check", str(kit)]) == 0
    assert "team: OK (3 agents and 0 skills" in capsys.readouterr().out
    monkeypatch.chdir(repo)
    assert main(["kits", "check", "team"]) == 0
    assert main(["kits", "check", "default"]) == 0
    capsys.readouterr()
    (kit / "agents" / "rev.md").write_text(
        "---\nname: rev\ndescription: d\nmodel: x\n---\nSee ~/notes.\n"
    )
    assert main(["kits", "check", str(kit)]) == 1
    assert "unknown keys model" in capsys.readouterr().err
    (kit / "agents" / "rev.md").write_text("---\nname: rev\ndescription: d\n---\nSee ~/notes.\n")
    assert main(["kits", "check", str(kit)]) == 1
    assert 'hardcoded path "~/notes."' in capsys.readouterr().err
    assert main(["kits", "check", "nope"]) == 1
