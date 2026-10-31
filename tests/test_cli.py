import datetime
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import agent_helpers
import pytest
from agent_helpers import init_repo, install_kit, publish

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
    project_secrets,
    projects,
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
    claude_config.refuse()  # Claude Code trusts no folder, and LADO cannot record it
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


def test_start_logs_that_lado_recorded_claude_codes_trust_and_says_nothing(
    repo, fake_tmux, claude_config, capsys
):
    claude_config.trust()  # Claude Code trusts no folder
    start = ["start", str(repo), "--name", "s", "--provider", "claude", "--no-attach"]
    assert main(start) == 0
    assert "LADO recorded" not in capsys.readouterr().err
    log = (state.home() / "loop.log").read_text()
    assert log.count(f"s: supervisor: {claude_config.note(repo)}") == 1


def test_start_refuses_a_resume_by_hand_without_the_login(repo, fake_tmux, cli_logins, capsys):
    start = ["start", str(repo), "--name", "s", "--provider", "claude", "--no-attach"]
    assert main(start) == 0
    assert main(["stop", "s"]) == 0
    cli_logins.logged_out()
    capsys.readouterr()
    assert main(["start", str(repo), "--name", "s", "--no-attach"]) == 1
    assert "Claude Code is not logged in, so the session was not resumed: " in (
        capsys.readouterr().err
    )
    assert state.get_session("s").stopped_at
    # LADO's own resume (lado update) waits for the login instead.
    assert main(["start", str(repo), "--name", "s", "--no-attach", "--wait-for-login"]) == 0
    assert "Claude Code is not logged in: " in capsys.readouterr().err
    assert state.get_agent("s", "supervisor").status == state.WAITING


def test_start_does_not_list_the_wait_for_login(capsys):
    with pytest.raises(SystemExit):
        main(["start", "--help"])
    assert "--wait-for-login" not in capsys.readouterr().out


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


def test_ls_shows_an_agent_in_background_with_its_time_in_line(repo, fake_tmux, capsys):
    main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"])
    runtime.spawn_worker("s", "task", name="w1")
    state.set_status("s", "w1", state.BACKGROUND)
    capsys.readouterr()
    main(["ls"])
    lines = capsys.readouterr().out.splitlines()
    assert lines[2].split() == ["w1", "worker", "claude", "background", "0s", "lado/s/w1"]
    assert lines[1].index(lines[1].split()[4]) == lines[2].index("0s")
    assert len(lines) == 3  # no reason line, no task count


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
    assert capsys.readouterr().err.splitlines() == [
        f"lado: {empty} has no commits yet",
        "lado: Make a first commit, in that folder: git add -A && git commit -m 'First commit'",
    ]


def test_start_outside_git_prints_the_reason_and_the_hint(tmp_path, fake_tmux, capsys):
    assert main(["start", str(tmp_path), "--no-attach"]) == 1
    assert capsys.readouterr().err.splitlines() == [
        f"lado: {tmp_path} is not inside a git repository",
        "lado: Make it a repository with a first commit, in that folder: "
        "git init && git add -A && git commit -m 'First commit'",
    ]


def _no_git(tmp_path, monkeypatch) -> Path:
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.setattr(runtime.platform, "system", lambda: "Darwin")
    return empty


def test_start_without_git_says_so_with_no_traceback(repo, fake_tmux, capsys, monkeypatch):
    empty = _no_git(repo.parent, monkeypatch)
    assert main(["start", str(repo), "--no-attach"]) == 1
    assert capsys.readouterr().err.splitlines() == [
        f"lado: git is not installed or not on PATH ({empty})",
        "lado: Install the Xcode command line tools (or `brew install git`): "
        "xcode-select --install",
    ]


def test_start_with_a_git_that_does_not_run(repo, fake_tmux, capsys, monkeypatch):
    bin_dir = _no_git(repo.parent, monkeypatch)
    git = bin_dir / "git"
    git.write_text("#!/bin/sh\necho 'xcrun: error: invalid active developer path' >&2\nexit 1\n")
    git.chmod(0o755)
    assert main(["start", str(repo), "--no-attach"]) == 1
    assert capsys.readouterr().err.splitlines() == [
        "lado: git does not run: xcrun: error: invalid active developer path",
        "lado: Install the Xcode command line tools, which this git needs: xcode-select --install",
    ]


def test_kits_add_without_git_says_so_with_no_traceback(tmp_path, capsys, monkeypatch):
    empty = _no_git(tmp_path, monkeypatch)
    assert main(["kits", "add", "https://example.invalid/kit.git", "--yes"]) == 1
    err = capsys.readouterr().err
    assert f"git is not installed or not on PATH ({empty})" in err
    assert err.startswith("lado: ")
    assert "Traceback" not in err


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


REV = "---\nname: rev\ndescription: reviews\n---\nReview.\n"


def _kit(base, name, body=REV):
    """A kit with one role, rev, in base/kits/name."""
    kit = base / "kits" / name
    (kit / "agents").mkdir(parents=True)
    (kit / "kit.yaml").write_text(f"name: {name}\nversion: 1.0.0\ndescription: about {name}\n")
    (kit / "agents" / "rev.md").write_text(body)
    return kit


def _installed(repo, name, body=REV):
    """A kit made beside the repository (_kit) and installed from its folder."""
    kit = _kit(repo.parent, name, body)
    install_kit(kit)
    return kit


def test_a_repositorys_own_kit_is_not_read_by_start(repo, fake_tmux, capsys, lado_home):
    _kit(repo / ".lado", "team")
    args = ["start", str(repo), "--provider", "claude", "--name", "s", "--kit", "team"]
    assert main([*args, "--no-attach"]) == 1
    assert capsys.readouterr().err == (
        f'lado: kit "team" not found; looked in the installed kits in {lado_home / "lado.db"}, '
        f"{kits.BUILTIN}\n"
    )
    assert state.get_session("s") is None and fake_tmux == []


def test_kits_takes_no_repo(repo, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["kits", "--repo=."])
    assert exc.value.code == 2
    assert "unrecognized arguments: --repo=." in capsys.readouterr().err
    with pytest.raises(SystemExit) as exc:  # argparse reads the folder as a command then
        main(["kits", "--repo", str(repo), "show", "default"])
    assert exc.value.code == 2


def test_kits_lists_the_same_kits_in_every_folder(tmp_path, capsys, monkeypatch):
    one, two = init_repo(tmp_path / "one"), init_repo(tmp_path / "two")
    _kit(one / ".lado", "team")
    _kit(two / ".lado", "crew")
    _installed(tmp_path / "dev" / "x", "mine")
    outs = []
    for folder in (one, two):
        monkeypatch.chdir(folder)
        assert main(["kits"]) == 0
        outs.append(capsys.readouterr().out)
    assert outs[0] == outs[1]
    assert "mine " in outs[0] and "team" not in outs[0] and "crew" not in outs[0]


def test_start_with_kits_and_without(repo, fake_tmux):
    _installed(repo, "team")
    args = ["start", str(repo), "--provider", "claude", "--name", "s", "--kit", "default"]
    args += ["--kit", "team"]
    assert main([*args, "--without", "agent:rev", "--no-attach"]) == 0
    sess = state.get_session("s")
    assert (sess.kits, sess.without) == (["default", "team"], ["agent:rev"])


def test_start_says_who_leads_and_which_supervisor_is_not_used(repo, fake_tmux, capsys):
    kit = _installed(repo, "team")
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
    kit = _installed(repo, "team")
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
        f"team             user      {kit}\n  1.0.0    about team; 2 packs not fetched yet" in out
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
    kit = _installed(repo, "team")
    args = ["kits", "show", "default", "team", "--without", "agent:worker"]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert f"team 1.0.0  (user: {kit.resolve()})" in out
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
    kit = _installed(repo, "team", body)
    (kit / "kit.yaml").write_text("name: team\nversion: 1.0.0\nsupervisor: rev\n")
    (kit / "skills" / "notes").mkdir(parents=True)
    (kit / "skills" / "notes" / "SKILL.md").write_text("---\nname: notes\ndescription: n\n---\n")
    assert main(["kits", "show", "default", "team"]) == 0
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
        kit = _installed(repo, name)
        (kit / "kit.yaml").write_text(
            f"name: {name}\nversion: 1.0.0\ndependencies:\n  skills:\n    sp: {url}@{ref}\n"
        )
        (kit / "agents" / "rev.md").write_text(f"---\nname: rev-{name}\ndescription: d\n---\n")
        (kit / "agents" / "rev.md").rename(kit / "agents" / f"rev-{name}.md")
    assert main(["kits", "show", "default", "one", "two"]) == 0
    skills = capsys.readouterr().out.split("Skills:\n", 1)[1]
    for name, ref in (("one", "v1"), ("two", "v2")):
        folder = gitcache.clone_dir(url, ref).resolve() / "skills" / "tdd"
        assert f"  tdd  from sp@{ref} ({name}) (user): {folder}\n" in skills


def test_kits_show_names_packs_and_where_each_skill_comes_from(tmp_path, repo, capsys):
    url = publish(
        init_repo(tmp_path / "pack"),
        {"skills/tdd/SKILL.md": "---\nname: tdd\ndescription: test first\n---\n"},
        tag="v1",
    )
    kit = _installed(repo, "team")
    (kit / "kit.yaml").write_text(
        f"name: team\nversion: 1.0.0\ndependencies:\n  skills:\n    sp: {url}@v1\n"
    )
    (kit / "skills" / "notes").mkdir(parents=True)
    (kit / "skills" / "notes" / "SKILL.md").write_text("---\nname: notes\ndescription: n\n---\n")
    shared = repo.parent / "kits" / "shared"
    (shared / "skills" / "plan").mkdir(parents=True)
    (shared / "kit.yaml").write_text(
        "name: shared\nversion: 1.0.0\ndependencies:\n  skills:\n    lp: ../../lp\n"
    )
    (shared / "skills" / "plan" / "SKILL.md").write_text("---\nname: plan\ndescription: p\n---\n")
    install_kit(shared)
    (repo.parent / "lp" / "skills" / "grill").mkdir(parents=True)
    (repo.parent / "lp" / "skills" / "grill" / "SKILL.md").write_text(
        "---\nname: grill\ndescription: g\n---\n"
    )
    assert main(["kits", "show", "default", "team", "shared"]) == 0
    out = capsys.readouterr().out
    clone = gitcache.clone_dir(url, "v1").resolve()
    assert f"    pack sp: {url}@v1  {clone}" in out
    assert f"    pack lp: ../../lp  {(repo.parent / 'lp').resolve()}" in out
    assert "    shares its packs with the session (no agents)" in out
    assert (
        "    skills (all): notes (team), plan (shared), grill (lp (shared)), tdd (sp@v1 (team))"
    ) in out
    assert "    skills (all): notes (team), plan (shared), grill (lp (shared))\n" in out


def test_kits_check(repo, capsys, monkeypatch):
    kit = _installed(repo, "team")
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


READ_ONLY_REV = "---\nname: rev\ndescription: reviews\nread_only: true\n---\nReview.\n"


def test_kits_show_and_check_name_read_only_roles(repo, capsys):
    kit = _installed(repo, "team", READ_ONLY_REV)
    assert main(["kits", "show", "default", "team"]) == 0
    out = capsys.readouterr().out
    rev = out[out.index("  rev  from team") :]
    assert rev.splitlines()[1:3] == ["    skills (all): none", "    read-only: yes"]
    assert out.count("    read-only: yes") == 1
    assert main(["kits", "check", str(kit)]) == 0
    assert "\nread-only roles: rev\n" in capsys.readouterr().out
    assert main(["kits", "check", "default"]) == 0
    assert "read-only roles" not in capsys.readouterr().out


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
    _kit(old, "team")  # old/kits/team: no kit.yaml at the root of old
    assert main(["kits", "check", str(old), "--tag", "v1.0.0"]) == 1
    assert "kits in kits/<name>/ are no longer supported" in capsys.readouterr().err
    assert main(["kits", "check", str(old / "kits" / "team")]) == 0  # as before
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
    install_kit(gitcache.fetch_pinned(url, commit))
    assert main(["kits", "check", "team"]) == 0
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
    kit = _installed(repo, "team")
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


VIEW = "Reject: no test of the turn end.\nThe build is red.\nCheck CI first."


def _recommended(choice="reject", disagrees=False, text=VIEW, gate=1):
    runtime.recommend("s", "supervisor", text, gate=gate, choice=choice, disagrees=disagrees)


def _answer_out(monkeypatch, capsys, *typed) -> str:
    _typing(monkeypatch, *typed)
    assert main(["answer"]) == 0
    return capsys.readouterr().out


def test_answer_shows_the_recommendation_and_marks_the_option(repo, fake_tmux, capsys, monkeypatch):
    _at_gate(repo, capsys)
    _recommended()
    out = _answer_out(monkeypatch, capsys, "")
    assert (
        "Supervisor recommends: reject (v: the full text, 2 more lines)\n"
        "  Reject: no test of the turn end.\n"
    ) in out
    assert "  1) approve\n  2) reject   ← supervisor recommends\n" in out
    assert "The build is red." not in out
    assert "Answer (number or name, v for the full note, Enter to leave it open): " in out


def test_answer_shows_the_recommendation_with_a_disagreement(repo, fake_tmux, capsys, monkeypatch):
    _at_gate_with_a_long_note(repo, capsys)  # gate #2, after rev's report
    _recommended(disagrees=True, text="Reject: no test.", gate=2)
    out = _answer_out(monkeypatch, capsys, "")
    assert "Supervisor recommends: reject (disagrees with rev)\n  Reject: no test.\n" in out


def test_answer_shows_a_recommendation_without_an_option(repo, fake_tmux, capsys, monkeypatch):
    _at_gate(repo, capsys)
    _recommended(choice=None, text="Either is fine.")
    out = _answer_out(monkeypatch, capsys, "")
    assert "Supervisor's recommendation:\n  Either is fine.\n" in out
    assert "  1) approve\n  2) reject\n" in out


def test_answer_says_the_recommendation_is_prepared(repo, fake_tmux, capsys, monkeypatch):
    _at_gate(repo, capsys)  # flow-set into the gate: the lead is asked
    assert state.get_gate(1).recommendation_state == state.REC_ASKED
    out = _answer_out(monkeypatch, capsys, "")
    assert "Supervisor is preparing a recommendation… (v shows it once it is given)\n" in out
    assert "Answer (number or name, v for the full note, Enter to leave it open): " in out


def _set_recommendation_state(value):
    with state.connect() as db:
        db.execute("UPDATE gates SET recommendation_state = ? WHERE id = 1", (value,))


def test_answer_says_when_none_was_given(repo, fake_tmux, capsys, monkeypatch):
    _at_gate(repo, capsys)
    _set_recommendation_state(state.REC_MISSING)
    out = _answer_out(monkeypatch, capsys, "")
    assert "The supervisor gave no recommendation.\n" in out


def test_answer_without_a_recommendation_shows_nothing_new(repo, fake_tmux, capsys, monkeypatch):
    _at_gate(repo, capsys)
    _set_recommendation_state(None)
    out = _answer_out(monkeypatch, capsys, "")
    assert "upervisor" not in out
    assert "  1) approve\n  2) reject\n" in out
    assert "Answer (number or name, Enter to leave it open): " in out


def test_v_shows_the_whole_recommendation_given_meanwhile(repo, fake_tmux, capsys, monkeypatch):
    """Given while the human reads the gate: "v" and the gate after it show it."""
    _at_gate(repo, capsys)
    monkeypatch.setattr(cli, "PAGER", ["no-such-pager-for-lado-tests"])
    asked = iter(["v", ""])

    def typing(prompt=""):
        print(prompt, end="")
        _recommended()
        return next(asked)

    monkeypatch.setattr("builtins.input", typing)
    assert main(["answer"]) == 0
    out = capsys.readouterr().out
    assert f"Supervisor's recommendation:\n\n{VIEW}\n" in out
    assert out.count("Supervisor is preparing a recommendation…") == 1
    assert "  2) reject   ← supervisor recommends\n" in out


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
    kit = _installed(repo, "team")
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
    "Supervisor is preparing a recommendation… (v shows it once it is given)\n"
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
        "Supervisor is preparing a recommendation… (v shows it once it is given)\n"
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

    def refused(*args, **kwargs):
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
    kit = _installed(repo, "team")
    (kit / "flows").mkdir()
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    assert main(["kits", "show", "default", "team"]) == 0
    out = capsys.readouterr().out
    assert f"Flows:\n  ship  from team (user): {kit.resolve()}/flows/ship.yaml" in out
    assert "    build and ship\n    build: rev (team)\n" in out


def test_kits_show_names_whose_role_does_each_step(repo, capsys):
    """Kit b's flow calls a role of the same name as its own, switched off: kit a's."""
    _installed(repo, "a")
    kit = _installed(repo, "b")
    (kit / "flows").mkdir()
    (kit / "flows" / "ship.yaml").write_text(
        SHIP.replace(
            "  build:", "  plan: {agent: supervisor, do: Plan., outcomes: {ok: build}}\n  build:"
        ).replace("start: build", "start: plan")
    )
    args = ["kits", "show", "default", "a", "b", "--without", "agent:rev@b"]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "    plan: the lead (supervisor of kit default)\n    build: rev (a)\n" in out


def test_kits_check_warns_about_a_flow_role_of_another_installed(repo, capsys):
    kit = _installed(repo, "team")
    (kit / "flows").mkdir()
    (kit / "flows" / "ship.yaml").write_text(SHIP.replace("agent: rev", "agent: worker"))
    assert main(["kits", "check", "team"]) == 0
    captured = capsys.readouterr()
    ship = kit.resolve() / "flows" / "ship.yaml"
    assert (
        f'warning: {ship}: state "build": role "worker" is not in kit "team"; '
        "a session needs a kit that has it"
    ) in captured.err
    assert captured.err.count("is not in kit") == 1  # kits.warnings says it, the CLI prints
    assert "team: OK (1 agents, 0 skills, 0 packs and 1 flows)" in captured.out
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    assert main(["kits", "check", "team"]) == 0
    assert "warning" not in capsys.readouterr().err
    # A step of the supervisor is the session's lead's, whichever kit leads.
    (kit / "flows" / "ship.yaml").write_text(SHIP.replace("agent: rev", "agent: supervisor"))
    assert main(["kits", "check", "team"]) == 0
    assert "is not in kit" not in capsys.readouterr().err


def test_kits_check_warns_about_a_role_that_acts_in_no_flow(repo, capsys):
    kit = _installed(repo, "team")
    (kit / "flows").mkdir()
    (kit / "flows" / "ship.yaml").write_text(SHIP.replace("agent: rev", "agent: supervisor"))
    assert main(["kits", "check", "team"]) == 0
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
    kit = _installed(repo, "team")
    (kit / "flows").mkdir()
    (kit / "flows" / "ship.yaml").write_text(change(SHIP))
    assert main(["kits", "check", "team"]) == 1
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


def test_the_commands_lado_doctor_names_for_an_upgrade_migrate():
    """lado doctor's line on an older lado.db says `lado ls` or `lado start` upgrades it."""
    assert "ls" not in cli.NOT_MIGRATING and "start" not in cli.NOT_MIGRATING
    assert "doctor" in cli.NOT_MIGRATING


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


def _stopped_session_on_schema(old: int) -> None:
    """A stopped session in lado.db, whose schema is set back to `old`, the one before; the
    last step of the migration then fails (FAILING_STEP)."""
    state.add_session(state.Session("s", "/r", None, "claude", ["default"], []))
    state.stop_session("s")
    agent_helpers.previous_schema()


FAILING_STEP = "SELECT no_such_function()"


def _journal(lado_home) -> list[dict]:
    path = lado_home / "errors.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_a_command_on_an_older_schema_says_it_upgraded_and_where_the_backup_is(
    lado_home, fake_tmux, capsys
):
    state.add_session(state.Session("s", "/r", None, "claude", ["default"], []))
    state.stop_session("s")
    agent_helpers.previous_schema()
    old, backup = state.SCHEMA_VERSION - 1, lado_home / "backups"
    assert main(["ls"]) == 0
    captured = capsys.readouterr()
    assert captured.err == (
        f"lado: upgraded lado.db from schema {old} to {state.SCHEMA_VERSION}; "
        f"its backup is {backup / f'lado.db.schema-{old}'}\n"
    )
    assert "s  /r  (stopped)" in captured.out
    assert main(["ls"]) == 0
    assert capsys.readouterr().err == ""  # nothing more to migrate


@pytest.mark.parametrize(
    ("container", "way_back"),
    [
        (False, "To go back, install the LADO you had before."),
        (
            True,
            "To go back, run the image of the LADO version you ran before "
            "(ghcr.io/ladohq/lado:<that version>) on the same home volume.",
        ),
    ],
)
def test_a_failed_migration_is_one_message_with_the_way_back(
    lado_home, fake_tmux, monkeypatch, capsys, container, way_back
):
    if container:
        monkeypatch.setenv("LADO_CONTAINER", "1")
    old = state.SCHEMA_VERSION - 1
    _stopped_session_on_schema(old)
    monkeypatch.setitem(state.MIGRATIONS, old, [*state.MIGRATIONS[old], FAILING_STEP])
    assert main(["ls"]) == 1
    backup = lado_home / "backups" / f"lado.db.schema-{old}"
    assert capsys.readouterr().err == (
        f"lado: could not upgrade lado.db from schema {old} to {state.SCHEMA_VERSION}: "
        "OperationalError: no such function: no_such_function. lado.db is unchanged; "
        "its backup is "
        f"{backup}. {way_back} Report it with lado bug-report.\n"
    )
    assert state.schema_version() == old
    assert backup.exists()
    [line] = _journal(lado_home)  # LADO's own bug: journaled, without a traceback shown
    assert (line["where"], line["type"]) == ("cli:ls", "sqlite3.OperationalError")


def test_a_backup_that_cannot_be_written_is_a_message_and_no_migration(
    lado_home, fake_tmux, capsys
):
    old = state.SCHEMA_VERSION - 1
    state.add_session(state.Session("s", "/r", None, "claude", ["default"], []))
    agent_helpers.previous_schema()
    (lado_home / "backups").write_text("a file where the folder goes")
    assert main(["ls"]) == 1
    err = capsys.readouterr().err
    backup = lado_home / "backups" / f"lado.db.schema-{old}"
    assert err.startswith(
        f"lado: could not back up lado.db to {backup} before upgrading it from schema {old} "
        f"to {state.SCHEMA_VERSION}: "
    )
    assert err.endswith("; nothing was changed\n") and err.count("\n") == 1
    assert state.schema_version() == old
    assert _journal(lado_home) == []  # the machine's problem, not LADO's bug


def test_stop_all_on_an_older_schema_says_it_upgraded(repo, fake_tmux, lado_home, capsys):
    main(["start", str(repo), "--provider", "claude", "--name", "a", "--no-attach"])
    agent_helpers.previous_schema()
    capsys.readouterr()
    assert main(["stop", "--all"]) == 0
    old = state.SCHEMA_VERSION - 1
    assert capsys.readouterr().err == (
        f"lado: upgraded lado.db from schema {old} to {state.SCHEMA_VERSION}; "
        f"its backup is {lado_home / 'backups' / f'lado.db.schema-{old}'}\n"
    )


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

    def fail(*args, **kwargs):
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
    kit = _installed(
        repo, "sdlc", "---\nname: analyst\ndescription: a\nskills: [tracker]\n---\nA.\n"
    )
    (kit / "agents" / "rev.md").rename(kit / "agents" / "analyst.md")
    (kit / "kit.yaml").write_text(EXPECTING)
    tracker = repo.parent / "kits" / "tracker"
    (tracker / "skills" / "tracker").mkdir(parents=True)
    (tracker / "kit.yaml").write_text("name: tracker\nversion: 1.0.0\n")
    (tracker / "skills" / "tracker" / "SKILL.md").write_text(
        "---\nname: tracker\ndescription: t\n---\n"
    )
    install_kit(tracker)
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
    assert main(["kits", "show", "sdlc"]) == 0
    out = capsys.readouterr().out
    assert "  sdlc 1.0.0  (user: " in out
    assert "    expects skill tracker: no kit here provides it\n" in out
    assert "  analyst  from sdlc" in out and "    skills: none\n" in out
    assert main(["kits", "show", "sdlc", "tracker"]) == 0
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
    kit = _installed(repo, "cmd")
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
    kit = _installed(repo, "cmd")
    (kit / "kit.yaml").write_text(f"name: cmd\nversion: 1.0.0\nexpects:\n  commands: [{bad}]\n")
    assert main(["kits", "check", str(kit)]) == 1
    assert "expects.commands: " in capsys.readouterr().err


def test_kits_show_looks_for_expected_commands_on_the_agents_path(
    repo, capsys, monkeypatch, tmp_path
):
    (_installed(repo, "cmd") / "kit.yaml").write_text(COMMANDING)
    found = _executable(tmp_path / "agents-bin", "uv")
    _executable(tmp_path / "process-bin", "openspec")
    _process_path(monkeypatch, tmp_path / "process-bin")
    calls = []

    def resolve():
        calls.append(1)
        return {"PATH": str(tmp_path / "agents-bin")}

    monkeypatch.setattr(agent_env, "resolve", resolve)
    assert main(["kits", "show", "cmd"]) == 0
    out = capsys.readouterr().out
    assert "    expects command openspec: not on the agents' PATH\n" in out
    assert f"    expects command uv: {found}\n" in out
    assert calls == [1]
    # A kit that expects no command does not resolve the agents' environment.
    assert main(["kits", "show", "default"]) == 0
    assert calls == [1] and "expects command" not in capsys.readouterr().out


def test_kits_show_says_when_it_cannot_tell_the_agents_path(repo, capsys, monkeypatch):
    (_installed(repo, "cmd") / "kit.yaml").write_text(COMMANDING)

    def broken():
        raise agent_env.AgentEnvError("your shell failed with exit status 1")

    monkeypatch.setattr(agent_env, "resolve", broken)
    assert main(["kits", "show", "cmd"]) == 0
    out = capsys.readouterr().out
    for name in ("openspec", "uv"):
        assert (
            f"    expects command {name}: cannot tell: your shell failed with exit status 1\n"
            in out
        )


# lado start <git-url> [<folder>] [--branch NAME] (openspec change clone-from-url)


def test_branch_or_a_second_folder_needs_a_git_url(repo, capsys):
    with pytest.raises(SystemExit) as exited:
        main(["start", str(repo), "--branch", "dev"])
    assert exited.value.code == 2
    assert "--branch needs a git URL" in capsys.readouterr().err
    with pytest.raises(SystemExit) as exited:
        main(["start", str(repo), str(repo.parent / "other")])
    assert exited.value.code == 2
    assert "a second folder needs a git URL" in capsys.readouterr().err


def test_the_clone_is_there_already(tmp_path, fake_tmux, capsys):
    folder = init_repo(tmp_path / "lado")
    subprocess.run(
        ["git", "-C", str(folder), "remote", "add", "origin", "https://github.com/ladohq/lado"],
        check=True,
    )
    assert main(["start", "git@github.com:ladohq/lado.git", str(folder), "--no-attach"]) == 1
    assert capsys.readouterr().err.splitlines() == [
        f"lado: {folder} is already a clone of this repository "
        "(origin https://github.com/ladohq/lado), on branch main",
        f"lado: To start a session in it as it is: lado start {folder}",
    ]
    assert state.list_sessions() == []


def test_a_folder_of_another_repository_or_with_files_is_refused(tmp_path, fake_tmux, capsys):
    folder = init_repo(tmp_path / "app")
    subprocess.run(
        ["git", "-C", str(folder), "remote", "add", "origin", "git@github.com:acme/app.git"],
        check=True,
    )
    assert main(["start", "git@github.com:ladohq/app.git", str(folder), "--no-attach"]) == 1
    assert capsys.readouterr().err.splitlines() == [
        f"lado: {folder} is a clone of another repository (origin git@github.com:acme/app.git): "
        f"choose another folder, e.g. {tmp_path / 'ladohq-app'}"
    ]
    (tmp_path / "files").mkdir()
    (tmp_path / "files" / "a.txt").write_text("x")
    assert main(["start", "https://h/a/b", str(tmp_path / "files"), "--no-attach"]) == 1
    assert "is not empty and is not a clone of https://h/a/b" in capsys.readouterr().err


def test_a_relative_folder_is_refused(tmp_path, fake_tmux, capsys):
    assert main(["start", "https://h/a/app", "app", "--no-attach"]) == 1
    assert capsys.readouterr().err.splitlines() == [
        "lado: app is not a full path: give one from / or ~"
    ]


def test_a_name_of_a_session_in_another_folder_is_refused_before_the_clone(
    tmp_path, repo, fake_tmux, capsys, monkeypatch
):
    assert main(["start", str(repo), "--name", "app", "--provider", "kilo", "--no-attach"]) == 0
    capsys.readouterr()
    for key, value in agent_helpers.fake_git(tmp_path / "fake", "ok").items():
        monkeypatch.setenv(key, value)
    assert main(["start", "https://h/a/app", str(tmp_path / "work" / "app"), "--no-attach"]) == 1
    assert f'session "app" was started in {repo}' in capsys.readouterr().err
    assert agent_helpers.fake_git_calls(tmp_path / "fake") == []
    assert not (tmp_path / "work").exists()


def _branch_of(folder: Path) -> str:
    return runtime.branch(str(folder))


def test_clone_and_start(tmp_path, fake_tmux, capsys):
    url = agent_helpers.bare_remote(tmp_path)
    folder = tmp_path / "work" / "app"
    start = ["start", url, str(folder), "--branch", "develop", "--provider", "kilo"]
    assert main([*start, "--no-attach"]) == 0
    assert _branch_of(folder) == "develop"
    sess = state.get_session("app")
    assert sess.repo == os.path.realpath(folder)
    captured = capsys.readouterr()
    assert f"Cloning branch develop of {url} into {folder}" in captured.err
    assert f'Started session "app" in {sess.repo}' in captured.out


def test_clone_into_the_default_folder_with_the_remotes_default_branch(
    home_workspace, tmp_path, fake_tmux, capsys, monkeypatch
):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    url = agent_helpers.bare_remote(tmp_path)
    assert main(["start", url, "--provider", "kilo", "--no-attach"]) == 0
    folder = tmp_path / "home" / "workspace" / "app"
    assert _branch_of(folder) == "main"
    assert f"Cloning the default branch of {url} into {folder}" in capsys.readouterr().err


def test_a_start_refused_after_the_clone_keeps_the_clone(tmp_path, fake_tmux, capsys):
    url = agent_helpers.bare_remote(tmp_path)
    folder = tmp_path / "app"
    assert main(["start", url, str(folder), "--provider", "nosuch", "--no-attach"]) == 1
    assert capsys.readouterr().err.splitlines()[-1] == f"lado: the clone stays in {folder}"
    assert _branch_of(folder) == "main"


def test_a_git_url_without_the_login_is_refused_before_the_clone(
    tmp_path, fake_tmux, capsys, monkeypatch, cli_logins
):
    for key, value in agent_helpers.fake_git(tmp_path / "fake", "ok").items():
        monkeypatch.setenv(key, value)
    cli_logins.logged_out()
    folder = tmp_path / "work" / "app"
    argv = ["start", "https://h/a/app", str(folder), "--provider", "claude", "--no-attach"]
    assert main(argv) == 1
    assert capsys.readouterr().err.splitlines() == [
        "lado: Claude Code is not logged in, so the session was not started: log in in LADO's "
        "UI (Settings → Providers and environment, `lado ui`), or set CLAUDE_CODE_OAUTH_TOKEN "
        "as LADO's secret or a project secret"
    ]
    assert agent_helpers.fake_git_calls(tmp_path / "fake") == []
    assert not (tmp_path / "work").exists()
    assert state.list_sessions() == []


def test_ctrl_c_during_the_clone(tmp_path, fake_tmux, capsys, monkeypatch):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.clone, "clone", interrupted)
    assert main(["start", "https://h/a/app", str(tmp_path / "app"), "--no-attach"]) == 130
    assert capsys.readouterr().err.splitlines()[-1] == "lado: clone cancelled"


def test_clone_progress_keeps_the_last_line_of_each_phase(capsys):
    shown = cli._CloneProgress(sys.stderr)
    for line in ("Counting objects:  50% (1/2)", "Counting objects: 100% (2/2), done."):
        shown(lado.clone.parse_progress(line))
    shown(lado.clone.parse_progress("Receiving objects:  10% (1/10)"))
    shown.done()
    assert capsys.readouterr().err.splitlines() == [
        "Counting objects: 100% (2/2), done.",
        "Receiving objects:  10% (1/10)",
    ]


def test_a_clone_failure_prints_its_hint(tmp_path, fake_tmux, capsys, monkeypatch):
    def refused(*args, **kwargs):
        raise lado.clone.CloneError(
            "ssh_denied",
            "cannot clone git@github.com:a/b.git: github.com refused this machine's ssh key (x)",
            runtime.Hint("Check that this machine's ssh key is added:", "ssh -T git@github.com"),
        )

    monkeypatch.setattr(cli.clone, "clone", refused)
    assert main(["start", "git@github.com:a/b.git", str(tmp_path / "b"), "--no-attach"]) == 1
    assert capsys.readouterr().err.splitlines()[-2:] == [
        "lado: cannot clone git@github.com:a/b.git: github.com refused this machine's ssh key (x)",
        "lado: Check that this machine's ssh key is added: ssh -T git@github.com",
    ]


# lado start --prompt / --prompt-file (openspec change first-message)


def _humans(session: str) -> list[str]:
    return [m.body for m in state.list_messages(session) if m.sender == state.HUMAN]


def _start(repo, name: str, *more: str) -> list[str]:
    return ["start", str(repo), "--name", name, "--provider", "kilo", "--no-attach", *more]


def test_start_with_a_prompt_queues_it_and_says_so(repo, fake_tmux, capsys):
    assert main(_start(repo, "s", "--prompt", "Take LAD-19")) == 0
    out = capsys.readouterr().out.splitlines()
    started = next(i for i, line in enumerate(out) if line.startswith('Started session "s"'))
    assert out[started + 1] == "first message: queued for the supervisor"
    assert _humans("s") == ["Take LAD-19"]


def test_start_without_a_prompt_says_nothing_of_it(repo, fake_tmux, capsys):
    assert main(_start(repo, "s")) == 0
    assert "first message" not in capsys.readouterr().out
    assert _humans("s") == []


def test_start_reads_the_prompt_from_a_file_and_from_stdin(repo, tmp_path, fake_tmux, monkeypatch):
    brief = tmp_path / "brief.md"
    brief.write_text("Это первое\nсообщение\n", encoding="utf-8")
    assert main(_start(repo, "a", "--prompt-file", str(brief))) == 0
    assert _humans("a") == ["Это первое\nсообщение"]
    monkeypatch.setattr("sys.stdin", io.StringIO("Line one\nLine two\n"))
    assert main(_start(repo, "b", "--prompt-file", "-")) == 0
    assert _humans("b") == ["Line one\nLine two"]


def test_start_refuses_both_prompt_options(repo, fake_tmux, capsys):
    with pytest.raises(SystemExit) as exited:
        main(_start(repo, "s", "--prompt", "a", "--prompt-file", "b"))
    assert exited.value.code == 2
    assert "not allowed with" in capsys.readouterr().err
    assert state.get_session("s") is None


def test_start_refuses_a_prompt_file_it_cannot_read(repo, tmp_path, fake_tmux, capsys):
    missing = tmp_path / "missing.md"
    assert main(_start(repo, "s", "--prompt-file", str(missing))) == 1
    err = capsys.readouterr().err
    assert err.startswith(f"lado: cannot read the first message from {missing}: ")
    assert state.get_session("s") is None
    assert fake_tmux == []


def test_start_refuses_a_prompt_file_that_is_no_utf8(repo, tmp_path, fake_tmux, capsys):
    binary = tmp_path / "image.png"
    binary.write_bytes(b"\x89PNG\xff\xfe")
    assert main(_start(repo, "s", "--prompt-file", str(binary))) == 1
    assert f"cannot read the first message from {binary}: " in capsys.readouterr().err
    assert state.get_session("s") is None


def test_start_refuses_an_empty_prompt(repo, fake_tmux, capsys):
    assert main(_start(repo, "s", "--prompt", "")) == 1
    assert capsys.readouterr().err.splitlines() == ["lado: the first message is empty"]
    assert state.get_session("s") is None
    assert fake_tmux == []


def test_a_git_url_with_a_bad_prompt_clones_nothing(tmp_path, fake_tmux, capsys, monkeypatch):
    def no_clone(*args, **kwargs):
        raise AssertionError("cloned")

    monkeypatch.setattr(cli.clone, "clone", no_clone)
    start = ["start", "file:///nowhere/app.git", str(tmp_path / "app"), "--no-attach"]
    assert main([*start, "--prompt", " "]) == 1
    assert "lado: the first message is empty" in capsys.readouterr().err
    assert not (tmp_path / "app").exists()


def test_a_git_url_reads_stdin_once_before_the_clone(tmp_path, fake_tmux, capsys, monkeypatch):
    url = agent_helpers.bare_remote(tmp_path)
    read = []

    class Stdin(io.StringIO):
        def read(self, *args):
            read.append(1)
            return super().read(*args)

    monkeypatch.setattr("sys.stdin", Stdin("Go\n"))
    start = ["start", url, str(tmp_path / "work" / "app"), "--provider", "kilo", "--no-attach"]
    assert main([*start, "--prompt-file", "-"]) == 0
    assert read == [1]  # a second read after the clone would give "" and refuse
    assert _humans("app") == ["Go"]
    assert "first message: queued for the supervisor" in capsys.readouterr().out


def test_a_resume_with_a_prompt(repo, fake_tmux, capsys):
    assert main(_start(repo, "s")) == 0
    assert main(["stop", "s"]) == 0
    capsys.readouterr()
    assert main(["start", str(repo), "--name", "s", "--no-attach", "--prompt", "Continue"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith('Resumed session "s"')
    assert out[1] == "first message: queued for the supervisor"
    last = state.list_messages("s")[-1]
    assert (last.sender, last.body) == ("human", "Continue")


def test_start_help_names_the_prompt_options(capsys):
    with pytest.raises(SystemExit):
        main(["start", "--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert "--prompt TEXT" in out
    assert "--prompt-file FILE" in out
    assert "- reads it from stdin" in out


def test_uninstall_help_names_its_options(capsys):
    with pytest.raises(SystemExit):
        main(["uninstall", "--help"])
    out = capsys.readouterr().out
    for option in ("--dry-run", "--keep-data", "--yes"):
        assert option in out


def test_uninstall_inside_an_agent_is_refused(lado_home, capsys, monkeypatch):
    monkeypatch.setenv("LADO_AGENT", "dev")
    state.home()
    before = sorted(p.name for p in lado_home.iterdir())
    assert main(["uninstall", "--yes"]) == 1
    assert capsys.readouterr().err == (
        'lado: lado uninstall is for the human; agent "dev" cannot use it\n'
    )
    assert sorted(p.name for p in lado_home.iterdir()) == before


def test_uninstall_asks_and_needs_yes_without_a_terminal(lado_home, capsys, monkeypatch):
    from lado import uninstall

    ran = []
    monkeypatch.setattr(uninstall, "run", lambda found, say=print: ran.append(found) or 0)
    tty(monkeypatch, None)
    assert main(["uninstall"]) == 1
    captured = capsys.readouterr()
    assert "will be uninstalled" in captured.out
    assert captured.err == "lado: not uninstalled: confirm with --yes\n"
    for answer in ("n", ""):
        tty(monkeypatch, answer)
        assert main(["uninstall"]) == 1
        assert capsys.readouterr().out.endswith("Uninstall? [y/N] Not uninstalled.\n")
    assert ran == []
    tty(monkeypatch, "y")
    assert main(["uninstall"]) == 0
    assert main(["uninstall", "--yes"]) == 0
    assert main(["uninstall", "--yes", "--keep-data"]) == 0
    assert [found.keep_data for found in ran] == [False, False, True]


@pytest.mark.parametrize("ends", ["deleted", "crashed"])
def test_uninstall_starts_no_statistics_sender_and_records_no_error(lado_home, monkeypatch, ends):
    """Both would make the LADO_HOME it deleted again (lado.telemetry's folder)."""
    from lado import telemetry, uninstall

    def run(found, say=print):
        if ends == "crashed":
            raise RuntimeError("boom")
        return 0

    called = []
    monkeypatch.setattr(uninstall, "run", run)
    monkeypatch.setattr(telemetry, "kick", lambda: called.append("kick"))
    monkeypatch.setattr(telemetry, "record", lambda *a, **k: called.append("record"))
    if ends == "crashed":
        with pytest.raises(RuntimeError):
            main(["uninstall", "--yes"])
    else:
        assert main(["uninstall", "--yes"]) == 0
    assert called == []


def test_uninstall_does_not_migrate_before_its_plan(repo, fake_tmux, capsys, monkeypatch):
    assert main(["start", str(repo), "--provider", "claude", "--name", "old", "--no-attach"]) == 0
    agent_helpers.previous_schema()
    capsys.readouterr()
    assert main(["uninstall", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert f"lado.db (schema {state.SCHEMA_VERSION - 1}) is upgraded first" in out
    assert state.schema_version() == state.SCHEMA_VERSION - 1


def test_uninstall_of_a_newer_database_is_an_error(lado_home, capsys):
    state.home()
    with sqlite3.connect(lado_home / "lado.db") as db:
        db.execute(f"PRAGMA user_version = {state.SCHEMA_VERSION + 1}")
    assert main(["uninstall", "--yes"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("lado: ") and "made by a newer LADO" in err


def test_title_sets_reads_and_clears(capsys):
    state.add_session(state.Session("s", "/r", None, "claude"))
    assert main(["title", "s"]) == 0
    assert capsys.readouterr().out == "s has no title\n"
    assert main(["title", "s", "  Review  "]) == 0
    assert capsys.readouterr().out == 's: title "Review"\n'
    assert main(["title", "s"]) == 0
    assert capsys.readouterr().out == "Review\n"
    assert main(["title", "s", "--clear"]) == 0
    assert capsys.readouterr().out == "s has no title\n"
    assert state.get_session("s").title is None
    assert main(["title", "s", "s"]) == 0  # its own name is no title
    assert capsys.readouterr().out == "s has no title\n"


def test_title_with_text_and_clear_exits_2(capsys):
    state.add_session(state.Session("s", "/r", None, "claude"))
    with pytest.raises(SystemExit) as exit_:
        main(["title", "s", "Review", "--clear"])
    assert exit_.value.code == 2
    assert "argument --clear: not allowed with argument text" in capsys.readouterr().err


def test_title_refuses_a_bad_title_and_changes_nothing(capsys):
    state.add_session(state.Session("s", "/r", None, "claude"))
    main(["title", "s", "Old"])
    capsys.readouterr()
    assert main(["title", "s", "a\nb"]) == 1
    assert "a title is one line" in capsys.readouterr().err
    assert main(["title", "s", "x" * 81]) == 1
    assert "a title is at most 80 characters" in capsys.readouterr().err
    assert state.get_session("s").title == "Old"


def test_title_is_refused_inside_an_agent_but_read(capsys, monkeypatch):
    state.add_session(state.Session("s", "/r", None, "claude"))
    state.set_title("s", "Review")
    monkeypatch.setenv("LADO_AGENT", "w1")
    for argv in (["title", "s", "x"], ["title", "s", "--clear"]):
        assert main(argv) == 1
        assert 'lado title is for the human; agent "w1" cannot use it' in capsys.readouterr().err
    assert state.get_session("s").title == "Review"
    assert main(["title", "s"]) == 0
    assert capsys.readouterr().out == "Review\n"


def test_title_of_an_unknown_session(capsys):
    for argv in (["title", "nope"], ["title", "nope", "x"]):
        assert main(argv) == 1
        assert 'unknown session "nope"' in capsys.readouterr().err


def test_ls_shows_the_title_after_the_name(repo, fake_tmux, capsys):
    main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"])
    main(["start", str(repo), "--provider", "claude", "--name", "t", "--no-attach"])
    runtime.set_title("s", "Rename sessions (LAD-66)")
    capsys.readouterr()
    main(["ls"])
    lines = capsys.readouterr().out.splitlines()
    heads = [line.partition("  (")[0] for line in lines if not line.startswith(" ")]
    assert heads == [f's "Rename sessions (LAD-66)"  {repo}', f"t  {repo}"]


# lado start --new [<folder>] (openspec change start-from-scratch)


def test_new_with_a_git_url_or_a_second_folder_is_a_usage_error(tmp_path, capsys):
    for argv in (
        ["start", "--new", "https://h/a/app"],
        ["start", "--new", str(tmp_path / "a"), str(tmp_path / "b")],
    ):
        with pytest.raises(SystemExit) as exited:
            main(argv)
        assert exited.value.code == 2
        assert "--new takes a folder, not a git URL or a second folder" in capsys.readouterr().err
    assert not (tmp_path / "a").exists()


def test_a_new_folder_from_the_terminal(tmp_path, git_config, fake_tmux, capsys):
    folder = tmp_path / "lado" / "shop"
    assert main(["start", "--new", str(folder), "--provider", "kilo", "--no-attach"]) == 0
    out = capsys.readouterr().out.splitlines()
    sess = state.get_session("shop")
    assert sess.repo == os.path.realpath(folder)
    assert out[:2] == [
        f"Made {folder} a git repository with an empty first commit",
        f'Started session "shop" in {sess.repo}',
    ]
    log = subprocess.run(
        ["git", "-C", str(folder), "log", "--format=%s"], capture_output=True, text=True
    )
    assert log.stdout == "Start from scratch\n"


def test_new_without_the_login_makes_no_folder(tmp_path, git_config, fake_tmux, capsys, cli_logins):
    cli_logins.logged_out()
    folder = tmp_path / "lado" / "shop"
    assert main(["start", "--new", str(folder), "--provider", "claude", "--no-attach"]) == 1
    assert "so the session was not started" in capsys.readouterr().err
    assert not folder.exists()
    assert state.list_sessions() == []


def test_new_takes_the_name_given_and_a_relative_folder(
    tmp_path, git_config, fake_tmux, capsys, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    argv = ["start", "--new", "shop", "--name", "Coffee", "--provider", "kilo", "--no-attach"]
    assert main(argv) == 0
    assert f"Made {tmp_path / 'shop'} a git repository" in capsys.readouterr().out
    assert state.get_session("coffee").repo == os.path.realpath(tmp_path / "shop")


def test_new_in_the_current_folder(tmp_path, git_config, fake_tmux, monkeypatch):
    (tmp_path / "coffee-site").mkdir()
    monkeypatch.chdir(tmp_path / "coffee-site")
    assert main(["start", "--new", "--provider", "kilo", "--no-attach"]) == 0
    assert state.get_session("coffee-site").repo == os.path.realpath(tmp_path / "coffee-site")


def test_a_folder_with_files(tmp_path, git_config, fake_tmux, capsys):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "todo.txt").write_text("x")
    assert main(["start", "--new", str(tmp_path / "notes"), "--no-attach"]) == 1
    assert capsys.readouterr().err.splitlines() == [
        f"lado: {tmp_path / 'notes'} is not empty: choose a new or empty folder",
        "lado: Make it a repository with a first commit, in that folder: "
        "git init && git add -A && git commit -m 'First commit'",
    ]
    assert os.listdir(tmp_path / "notes") == ["todo.txt"]
    assert state.list_sessions() == []


def test_new_inside_a_repository_names_its_start(repo, git_config, fake_tmux, capsys):
    assert main(["start", "--new", str(repo / "site"), "--no-attach"]) == 1
    err = capsys.readouterr().err.splitlines()
    real = os.path.realpath(repo)
    assert err[-1] == f"lado: Start a session in that repository: lado start '{real}'"
    assert not (repo / "site").exists()


def test_new_without_the_author(tmp_path, git_config, fake_tmux, capsys):
    git_config.write_text("")
    assert main(["start", "--new", str(tmp_path / "shop"), "--no-attach"]) == 1
    assert capsys.readouterr().err.splitlines() == [
        "lado: git doesn't know who signs the agents' commits: it has no user.name or user.email",
        "lado: Tell git who you are, once for this computer: git config --global user.name "
        '"Your Name" && git config --global user.email you@example.com',
    ]
    assert not (tmp_path / "shop").exists()


def test_a_start_refused_after_new_keeps_the_repository(tmp_path, git_config, fake_tmux, capsys):
    folder = tmp_path / "shop"
    assert main(["start", "--new", str(folder), "--provider", "nosuch", "--no-attach"]) == 1
    assert capsys.readouterr().err.splitlines()[-1] == f"lado: the repository stays in {folder}"
    assert runtime.check_repo(str(folder)) == os.path.realpath(folder)


# lado project (openspec change projects-in-core)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """The workspace: LADO_REPOS=<tmp>/ws, not made."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    return tmp_path / "ws"


def test_project_create_list_show_rename(ws, capsys):
    assert main(["project", "list"]) == 0
    assert capsys.readouterr().out == "No projects. Make one with: lado project create <id>\n"
    assert main(["project", "create", "shop-eu", "--title", "Shop EU"]) == 0
    folder = ws / "projects" / "shop-eu"
    assert capsys.readouterr().out == f'Made project shop-eu "Shop EU": {folder}\n'
    assert folder.is_dir()
    assert main(["project", "create", "a"]) == 0
    assert capsys.readouterr().out == f"Made project a: {ws / 'projects' / 'a'}\n"
    (ws / "projects" / "a").rmdir()
    assert main(["project", "list"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        f"a        a        {ws / 'projects' / 'a'}  (folder not found)",
        f"shop-eu  Shop EU  {folder}",
    ]
    utc = datetime.datetime(2026, 10, 21, 18, 5, 9, tzinfo=datetime.timezone.utc)
    with state.connect() as db:
        db.execute("UPDATE projects SET created_at = '2026-10-21 18:05:09' WHERE id = 'shop-eu'")
    assert main(["project", "show", "shop-eu"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        'shop-eu "Shop EU"',
        f"  folder:  {folder}",
        f"  made:    {utc.astimezone():%Y-%m-%d %H:%M}",
        "  repositories: none",
        "  variables: none",
        "  secrets: none",
    ]
    assert main(["project", "show", "a"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[:2] == ["a", f"  folder:  {ws / 'projects' / 'a'}  (folder not found)"]
    assert main(["project", "rename", "shop-eu", "Shop"]) == 0
    assert capsys.readouterr().out == 'shop-eu: title "Shop"\n'
    assert main(["project", "rename", "shop-eu", ""]) == 0
    assert capsys.readouterr().out == "shop-eu: no title\n"
    assert folder.is_dir()


@pytest.mark.parametrize(
    "argv",
    [["show", "nope"], ["rename", "nope", "x"], ["delete", "nope"], ["delete", "nope", "--yes"]],
)
def test_project_commands_refuse_an_unknown_project(ws, capsys, argv):
    assert main(["project", *argv]) == 1
    assert capsys.readouterr().err == 'lado: unknown project "nope"\n'


def test_project_create_refuses_with_its_reason(ws, capsys):
    assert main(["project", "create", "Shop"]) == 1
    assert "lado: the project id Shop is not valid" in capsys.readouterr().err
    assert not ws.exists()


def test_project_delete_shows_unpushed_work_and_needs_yes(ws, git_config, capsys):
    assert main(["project", "create", "shop"]) == 0
    folder = ws / "projects" / "shop"
    repo = init_repo(folder / "frontend")
    (repo / "new.txt").write_text("x")
    capsys.readouterr()
    assert main(["project", "delete", "shop"]) == 1
    captured = capsys.readouterr()
    assert captured.out.splitlines() == [
        f"Unpushed work in {folder}:",
        "  frontend: uncommitted changes; branch main not pushed",
    ]
    assert captured.err == (
        f"lado: deleting project shop removes its folder {folder} with everything in it; "
        "run again with --yes\n"
    )
    assert folder.is_dir() and state.get_project("shop")
    assert main(["project", "delete", "shop", "--yes"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "Deleted project shop"
    assert not folder.exists() and state.get_project("shop") is None
    assert (ws / "projects").is_dir()


def test_project_delete_with_nothing_unpushed_prints_no_list(ws, capsys):
    assert main(["project", "create", "shop"]) == 0
    capsys.readouterr()
    assert main(["project", "delete", "shop"]) == 1
    assert capsys.readouterr().out == ""


def test_project_delete_names_a_session_from_before_projects(ws, capsys):
    assert main(["project", "create", "shop"]) == 0
    folder = ws / "projects" / "shop"
    state.add_session(state.Session("old-site", str(folder / "site"), None, "kilo"))
    state.stop_session("old-site")
    capsys.readouterr()
    assert main(["project", "delete", "shop"]) == 1
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["Sessions to forget: old-site (no project)"]
    assert captured.err.endswith(" and forgets its 1 session; run again with --yes\n")
    assert main(["project", "delete", "shop", "--yes"]) == 0
    assert state.list_sessions() == [] and not folder.exists()


def test_project_delete_of_a_link_folder_lists_nothing_of_its_target(ws, git_config, capsys):
    assert main(["project", "create", "shop"]) == 0
    link = ws / "projects" / "shop"
    link.rmdir()
    target = ws.parent / "srv-shop"
    (init_repo(target / "app") / "new.txt").write_text("x")
    link.symlink_to(target)
    capsys.readouterr()
    assert main(["project", "delete", "shop"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"lado: deleting project shop removes the link {link} only, not its target {target}; "
        "run again with --yes\n"
    )
    assert main(["project", "delete", "shop", "--yes"]) == 0
    assert not os.path.lexists(link) and (target / "app" / "new.txt").is_file()


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any folder")
def test_project_delete_of_an_unreadable_folder_prints_no_traceback(ws, capsys):
    assert main(["project", "create", "shop"]) == 0
    folder = ws / "projects" / "shop"
    folder.chmod(0)
    capsys.readouterr()
    try:
        assert main(["project", "delete", "shop"]) == 1
    finally:
        folder.chmod(0o755)
    captured = capsys.readouterr()
    assert captured.out.splitlines() == [
        f"Unpushed work in {folder}:",
        "  the project's folder: could not check: Permission denied",
    ]
    assert captured.err.startswith("lado: deleting project shop removes its folder ")
    assert "Traceback" not in captured.err


@pytest.mark.parametrize(
    "argv",
    [["create", "acme"], ["rename", "shop", "X"], ["delete", "shop"], ["delete", "shop", "--yes"]],
)
def test_agents_cannot_change_projects(ws, capsys, monkeypatch, argv):
    assert main(["project", "create", "shop", "--title", "Shop"]) == 0
    capsys.readouterr()
    monkeypatch.setenv("LADO_SESSION", "s")
    monkeypatch.setenv("LADO_AGENT", "w1")
    assert main(["project", *argv]) == 1
    assert capsys.readouterr().err == (
        f'lado: lado project {argv[0]} is for the human; agent "w1" cannot use it\n'
    )
    assert [(p.id, p.title) for p in state.list_projects()] == [("shop", "Shop")]
    assert (ws / "projects" / "shop").is_dir() and not (ws / "projects" / "acme").exists()
    assert main(["project", "list"]) == 0
    assert main(["project", "show", "shop"]) == 0


# Sessions in projects (openspec change sessions-in-projects)


@pytest.fixture
def shop(ws, git_config, capsys):
    """The project shop titled Shop with its repository frontend; its folder."""
    assert main(["project", "create", "shop", "--title", "Shop"]) == 0
    init_repo(ws / "projects" / "shop" / "frontend")
    capsys.readouterr()
    return ws / "projects" / "shop"


def test_start_in_a_project(shop, fake_tmux, capsys):
    argv = ["start", "--project", "shop", "--repo", "frontend", "--provider", "kilo", "--no-attach"]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert f'Started session "shop-frontend" in {shop / "frontend"} (project shop)\n' in out
    assert state.get_session("shop-frontend").project == "shop"
    assert main(["ls"]) == 0
    assert (
        capsys.readouterr()
        .out.splitlines()[0]
        .startswith(f"shop-frontend  {shop / 'frontend'}  project shop  (session loop not running")
    )  # the project after the folder, before the status


@pytest.mark.parametrize(
    ("argv", "said"),
    [
        (["--project", "shop"], "--project needs --repo NAME"),
        (["--repo", "frontend"], "--repo needs --project ID"),
        (["/src/app", "--project", "shop", "--repo", "frontend"], "--project takes no folder"),
        (["https://h/a/app", "--project", "shop", "--repo", "frontend"], "--project takes no"),
        (["--new", "--project", "shop", "--repo", "frontend"], "--project takes no folder"),
        (["--branch", "dev", "--project", "shop", "--repo", "frontend"], "--project takes no"),
    ],
)
def test_start_with_a_project_takes_its_repository_only(shop, fake_tmux, capsys, argv, said):
    with pytest.raises(SystemExit) as usage:
        main(["start", *argv, "--no-attach"])
    assert usage.value.code == 2
    assert said in capsys.readouterr().err
    assert state.list_sessions() == []


def test_start_refuses_a_repository_the_project_does_not_have(shop, fake_tmux, capsys):
    assert main(["start", "--project", "shop", "--repo", "web", "--no-attach"]) == 1
    assert capsys.readouterr().err == (
        "lado: project shop has no repository web; its repositories: frontend\n"
    )


def test_start_without_the_project_in_its_repository_offers_it(shop, fake_tmux, capsys):
    assert main(["start", str(shop / "frontend"), "--no-attach"]) == 1
    assert capsys.readouterr().err.splitlines() == [
        f"lado: {shop / 'frontend'} belongs to the project Shop: start a session in the project",
        "lado: Start a session in the project: lado start --project shop --repo frontend",
    ]
    assert state.list_sessions() == []


def test_a_clone_into_a_project_is_refused_before_cloning(shop, fake_tmux, capsys):
    assert main(["start", "https://h/shop/web", str(shop / "web"), "--no-attach"]) == 1
    assert capsys.readouterr().err.splitlines() == [
        f"lado: {shop / 'web'} belongs to the project Shop: start a session in the project",
        "lado: Add a repository to the project: lado project repo add shop https://h/shop/web",
    ]
    assert sorted(p.name for p in shop.iterdir()) == ["frontend"]


def test_a_fresh_start_in_a_project_is_refused(shop, fake_tmux, capsys):
    assert main(["start", "--new", str(shop / "site"), "--no-attach"]) == 1
    assert capsys.readouterr().err.splitlines() == [
        f"lado: {shop / 'site'} belongs to the project Shop: start a session in the project",
        "lado: Add a repository to the project: lado project repo add shop --new site",
    ]
    assert not (shop / "site").exists()


def test_project_show_lists_the_repositories(shop, tmp_path, capsys):
    frontend = shop / "frontend"
    subprocess.run(
        ["git", "-C", str(frontend), "remote", "add", "origin", "https://github.com/shop/frontend"],
        check=True,
    )
    backend = init_repo(shop / "backend")
    subprocess.run(["git", "-C", str(backend), "switch", "-q", "-c", "dev"], check=True)
    docs = init_repo(tmp_path / "docs")
    (shop / "docs").symlink_to(docs)
    assert main(["project", "show", "shop"]) == 0
    assert capsys.readouterr().out.splitlines()[3:] == [
        "  repositories:",
        "    backend   dev   (no remote)",
        f"    docs      (a link to {docs}: clone it into {shop} instead)",
        "    frontend  main  https://github.com/shop/frontend",
        "  variables: none",
        "  secrets: none",
    ]


def test_project_show_without_repositories(shop, capsys):
    shutil.rmtree(shop)
    assert main(["project", "show", "shop"]) == 0
    assert capsys.readouterr().out.splitlines()[-3] == "  repositories: none"


def test_project_delete_with_sessions(shop, capsys):
    for name in ("shop-frontend", "fix-login"):
        state.add_session(
            state.Session(name, str(shop / "frontend"), None, provider="kilo", project="shop")
        )
    state.stop_session("fix-login")
    assert main(["project", "delete", "shop", "--yes"]) == 1
    assert capsys.readouterr().err == (
        "lado: project shop has sessions not stopped: shop-frontend; stop them first with "
        "lado stop <name>\n"
    )
    state.stop_session("shop-frontend")
    run = state.Run("shop-frontend", "f/x", "feature", "{}", {}, "do x", "design", "/w", "b")
    state.add_run(run, [], None)
    assert main(["project", "delete", "shop"]) == 1
    captured = capsys.readouterr()
    assert (
        captured.out.splitlines()[0] == "Sessions to forget: fix-login, shop-frontend (1 open run)"
    )
    assert captured.err.endswith(" and forgets its 2 sessions; run again with --yes\n")
    assert main(["project", "delete", "shop", "--yes"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "Deleted project shop"
    assert state.list_sessions() == [] and not shop.exists()


def test_project_alone_prints_its_help(capsys):
    assert main(["project"]) == 0
    out = capsys.readouterr().out
    for command in ("list", "create", "show", "rename", "delete", "repo"):
        assert command in out


# A project's repositories (openspec change project-repositories)


def test_project_repo_alone_prints_its_help(capsys):
    assert main(["project", "repo"]) == 0
    out = capsys.readouterr().out
    assert "add" in out and "remove" in out


def _added(folder: Path, name: str) -> list[str]:
    return [
        f"Added repository {name} to project shop: {folder / name}",
        f"Start a session in it: lado start --project shop --repo {name}",
    ]


def test_project_repo_add_clones_into_the_project(shop, tmp_path, capsys):
    url = agent_helpers.bare_remote(tmp_path)
    assert main(["project", "repo", "add", "shop", url]) == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines() == _added(shop, "app")
    assert captured.err.splitlines()[0] == (
        f"Cloning the default branch of {url} into {shop / 'app'}"
    )
    assert (
        main(["project", "repo", "add", "shop", url, "--name", "dev", "--branch", "develop"]) == 0
    )
    captured = capsys.readouterr()
    assert captured.err.splitlines()[0] == f"Cloning branch develop of {url} into {shop / 'dev'}"
    assert main(["project", "show", "shop"]) == 0
    listed = capsys.readouterr().out
    assert f"    app       main     {url}" in listed
    assert f"    dev       develop  {url}" in listed


def test_project_repo_add_new(shop, capsys):
    assert main(["project", "repo", "add", "shop", "--new", "site"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        f"Made {shop / 'site'} a git repository with an empty first commit",
        *_added(shop, "site"),
    ]
    assert [r.name for r in projects.repositories("shop")] == ["frontend", "site"]


@pytest.mark.parametrize(
    ("argv", "said"),
    [
        (["https://h/shop/web", "--new", "web"], "a git URL or --new, not both"),
        ([], "a git URL or --new NAME"),
        (["--new", "web", "--name", "x"], "--name and --branch go with a git URL"),
        (["--new", "web", "--branch", "dev"], "--name and --branch go with a git URL"),
        (["./web"], "./web is not a git URL"),
    ],
)
def test_project_repo_add_usage(shop, capsys, argv, said):
    with pytest.raises(SystemExit) as usage:
        main(["project", "repo", "add", "shop", *argv])
    assert usage.value.code == 2
    assert said in capsys.readouterr().err
    assert sorted(p.name for p in shop.iterdir()) == ["frontend"]


@pytest.mark.parametrize(
    ("argv", "said"),
    [
        (["shop", "--new", "frontend"], "already exists in project shop"),
        (["shop", "--new", ".hidden"], "the repository name .hidden is not valid"),
        (["shop", "https://h/"], "names no repository"),
        (["shop", "https://h/shop/web", "--name", ""], "the repository name  is not valid"),
        (["acme", "--new", "crm"], 'unknown project "acme"'),
    ],
)
def test_project_repo_add_refusals(shop, capsys, argv, said):
    assert main(["project", "repo", "add", *argv]) == 1
    err = capsys.readouterr().err
    assert err.startswith("lado: ") and said in err
    assert sorted(p.name for p in shop.iterdir()) == ["frontend"]


@pytest.mark.parametrize(
    "argv",
    [["add", "shop", "--new", "site"], ["remove", "shop", "frontend"], ["remove", "shop", "x"]],
)
def test_agents_cannot_change_a_projects_repositories(shop, capsys, monkeypatch, argv):
    monkeypatch.setenv("LADO_SESSION", "s")
    monkeypatch.setenv("LADO_AGENT", "w1")
    assert main(["project", "repo", *argv]) == 1
    assert capsys.readouterr().err == (
        f'lado: lado project repo {argv[0]} is for the human; agent "w1" cannot use it\n'
    )
    assert sorted(p.name for p in shop.iterdir()) == ["frontend"]


def test_project_repo_remove(shop, capsys):
    state.add_session(
        state.Session("shop-frontend", str(shop / "frontend"), None, "kilo", project="shop")
    )
    assert main(["project", "repo", "remove", "shop", "frontend", "--yes"]) == 1
    assert capsys.readouterr().err == (
        "lado: repository frontend of project shop has sessions not stopped: shop-frontend; "
        "stop them first with lado stop <name>\n"
    )
    state.stop_session("shop-frontend")
    assert main(["project", "repo", "remove", "shop", "frontend"]) == 1
    captured = capsys.readouterr()
    assert captured.out.splitlines() == [
        "Sessions to forget: shop-frontend",
        f"Unpushed work in {shop / 'frontend'}:",
        "  frontend: branch main not pushed",
    ]
    assert captured.err == (
        f"lado: removing repository frontend of project shop deletes its folder "
        f"{shop / 'frontend'} with everything in it and forgets its 1 session; run again with "
        "--yes\n"
    )
    assert (shop / "frontend").is_dir()
    assert main(["project", "repo", "remove", "shop", "frontend", "--yes"]) == 0
    assert (
        capsys.readouterr().out.splitlines()[-1] == "Removed repository frontend from project shop"
    )
    assert not (shop / "frontend").exists() and state.list_sessions() == []
    assert state.get_project("shop") and shop.is_dir()


def test_project_repo_remove_names_a_session_from_before_projects(shop, capsys):
    state.add_session(state.Session("old-frontend", str(shop / "frontend"), None, "kilo"))
    state.stop_session("old-frontend")
    assert main(["project", "repo", "remove", "shop", "frontend"]) == 1
    captured = capsys.readouterr()
    assert captured.out.splitlines()[0] == "Sessions to forget: old-frontend (no project)"
    assert captured.err.endswith("and forgets its 1 session; run again with --yes\n")
    assert main(["project", "repo", "remove", "shop", "frontend", "--yes"]) == 0
    assert not (shop / "frontend").exists() and state.list_sessions() == []


def test_project_repo_remove_a_link(shop, tmp_path, capsys):
    target = tmp_path / "docs"
    target.mkdir()
    (shop / "docs").symlink_to(target)
    assert main(["project", "repo", "remove", "shop", "docs"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"lado: removing docs of project shop deletes the link only, not its target {target}; "
        "run again with --yes\n"
    )
    assert main(["project", "repo", "remove", "shop", "docs", "--yes"]) == 0
    assert capsys.readouterr().out == "Removed the link docs from project shop\n"
    assert target.is_dir() and not os.path.lexists(shop / "docs")


def test_project_repo_remove_refusals(shop, capsys):
    (shop / "notes").mkdir()
    assert main(["project", "repo", "remove", "shop", "notes", "--yes"]) == 1
    assert capsys.readouterr().err == (
        "lado: notes in project shop is not a repository: LADO removes only repositories and "
        "links\n"
    )
    assert main(["project", "repo", "remove", "shop", "web"]) == 1
    assert capsys.readouterr().err == (
        "lado: project shop has no repository web; its repositories: frontend\n"
    )
    assert main(["project", "repo", "remove", "acme", "web"]) == 1
    assert capsys.readouterr().err == 'lado: unknown project "acme"\n'
    assert (shop / "notes").is_dir() and (shop / "frontend").is_dir()


# A project's variables (openspec change project-variables)


def test_project_set_unset_and_show(shop, capsys):
    assert main(["project", "set", "shop", "MODEL_URL", "http://localhost:11434"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Set MODEL_URL in project shop.",
        "Agents started from now on get it.",
    ]
    assert main(["project", "set", "shop", "BOARD_URL", "https://old"]) == 0
    assert main(["project", "set", "shop", "BOARD_URL", "https://a\nnext\r"]) == 0
    capsys.readouterr()
    assert main(["project", "show", "shop"]) == 0
    assert capsys.readouterr().out.splitlines()[-4:] == [
        "  variables:",
        "    BOARD_URL  https://a\\nnext\\r",
        "    MODEL_URL  http://localhost:11434",
        "  secrets: none",
    ]
    assert state.project_variables("shop")["BOARD_URL"] == "https://a\nnext\r"
    assert main(["project", "unset", "shop", "BOARD_URL"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Removed BOARD_URL from project shop.",
        "Agents started from now on do not get it.",
    ]
    assert main(["project", "unset", "shop", "MODEL_URL"]) == 0
    capsys.readouterr()
    assert main(["project", "show", "shop"]) == 0
    assert capsys.readouterr().out.splitlines()[-2] == "  variables: none"


def test_project_set_names_the_running_sessions(shop, capsys, monkeypatch):
    for name in ("shop-frontend", "fix-login", "old"):
        state.add_session(
            state.Session(name, str(shop / "frontend"), None, provider="kilo", project="shop")
        )
    state.stop_session("old")
    monkeypatch.setattr(runtime, "session_status", _not_stopped)
    assert main(["project", "set", "shop", "BOARD_URL", "https://a"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Set BOARD_URL in project shop.",
        "Agents started from now on get it; running sessions of shop keep the old environment "
        "until restarted: fix-login, shop-frontend",
    ]
    assert main(["project", "unset", "shop", "BOARD_URL"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == (
        "Agents started from now on do not get it; running sessions of shop keep the old "
        "environment until restarted: fix-login, shop-frontend"
    )


def _not_stopped(sess):
    return runtime.SessionStatus.STOPPED if sess.stopped_at else runtime.SessionStatus.RUNNING


def test_project_set_a_value_that_starts_with_a_dash(shop, capsys):
    assert main(["project", "set", "shop", "FLAGS", "--", "-v"]) == 0
    assert state.project_variables("shop") == {"FLAGS": "-v"}


@pytest.mark.parametrize(
    ("argv", "said"),
    [
        (["set", "shop", "GH_TOKEN", "x"], "GH_TOKEN looks like a secret (TOKEN): "),
        (["set", "shop", "yougile_api_key", "x"], "yougile_api_key looks like a secret (KEY): "),
        (["set", "shop", "PATH", "/tmp"], "PATH is reserved: LADO or the agent CLIs set it"),
        (["set", "shop", "LADO_HOME", "/h"], "LADO_HOME is reserved: "),
        (["set", "shop", "CLAUDE_CONFIG_DIR", "/c"], "CLAUDE_CONFIG_DIR is reserved: "),
        (["set", "shop", "A-B", "x"], "the name A-B is not a variable name: "),
        (["set", "shop", "BIG", "x" * 70000], "the value of BIG is larger than 64 KiB"),
        (["set", "nope", "BOARD_URL", "x"], 'unknown project "nope"'),
        (["unset", "nope", "BOARD_URL"], 'unknown project "nope"'),
        (["show", "nope"], 'unknown project "nope"'),
        (
            ["unset", "shop", "MODEL_URL"],
            "project shop has no variable or secret MODEL_URL; its variables: none; its "
            "secrets: none",
        ),
    ],
)
def test_project_set_and_unset_refusals(shop, capsys, argv, said):
    assert main(["project", *argv]) == 1
    err = capsys.readouterr().err
    assert err.startswith(f"lado: {said}") and err.count("\n") == 1
    assert state.project_variables("shop") == {}


def test_project_set_s_secret_hint(shop, capsys):
    assert main(["project", "set", "shop", "DB_PASSWORD", "x"]) == 1
    assert capsys.readouterr().err == (
        "lado: DB_PASSWORD looks like a secret (PASSWORD): a plain variable takes no name with "
        "TOKEN, KEY, SECRET or PASSWORD; set it as a secret with lado project set shop "
        "DB_PASSWORD --secret\n"
    )


@pytest.mark.parametrize(
    "argv", [["set", "shop", "MODEL_URL", "http://evil"], ["unset", "shop", "BOARD_URL"]]
)
def test_agents_cannot_change_a_project_s_variables(shop, capsys, monkeypatch, argv):
    assert main(["project", "set", "shop", "BOARD_URL", "https://a"]) == 0
    capsys.readouterr()
    monkeypatch.setenv("LADO_SESSION", "s")
    monkeypatch.setenv("LADO_AGENT", "w1")
    assert main(["project", *argv]) == 1
    assert capsys.readouterr().err == (
        f'lado: lado project {argv[0]} is for the human; agent "w1" cannot use it\n'
    )
    assert state.project_variables("shop") == {"BOARD_URL": "https://a"}
    assert main(["project", "show", "shop"]) == 0
    assert capsys.readouterr().out.splitlines()[-2] == "    BOARD_URL  https://a"


def test_project_set_racing_a_delete_is_an_unknown_project(shop, capsys, monkeypatch):
    checked = projects.check_variable

    def check_then_delete(id, name, value):
        checked(id, name, value)
        state.delete_project(id)

    monkeypatch.setattr(projects, "check_variable", check_then_delete)
    assert main(["project", "set", "shop", "BOARD_URL", "https://a"]) == 1
    assert capsys.readouterr().err == 'lado: unknown project "shop"\n'
    assert state.project_variables("shop") == {}


def test_project_delete_takes_the_variables_along(shop, capsys, monkeypatch):
    assert main(["project", "set", "shop", "BOARD_URL", "https://a"]) == 0
    monkeypatch.setattr("sys.stdin", Stdin("ghp_1\n"))
    assert main(["project", "set", "shop", "GH_TOKEN", "--secret"]) == 0
    assert main(["project", "delete", "shop", "--yes"]) == 0
    assert not os.path.lexists(project_secrets.data_folder("shop"))
    assert main(["project", "create", "shop"]) == 0
    capsys.readouterr()
    assert main(["project", "show", "shop"]) == 0
    assert capsys.readouterr().out.splitlines()[-2:] == ["  variables: none", "  secrets: none"]


# A project's secrets (openspec change project-secrets)


class Stdin(io.StringIO):
    """stdin as a pipe (no terminal) holding `text`, or a terminal; whether it was read."""

    def __init__(self, text: str = "", tty: bool = False):
        super().__init__()
        self.buffer = io.BytesIO(text.encode())
        self.tty = tty

    def isatty(self) -> bool:
        return self.tty

    @property
    def touched(self) -> bool:
        return self.buffer.tell() > 0


def secret_file(name: str) -> Path:
    return project_secrets.folder("shop") / name


@pytest.mark.parametrize(
    ("given", "stored"),
    [
        ("ghp_2\n", "ghp_2"),
        ("ghp_2\r\n", "ghp_2"),
        ("ghp_2", "ghp_2"),
        ("line1\nline2\n", "line1\nline2"),
        ("a=b c é\n\n", "a=b c é\n"),
        ("x\r\n\r\n", "x\r\n"),
        ("\n\n", "\n"),  # one line break dropped: a line break is left, a value
    ],
)
def test_project_set_secret_from_a_pipe(shop, capsys, monkeypatch, given, stored):
    """`stored` is what the agents get: one line break of stdin's end dropped, no more."""
    monkeypatch.setattr("sys.stdin", Stdin(given))
    monkeypatch.setattr("getpass.getpass", lambda prompt: pytest.fail("asked"))
    assert main(["project", "set", "shop", "GH_TOKEN", "--secret"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Set secret GH_TOKEN in project shop.",
        "Agents started from now on get it.",
    ]
    assert project_secrets.read("shop").values == {"GH_TOKEN": stored}
    assert state.project_variables("shop") == {}


def test_project_set_secret_on_a_terminal_asks_without_echo(shop, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", Stdin(tty=True))
    asked = []
    monkeypatch.setattr("getpass.getpass", lambda prompt: asked.append(prompt) or "ghp_1")
    assert main(["project", "set", "shop", "GH_TOKEN", "--secret"]) == 0
    assert asked == ["Value of GH_TOKEN (not shown): "]
    assert secret_file("GH_TOKEN").read_text() == "ghp_1"
    assert "ghp_1" not in capsys.readouterr().out


def test_project_set_secret_ended_on_a_terminal_is_an_empty_value(shop, capsys, monkeypatch):
    """Ctrl-D at the prompt: no value, refused as an empty one, no traceback."""
    monkeypatch.setattr("sys.stdin", Stdin(tty=True))

    def ended(prompt):
        raise EOFError

    monkeypatch.setattr("getpass.getpass", ended)
    assert main(["project", "set", "shop", "GH_TOKEN", "--secret"]) == 1
    assert capsys.readouterr().err == (
        "\n"  # the prompt's line ends first
        "lado: the secret GH_TOKEN is empty; to remove it: lado project unset shop GH_TOKEN\n"
    )
    assert project_secrets.names("shop") == []


def test_project_set_secret_with_the_value_given_is_refused_before_reading(
    shop, capsys, monkeypatch
):
    stdin = Stdin("ghp_x\n")
    monkeypatch.setattr("sys.stdin", stdin)
    assert main(["project", "set", "shop", "GH_TOKEN", "ghp_3", "--secret"]) == 1
    err = capsys.readouterr().err
    assert err == (
        "lado: a secret's value is never given on the command line (ps and the shell's history "
        "keep it); run lado project set shop GH_TOKEN --secret and type it, or pipe it in\n"
    )
    assert "ghp_3" not in err
    assert not stdin.touched
    assert project_secrets.names("shop") == []


@pytest.mark.parametrize(
    ("name", "given", "said"),
    [
        (
            "GH_TOKEN",
            "\n",
            "the secret GH_TOKEN is empty; to remove it: lado project unset shop GH_TOKEN",
        ),
        ("GH_TOKEN", "x" * 70000, "the value of GH_TOKEN is larger than 64 KiB"),
        ("LADO_HOME", "x", "LADO_HOME is reserved: LADO or the agent CLIs set it"),
        ("A-B", "x", "the name A-B is not a variable name: "),
    ],
)
def test_project_set_secret_refusals(shop, capsys, monkeypatch, name, given, said):
    monkeypatch.setattr("sys.stdin", Stdin(given))
    assert main(["project", "set", "shop", name, "--secret"]) == 1
    err = capsys.readouterr().err
    assert err.startswith(f"lado: {said}") and err.count("\n") == 1
    assert not project_secrets.data_folder("shop").exists()


def test_project_set_without_a_value_or_secret(shop, capsys):
    assert main(["project", "set", "shop", "BOARD_URL"]) == 1
    assert capsys.readouterr().err == (
        "lado: lado project set shop BOARD_URL needs a value; for a secret: lado project set "
        "shop BOARD_URL --secret\n"
    )


def test_project_set_secret_of_an_unknown_project_reads_nothing(shop, capsys, monkeypatch):
    stdin = Stdin("x")
    monkeypatch.setattr("sys.stdin", stdin)
    assert main(["project", "set", "nope", "GH_TOKEN", "--secret"]) == 1
    assert capsys.readouterr().err == 'lado: unknown project "nope"\n'
    assert not stdin.touched


def test_project_set_secret_needs_one_value_per_name(shop, capsys, monkeypatch):
    assert main(["project", "set", "shop", "DATABASE_URL", "postgres://x"]) == 0
    monkeypatch.setattr("sys.stdin", Stdin("postgres://y"))
    assert main(["project", "set", "shop", "DATABASE_URL", "--secret"]) == 1
    assert capsys.readouterr().err == (
        "lado: DATABASE_URL is a plain variable of shop; remove it first with lado project "
        "unset shop DATABASE_URL\n"
    )


def test_agents_cannot_set_a_secret_and_stdin_is_not_read(shop, capsys, monkeypatch):
    stdin = Stdin("x")
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setenv("LADO_SESSION", "s")
    monkeypatch.setenv("LADO_AGENT", "w1")
    assert main(["project", "set", "shop", "GH_TOKEN", "--secret"]) == 1
    assert capsys.readouterr().err == (
        'lado: lado project set is for the human; agent "w1" cannot use it\n'
    )
    assert not stdin.touched
    assert project_secrets.names("shop") == []


def test_project_show_lists_secrets_by_name_only(shop, capsys, monkeypatch):
    for name, value in [("YOUGILE_API_KEY", "canary-y"), ("GH_TOKEN", "canary-g")]:
        monkeypatch.setattr("sys.stdin", Stdin(value))
        assert main(["project", "set", "shop", name, "--secret"]) == 0
    capsys.readouterr()
    assert main(["project", "show", "shop"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[-3:] == ["  secrets:", "    GH_TOKEN", "    YOUGILE_API_KEY"]
    assert "canary" not in out


def test_project_unset_removes_a_secret(shop, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", Stdin("g"))
    assert main(["project", "set", "shop", "GH_TOKEN", "--secret"]) == 0
    capsys.readouterr()
    assert main(["project", "unset", "shop", "GH_TOKEN"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Removed GH_TOKEN from project shop.",
        "Agents started from now on do not get it.",
    ]
    assert not secret_file("GH_TOKEN").exists()
