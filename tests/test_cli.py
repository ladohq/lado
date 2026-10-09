import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import agent_helpers
import pytest
from agent_helpers import init_repo, publish

import lado
from lado import (
    __version__,
    agent_env,
    artifacts,
    artifacts_local,
    cli,
    flows,
    gitcache,
    kits,
    marketplaces,
    runs,
    runtime,
    state,
)
from lado.cli import format_duration, main


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


def test_start_and_ls_say_what_the_supervisors_cli_asks_first(
    repo, fake_tmux, claude_config, capsys
):
    claude_config.trust()  # Claude Code trusts no folder
    why = f"Claude Code asks whether to trust {repo}"
    start = ["start", str(repo), "--name", "s", "--provider", "claude", "--no-attach"]
    assert main(start) == 0
    assert f"lado: {why}: " in capsys.readouterr().err
    main(["ls"])
    assert why in capsys.readouterr().out
    main(["stop", "s"])
    capsys.readouterr()
    assert main(start) == 0  # a resume
    assert f"lado: {why}: " in capsys.readouterr().err


def test_start_without_provider_says_which_it_took_and_why(repo, fake_tmux, capsys):
    assert main(["start", str(repo), "--name", "a", "--provider", "opencode", "--no-attach"]) == 0
    assert "provider:" not in capsys.readouterr().out  # given, not chosen
    assert main(["start", str(repo), "--name", "b", "--no-attach"]) == 0
    assert "provider: opencode (the folder's last session)" in capsys.readouterr().out


def test_start_without_provider_refuses_a_choice_it_cannot_make(repo, fake_tmux, capsys):
    assert main(["start", str(repo), "--no-attach"]) == 1
    assert "give one with --provider NAME" in capsys.readouterr().err


def test_start_help_names_no_default_provider(capsys):
    with pytest.raises(SystemExit):
        main(["start", "--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert "default: claude" not in out
    assert "without it, a new session takes its folder's last session's provider" in out


def test_ls_says_a_newer_version_is_available_but_not_why_a_check_failed(
    published, capsys, tmp_path, monkeypatch
):
    published(**{"99.0.0": "2026-10-04"})
    assert main(["ls"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "LADO 99.0.0 is available: lado update"
    (state.home() / "update-check.json").unlink()
    monkeypatch.setenv("LADO_UPDATE_INDEX", str(tmp_path / "missing.json"))
    assert main(["ls"]) == 0
    captured = capsys.readouterr()
    assert "available" not in captured.out and "missing.json" not in captured.out + captured.err


@pytest.mark.parametrize(
    "seconds, shown",
    [
        (-3, "0s"),
        (0, "0s"),
        (59, "59s"),
        (60, "1m"),
        (3599, "59m"),
        (3600, "1h00m"),
        (3 * 3600 + 5 * 60 + 59, "3h05m"),
        (86399, "23h59m"),
        (86400, "1d0h"),
        (2 * 86400 + 4 * 3600 + 3599, "2d4h"),
    ],
)
def test_duration_is_short(seconds, shown):
    assert format_duration(seconds) == shown


def test_ls_shows_how_long_each_agent_has_had_its_status(repo, fake_tmux, capsys):
    main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"])
    runtime.spawn_worker("s", "task", name="w1")
    agent_helpers.forget_tasks("s")
    with state.connect() as db:
        db.execute(
            "UPDATE events SET created_at = strftime('%Y-%m-%d %H:%M:%f', 'now', '-11105 seconds')"
            " WHERE agent = 'supervisor'"
        )
        db.execute("DELETE FROM events WHERE agent = 'w1'")
    capsys.readouterr()
    main(["ls"])
    lines = capsys.readouterr().out.splitlines()
    assert lines[1].split() == ["supervisor", "supervisor", "claude", "starting", "3h05m"]
    assert lines[2].split() == ["w1", "worker", "claude", "starting", "-", "lado/s/w1"]
    assert lines[1].index("3h05m") == lines[2].index("-")


def test_ls_says_why_an_agent_waits_after_failed_messages(repo, fake_tmux, capsys):
    main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"])
    runtime.spawn_worker("s", "task", name="w1")
    agent_helpers.forget_tasks("s")
    state.set_status("s", "supervisor", state.IDLE)
    runtime.send_message("s", "w1", "supervisor", "report")
    at = state.list_messages("s")[0].sent_at
    for delay in runtime.RETRY_DELAYS + runtime.RETRY_DELAYS[-1:]:
        at += delay
        runtime.sweep("s", now=at)
    capsys.readouterr()
    main(["ls"])
    lines = capsys.readouterr().out.splitlines()
    assert lines[1].split()[:4] == ["supervisor", "supervisor", "claude", "waiting"]
    assert lines[2] == (
        "    waiting: did not take 1 message: answer the dialog in its window "
        "or type any line there"
    )


def test_ls_says_why_an_agent_stopped(repo, fake_tmux, capsys):
    main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"])
    runtime.spawn_worker("s", "task", name="w1")
    agent_helpers.forget_tasks("s")
    runtime.agent_ended("s", "w1", "its CLI exited")
    capsys.readouterr()
    main(["ls"])
    lines = capsys.readouterr().out.splitlines()
    assert lines[2].split()[:4] == ["w1", "worker", "claude", "stopped"]
    assert lines[3] == "    stopped: its CLI exited"


def test_finish_ends_a_worker(repo, fake_tmux, capsys):
    main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"])
    worker = runtime.spawn_worker("s", "task", name="w1")
    (Path(worker.cwd) / "x.txt").write_text("x")
    assert main(["finish", "s", "w1"]) == 1
    assert 'lado: worker "w1" has uncommitted changes' in capsys.readouterr().err
    assert main(["finish", "s", "w1", "--discard"]) == 0
    out = capsys.readouterr().out
    finished = 'Finished worker "w1" (discarded; 1 message dropped): removed window, worktree'
    assert f"{finished} {worker.cwd}" in out  # the message: its task
    assert "branch lado/s/w1" in out
    assert state.get_agent("s", "w1") is None


def test_start_with_unknown_provider_fails(repo, fake_tmux, capsys):
    assert main(["start", str(repo), "--provider", "nope", "--no-attach"]) == 1
    assert (
        'unknown provider "nope"; known: claude, codex, kilo, opencode' in capsys.readouterr().err
    )


def test_start_in_a_repository_without_commits_fails(tmp_path, fake_tmux, capsys):
    empty = tmp_path / "empty"
    subprocess.run(["git", "init", "-q", str(empty)], check=True)
    assert main(["start", str(empty), "--no-attach"]) == 1
    assert f"{empty} has no commits yet: make a first commit, then start" in (
        capsys.readouterr().err
    )


def test_start_help_lists_each_providers_permission_modes(capsys):
    with pytest.raises(SystemExit):
        main(["start", "--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert "kilo: default, acceptEdits, bypassPermissions, plan" in out
    assert "opencode: default, acceptEdits, bypassPermissions, plan" in out
    assert "claude: " in out and "dontAsk" in out


def test_start_with_a_mode_the_provider_cannot_honour_fails(repo, fake_tmux, capsys):
    args = ["start", str(repo), "--provider", "kilo", "--permission-mode", "dontAsk"]
    assert main([*args, "--no-attach"]) == 1
    assert '"dontAsk" is not supported by Kilo CLI (kilo)' in capsys.readouterr().err
    assert fake_tmux == []


def _kit(repo, name, body="---\nname: rev\ndescription: reviews\n---\nReview.\n"):
    kit = repo / ".lado" / "kits" / name
    (kit / "agents").mkdir(parents=True)
    (kit / "kit.yaml").write_text(f"name: {name}\nversion: 1.0.0\ndescription: about {name}\n")
    (kit / "agents" / "rev.md").write_text(body)
    return kit


def test_start_with_kits_and_without(repo, fake_tmux):
    _kit(repo, "team")
    args = ["start", str(repo), "--provider", "claude", "--name", "s", "--kit", "default"]
    args += ["--kit", "team"]
    assert main([*args, "--without", "agent:rev", "--no-attach"]) == 0
    sess = state.get_session("s")
    assert (sess.kits, sess.without) == (["default", "team"], ["agent:rev"])


def test_start_says_who_leads_and_which_supervisor_is_not_used(repo, fake_tmux, capsys):
    kit = _kit(repo, "team")
    (kit / "kit.yaml").write_text("name: team\nversion: 1.0.0\nsupervisor: rev\n")
    assert (
        main(
            [
                "start",
                str(repo),
                "--provider",
                "claude",
                "--name",
                "s",
                "--kit",
                "team",
                "--no-attach",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "lead: rev of kit team\n" in captured.out and captured.err == ""
    assert main(["stop", "s"]) == 0
    capsys.readouterr()
    # A resume with one more kit that has a supervisor.
    args = [
        "start",
        str(repo),
        "--provider",
        "claude",
        "--name",
        "s",
        "--kit",
        "default",
        "--kit",
        "team",
    ]
    assert main([*args, "--no-attach"]) == 0
    captured = capsys.readouterr()
    assert (
        "lead: LADO's built-in supervisor (kits default and team each have a supervisor)\n"
        in captured.out
    )
    assert (
        "lado: kit team's supervisor does not lead (several kits have a supervisor): its "
        "prompt is the built-in supervisor's skill lead-team; to make it the lead, switch the "
        "others off: --without agent:supervisor@default\n"
    ) in captured.err
    assert "lado: kit team's supervisor lists no skills: its lead skill carries none\n" in (
        captured.err
    )
    assert "lado: kit default's supervisor leads as LADO's built-in supervisor" in captured.err


def test_start_with_bad_kit_fails(repo, fake_tmux, capsys):
    assert main(["start", str(repo), "--provider", "claude", "--kit", "nope", "--no-attach"]) == 1
    assert 'lado: kit "nope" not found' in capsys.readouterr().err


def test_kits_lists_where_each_kit_is(repo, capsys, monkeypatch, tmp_path, lado_home):
    kit = _kit(repo, "team")
    (kit / "kit.yaml").write_text(
        "name: team\nversion: 1.0.0\ndescription: about team\ndependencies:\n  skills:\n"
        "    a: https://example.com/a.git@v1\n    b: https://example.com/b.git@v1\n"
    )
    local = _kit(tmp_path / "dev", "mine")
    solo = "name: solo\nversion: 1.0.0\n"
    url = publish(init_repo(tmp_path / "solo"), {"kit.yaml": solo}, tag="v1.0.0")
    market = publish(
        init_repo(tmp_path / "market"), {"marketplace.yaml": f"kits:\n  solo: {url}\n"}
    )
    assert main(["marketplaces", "add", "ours", market]) == 0
    assert main(["kits", "add", str(local)]) == 0
    assert main(["kits", "add", "solo", "-m", "ours", "--yes"]) == 0
    gone = _kit(tmp_path / "gone", "gone")
    assert main(["kits", "add", str(gone)]) == 0
    shutil.rmtree(tmp_path / "gone")
    capsys.readouterr()
    monkeypatch.chdir(repo)
    assert main(["kits"]) == 0
    captured = capsys.readouterr()
    out = captured.out
    assert (
        f"team             project   {kit}\n  1.0.0    about team; 2 packs not fetched yet" in out
    )
    assert f"mine             user      {local.resolve()}\n  1.0.0" in out
    # The marketplace it was added from is its row's.
    clone = gitcache.clone_dir(url, "v1.0.0")
    assert f"solo             user      {clone}  from {url}@v1.0.0 (marketplace ours)\n" in out
    assert f'gone             user      {gone.resolve()}\n  invalid: kit "gone": its folder ' in out
    assert "default          built-in" in out
    assert captured.err == ""
    # Nothing was fetched for the list.
    assert not (lado_home / "cache" / "a").exists()
    # A marketplace removed: its kits stay, and name it.
    assert main(["marketplaces", "remove", "ours"]) == 0
    assert main(["kits"]) == 0
    assert f"{clone}  from {url}@v1.0.0 (marketplace ours, removed)\n" in capsys.readouterr().out
    # LADO_HOME/kits of an older LADO is named, with what to do.
    (lado_home / "kits").mkdir()
    (lado_home / "kits" / "mine").symlink_to(local)
    assert main(["kits"]) == 0
    assert capsys.readouterr().err == (
        f"lado: {lado_home / 'kits'} is no longer read: installed kits are kept in lado.db; "
        f"add them again:\n  lado kits add {local.resolve()}\nthen delete {lado_home / 'kits'}\n"
    )


def test_kits_show(repo, capsys):
    kit = _kit(repo, "team")
    args = ["kits", "--repo", str(repo), "show", "default", "team", "--without", "agent:worker"]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert f"team 1.0.0  (project: {kit.resolve()})" in out
    assert f"rev  from team: {kit.resolve()}/agents/rev.md" in out
    assert out.startswith("lead: supervisor of kit default\nKits:\n")
    assert "  supervisor  [lead]  from default" in out
    assert "  worker" not in out
    assert "Switched off: agent:worker" in out


def test_kits_show_lists_the_lead_skills_of_supervisors_that_do_not_lead(repo, capsys):
    body = (
        "---\nname: rev\ndescription: reviews\nskills: [notes]\n"
        "mcp: {db: {command: [db]}}\n---\nReview.\n"
    )
    kit = _kit(repo, "team", body)
    (kit / "kit.yaml").write_text("name: team\nversion: 1.0.0\nsupervisor: rev\n")
    (kit / "skills" / "notes").mkdir(parents=True)
    (kit / "skills" / "notes" / "SKILL.md").write_text("---\nname: notes\ndescription: n\n---\n")
    assert main(["kits", "--repo", str(repo), "show", "default", "team"]) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith(
        "lead: LADO's built-in supervisor (kits default and team each have a supervisor)\n"
    )
    assert "warning: kit default's supervisor leads as LADO's built-in supervisor" in captured.err
    assert "warning: kit team's supervisor does not lead" in captured.err
    assert "warning: MCP servers of kit team's supervisor (db) are not available" in captured.err
    assert (
        "Lead skills of LADO's built-in supervisor:\n"
        f"  lead-team  from team: {kit.resolve()}/agents/rev.md\n"
        "    skills: notes (team)\n"
        "    mcp not available: db\n"
    ) in captured.out


def test_kits_show_lists_each_version_of_a_skill(tmp_path, repo, capsys):
    work = init_repo(tmp_path / "pack")
    skill = "skills/tdd/SKILL.md"
    url = publish(work, {skill: "---\nname: tdd\ndescription: t\n---\n"}, tag="v1")
    publish(work, {skill: "---\nname: tdd\ndescription: t2\n---\n"}, tag="v2")
    for name, ref in (("one", "v1"), ("two", "v2")):
        kit = _kit(repo, name)
        (kit / "kit.yaml").write_text(
            f"name: {name}\nversion: 1.0.0\ndependencies:\n  skills:\n    sp: {url}@{ref}\n"
        )
        (kit / "agents" / "rev.md").write_text(f"---\nname: rev-{name}\ndescription: d\n---\n")
        (kit / "agents" / "rev.md").rename(kit / "agents" / f"rev-{name}.md")
    assert main(["kits", "--repo", str(repo), "show", "default", "one", "two"]) == 0
    skills = capsys.readouterr().out.split("Skills:\n", 1)[1]
    for name, ref in (("one", "v1"), ("two", "v2")):
        folder = gitcache.clone_dir(url, ref).resolve() / "skills" / "tdd"
        assert f"  tdd  from sp@{ref} ({name}) (project): {folder}\n" in skills


def test_kits_show_names_packs_and_where_each_skill_comes_from(tmp_path, repo, capsys):
    url = publish(
        init_repo(tmp_path / "pack"),
        {"skills/tdd/SKILL.md": "---\nname: tdd\ndescription: test first\n---\n"},
        tag="v1",
    )
    kit = _kit(repo, "team")
    (kit / "kit.yaml").write_text(
        f"name: team\nversion: 1.0.0\ndependencies:\n  skills:\n    sp: {url}@v1\n"
    )
    (kit / "skills" / "notes").mkdir(parents=True)
    (kit / "skills" / "notes" / "SKILL.md").write_text("---\nname: notes\ndescription: n\n---\n")
    shared = repo / ".lado" / "kits" / "shared"
    (shared / "skills" / "plan").mkdir(parents=True)
    (shared / "kit.yaml").write_text(
        "name: shared\nversion: 1.0.0\ndependencies:\n  skills:\n    lp: ../../lp\n"
    )
    (shared / "skills" / "plan" / "SKILL.md").write_text("---\nname: plan\ndescription: p\n---\n")
    (repo / ".lado" / "lp" / "skills" / "grill").mkdir(parents=True)
    (repo / ".lado" / "lp" / "skills" / "grill" / "SKILL.md").write_text(
        "---\nname: grill\ndescription: g\n---\n"
    )
    assert main(["kits", "--repo", str(repo), "show", "default", "team", "shared"]) == 0
    out = capsys.readouterr().out
    clone = gitcache.clone_dir(url, "v1").resolve()
    assert f"    pack sp: {url}@v1  {clone}" in out
    assert f"    pack lp: ../../lp  {(repo / '.lado' / 'lp').resolve()}" in out
    assert "    shares its packs with the session (no agents)" in out
    assert (
        "    skills (all): notes (team), plan (shared), grill (lp (shared)), tdd (sp@v1 (team))"
    ) in out
    assert "    skills (all): notes (team), plan (shared), grill (lp (shared))\n" in out


def test_kits_check(repo, capsys, monkeypatch):
    kit = _kit(repo, "team")
    assert main(["kits", "check", str(kit)]) == 0
    assert "team: OK (1 agents, 0 skills, 0 packs and 0 flows)" in capsys.readouterr().out
    monkeypatch.chdir(repo)
    assert main(["kits", "check", "team"]) == 0
    assert main(["kits", "check", "default"]) == 0
    assert main(["kits", "check", "team", "--tag", "v1.0.0"]) == 0
    assert main(["kits", "check", "team", "--tag", "v2.0.0"]) == 1
    assert "team@v2.0.0: kit.yaml says version 1.0.0" in capsys.readouterr().err
    (kit / "agents" / "rev.md").write_text(
        "---\nname: rev\ndescription: d\nmodel: x\n---\nSee ~/notes.\n"
    )
    assert main(["kits", "check", str(kit)]) == 1
    assert "unknown keys model" in capsys.readouterr().err
    (kit / "agents" / "rev.md").write_text("---\nname: rev\ndescription: d\n---\nSee ~/notes.\n")
    assert main(["kits", "check", str(kit)]) == 1
    assert 'hardcoded path "~/notes."' in capsys.readouterr().err
    assert main(["kits", "check", "nope"]) == 1


def test_kits_check_tag(tmp_path, capsys):
    """A kit's CI: `lado kits check . --tag "$TAG"` says what `lado kits add <url>@<tag>` would."""
    kit = tmp_path / "team"
    kit.mkdir()
    (kit / "kit.yaml").write_text("name: team\nversion: 1.2.0\n")
    assert main(["kits", "check", str(kit), "--tag", "v1.2.0"]) == 0
    assert "team: OK" in capsys.readouterr().out
    for tag, error in {
        "": f"{kit}@: a kit is pinned by its version tag vX.Y.Z",  # CI's $TAG unset
        "1.2.0": f"{kit}@1.2.0: a kit is pinned by its version tag vX.Y.Z",
        "v1.3.0": f"{kit}@v1.3.0: kit.yaml says version 1.2.0; the tag and kit.yaml must agree",
    }.items():
        assert main(["kits", "check", str(kit), "--tag", tag]) == 1
        err = capsys.readouterr().err
        assert err.startswith(error) and err.count("\n") == 1
    old = tmp_path / "old"
    _kit(old, "team")  # old/.lado/kits/team: no kit.yaml at the root of .lado
    assert main(["kits", "check", str(old / ".lado"), "--tag", "v1.0.0"]) == 1
    assert "kits in kits/<name>/ are no longer supported" in capsys.readouterr().err
    assert main(["kits", "check", str(old / ".lado" / "kits" / "team")]) == 0  # as before
    (kit / "kit.yaml").write_text('name: team\nversion: 1.2.0\ndependencies:\n  lado: ">=99.1"\n')
    for extra in (["--tag", "v1.2.0"], []):
        assert main(["kits", "check", str(kit), *extra]) == 1
        assert capsys.readouterr().err == (
            f"team 1.2.0 needs LADO 99.1, this is {__version__}; upgrade LADO\n"
        )
    with pytest.raises(SystemExit):
        main(["kits", "check", "--help"])
    assert "--tag vX.Y.Z" in capsys.readouterr().out


def team_repo(tmp_path, *versions, agent=None):
    """A kit "team" with a tag v<version> for each version: (work repo, URL)."""
    work = init_repo(tmp_path / "team")
    url = ""
    for version in versions:
        files = {"kit.yaml": f"name: team\nversion: {version}\n"}
        if agent:
            files["agents/w.md"] = agent
        url = publish(work, files, tag=f"v{version}")
    return work, url


def tty(monkeypatch, answer: str | None):
    """stdin a terminal where the human types `answer`, or a pipe for None."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: answer is not None)
    monkeypatch.setattr("builtins.input", lambda prompt: print(prompt, end="") or answer)


def test_kits_add_from_git_shows_the_plan_and_asks(tmp_path, capsys, lado_home, monkeypatch):
    mcp = "---\nname: w\ndescription: d\nmcp: {db: {command: [db-server, --ro]}}\n---\n"
    work, url = team_repo(tmp_path, "1.0.0", agent=mcp)
    commit = gitcache.commit(gitcache.fetch_pinned(url, "v1.0.0"))
    tty(monkeypatch, None)
    assert main(["kits", "add", url]) == 1
    captured = capsys.readouterr()
    assert captured.out == (
        f"Kit team 1.0.0 from git: {url}\n"
        f"  version v1.0.0, commit {commit}\n"
        "  MCP servers it starts: db (db-server --ro)\n"
    )
    assert captured.err == "lado: not installed: confirm with --yes\n"
    assert state.list_kits() == []
    tty(monkeypatch, "n")
    assert main(["kits", "add", url]) == 1
    assert capsys.readouterr().out.endswith("Install? [y/N] Not installed.\n")

    def end_of_input(prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", end_of_input)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    assert main(["kits", "add", url]) == 1  # Ctrl-D: no traceback
    assert capsys.readouterr().out.endswith("\nNot installed.\n")
    assert state.list_kits() == []
    tty(monkeypatch, "y")
    assert main(["kits", "add", url]) == 0
    clone = gitcache.clone_dir(url, "v1.0.0").resolve()
    assert f'Added kit "team" 1.0.0: installed, in {clone}\n' in capsys.readouterr().out
    assert [k.name for k in state.list_kits()] == ["team"]
    assert not (lado_home / "kits").exists()
    # With --yes, too, the plan says what was installed.
    assert main(["kits", "remove", "team"]) == 0
    assert capsys.readouterr().out == (
        f'Removed kit "team" (was in {gitcache.clone_dir(url, "v1.0.0")}); the folder stays\n'
    )
    assert main(["kits", "add", url, "--yes"]) == 0
    assert capsys.readouterr().out.startswith(
        f"Kit team 1.0.0 from git: {url}\n  version v1.0.0, commit {commit}\n"
    )


def test_kits_add_of_the_official_marketplace_and_a_folder_does_not_ask(
    tmp_path, capsys, lado_home, monkeypatch
):
    _, url = team_repo(tmp_path, "1.0.0")
    official = publish(
        init_repo(tmp_path / "official"), {"marketplace.yaml": f"kits:\n  team: {url}\n"}
    )
    monkeypatch.setattr(marketplaces, "OFFICIAL_URL", official)
    tty(monkeypatch, None)
    assert main(["kits", "add", "team", "-m", "official"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"Kit team 1.0.0 from official: {url}\n  version v1.0.0, commit ")
    assert 'Added kit "team" 1.0.0 (official)' in out
    assert main(["kits", "remove", "team"]) == 0
    capsys.readouterr()
    folder = _kit(tmp_path / "dev", "team")
    assert main(["kits", "add", str(folder)]) == 0
    out = capsys.readouterr().out
    assert out.startswith(
        f"Kit team 1.0.0 from folder: {folder.resolve()}\n  MCP servers it starts: none\n"
    )
    assert 'Added kit "team" 1.0.0 (folder)' in out
    assert main(["kits", "remove", "team"]) == 0
    other = publish(init_repo(tmp_path / "other"), {"marketplace.yaml": f"kits:\n  team: {url}\n"})
    assert main(["marketplaces", "add", "other", other]) == 0
    assert main(["kits", "add", "team@v1.0.0", "-m", "other"]) == 1
    assert "lado: not installed: confirm with --yes" in capsys.readouterr().err
    assert main(["kits", "add", "team@v1.0.0", "-m", "other", "--yes"]) == 0
    assert 'Added kit "team" 1.0.0 (marketplace other)' in capsys.readouterr().out


def test_kits_update_does_not_ask_and_warns_about_new_mcp_servers(
    tmp_path, capsys, lado_home, monkeypatch
):
    work, url = team_repo(tmp_path, "1.0.0")
    assert main(["kits", "add", url, "--yes"]) == 0
    agent = "---\nname: w\ndescription: d\nmcp: {db: {command: [db-server]}}\n---\n"
    publish(work, {"kit.yaml": "name: team\nversion: 1.1.0\n", "agents/w.md": agent}, "v1.1.0")
    capsys.readouterr()
    tty(monkeypatch, None)
    assert main(["kits", "update", "team"]) == 0
    captured = capsys.readouterr()
    new = gitcache.clone_dir(url, "v1.1.0").resolve()
    commit = gitcache.commit(new)
    assert captured.out.startswith(
        f"Kit team 1.1.0 from git: {url}\n  version v1.1.0, commit {commit}\n"
        "  MCP servers it starts: db (db-server)\n"
    )
    assert f'Updated kit "team" from v1.0.0 to v1.1.0: installed, in {new}\n' in captured.out
    assert "running sessions get v1.1.0 for new agents only" in captured.out
    assert (
        "lado: WARNING: team v1.1.0 starts an MCP server v1.0.0 did not: db (db-server)\n"
    ) in captured.err
    assert main(["kits", "update", "team"]) == 0
    assert capsys.readouterr().out == 'Kit "team" is at v1.1.0 already.\n'
    assert main(["kits", "update", "team", "v1.0.0"]) == 0
    assert state.get_kit("team").tag == "v1.0.0"


def _sessions_using(tmp_path, monkeypatch, kit, **statuses):
    """Sessions named by `statuses` (name -> runtime.SessionStatus) whose kits name `kit`."""
    for name in statuses:
        state.add_session(state.Session(name, str(tmp_path), None, kits=[kit], provider="claude"))
    monkeypatch.setattr(runtime, "session_status", lambda sess: statuses[sess.name])


def test_kits_update_and_remove_name_the_sessions_that_use_the_kit(
    tmp_path, capsys, lado_home, monkeypatch
):
    _, url = team_repo(tmp_path, "1.0.0", "1.1.0")
    assert main(["kits", "add", f"{url}@v1.0.0", "--yes"]) == 0
    status = runtime.SessionStatus
    _sessions_using(tmp_path, monkeypatch, "team", a=status.RUNNING, b=status.STOPPED)
    capsys.readouterr()
    assert main(["kits", "update", "team"]) == 0
    assert "running session a gets v1.1.0 for new agents only\n" in capsys.readouterr().out
    assert main(["kits", "remove", "team"]) == 0
    assert capsys.readouterr().err == (
        'lado: WARNING: running session a uses kit "team": its new agents and flow runs fail '
        "to start until it is added again; the agents running now keep working\n"
        'lado: WARNING: stopped session b uses kit "team" too: a resume needs it\n'
    )


def test_marketplaces_remove_names_the_installed_kits_that_stay(tmp_path, capsys, lado_home):
    _, url = team_repo(tmp_path, "1.0.0")
    market = publish(init_repo(tmp_path / "ours"), {"marketplace.yaml": f"kits:\n  team: {url}\n"})
    assert main(["marketplaces", "add", "ours", market]) == 0
    assert main(["kits", "add", "team", "-m", "ours", "--yes"]) == 0
    capsys.readouterr()
    assert main(["marketplaces", "remove", "ours"]) == 0
    assert capsys.readouterr().out == (
        'Removed marketplace "ours"; 1 kit installed from it stays: team\n'
    )


def test_kits_outdated(tmp_path, capsys, lado_home):
    work, url = team_repo(tmp_path, "1.0.0")
    assert main(["kits", "add", url, "--yes"]) == 0
    publish(work, {"kit.yaml": "name: team\nversion: 1.1.0\n"}, "v1.1.0")
    publish(work, {"kit.yaml": "name: team\nversion: 1.2.0-rc.1\n"}, "v1.2.0-rc.1")
    assert main(["kits", "add", str(_kit(tmp_path / "dev", "mine"))]) == 0
    # The tag of the installed version is moved.
    git = ["git", "-C", str(work)]
    subprocess.run([*git, "tag", "-f", "v1.0.0", "v1.1.0"], check=True, capture_output=True)
    subprocess.run([*git, "push", "-q", "-f", url, "v1.0.0"], check=True, capture_output=True)
    capsys.readouterr()
    assert main(["kits", "outdated"]) == 0
    captured = capsys.readouterr()
    assert captured.out == (
        "mine             -          local, not checked\n"
        "team             v1.0.0     latest v1.1.0  pre: v1.2.0-rc.1\n"
    )
    assert captured.err.startswith("lado: WARNING: tag v1.0.0 of ")


def test_kits_add_refusals(tmp_path, capsys, lado_home):
    _, url = team_repo(tmp_path, "1.0.0")
    assert main(["kits", "add", "lado-dev"]) == 1
    assert "for a kit of a marketplace add -m <marketplace>" in capsys.readouterr().err
    assert main(["kits", "add", "lado-dev", "-m", "nowhere"]) == 1
    assert 'lado: no marketplace "nowhere"; lado marketplaces lists them' in (
        capsys.readouterr().err
    )
    assert main(["kits", "add", f"{url}@main", "--yes"]) == 1
    assert "a kit is pinned by its version tag vX.Y.Z" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["kits", "add", url, "--kit", "team"])  # --kit is gone
    assert "unrecognized arguments: --kit team" in capsys.readouterr().err
    assert main(["kits", "add", url, "--yes"]) == 0
    assert main(["kits", "add", url, "--yes"]) == 1
    assert 'kit "team" is installed already' in capsys.readouterr().err


def test_marketplaces_commands(tmp_path, capsys, lado_home, monkeypatch):
    monkeypatch.setattr(marketplaces, "OFFICIAL_URL", "file:///nowhere/official.git")
    work = init_repo(tmp_path / "ours")
    market = publish(work, {"marketplace.yaml": "kits:\n  a: https://example.com/a.git\n"})
    assert main(["marketplaces"]) == 0
    assert capsys.readouterr().out == (
        "official  enabled   file:///nowhere/official.git  updated never\n"
    )
    assert main(["marketplaces", "add", "ours", market]) == 0
    assert capsys.readouterr().out == f'Added marketplace "ours": {market} (1 kit)\n'
    assert main(["marketplaces", "disable", "ours"]) == 0
    assert main(["marketplaces", "list"]) == 0
    assert f"ours      disabled  {market}  updated 20" in capsys.readouterr().out
    assert main(["marketplaces", "enable", "ours"]) == 0
    publish(
        work, {"marketplace.yaml": "kits:\n  a: https://e.com/a.git\n  b: https://e.com/b.git\n"}
    )
    capsys.readouterr()
    assert main(["marketplaces", "update", "ours"]) == 0
    assert capsys.readouterr().out == 'Updated marketplace "ours" (2 kits)\n'
    # Each enabled one: the official one is not there, the others are updated all the same.
    assert main(["marketplaces", "update"]) == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("lado: official: cannot clone file:///nowhere/official.git")
    assert captured.out == 'Updated marketplace "ours" (2 kits)\n'
    assert main(["marketplaces", "remove", "official"]) == 1
    err = capsys.readouterr().err
    assert err == (
        "lado: the official marketplace cannot be removed; disable it: "
        "lado marketplaces disable official\n"
    )
    assert main(["marketplaces", "remove", "ours"]) == 0
    assert capsys.readouterr().out == 'Removed marketplace "ours"; kits installed from it stay\n'


def test_kits_add_update_remove(tmp_path, repo, capsys, lado_home):
    _, url = team_repo(tmp_path, "1.0.0", "1.1.0")
    assert main(["kits", "add", f"{url}@v1.0.0", "--yes"]) == 0
    capsys.readouterr()
    assert main(["kits", "update", "team", "v1.1.0"]) == 0
    new = gitcache.clone_dir(url, "v1.1.0")
    capsys.readouterr()
    assert main(["kits", "remove", "team"]) == 0
    assert capsys.readouterr().out == f'Removed kit "team" (was in {new}); the folder stays\n'
    assert state.list_kits() == [] and new.is_dir()
    assert main(["kits", "remove", "team"]) == 1
    assert 'no kit "team" is installed' in capsys.readouterr().err
    # A kit whose folder is gone is removed all the same.
    gone = _kit(tmp_path / "dev", "gone")
    assert main(["kits", "add", str(gone)]) == 0
    shutil.rmtree(gone)
    capsys.readouterr()
    assert main(["kits", "remove", "gone"]) == 0
    assert capsys.readouterr().out == (
        f'Removed kit "gone" (was in {gone.resolve()}, a folder no longer there)\n'
    )


def test_kits_check_fetches_packs_and_warns_about_a_version(tmp_path, repo, capsys):
    pack = publish(
        init_repo(tmp_path / "pack"),
        {"skills/tdd/SKILL.md": "---\nname: tdd\ndescription: test first\n---\n"},
        tag="v1",
    )
    files = {
        "kit.yaml": f"name: team\nversion: 1.0.0\ndependencies:\n  skills:\n    p: {pack}@v1\n"
    }
    work = init_repo(tmp_path / "team")
    url = publish(work, files, tag="v2.0.0")
    # Pinned to a commit by an older LADO, which did not check the version.
    commit = gitcache.commit(work)
    (repo / ".lado" / "kits").mkdir(parents=True)
    (repo / ".lado" / "kits" / "team").symlink_to(gitcache.fetch_pinned(url, commit))
    assert main(["kits", "--repo", str(repo), "check", "team"]) == 0
    captured = capsys.readouterr()
    assert f"warning: team: version 1.0.0 in kit.yaml, but {url}@{commit} is at v2.0.0" in (
        captured.err
    )
    assert "team: OK (0 agents, 1 skills, 1 packs and 0 flows)" in captured.out


def test_sources_yaml_gets_a_warning_and_sources_is_gone(repo, capsys, fake_tmux, lado_home):
    lado_home.mkdir(exist_ok=True)
    (lado_home / "sources.yaml").write_text(
        "sources:\n- {name: dev, kind: path, location: /nowhere/dev}\n"
    )
    hint = f"{lado_home / 'sources.yaml'} is no longer read"
    for command in (
        ["kits"],
        ["doctor"],
        ["start", str(repo), "--provider", "claude", "--no-attach"],
        # A kit not found says it in its error: once, not twice.
        ["start", str(repo), "--provider", "claude", "--name", "t", "--kit", "mine", "--no-attach"],
    ):
        main(command)
        err = capsys.readouterr().err
        assert err.count(hint) == 1, (command, err)
        assert "  dev: /nowhere/dev is gone; nothing to move" in err
    assert main(["sources", "add", "x"]) == 1
    assert f"{lado_home / 'sources.yaml'} is no longer read" in capsys.readouterr().err
    (lado_home / "sources.yaml").unlink()
    assert main(["sources"]) == 1
    err = capsys.readouterr().err
    assert "lado sources is gone: install kits with `lado kits add" in err
    assert main(["kits"]) == 0
    assert "no longer read" not in capsys.readouterr().err


SHIP = """\
name: ship
description: build and ship
start: build
states:
  build: {agent: rev, do: Build it., outcomes: {done: check}}
  check: {gate: approval, ask: 'Ship it?', outcomes: {approved: end, rejected: build}}
  end: {end: true}
"""


def _session_with_run(repo):
    kit = _kit(repo, "team")
    (kit / "flows").mkdir()
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    main(
        [
            "start",
            str(repo),
            "--provider",
            "claude",
            "--name",
            "s",
            "--kit",
            "default",
            "--kit",
            "team",
            "--no-attach",
        ]
    )
    return runs.start("s", "ship", "Add x", name="x")


def test_ls_shows_open_runs_with_who_acts(repo, fake_tmux, capsys):
    _session_with_run(repo)
    capsys.readouterr()
    main(["ls"])
    lines = capsys.readouterr().out.splitlines()
    assert lines[-1].split() == ["run", "ship/x", "build", "→", "rev", "(not", "spawned)", "0s"]
    runs.force("s", "ship/x", "check", "skip the build")
    main(["ls"])
    run, gate = capsys.readouterr().out.splitlines()[-2:]
    assert run.split()[:8] == ["run", "ship/x", "check", "waiting", "for", "human:", "gate", "#1"]
    assert gate == "    gate #1 waiting: Ship it?"
    runs.answer("s", "1", "reject")
    main(["ls"])
    assert "gate #1" not in capsys.readouterr().out


def test_ls_shows_a_run_whose_flow_cannot_be_read_and_goes_on(repo, fake_tmux, capsys):
    _session_with_run(repo)
    runs.start("s", "ship", "Add y", name="y")
    agent_helpers.spoil_snapshot("s", "ship/x", "{not json")
    capsys.readouterr()
    assert main(["ls"]) == 0
    x, y = capsys.readouterr().out.splitlines()[-2:]
    assert x.startswith("  run ship/x  build  its flow snapshot is not JSON: Expecting")
    assert y.split()[:5] == ["run", "ship/y", "build", "→", "rev"]
    runs.force("s", "ship/y", "check", "built by hand")  # waits at gate #1
    agent_helpers.spoil_snapshot("s", "ship/y", "[]")
    assert main(["ls"]) == 0
    y, gate = capsys.readouterr().out.splitlines()[-2:]
    # Its gate cannot be answered without the flow: the problem shows here too.
    assert y.startswith("  run ship/y  check  its flow snapshot is not a mapping  ")
    assert gate == "    gate #1 waiting: Ship it?"


def test_the_human_cannot_move_a_run_whose_flow_cannot_be_read(repo, fake_tmux, capsys):
    _session_with_run(repo)
    runs.force("s", "ship/x", "check", "built by hand")
    agent_helpers.spoil_snapshot("s", "ship/x", "{not json")
    capsys.readouterr()
    for argv in (
        ["answer", "s", "1", "approve"],
        ["flow-set", "s", "ship/x", "build", "--reason", "r"],
    ):
        assert main(argv) == 1
        err = capsys.readouterr().err
        assert err.startswith('lado: run "ship/x": its flow snapshot is not JSON: ')
        assert "Traceback" not in err
    assert state.open_gate("s", "ship/x").answer is None  # the gate is still open


def _at_gate(repo, capsys):
    _session_with_run(repo)
    runs.force("s", "ship/x", "check", "built by hand")
    capsys.readouterr()


def test_answer_with_all_arguments_answers_the_gate(repo, fake_tmux, capsys):
    _at_gate(repo, capsys)
    assert main(["answer", "s", "1", "reject", "-m", "too big"]) == 0
    assert capsys.readouterr().out == (
        "gate #1: reject. ship/x: check -> build (→ rev (not spawned))\n"
    )
    assert state.get_run("s", "ship/x").note == "rejected: too big"
    assert main(["answer", "s", "1", "approve"]) == 1
    assert "gate #1 is closed already: reject by human" in capsys.readouterr().err


def test_answer_refuses_unknown_options_and_agents(repo, fake_tmux, capsys, monkeypatch):
    _at_gate(repo, capsys)
    assert main(["answer", "s", "ship/x", "maybe"]) == 1
    assert 'no option "maybe" for gate #1; options: approve, reject' in capsys.readouterr().err
    monkeypatch.setenv("LADO_AGENT", "w1")
    for argv in (
        ["answer", "s", "1", "approve"],
        ["flow-set", "s", "ship/x", "end", "--reason", "x"],
    ):
        assert main(argv) == 1
        assert 'is for the human; agent "w1" cannot use it' in capsys.readouterr().err
    assert state.open_gate("s", "ship/x").id == 1


def _typing(monkeypatch, *lines):
    """Stdin with these lines, then its end."""
    answers = iter(lines)

    def fake_input(prompt=""):
        print(prompt, end="")
        try:
            return next(answers)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", fake_input)


def test_answer_asks_about_the_only_open_gate(repo, fake_tmux, capsys, monkeypatch):
    _at_gate(repo, capsys)
    runs.answer("s", "1", "reject", "first")
    runs.spawn_worker("s", "ship/x")
    runs.advance("s", "rev", "ship/x", "done", "built it", "all\ntests pass")
    capsys.readouterr()
    _typing(monkeypatch, "x", "2", "still too big")
    assert main(["answer"]) == 0
    out = capsys.readouterr().out
    assert "Gate #2, session s, run ship/x at check:\nShip it?\n" in out
    # The note's summary only: its body can be long. "v" shows all of it.
    assert "Note: built it (v: the full note, 2 more lines)\n" in out
    assert "tests pass" not in out
    assert "  1) approve\n  2) reject\n" in out
    assert "Answer (number or name, v for the full note, Enter to leave it open): " in out
    assert 'no option "x" for gate #2' in out
    assert "gate #2: reject. ship/x: check -> build (→ rev)" in out
    assert out.endswith("No more open gates.\n")
    assert state.get_run("s", "ship/x").note == "rejected: still too big"


def _at_gate_with_a_long_note(repo, capsys):
    _at_gate(repo, capsys)
    runs.answer("s", "1", "reject", "first")
    runs.spawn_worker("s", "ship/x")
    body = "\n".join(f"line {n}" for n in range(1, 61))
    runs.advance("s", "rev", "ship/x", "done", "built it", body)
    capsys.readouterr()
    return body


def test_v_shows_the_full_note_in_a_pager_then_asks_again(
    repo, fake_tmux, capsys, monkeypatch, tmp_path
):
    body = _at_gate_with_a_long_note(repo, capsys)
    assert cli.PAGER == ["less", "-R"]
    paged = tmp_path / "paged.txt"
    copy = f"import sys; open({str(paged)!r}, 'w').write(sys.stdin.read())"
    monkeypatch.setattr(cli, "PAGER", [sys.executable, "-c", copy])
    _typing(monkeypatch, "v", "approve", "")
    assert main(["answer"]) == 0
    assert paged.read_text() == f"Note: built it\n\n{body}\n"
    out = capsys.readouterr().out
    assert "line 60" not in out
    # Back at the question after the pager.
    assert out.count("Ship it?\n") == 2
    assert "gate #2: approve. ship/x: check -> end (ended)" in out


def test_v_prints_the_full_note_without_a_pager(repo, fake_tmux, capsys, monkeypatch):
    _at_gate_with_a_long_note(repo, capsys)
    monkeypatch.setattr(cli, "PAGER", ["no-such-pager-for-lado-tests"])
    _typing(monkeypatch, "v")
    assert main(["answer"]) == 0
    out = capsys.readouterr().out
    assert "Note: built it\n\nline 1\nline 2\n" in out and "line 60\n" in out
    assert out.count("Ship it?\n") == 2
    assert out.endswith("Gate #2 stays open.\n")


PLAN = """\
name: plan
description: plan, build and ship
start: plan
states:
  plan: {agent: supervisor, do: Plan it., produces: [plan], outcomes: {ready: build}}
  build: {agent: rev, do: Build it., outcomes: {done: check, polish: polish}}
  polish: {agent: rev, do: Polish it., produces: [polish], outcomes: {done: check}}
  check:
    gate: approval
    ask: Ship it?
    reads: [plan, polish]
    outcomes: {approved: end, rejected: build}
  end: {end: true}
"""


def _at_gate_with_reads(repo, capsys):
    kit = _kit(repo, "team")
    (kit / "flows").mkdir()
    (kit / "flows" / "plan.yaml").write_text(PLAN)
    main(
        [
            "start",
            str(repo),
            "--provider",
            "claude",
            "--name",
            "s",
            "--kit",
            "default",
            "--kit",
            "team",
            "--no-attach",
        ]
    )
    runs.start("s", "plan", "Add x", name="x")
    artifacts.write(
        "s",
        "supervisor",
        "plan/x/plan",
        content="step 1\nstep 2",
        title="The plan",
        summary="the plan",
    )
    runs.advance("s", "supervisor", "plan/x", "ready", "planned")
    runs.spawn_worker("s", "plan/x")
    runs.advance("s", "rev", "plan/x", "done", "built it", "all\ntests pass")
    capsys.readouterr()


READS = (
    "Ship it?\n"
    "Note: built it (v: the full note, 2 more lines)\n"
    "Artifacts it reads:\n"
    "  plan/x/plan: The plan — {}\n"
    "  plan/x/polish: no record yet\n"
    "Options:\n"
)


def test_answer_shows_the_note_then_the_artifacts_the_gate_reads(
    repo, fake_tmux, capsys, monkeypatch
):
    _at_gate_with_reads(repo, capsys)
    _typing(monkeypatch, "")
    assert main(["answer"]) == 0
    out = capsys.readouterr().out
    assert READS.format("the plan") in out
    assert "step 1" not in out
    assert "Answer (number or name, v for the full note, Enter to leave it open): " in out


def test_answer_shows_the_latest_record_again_after_v(repo, fake_tmux, capsys, monkeypatch):
    _at_gate_with_reads(repo, capsys)
    monkeypatch.setattr(cli, "PAGER", ["no-such-pager-for-lado-tests"])
    asked = iter(["v", ""])

    def typing(prompt=""):
        print(prompt, end="")
        # The supervisor writes the plan again while the human reads the gate.
        artifacts.write("s", "supervisor", "plan/x/plan", content="step 1", summary="new plan")
        return next(asked)

    monkeypatch.setattr("builtins.input", typing)
    assert main(["answer"]) == 0
    out = capsys.readouterr().out
    assert READS.format("the plan") in out
    assert "plan/x/plan: The plan — new plan\n\nstep 1\n" in out  # v: the latest one
    assert READS.format("new plan") in out  # and the gate after it


def _at_gate_from_polish(repo, capsys):
    """At gate check, reached from polish, whose note has the artifact polish attached."""
    _at_gate_with_reads(repo, capsys)
    runs.answer("s", "1", "reject", "polish it")
    runs.advance("s", "rev", "plan/x", "polish", "to polish")
    artifacts.write("s", "rev", "polish", content="shiny\nnow", summary="polished up")
    runs.advance("s", "rev", "plan/x", "done", "polished", "all\nshiny")
    capsys.readouterr()


def test_an_artifact_attached_to_the_note_before_the_gate_is_shown_once(
    repo, fake_tmux, capsys, monkeypatch
):
    _at_gate_from_polish(repo, capsys)
    [gate] = state.open_gates("s")
    assert runs.gate_reads(gate) == ["plan"]
    monkeypatch.setattr(cli, "PAGER", ["no-such-pager-for-lado-tests"])
    _typing(monkeypatch, "v")
    assert main(["answer"]) == 0
    out = capsys.readouterr().out
    assert (
        "Ship it?\n"
        "Note: polished (v: the full note, 2 more lines)\n"
        "Artifacts: plan/x/polish\n"
        "Artifacts it reads:\n"
        "  plan/x/plan: The plan — the plan\n"
        "Options:\n"
    ) in out
    # v: the note in full with its artifacts as attached, then those the gate reads.
    assert (
        "Note: polished\n\nall\nshiny\n\n"
        "plan/x/polish: polished up\n\nshiny\nnow\n\n"
        "plan/x/plan: The plan — the plan\n\nstep 1\nstep 2\n"
    ) in out
    assert out.count("shiny\nnow") == 1


def test_v_names_an_artifact_that_is_not_text(repo, fake_tmux, capsys, monkeypatch):
    _at_gate_with_reads(repo, capsys)
    (repo / "shot.png").write_bytes(b"\x89PNG not really")
    artifacts.write("s", "supervisor", "plan/x/plan", file="shot.png", summary="a picture")
    monkeypatch.setattr(cli, "PAGER", ["no-such-pager-for-lado-tests"])
    _typing(monkeypatch, "v")
    assert main(["answer"]) == 0
    out = capsys.readouterr().out
    assert "plan/x/plan: The plan — a picture\n\n(image/png, 15 bytes: not text)\n" in out
    assert "plan/x/polish: no record yet\n" in out
    assert "PNG not really" not in out


def test_answer_shows_a_gate_whose_flow_cannot_be_read_and_goes_on(
    repo, fake_tmux, capsys, monkeypatch
):
    _at_gate_with_reads(repo, capsys)
    runs.start("s", "plan", "Add y", name="y")
    runs.force("s", "plan/y", "check", "built by hand")
    agent_helpers.spoil_snapshot("s", "plan/x")
    capsys.readouterr()
    _typing(monkeypatch, "1", "reject", "")
    assert main(["answer", "s"]) == 0
    out = capsys.readouterr().out
    assert "Gate #1, session s, run plan/x at check:\nShip it?\nNote: built it" in out
    assert 'Gate #1 cannot be answered: run "plan/x": its flow snapshot is not JSON' in out
    assert "the supervisor can cancel the run with flow_cancel" in out
    assert "gate #2: reject. plan/y: check -> build" in out
    assert out.endswith("No more open gates.\n")
    assert state.open_gate("s", "plan/x").answer is None


@pytest.mark.parametrize("failing", ["latest", "content"])
def test_an_error_of_the_store_is_said_in_the_artifacts_line_and_the_gate_is_asked(
    repo, fake_tmux, capsys, monkeypatch, failing
):
    _at_gate_with_reads(repo, capsys)

    def broken(*args):
        raise artifacts.ArtifactError("content of plan/x/plan is missing")

    monkeypatch.setattr(artifacts_local.LocalStore, failing, broken)
    monkeypatch.setattr(cli, "PAGER", ["no-such-pager-for-lado-tests"])
    _typing(monkeypatch, "v", "approve", "")
    assert main(["answer"]) == 0
    out = capsys.readouterr().out
    assert "plan/x/plan: cannot be read now: content of plan/x/plan is missing" in out
    assert "gate #1: approve. plan/x: check -> end (ended)" in out


def test_answer_goes_on_with_other_sessions_after_a_gate_whose_flow_cannot_be_read(
    repo, fake_tmux, capsys, monkeypatch
):
    _at_gate_with_reads(repo, capsys)
    agent_helpers.spoil_snapshot("s", "plan/x")
    runtime.start_session(str(repo), "t", None, kit_names=["default", "team"], provider="claude")
    runs.start("t", "plan", "Add y", name="y")
    runs.force("t", "plan/y", "check", "built by hand")
    capsys.readouterr()
    _typing(monkeypatch, "1", "reject", "")
    assert main(["answer"]) == 0
    out = capsys.readouterr().out
    assert "Gate #1 cannot be answered" in out
    # The problem gate does not narrow the question to its session: t's gate comes next.
    assert "gate #2: reject. plan/y: check -> build" in out
    assert out.endswith("No more open gates.\n")


def test_answer_lets_the_human_pick_a_gate_and_leave(repo, fake_tmux, capsys, monkeypatch):
    _at_gate(repo, capsys)
    runs.start("s", "ship", "Add y", name="y")
    runs.force("s", "ship/y", "check", "built by hand")
    capsys.readouterr()
    _typing(monkeypatch, "2", "approve", "2")
    assert main(["answer", "-m", "ship y"]) == 0
    out = capsys.readouterr().out
    assert "  1) #1 s ship/x at check: Ship it?\n  2) #2 s ship/y at check: Ship it?\n" in out
    assert "gate #2: approve. ship/y: check -> end (ended)" in out
    assert state.get_gate(2).comment == "ship y"
    # On with the gates left; -m was for the first answer, so the comment is asked for, and
    # the end of input leaves gate #1 open.
    assert "Gate #1, session s, run ship/x at check:" in out
    assert out.endswith("Comment for the next step (Enter for none): \nGate #1 stays open.\n")
    assert [g.id for g in state.open_gates()] == [1]


def test_answer_that_failed_exits_non_zero(repo, fake_tmux, capsys, monkeypatch):
    _at_gate(repo, capsys)

    def refused(*args):
        raise runtime.LadoError("gate #1 is closed already: approve by human")

    monkeypatch.setattr(runs, "answer", refused)
    _typing(monkeypatch, "1", "")
    assert main(["answer"]) == 1
    assert "lado: gate #1 is closed already" in capsys.readouterr().out


def test_answer_names_a_gate_and_goes_on_with_its_session(repo, fake_tmux, capsys, monkeypatch):
    _at_gate(repo, capsys)
    _typing(monkeypatch)
    assert main(["answer", "s", "7"]) == 0
    out = capsys.readouterr().out
    # A popup for a gate that is gone shows why, then the session's open gates.
    assert out.startswith("lado: no gate #7\n\nGate #1, session s")
    assert main(["answer", "other"]) == 0
    assert capsys.readouterr().out == "No open gates.\n"


@pytest.fixture
def terminal(monkeypatch):
    """A real terminal (a pty) as stdin: the end the human types into, and the stdin."""
    import pty

    keyboard, tty = pty.openpty()
    stdin = os.fdopen(tty, "r")
    monkeypatch.setattr(cli, "POLL", 0.05)
    yield keyboard, stdin
    stdin.close()
    os.close(keyboard)


def test_a_line_is_read_while_it_is_still_wanted(terminal):
    keyboard, stdin = terminal
    os.write(keyboard, b"approve\n")
    assert cli.read_line_while(stdin, lambda: True) == "approve"


def test_typing_is_dropped_when_it_is_no_longer_wanted(terminal):
    keyboard, stdin = terminal
    os.write(keyboard, b"appro")  # typed, no Enter yet
    checks = iter([True, True, False])
    with pytest.raises(cli.NotWanted):
        cli.read_line_while(stdin, lambda: next(checks))
    # What was typed went with it: it does not reach the next prompt.
    os.write(keyboard, b"x\n")
    assert cli.read_line_while(stdin, lambda: True) == "x"


def test_answer_notices_a_gate_answered_elsewhere(repo, fake_tmux, capsys, monkeypatch, terminal):
    import threading
    import time

    keyboard, stdin = terminal
    _at_gate(repo, capsys)
    runs.start("s", "ship", "Add y", name="y")
    runs.force("s", "ship/y", "check", "built by hand")
    monkeypatch.setattr(sys, "stdin", stdin)
    os.write(keyboard, b"appr")  # the human was typing
    done = []
    asking = threading.Thread(target=lambda: done.append(main(["answer", "s", "1"])), daemon=True)
    asking.start()
    out = ""
    deadline = time.monotonic() + 10
    while "Answer (" not in out:
        assert time.monotonic() < deadline, out
        time.sleep(0.02)
        out += capsys.readouterr().out
    runs.answer("s", "1", "reject", "from the UI")
    while "Gate #2, session s" not in out:
        assert time.monotonic() < deadline, out
        time.sleep(0.02)
        out += capsys.readouterr().out
    os.write(keyboard, b"\n")  # leaves gate #2 open: "appr" was dropped
    asking.join(10)
    out += capsys.readouterr().out
    assert done == [0]
    assert "Gate #1 was answered elsewhere: reject by human\n" in out
    assert out.endswith("Gate #2 stays open.\n")
    assert state.get_gate(2).answer is None


def test_a_comment_given_with_m_is_not_taken_to_the_next_gate(
    repo, fake_tmux, capsys, monkeypatch, terminal
):
    """-m is for the gate it was given for: answered elsewhere, the next gate asks for its
    own comment."""
    import threading
    import time

    keyboard, stdin = terminal
    _at_gate(repo, capsys)
    runs.start("s", "ship", "Add y", name="y")
    runs.force("s", "ship/y", "check", "built by hand")
    monkeypatch.setattr(sys, "stdin", stdin)
    done = []
    argv = ["answer", "s", "1", "-m", "split it"]
    asking = threading.Thread(target=lambda: done.append(main(argv)), daemon=True)
    asking.start()
    out = ""
    deadline = time.monotonic() + 10
    while "Answer (" not in out:
        assert time.monotonic() < deadline, out
        time.sleep(0.02)
        out += capsys.readouterr().out
    runs.answer("s", "1", "reject")
    while "Gate #2, session s" not in out:
        assert time.monotonic() < deadline, out
        time.sleep(0.02)
        out += capsys.readouterr().out
    os.write(keyboard, b"approve\n")
    while "Comment for the next step" not in out and not done:
        assert time.monotonic() < deadline, out
        time.sleep(0.02)
        out += capsys.readouterr().out
    os.write(keyboard, b"ship y\n")
    asking.join(10)
    assert done == [0]
    assert state.get_gate(2).comment == "ship y"


def test_answer_ends_when_the_last_gate_is_answered_elsewhere(
    repo, fake_tmux, capsys, monkeypatch, terminal
):
    import threading
    import time

    keyboard, stdin = terminal
    _at_gate(repo, capsys)
    monkeypatch.setattr(sys, "stdin", stdin)
    done = []
    asking = threading.Thread(target=lambda: done.append(main(["answer"])), daemon=True)
    asking.start()
    out = ""
    deadline = time.monotonic() + 10
    while "Answer (" not in out:
        assert time.monotonic() < deadline, out
        time.sleep(0.02)
        out += capsys.readouterr().out
    runs.answer("s", "1", "approve")
    asking.join(10)
    out += capsys.readouterr().out
    assert done == [0]
    assert out.endswith("Gate #1 was answered elsewhere: approve by human\nNo more open gates.\n")


def test_flow_set_moves_a_run_and_is_logged(repo, fake_tmux, capsys):
    _session_with_run(repo)
    assert main(["flow-set", "s", "ship/x", "check", "--reason", "built by hand"]) == 0
    assert "ship/x: build -> check (waiting for human: gate #1)" in capsys.readouterr().out
    assert main(["flow-set", "s", "ship/x", "end", "--reason", "approved"]) == 0
    assert "ship/x: check -> end (ended)" in capsys.readouterr().out
    assert main(["flow-set", "s", "ship/x", "build", "--reason", "x"]) == 1
    assert 'run "ship/x" is ended' in capsys.readouterr().err
    main(["log", "s"])
    log = capsys.readouterr().out
    assert "human: flow_set ship/x (build -> check: built by hand)" in log
    assert "lado: flow_end ship/x (at end)" in log


def test_finish_and_stop_with_run_workers(repo, fake_tmux, capsys):
    run = _session_with_run(repo)
    runs.spawn_worker("s", "ship/x")
    runs.spawn_worker("s", "ship/x", role="rev", task="Help.")
    assert main(["finish", "s", "rev-2"]) == 0
    out = capsys.readouterr().out
    finished = 'Finished worker "rev-2" (closed; 1 message dropped): closed its window'
    assert f"{finished}; run ship/x keeps {run.worktree}" in out  # the message: its task
    assert main(["stop", "s"]) == 0
    out = capsys.readouterr().out
    assert out.count(f"kept worktree {run.worktree}") == 1


def test_stop_and_start_again_resumes_the_session(repo, fake_tmux, capsys):
    run = _session_with_run(repo)
    runs.force("s", "ship/x", "check", "built by hand")
    runtime.spawn_worker(
        "s", "task", name="w1", role="worker"
    )  # starting: its task and a message wait
    runtime.send_message("s", "supervisor", "w1", "hi")
    capsys.readouterr()
    assert main(["stop", "s"]) == 0
    out = capsys.readouterr().out
    # The supervisor is starting as well: LADO's two messages to it about the run wait.
    assert out.startswith('Stopped session "s"; 4 undelivered messages dropped.\n')
    assert f"  kept worktree {run.worktree} (branch {run.branch})" in out
    assert f"  kept worktree {repo}/.lado/worktrees/s/w1 (branch lado/s/w1)" in out
    assert "History, open runs and gates are kept: lado start resumes the session" in out

    assert main(["ls"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == f"s  {repo}  (stopped)"
    assert lines[1].split()[:8] == [
        "run",
        "ship/x",
        "check",
        "waiting",
        "for",
        "human:",
        "gate",
        "#1",
    ]
    assert lines[2] == "    gate #1 waiting: Ship it?"
    assert main(["log", "s"]) == 0
    assert "lado: session_stop (4 messages dropped)" in capsys.readouterr().out
    for argv in (["answer", "s", "1", "approve"], ["answer", "s", "1"], ["answer", "s"]):
        assert main(argv) == 1
        assert 'session "s" is stopped; resume it with `lado start`' in capsys.readouterr().err
    assert main(["answer"]) == 0  # a stopped session's gates wait for its resume
    assert capsys.readouterr().out == "No open gates.\n"

    args = [
        "start",
        str(repo),
        "--provider",
        "claude",
        "--name",
        "s",
        "--without",
        "agent:rev",
        "--no-attach",
    ]
    assert main(args) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith(
        f'Resumed session "s" in {repo}: 1 open run, the supervisor is told.\n'
        "  changed without: none -> agent:rev\n"
    )
    assert captured.err == (
        "lado: run ship/x: role rev is not in the session now; cancel the run with "
        "flow_cancel, or move it on with lado flow-set\n"
    )
    assert main(["ls"]) == 0
    assert capsys.readouterr().out.splitlines()[0].startswith(f"s  {repo}  (session loop not")


def test_forget_drops_a_stopped_session(repo, fake_tmux, capsys):
    run = _session_with_run(repo)
    capsys.readouterr()
    assert main(["forget", "s"]) == 1
    assert 'session "s" is not stopped; stop it first with lado stop s' in capsys.readouterr().err
    main(["stop", "s"])
    capsys.readouterr()
    assert main(["forget", "s"]) == 1
    err = capsys.readouterr().err
    assert 'session "s" has open runs: ship/x; forget it with --force' in err
    assert main(["forget", "s", "--force"]) == 0
    assert capsys.readouterr().out == (
        'Forgot session "s" and its history; dropped open runs: ship/x.\n'
        f"  left on disk: worktree {run.worktree} (branch {run.branch})\n"
        "Remove a worktree with: git worktree remove <path>\n"
    )
    assert state.get_session("s") is None
    assert Path(run.worktree).exists()
    assert main(["log", "s"]) == 1
    assert main(["forget", "s"]) == 1
    assert 'unknown session "s"' in capsys.readouterr().err


def test_flow_set_needs_a_reason(repo, fake_tmux, capsys):
    _session_with_run(repo)
    with pytest.raises(SystemExit):
        main(["flow-set", "s", "ship/x", "check"])
    capsys.readouterr()


def test_kits_show_lists_flows_with_their_source(repo, capsys):
    kit = _kit(repo, "team")
    (kit / "flows").mkdir()
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    assert main(["kits", "--repo", str(repo), "show", "default", "team"]) == 0
    out = capsys.readouterr().out
    assert f"Flows:\n  ship  from team (project): {kit.resolve()}/flows/ship.yaml" in out
    assert "    build and ship\n    build: rev (team)\n" in out


def test_kits_show_names_whose_role_does_each_step(repo, capsys):
    """Kit b's flow calls a role of the same name as its own, switched off: kit a's."""
    _kit(repo, "a")
    kit = _kit(repo, "b")
    (kit / "flows").mkdir()
    (kit / "flows" / "ship.yaml").write_text(
        SHIP.replace(
            "  build:", "  plan: {agent: supervisor, do: Plan., outcomes: {ok: build}}\n  build:"
        ).replace("start: build", "start: plan")
    )
    args = ["kits", "--repo", str(repo), "show", "default", "a", "b", "--without", "agent:rev@b"]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "    plan: the lead (supervisor of kit default)\n    build: rev (a)\n" in out


def test_kits_check_warns_about_a_flow_role_of_another_kit(repo, capsys):
    kit = _kit(repo, "team")
    (kit / "flows").mkdir()
    (kit / "flows" / "ship.yaml").write_text(SHIP.replace("agent: rev", "agent: worker"))
    assert main(["kits", "--repo", str(repo), "check", "team"]) == 0
    captured = capsys.readouterr()
    ship = kit.resolve() / "flows" / "ship.yaml"
    assert (
        f'warning: {ship}: state "build": role "worker" is not in kit "team"; '
        "a session needs a kit that has it"
    ) in captured.err
    assert captured.err.count("is not in kit") == 1  # kits.warnings says it, the CLI prints
    assert "team: OK (1 agents, 0 skills, 0 packs and 1 flows)" in captured.out
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    assert main(["kits", "--repo", str(repo), "check", "team"]) == 0
    assert "warning" not in capsys.readouterr().err
    # A step of the supervisor is the session's lead's, whichever kit leads.
    (kit / "flows" / "ship.yaml").write_text(SHIP.replace("agent: rev", "agent: supervisor"))
    assert main(["kits", "--repo", str(repo), "check", "team"]) == 0
    assert "is not in kit" not in capsys.readouterr().err


def test_kits_check_warns_about_a_role_that_acts_in_no_flow(repo, capsys):
    kit = _kit(repo, "team")
    (kit / "flows").mkdir()
    (kit / "flows" / "ship.yaml").write_text(SHIP.replace("agent: rev", "agent: supervisor"))
    assert main(["kits", "--repo", str(repo), "check", "team"]) == 0
    captured = capsys.readouterr()
    rev = kit.resolve() / "agents" / "rev.md"
    assert captured.err == (
        f'warning: {rev}: role "rev" acts in no state of the kit\'s flows; '
        "it can still be spawned outside a flow\n"
    )
    assert "team: OK" in captured.out


@pytest.mark.parametrize(
    "change, problem",
    [
        (
            lambda s: s.replace(
                "rejected: build}", "rejected: build}}\n  x: {agent: rev, do: X., outcomes: {a: x}"
            ).replace("done: check", "done: check, side: x"),
            'state "x": no end state can be reached from it',
        ),
        (
            lambda s: s.replace("done: check", "done: check, again: build"),
            "cycle build -> build has no state with max_visits and no gate",
        ),
        (
            lambda s: s.replace("{agent: rev,", "{agent: rev, reads: [late],").replace(
                "approved: end, rejected: build}}",
                "approved: x, rejected: build}}\n"
                "  x: {agent: rev, do: X., produces: [late], outcomes: {a: end}}",
            ),
            'state "build" reads "late", which no state before it produces',
        ),
    ],
)
def test_kits_check_fails_on_the_graph_problems_of_a_flow(repo, capsys, change, problem):
    kit = _kit(repo, "team")
    (kit / "flows").mkdir()
    (kit / "flows" / "ship.yaml").write_text(change(SHIP))
    assert main(["kits", "--repo", str(repo), "check", "team"]) == 1
    captured = capsys.readouterr()
    assert f"{kit.resolve() / 'flows' / 'ship.yaml'}: {problem}" in captured.err
    assert "OK" not in captured.out
    loaded = kits.load(kit)  # it still loads, and so does a run's snapshot of the flow
    flows.from_snapshot(loaded.flows["ship"].snapshot, "team")


def test_source_commands_are_not_under_kits(capsys):
    for command in ("sources", "list"):
        with pytest.raises(SystemExit):
            main(["kits", command, "x"])
    capsys.readouterr()


def test_a_command_does_not_migrate_the_database_under_a_running_session(repo, fake_tmux, capsys):
    assert main(["start", str(repo), "--provider", "claude", "--name", "old", "--no-attach"]) == 0
    agent_helpers.previous_schema()
    capsys.readouterr()
    assert main(["ls"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("lado: ") and "`lado stop --all`" in err
    assert state.pending_migration() == (state.SCHEMA_VERSION - 1, ["old"])
    # Stopping the only running session is what the refusal asks for: it kills, migrates
    # and marks it stopped.
    assert main(["stop", "old"]) == 0
    assert state.pending_migration() is None
    assert main(["ls"]) == 0
    assert f"old  {repo}  (stopped)" in capsys.readouterr().out


def test_stop_all_stops_every_running_session(repo, fake_tmux, capsys):
    for name in ("a", "b"):
        main(["start", str(repo), "--provider", "claude", "--name", name, "--no-attach"])
    agent_helpers.previous_schema()
    capsys.readouterr()
    assert main(["stop", "a"]) == 1
    assert "`lado stop --all`" in capsys.readouterr().err
    assert main(["stop", "--all"]) == 0
    out = capsys.readouterr().out
    assert 'Stopped session "a"' in out and 'Stopped session "b"' in out
    assert 'Only sessions on tmux socket "' in out
    assert state.pending_migration() is None
    assert main(["stop", "--all"]) == 0
    assert "No session runs." in capsys.readouterr().out


def test_stop_all_prints_each_session_stopped_before_a_failure(
    repo, fake_tmux, monkeypatch, capsys
):
    for name in ("a", "b"):
        main(["start", str(repo), "--provider", "claude", "--name", name, "--no-attach"])
    mark = state.stop_session

    def locked(session, gone=False):
        if session == "b":
            raise sqlite3.OperationalError("database is locked")
        return mark(session, gone)

    monkeypatch.setattr(state, "stop_session", locked)
    capsys.readouterr()
    assert main(["stop", "--all"]) == 1
    captured = capsys.readouterr()
    assert 'Stopped session "a".' in captured.out
    assert captured.err == (
        'lado: could not stop session "b": OperationalError: database is locked; stopped: "a"\n'
    )


def test_stop_takes_a_name_or_all(capsys):
    assert main(["stop"]) == 1
    assert main(["stop", "x", "--all"]) == 1
    assert "a session's name or --all" in capsys.readouterr().err


def test_a_newer_database_is_a_message_not_a_traceback(lado_home, capsys):
    lado_home.mkdir()
    sqlite3.connect(lado_home / "lado.db").execute("PRAGMA user_version = 99")
    assert main(["ls"]) == 1
    assert "lado: " in capsys.readouterr().err


def test_without_tmux_a_command_says_so_without_a_traceback(
    repo, fake_clis, loop_starts, tmp_path, monkeypatch, capsys
):
    tools = tmp_path / "no-tmux"
    tools.mkdir()
    (tools / "git").symlink_to(shutil.which("git"))
    path = f"{fake_clis}{os.pathsep}{tools}"
    monkeypatch.setenv("PATH", path)
    missing = f"lado: tmux is not installed or not on PATH ({path})\n"
    assert main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"]) == 1
    assert capsys.readouterr().err == missing
    assert state.get_session("s") is None
    # A session tmux cannot be asked about is not taken for gone: not by `lado ls`, and not
    # by the check before a migration, which would otherwise migrate under it.
    state.add_session(state.Session("s", str(repo), None, "claude", ["default"], []))
    assert main(["ls"]) == 1
    assert capsys.readouterr().err == missing
    agent_helpers.previous_schema()
    assert main(["ls"]) == 1
    assert capsys.readouterr().err == missing
    assert state.pending_migration() == (state.SCHEMA_VERSION - 1, ["s"])


def test_a_failed_start_shows_its_cause_then_what_its_undo_could_not_do(
    repo, fake_tmux, monkeypatch, capsys
):
    from lado import tmux

    def fail(*args):
        raise tmux.TmuxError("command too long")

    def locked(*args):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(tmux, "new_session", fail)
    monkeypatch.setattr(state, "delete_session", locked)
    assert main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"]) == 1
    assert capsys.readouterr().err == (
        "lado: command too long\n"
        "lado: undo of the start of s: forget the session failed: OperationalError: "
        "database is locked\n"
    )


def test_ls_shows_a_running_session_without_its_loop(repo, fake_tmux, capsys):
    from lado import loop

    main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"])
    capsys.readouterr()
    main(["ls"])
    assert capsys.readouterr().out.splitlines()[0] == (
        f"s  {repo}  (session loop not running: unconfirmed messages are not retried; "
        f"run `lado attach s` to restart it; see {state.home() / 'loop.log'})"
    )
    held = loop.take_lock("s")  # its loop runs
    main(["ls"])
    assert capsys.readouterr().out.splitlines()[0] == f"s  {repo}"
    held.close()


def test_attach_restarts_a_dead_loop(repo, fake_tmux, loop_starts, monkeypatch):
    from lado import loop

    attached = []
    monkeypatch.setattr(os, "execvpe", lambda *args: attached.append(args[1]))
    main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"])
    assert loop_starts == ["s"]
    main(["attach", "s"])
    assert loop_starts == ["s", "s"]  # its lock was free: the loop had died
    held = loop.take_lock("s")  # its loop runs
    main(["attach"])
    assert loop_starts == ["s", "s"]
    held.close()
    assert len(attached) == 2


def test_answer_names_the_artifacts_of_the_note_before_the_gate(
    repo, fake_tmux, capsys, monkeypatch
):
    _at_gate(repo, capsys)
    runs.answer("s", "1", "reject", "first")
    runs.spawn_worker("s", "ship/x")
    artifacts.write("s", "rev", "design", content="v1")
    artifacts.write("s", "rev", "plan", content="p1")
    runs.advance("s", "rev", "ship/x", "done", "built it", attached=["design", "plan"])
    artifacts.write("s", "rev", "plan", content="p2")
    capsys.readouterr()
    _typing(monkeypatch)
    main(["answer"])
    out = capsys.readouterr().out
    assert "Note: built it\nArtifacts: ship/x/design, ship/x/plan (changed since)\n" in out


def _with_artifacts(repo):
    main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"])
    state.add_run(
        state.Run("s", "ship/x", "ship", "{}", {}, "t", "build", "/w", "lado/s/x", {"build": 1}),
        [],
    )
    artifacts.write("s", "supervisor", "plan", content="# Plan\n", title="The plan")
    (repo / "logo.png").write_bytes(b"\x89PNG\x00")
    artifacts.write("s", "supervisor", "ship/x/logo", file="logo.png")


def test_artifacts_lists_shows_and_gets_a_sessions_artifacts(repo, fake_tmux, capsys, tmp_path):
    _with_artifacts(repo)
    main(["stop", "s"])  # a stopped session's too
    capsys.readouterr()
    assert main(["artifacts", "list", "s"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[:4] for line in lines] == [
        ["plan", "text/markdown", "7", "supervisor"],
        ["ship/x/logo", "image/png", "5", "supervisor"],
    ]
    assert lines[0].endswith("The plan")
    assert main(["artifacts", "list", "s", "--run", "ship/x"]) == 0
    assert [line.split()[0] for line in capsys.readouterr().out.splitlines()] == ["ship/x/logo"]
    assert main(["artifacts", "show", "s", "plan"]) == 0
    assert capsys.readouterr().out == "# Plan\n"
    assert main(["artifacts", "show", "s", "ship/x/logo"]) == 1
    assert "lado artifacts get s ship/x/logo -o FILE" in capsys.readouterr().err
    assert main(["artifacts", "get", "s", "ship/x/logo", "-o", str(tmp_path / "out.png")]) == 0
    assert (tmp_path / "out.png").read_bytes() == b"\x89PNG\x00"
    assert main(["artifacts", "show", "s", "nothing"]) == 1
    assert 'no artifact "nothing" in session s' in capsys.readouterr().err


def test_artifacts_get_writes_to_stdout_but_no_binary_to_a_terminal(
    repo, fake_tmux, capsysbinary, monkeypatch
):
    _with_artifacts(repo)
    capsysbinary.readouterr()
    assert main(["artifacts", "get", "s", "plan"]) == 0
    assert capsysbinary.readouterr().out == b"# Plan\n"
    assert main(["artifacts", "get", "s", "ship/x/logo"]) == 0
    assert capsysbinary.readouterr().out == b"\x89PNG\x00"
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    assert main(["artifacts", "get", "s", "ship/x/logo"]) == 1
    assert b"is binary (image/png): give -o FILE" in capsysbinary.readouterr().err


def test_artifacts_without_a_command_prints_its_help(capsys):
    assert main(["artifacts"]) == 0
    out = capsys.readouterr().out
    assert "usage: lado artifacts" in out and "list" in out and "get" in out


def test_artifacts_of_an_unknown_session_is_an_error(capsys):
    assert main(["artifacts", "list", "nope"]) == 1
    assert 'unknown session "nope"' in capsys.readouterr().err


def test_forget_says_how_many_artifacts_it_removed(repo, fake_tmux, capsys):
    _with_artifacts(repo)
    main(["stop", "s"])
    capsys.readouterr()
    assert main(["forget", "s", "--force"]) == 0
    assert capsys.readouterr().out.startswith(
        'Forgot session "s" and its history; removed 2 artifacts; dropped open runs: ship/x.\n'
    )


EXPECTING = "name: sdlc\nversion: 1.0.0\nexpects:\n  skills: [tracker]\n"


def _expecting_kit(repo):
    """Kit sdlc whose role analyst uses skill tracker, which it expects; and kit tracker,
    without agents, which has it."""
    kit = _kit(repo, "sdlc", "---\nname: analyst\ndescription: a\nskills: [tracker]\n---\nA.\n")
    (kit / "agents" / "rev.md").rename(kit / "agents" / "analyst.md")
    (kit / "kit.yaml").write_text(EXPECTING)
    tracker = repo / ".lado" / "kits" / "tracker"
    (tracker / "skills" / "tracker").mkdir(parents=True)
    (tracker / "kit.yaml").write_text("name: tracker\nversion: 1.0.0\n")
    (tracker / "skills" / "tracker" / "SKILL.md").write_text(
        "---\nname: tracker\ndescription: t\n---\n"
    )
    return kit


def test_kits_check_passes_a_kit_alone_with_the_skills_it_expects(repo, capsys, monkeypatch):
    kit = _expecting_kit(repo)
    assert main(["kits", "check", str(kit)]) == 0
    captured = capsys.readouterr()
    assert (
        captured.out
        == "sdlc: OK (1 agents, 0 skills, 0 packs and 0 flows)\nexpects skills: tracker\n"
    )
    assert (
        f"warning: {kit.resolve() / 'kit.yaml'}: expects.skills needs LADO 0.29 or newer; add "
        'dependencies.lado: ">=0.29" so an older LADO says to upgrade\n'
    ) in captured.err
    monkeypatch.setattr(lado, "__version__", "0.29.0")
    (kit / "kit.yaml").write_text(EXPECTING + 'dependencies:\n  lado: ">=0.29"\n')
    assert main(["kits", "check", str(kit)]) == 0
    assert "expects needs" not in capsys.readouterr().err


def test_kits_show_names_who_provides_what_a_kit_expects(repo, capsys):
    _expecting_kit(repo)
    assert main(["kits", "--repo", str(repo), "show", "sdlc"]) == 0
    out = capsys.readouterr().out
    assert "  sdlc 1.0.0  (project: " in out
    assert "    expects skill tracker: no kit here provides it\n" in out
    assert "  analyst  from sdlc" in out and "    skills: none\n" in out
    assert main(["kits", "--repo", str(repo), "show", "sdlc", "tracker"]) == 0
    out = capsys.readouterr().out
    assert "    expects skill tracker: from tracker\n" in out
    assert "    skills: tracker (tracker)\n" in out


COMMANDING = "name: cmd\nversion: 1.0.0\nexpects:\n  commands: [openspec, uv]\n"


def _executable(folder, name):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text("#!/bin/sh\n")
    (folder / name).chmod(0o755)
    return folder / name


def _process_path(monkeypatch, folder):
    """This process's PATH: `folder`, with git and nothing else of the machine's."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "git").symlink_to(shutil.which("git"))
    monkeypatch.setenv("PATH", str(folder))


def test_kits_check_names_the_commands_a_kit_expects(repo, capsys, monkeypatch, tmp_path):
    kit = _kit(repo, "cmd")
    monkeypatch.setattr(lado, "__version__", "0.30.0")
    (kit / "kit.yaml").write_text(COMMANDING + 'dependencies:\n  lado: ">=0.30"\n')
    bin_ = tmp_path / "bin"
    _executable(bin_, "uv")
    _process_path(monkeypatch, bin_)  # not the agents'
    assert main(["kits", "check", str(kit)]) == 0
    captured = capsys.readouterr()
    assert captured.out.endswith("\nexpects commands: openspec, uv\n")
    assert captured.err == (
        'warning: kit "cmd" expects command "openspec", which is not on this process\'s '
        "PATH; a session refuses to start without it\n"
    )
    _executable(bin_, "openspec")
    assert main(["kits", "check", str(kit)]) == 0
    assert capsys.readouterr().err == ""
    for deps in ("", 'dependencies:\n  lado: ">=0.29"\n'):
        (kit / "kit.yaml").write_text(COMMANDING + deps)
        assert main(["kits", "check", str(kit)]) == 0
        assert (
            'expects.commands needs LADO 0.30 or newer; add dependencies.lado: ">=0.30"'
            in capsys.readouterr().err
        )


@pytest.mark.parametrize("bad", ["/usr/bin/gh", "gh auth", "gh, gh"])
def test_kits_check_refuses_a_command_that_is_no_name(repo, capsys, bad):
    kit = _kit(repo, "cmd")
    (kit / "kit.yaml").write_text(f"name: cmd\nversion: 1.0.0\nexpects:\n  commands: [{bad}]\n")
    assert main(["kits", "check", str(kit)]) == 1
    assert "expects.commands: " in capsys.readouterr().err


def test_kits_show_looks_for_expected_commands_on_the_agents_path(
    repo, capsys, monkeypatch, tmp_path
):
    (_kit(repo, "cmd") / "kit.yaml").write_text(COMMANDING)
    found = _executable(tmp_path / "agents-bin", "uv")
    _executable(tmp_path / "process-bin", "openspec")
    _process_path(monkeypatch, tmp_path / "process-bin")
    calls = []

    def resolve():
        calls.append(1)
        return {"PATH": str(tmp_path / "agents-bin")}

    monkeypatch.setattr(agent_env, "resolve", resolve)
    assert main(["kits", "--repo", str(repo), "show", "cmd"]) == 0
    out = capsys.readouterr().out
    assert "    expects command openspec: not on the agents' PATH\n" in out
    assert f"    expects command uv: {found}\n" in out
    assert calls == [1]
    # A kit that expects no command does not resolve the agents' environment.
    assert main(["kits", "--repo", str(repo), "show", "default"]) == 0
    assert calls == [1] and "expects command" not in capsys.readouterr().out


def test_kits_show_says_when_it_cannot_tell_the_agents_path(repo, capsys, monkeypatch):
    (_kit(repo, "cmd") / "kit.yaml").write_text(COMMANDING)

    def broken():
        raise agent_env.AgentEnvError("your shell failed with exit status 1")

    monkeypatch.setattr(agent_env, "resolve", broken)
    assert main(["kits", "--repo", str(repo), "show", "cmd"]) == 0
    out = capsys.readouterr().out
    for name in ("openspec", "uv"):
        assert (
            f"    expects command {name}: cannot tell: your shell failed with exit status 1\n"
            in out
        )
