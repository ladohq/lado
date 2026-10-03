import os
import subprocess
import sys
from pathlib import Path

import agent_helpers
import pytest
from agent_helpers import init_repo, publish

from lado import __version__, cli, runs, runtime, sources, state
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
    runtime.spawn_worker("s", "task", name="w1")
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
    main(["start", str(repo), "--name", "s", "--no-attach"])
    runtime.spawn_worker("s", "task", name="w1")
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


def test_finish_ends_a_worker(repo, fake_tmux, capsys):
    main(["start", str(repo), "--name", "s", "--no-attach"])
    worker = runtime.spawn_worker("s", "task", name="w1")
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
    assert "claude: " in out and "dontAsk" in out


def test_start_with_a_mode_the_provider_cannot_honour_fails(repo, fake_tmux, capsys):
    args = ["start", str(repo), "--provider", "kilo", "--permission-mode", "dontAsk"]
    assert main([*args, "--no-attach"]) == 1
    assert '"dontAsk" is not supported by Kilo CLI (kilo)' in capsys.readouterr().err
    assert fake_tmux == []


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
    run, gate = capsys.readouterr().out.splitlines()[-2:]
    assert run.split()[:8] == ["run", "ship/x", "check", "waiting", "for", "human:", "gate", "#1"]
    assert gate == "    gate #1 waiting: Ship it?"
    runs.answer("s", "1", "reject")
    main(["ls"])
    assert "gate #1" not in capsys.readouterr().out


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
  plan: {agent: supervisor, do: Plan it., outcomes: {ready: build}}
  build: {agent: rev, do: Build it., outcomes: {done: check, polish: polish}}
  polish: {agent: rev, do: Polish it., outcomes: {done: check}}
  check:
    gate: approval
    ask: Ship it?
    needs: [plan, polish]
    outcomes: {approved: end, rejected: build}
  end: {end: true}
"""


def _at_gate_with_needs(repo, capsys):
    kit = _kit(repo, "team")
    (kit / "flows").mkdir()
    (kit / "flows" / "plan.yaml").write_text(PLAN)
    main(["start", str(repo), "--name", "s", "--kit", "team", "--no-attach"])
    runs.start("s", "plan", "Add x", name="x")
    runs.advance("s", "supervisor", "plan/x", "ready", "the plan", "step 1\nstep 2")
    runs.spawn_worker("s", "plan/x")
    runs.advance("s", "rev", "plan/x", "done", "built it", "all\ntests pass")
    capsys.readouterr()


def test_answer_shows_the_summaries_of_the_notes_a_gate_needs(repo, fake_tmux, capsys, monkeypatch):
    _at_gate_with_needs(repo, capsys)
    _typing(monkeypatch, "")
    assert main(["answer"]) == 0
    out = capsys.readouterr().out
    assert (
        "Ship it?\n"
        "Note: built it (v: the full note, 2 more lines)\n"
        "Note from plan: the plan\n"
        "Note from polish: no note yet\n"
        "Options:\n"
    ) in out
    assert "step 1" not in out
    assert "Answer (number or name, v for the full note, Enter to leave it open): " in out


def test_v_shows_the_needed_notes_then_the_note_before_the_gate(
    repo, fake_tmux, capsys, monkeypatch
):
    _at_gate_with_needs(repo, capsys)
    monkeypatch.setattr(cli, "PAGER", ["no-such-pager-for-lado-tests"])
    _typing(monkeypatch, "v")
    assert main(["answer"]) == 0
    assert (
        "Note from plan: the plan\nstep 1\nstep 2\n\n"
        "Note from polish: no note yet\n\n"
        "Note: built it\n\nall\ntests pass\n"
    ) in capsys.readouterr().out


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
    assert (
        f'Finished worker "rev-2" (closed): closed its window; run ship/x keeps {run.worktree}'
        in out
    )
    assert main(["stop", "s"]) == 0
    out = capsys.readouterr().out
    assert out.count(f"kept worktree {run.worktree}") == 1


def test_stop_and_start_again_resumes_the_session(repo, fake_tmux, capsys):
    run = _session_with_run(repo)
    runs.force("s", "ship/x", "check", "built by hand")
    runtime.spawn_worker("s", "task", name="w1")  # starting: a message to it waits
    runtime.send_message("s", "supervisor", "w1", "hi")
    capsys.readouterr()
    assert main(["stop", "s"]) == 0
    out = capsys.readouterr().out
    # The supervisor is starting as well: LADO's two messages to it about the run wait.
    assert out.startswith('Stopped session "s"; 3 undelivered messages dropped.\n')
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
    assert "lado: session_stop (3 messages dropped)" in capsys.readouterr().out
    for argv in (["answer", "s", "1", "approve"], ["answer", "s", "1"], ["answer", "s"]):
        assert main(argv) == 1
        assert 'session "s" is stopped; resume it with `lado start`' in capsys.readouterr().err
    assert main(["answer"]) == 0  # a stopped session's gates wait for its resume
    assert capsys.readouterr().out == "No open gates.\n"

    args = ["start", str(repo), "--name", "s", "--without", "agent:rev", "--no-attach"]
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


def test_a_command_does_not_migrate_the_database_under_a_running_session(repo, fake_tmux, capsys):
    assert main(["start", str(repo), "--name", "old", "--no-attach"]) == 0
    agent_helpers.previous_schema()
    capsys.readouterr()
    assert main(["ls"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("lado: ") and "`lado stop old`" in err
    assert state.pending_migration() == (state.SCHEMA_VERSION - 1, ["old"])
    # Stopping is what the refusal asks for, so it goes ahead; then the database migrates.
    assert main(["stop", "old"]) == 0
    assert main(["ls"]) == 0
    assert state.pending_migration() is None
    assert f"old  {repo}  (stopped)" in capsys.readouterr().out


def test_ls_shows_a_running_session_without_its_loop(repo, fake_tmux, capsys):
    from lado import loop

    main(["start", str(repo), "--name", "s", "--no-attach"])
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
    main(["start", str(repo), "--name", "s", "--no-attach"])
    assert loop_starts == ["s"]
    main(["attach", "s"])
    assert loop_starts == ["s", "s"]  # its lock was free: the loop had died
    held = loop.take_lock("s")  # its loop runs
    main(["attach"])
    assert loop_starts == ["s", "s"]
    held.close()
    assert len(attached) == 2
