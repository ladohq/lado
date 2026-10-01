import subprocess
import sys
from pathlib import Path

import pytest
from agent_helpers import init_repo, publish

from lado import __version__, runs, runtime, sources, state
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
    main(["start", str(repo), "--name", "s", "--no-attach"])
    runtime.spawn_worker("s", "task")
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


def test_finish_ends_a_worker(repo, fake_tmux, capsys):
    main(["start", str(repo), "--name", "s", "--no-attach"])
    worker = runtime.spawn_worker("s", "task")
    (Path(worker.cwd) / "x.txt").write_text("x")
    assert main(["finish", "s", "w1"]) == 1
    assert 'lado: worker "w1" has uncommitted changes' in capsys.readouterr().err
    assert main(["finish", "s", "w1", "--discard"]) == 0
    out = capsys.readouterr().out
    assert f'Finished worker "w1" (discarded): removed window, worktree {worker.cwd}' in out
    assert "branch lado/s/w1" in out
    assert state.get_agent("s", "w1") is None


def test_start_with_unknown_provider_fails(repo, fake_tmux, capsys):
    assert main(["start", str(repo), "--provider", "nope", "--no-attach"]) == 1
    assert 'unknown provider "nope"; known: claude, kilo' in capsys.readouterr().err


def _kit(repo, name, body="---\nname: rev\ndescription: reviews\n---\nReview.\n"):
    kit = repo / ".lado" / "kits" / name
    (kit / "agents").mkdir(parents=True)
    (kit / "kit.yaml").write_text(
        f"name: {name}\nversion: 1.0.0\ndescription: about {name}\ninclude: [default]\n"
    )
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
    assert f"team 1.0.0  (project: {kit.resolve()})" in out
    assert f"rev  from team: {kit.resolve()}/agents/rev.md" in out
    assert "supervisor  [supervisor]  from default" in out
    assert "  worker" not in out
    assert "Switched off: agent:worker" in out


def test_kits_check(repo, capsys, monkeypatch):
    kit = _kit(repo, "team")
    assert main(["kits", "check", str(kit)]) == 0
    assert "team: OK (3 agents, 0 skills" in capsys.readouterr().out
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


def test_kits_sources_add_update_remove(tmp_path, repo, capsys, monkeypatch):
    monkeypatch.chdir(repo)
    work = init_repo(tmp_path / "pack")
    skill = "---\nname: {0}\ndescription: use {0}\n---\n"
    url = publish(work, {"skills/eng/tdd/SKILL.md": skill.format("tdd")}, tag="v1.0.0")
    assert main(["sources", "list"]) == 0
    assert "No sources." in capsys.readouterr().out

    assert main(["sources", "add", f"{url}@v1.0.0"]) == 0
    clone = sources.get("pack").path()
    out = capsys.readouterr().out
    assert f'Added source "pack": git {url} @v1.0.0 at ' in out and str(clone) in out
    assert "  pack             skill pack with 1 skills" in out
    dev = _kit(tmp_path, "team")
    assert main(["sources", "add", str(tmp_path / ".lado"), "--name", "dev"]) == 0
    assert "  team             1.0.0    about team" in capsys.readouterr().out

    assert main(["sources"]) == 0
    assert main(["sources", "list"]) == 0
    listed = capsys.readouterr().out
    assert listed[: len(listed) // 2] == listed[len(listed) // 2 :]
    out = listed.splitlines()
    assert out[0].startswith(f"pack             git {url} @v1.0.0  at ")
    assert out[1] == f"dev              path {(tmp_path / '.lado').resolve()}"

    _kit(repo, "team")
    assert main(["kits"]) == 0
    out = capsys.readouterr().out
    assert f"team             source dev {dev.resolve()}  (shadowed by project)" in out
    assert f"pack             source pack {clone}\n  -        skill pack, 1 skills" in out

    publish(work, {"skills/plan/SKILL.md": skill.format("plan")}, tag="v1.1.0")
    assert main(["sources", "update"]) == 0
    out = capsys.readouterr().out
    assert "pack: at " in out and "dev: nothing to update" in out
    assert not (clone / "skills" / "plan").exists()  # still at v1.0.0

    assert main(["sources", "add", url, "--name", "pack"]) == 1
    assert 'a source named "pack" already exists' in capsys.readouterr().err
    assert main(["sources", "remove", "pack"]) == 0
    assert f'Removed source "pack"; deleted the clone {clone}.' in capsys.readouterr().out
    assert not clone.exists()
    assert main(["sources", "update", "pack"]) == 1
    assert 'no source "pack"; sources: dev' in capsys.readouterr().err


def test_kits_add_refuses_a_source_without_kits(tmp_path, capsys):
    (tmp_path / "empty").mkdir()
    assert main(["sources", "add", str(tmp_path / "empty")]) == 1
    err = capsys.readouterr().err
    assert "no kits and no skills found in" in err and "source not added" in err
    assert sources.registered() == []
    assert main(["sources", "add", "file:///nowhere/kits.git"]) == 1
    assert "lado: cannot get git file:///nowhere/kits.git" in capsys.readouterr().err


def test_kits_show_and_check_name_sources(tmp_path, repo, capsys):
    work = init_repo(tmp_path / "team")
    files = {
        "kits/team/kit.yaml": "name: team\nversion: 1.0.0\ninclude: [default]\n",
        "kits/team/skills/notes/SKILL.md": "---\nname: notes\ndescription: notes\n---\n",
    }
    url = publish(work, files, tag="v2.0.0")
    assert main(["sources", "add", url]) == 0
    source = sources.get("team")
    kit_dir = source.path().resolve() / "kits" / "team"
    capsys.readouterr()
    assert main(["kits", "--repo", str(repo), "show", "team"]) == 0
    out = capsys.readouterr().out
    assert f"team 1.0.0  (source team @ {source.revision()}: {kit_dir})" in out
    assert f"notes  from team (source team): {kit_dir}/skills/notes" in out
    assert main(["kits", "--repo", str(repo), "check", "team"]) == 0
    captured = capsys.readouterr()
    assert "warning: team: version 1.0.0 in kit.yaml, but team is at v2.0.0" in captured.err
    assert "team: OK (2 agents, 1 skills" in captured.out


def test_kits_add_with_skills_folders(tmp_path, capsys):
    pack = tmp_path / "pack"
    for skill in ("engineering/tdd", "productivity/grilling", "deprecated/tdd"):
        (pack / "skills" / skill).mkdir(parents=True)
        name = skill.rsplit("/", 1)[-1]
        (pack / "skills" / skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: d\n---\n"
        )
    assert main(["sources", "add", str(pack), "--name", "all"]) == 0
    assert "  all              invalid; see: lado kits check all" in capsys.readouterr().out
    args = ["--skills", "skills/engineering", "--skills", "skills/productivity"]
    assert main(["sources", "add", str(pack), *args]) == 0
    out = capsys.readouterr().out
    assert f"skills: skills/engineering, skills/productivity, {pack.resolve()}" in out
    assert "  pack             skill pack with 2 skills" in out
    assert sources.get("pack").skills == ("skills/engineering", "skills/productivity")
    assert main(["sources", "add", str(pack), "--name", "x", "--skills", "../up"]) == 1
    assert "skills folders are relative paths inside the source" in capsys.readouterr().err


def test_kits_check_warns_about_included_kits(repo, capsys):
    base = _kit(repo, "base")
    (base / "agents" / "rev.md").write_text("---\nname: rev\ndescription: d\n---\nSee ~/notes.\n")
    top = repo / ".lado" / "kits" / "top"
    top.mkdir()
    (top / "kit.yaml").write_text("name: top\nversion: 1.0.0\ninclude: [base]\n")
    assert main(["kits", "--repo", str(repo), "check", "top"]) == 0
    assert "warning: " in capsys.readouterr().err
    assert main(["kits", "--repo", str(repo), "check", "base"]) == 1


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
    main(["start", str(repo), "--name", "s", "--kit", "team", "--no-attach"])
    return runs.start("s", "ship", "Add x", name="x")


def test_ls_shows_open_runs_with_who_acts(repo, fake_tmux, capsys):
    _session_with_run(repo)
    capsys.readouterr()
    main(["ls"])
    lines = capsys.readouterr().out.splitlines()
    assert lines[-1].split() == ["run", "ship/x", "build", "→", "rev", "(not", "spawned)", "0s"]
    runs.force("s", "ship/x", "check", "skip the build")
    main(["ls"])
    line = capsys.readouterr().out.splitlines()[-1]
    assert line.split()[:3] == ["run", "ship/x", "check"]
    assert "waiting for human: Ship it?" in line


def test_flow_set_moves_a_run_and_is_logged(repo, fake_tmux, capsys):
    _session_with_run(repo)
    assert main(["flow-set", "s", "ship/x", "check", "--reason", "built by hand"]) == 0
    assert "ship/x: build -> check (waiting for human: Ship it?)" in capsys.readouterr().out
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
    assert main(["finish", "s", "w2"]) == 0
    out = capsys.readouterr().out
    assert (
        f'Finished worker "w2" (closed): closed its window; run ship/x keeps {run.worktree}' in out
    )
    assert main(["stop", "s"]) == 0
    out = capsys.readouterr().out
    assert out.count(f"kept worktree {run.worktree}") == 1


def test_flow_set_needs_a_reason(repo, fake_tmux, capsys):
    _session_with_run(repo)
    with pytest.raises(SystemExit):
        main(["flow-set", "s", "ship/x", "check"])
    capsys.readouterr()


def test_kits_show_lists_flows_with_their_source(repo, capsys):
    kit = _kit(repo, "team")
    (kit / "flows").mkdir()
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    assert main(["kits", "--repo", str(repo), "show", "team"]) == 0
    out = capsys.readouterr().out
    assert f"Flows:\n  ship  from team (project): {kit.resolve()}/flows/ship.yaml" in out
    assert "    build and ship" in out


def test_kits_check_refuses_a_flow_with_a_missing_role(repo, capsys):
    kit = _kit(repo, "team")
    (kit / "flows").mkdir()
    (kit / "flows" / "ship.yaml").write_text(SHIP.replace("agent: rev", "agent: tester"))
    assert main(["kits", "--repo", str(repo), "check", "team"]) == 1
    assert 'state "build": no role "tester" in this session' in capsys.readouterr().err
    (kit / "flows" / "ship.yaml").write_text(SHIP)
    assert main(["kits", "--repo", str(repo), "check", "team"]) == 0
    assert "team: OK (3 agents, 0 skills and 1 flows" in capsys.readouterr().out


def test_source_commands_are_not_under_kits(capsys):
    for command in ("add", "update", "remove", "sources"):
        with pytest.raises(SystemExit):
            main(["kits", command, "x"])
    capsys.readouterr()
