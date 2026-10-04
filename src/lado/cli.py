"""Command-line entry point for LADO."""

import argparse
import datetime
import os
import select
import shutil
import subprocess
import sys
import termios
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

from lado import (
    __version__,
    doctor,
    flows,
    kits,
    log,
    loop,
    providers,
    runs,
    runtime,
    state,
    tmux,
)

PAGER = ["less", "-R"]  # for a gate's full note
POLL = 1.0  # seconds between two checks that a gate the human is asked about is open


def cmd_start(args: argparse.Namespace) -> int:
    _sources_warning()
    started = runtime.start_session(
        args.path, args.name, args.permission_mode, args.provider, args.kit, args.without
    )
    sess = started.session
    if started.resumed:
        count = len(state.list_runs(sess.name, open_only=True))
        runs_told = f"{count} open run{'' if count == 1 else 's'}, the supervisor is told"
        print(f'Resumed session "{sess.name}" in {sess.repo}: {runs_told}.')
        for change in started.changes:
            print(f"  changed {change}")
        for problem in started.problems:
            print(f"lado: {problem}", file=sys.stderr)
    else:
        print(f'Started session "{sess.name}" in {sess.repo}')
    if args.no_attach or not sys.stdout.isatty():
        print(f"Attach with: lado attach {sess.name}")
        return 0
    return _attach(sess.name)


def cmd_kits(args: argparse.Namespace) -> int:
    _sources_warning()
    repo = _repo_or_none(args.repo)
    found = kits.available(repo)
    for kit, shadowed_by in found:
        note = f"  (shadowed by {shadowed_by})" if shadowed_by else ""
        link = kit.link()
        try:
            about = _about(kit.load())
        except kits.KitError as exc:
            about = (
                f"invalid: {exc}"
                if link and not kit.path.exists()
                else "invalid; see: lado kits check " + str(kit.path)
            )
        target = f" → {link}" if link else ""
        print(f"{kit.name:<16} {kit.where:<9} {kit.path}{target}{note}\n  {about}")
    if not found:
        print("No kits found.")
    return 0


def _about(kit: kits.Kit) -> str:
    count = len(kit.unfetched())
    unfetched = f"; {count} pack{'' if count == 1 else 's'} not fetched yet" if count else ""
    return f"{kit.version or '-':<8} {kit.description}{unfetched}"


def cmd_kits_add(args: argparse.Namespace) -> int:
    for kit in kits.add(args.spec, args.kit or []):
        link = kits.installed() / kit.name
        print(f'Added kit "{kit.name}" {kit.version or "-"}: {link} → {kit.path}')
    return 0


def cmd_kits_update(args: argparse.Namespace) -> int:
    kit = kits.update(args.name, args.ref)
    link = kits.installed() / kit.name
    print(f'Updated kit "{kit.name}" to {args.ref} ({kit.version or "-"}): {link} → {kit.path}')
    print(f"running sessions get {args.ref} for new agents only")
    return 0


def cmd_kits_remove(args: argparse.Namespace) -> int:
    target = kits.remove(args.name)
    print(f'Removed kit "{args.name}": {kits.installed() / args.name} → {target}; the folder stays')
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    """`lado sources` is gone: say what to do instead."""
    print(
        "lado: "
        + (
            kits.migration_hint()
            or "lado sources is gone: install kits with `lado kits add <git-url>@<tag|commit>` "
            "or `lado kits add <folder>`; list skill packs under dependencies.skills of a kit"
        ),
        file=sys.stderr,
    )
    return 1


def _sources_warning() -> None:
    hint = kits.migration_hint()
    if hint:
        print(f"lado: {hint}", file=sys.stderr)


def cmd_kits_show(args: argparse.Namespace) -> int:
    repo = _repo_or_none(args.repo)
    env = kits.resolve(repo, args.names, args.without)
    print("Kits:")
    labels = {}  # (kit, pack) -> the pack's name@ref
    for kit in env.kits:
        print(f"  {kit.name} {kit.version}  ({kit.source})")
        for pack in kit.packs.values():
            labels[kit.name, pack.name] = pack.label
            print(f"    pack {pack.name}: {pack.spec}  {pack.path}")
        if kit.packs and not kit.agents:
            print("    shares its packs with the session (no agents)")

    def origin(skill: kits.Skill) -> str:
        return f"{labels[skill.kit, skill.pack]} ({skill.kit})" if skill.pack else skill.kit

    print("Agents:")
    for agent in env.agents.values():
        resolved = env.resolve(agent.name)
        flag = "  [supervisor]" if agent.supervisor else ""
        default = "  [default]" if agent.name == env.default_agent else ""
        print(f"  {agent.name}{flag}{default}  from {agent.kit}: {agent.path}")
        skills = ", ".join(f"{s.name} ({origin(s)})" for s in resolved.skills.values()) or "none"
        print(f"    skills{' (all)' if agent.skills is None else ''}: {skills}")
        for mcp in resolved.mcp.values():
            print(f"    mcp {mcp.name}: {' '.join(mcp.command)}")
    print("Skills:")
    where = {kit.name: kit.where for kit in env.kits}
    for skill in env.all_skills().values():
        print(f"  {skill.name}  from {origin(skill)} ({where[skill.kit]}): {skill.path}")
    if env.flows:
        print("Flows:")
    for flow in env.flows.values():
        print(f"  {flow.name}  from {flow.kit} ({where[flow.kit]}): {flow.path}")
        print(f"    {flow.description}")
    if env.without:
        print(f"Switched off: {', '.join(env.without)}")
    env.supervisor()  # a session needs exactly one
    return 0


def cmd_kits_check(args: argparse.Namespace) -> int:
    target = Path(args.kit)
    repo = _repo_or_none(str(target) if target.is_dir() else args.repo)
    try:
        # A folder may be any kit, e.g. a kit at the root of its repository.
        kit = kits.fetch(
            kits.load(target, named_folder=False)
            if target.is_dir()
            else kits.find(args.kit, repo).load()
        )
        env = kits.resolve(repo, [kit])
        problems = kits.lint(kit)
        doubts = kits.warnings(kit)
    except kits.KitError as exc:
        print(exc, file=sys.stderr)
        return 1
    # A flow may take a role from another kit of the session.
    for flow in kit.flows.values():
        for step in flow.states.values():
            if step.kind == flows.WORK and step.agent not in kit.agents:
                doubts.append(
                    f'flow "{flow.name}": state "{step.name}": role "{step.agent}" is not in '
                    f'kit "{kit.name}"; a session needs a kit that has it'
                )
    for doubt in doubts:
        print(f"warning: {doubt}", file=sys.stderr)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    skills = len(env.all_skills())
    counts = f"{len(env.agents)} agents, {skills} skills, {len(kit.packs)} packs"
    print(f"{kit.name}: OK ({counts} and {len(env.flows)} flows)")
    return 0


def _repo_or_none(path: str) -> str | None:
    try:
        return runtime.repo_root(path)
    except runtime.LadoError:
        return None


def cmd_ls(args: argparse.Namespace) -> int:
    sessions = state.list_sessions()
    if not sessions:
        print("No sessions. Start one with: lado start <repo>")
    for sess in sessions:
        alive = {
            runtime.SessionStatus.RUNNING: "",
            runtime.SessionStatus.STOPPED: "  (stopped)",
            runtime.SessionStatus.TMUX_GONE: "  (tmux session is gone)",
            runtime.SessionStatus.LOOP_DOWN: (
                "  (session loop not running: unconfirmed messages are not retried; "
                f"run `lado attach {sess.name}` to restart it; "
                f"see {state.home() / 'loop.log'})"
            ),
        }[runtime.session_status(sess)]
        print(f"{sess.name}  {sess.repo}{alive}")
        since = state.status_since(sess.name)
        now = datetime.datetime.now(datetime.timezone.utc)
        reasons = runtime.waiting_reasons(sess.name)
        for agent in state.list_agents(sess.name):
            when = since.get(agent.name)
            took = format_duration((now - when).total_seconds()) if when else "-"
            line = f"  {agent.name:<12} {agent.role:<10} {agent.provider:<8} {agent.status:<9}"
            print(f"{line} {took:<6}  {agent.branch or ''}".rstrip())
            if agent.name in reasons:
                print(f"    waiting: {reasons[agent.name]}")
        run_since = state.run_since(sess.name)
        for run in state.list_runs(sess.name, open_only=True):
            when = run_since.get(run.name)
            took = format_duration((now - when).total_seconds()) if when else "-"
            print(f"  run {run.name}  {run.state}  {runs.now(run)}  {took}")
            gate = state.open_gate(sess.name, run.name)
            if gate:
                print(f"    gate #{gate.id} waiting: {gate.question}")
    return 0


def _human_only(command: str) -> None:
    """Agents have LADO_AGENT set: they must not answer for the human."""
    agent = os.environ.get("LADO_AGENT")
    if agent:
        raise runtime.LadoError(f'lado {command} is for the human; agent "{agent}" cannot use it')


def cmd_flow_set(args: argparse.Namespace) -> int:
    _human_only("flow-set")
    before = state.get_run(args.session, args.run)
    run = runs.force(args.session, args.run, args.state, args.reason)
    print(f"{run.name}: {before.state} -> {run.state} ({runs.now(run)})")
    return 0


def cmd_answer(args: argparse.Namespace) -> int:
    _human_only("answer")
    named = state.get_session(args.session) if args.session else None
    if named and named.stopped_at:
        runtime.running_session(named.name)  # says it is stopped and how to resume it
    if args.option:
        _answer(args.session, args.gate, args.option, args.comment)
        return 0
    if args.gate:
        try:
            first = runs.find_gate(args.session, args.gate)
        except runtime.LadoError as exc:
            # E.g. a popup for a gate answered meanwhile: on with the session's gates.
            print(f"lado: {exc}")
            first = None
    else:
        first = None
    session, answered, failed = args.session, False, 0
    # A stopped session's gates wait for its resume: its runs have no agents to go on with.
    stopped = {s.name for s in state.list_sessions() if s.stopped_at}
    while True:
        gates = [first] if first else state.open_gates(session)
        gates = [g for g in gates if g.session not in stopped]
        first = None
        if not gates:
            print("No more open gates." if answered else "No open gates.")
            return failed
        gate = gates[0] if len(gates) == 1 else _pick(gates)
        if gate is None:
            return failed
        # -m is for the first gate only, also when that one is answered elsewhere.
        comment, args.comment = args.comment, None
        try:
            option = _choose(gate)
            if option is not None and comment is None:
                comment = _input("Comment for the next step (Enter for none): ", gate)
            if option is None or comment is None:
                print(f"Gate #{gate.id} stays open.")
                return failed
            _answer(gate.session, str(gate.id), option, comment)
            answered = True
        except NotWanted:
            closed = state.get_gate(gate.id)
            print(
                f"Gate #{gate.id} was answered elsewhere: {closed.answer} by {closed.answered_by}"
            )
            answered = True
        except runtime.LadoError as exc:
            print(f"lado: {exc}")
            failed = 1
            first = gate if state.get_gate(gate.id).answer is None else None
        # Then the session's other open gates: a popup asks about them all.
        session = gate.session


def _answer(session: str, ref: str, option: str, comment: str | None) -> None:
    print(runs.answer_text(session, ref, option, comment))


class NotWanted(Exception):
    """What the human was asked for is no longer wanted: e.g. the gate was answered in the
    UI or in another `lado answer`."""


def _input(prompt: str, gate: state.Gate | None = None) -> str | None:
    """A line the human typed; None when they end the input or press Ctrl-C. While asked
    about `gate` on a terminal, NotWanted when the gate is answered elsewhere."""
    try:
        if gate is None or not sys.stdin.isatty():
            return input(prompt).strip()
        print(prompt, end="", flush=True)
        return read_line_while(sys.stdin, lambda: state.get_gate(gate.id).answer is None)
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def read_line_while(stdin: TextIO, wanted: Callable[[], bool]) -> str:
    """A line typed on the terminal `stdin`, checking every POLL seconds that it is still
    wanted. When it is not, what was typed so far is dropped, so it does not go to the next
    prompt, and NotWanted is raised."""
    while True:
        ready, _, _ = select.select([stdin], [], [], POLL)
        if ready:
            line = stdin.readline()
            if not line:
                raise EOFError
            return line.strip()
        if not wanted():
            termios.tcflush(stdin, termios.TCIFLUSH)
            print()
            raise NotWanted


def _pick(gates: list[state.Gate]) -> state.Gate | None:
    print("Open gates:")
    for n, gate in enumerate(gates, 1):
        print(f"  {n}) #{gate.id} {gate.session} {gate.run} at {gate.state}: {gate.question}")
    while True:
        picked = _input("Which one? (number, Enter to quit): ")
        if not picked:
            return None
        if picked.isdigit() and 1 <= int(picked) <= len(gates):
            return gates[int(picked) - 1]


def _choose(gate: state.Gate) -> str | None:
    """The option the human picks for the gate, by number or name; None to leave it. The
    note and the notes the gate needs show as their summaries; when there is more, "v"
    shows all of it in a pager."""
    needed = runs.gate_notes(gate)
    full_note = gate.note_body.strip() != "" or bool(needed)
    v = ", v for the full note" if full_note else ""
    _show_gate(gate, needed)
    while True:
        chosen = _input(f"Answer (number or name{v}, Enter to leave it open): ", gate)
        if not chosen:
            return None
        if full_note and chosen.lower() == "v":
            parts = [f"Note from {name}: {_note_text(note)}\n" for name, note in needed]
            parts.append(f"Note: {gate.note}\n\n{gate.note_body.strip()}\n")
            _page("\n".join(parts))
            _show_gate(gate, needed)
            continue
        if chosen.isdigit() and 1 <= int(chosen) <= len(gate.options):
            return gate.options[int(chosen) - 1]
        try:
            return runs.canonical_option(gate, chosen)
        except runtime.LadoError as exc:
            print(f"lado: {exc}")


def _note_text(note: state.Note | None) -> str:
    return f"{note.summary}\n{note.body.strip()}".rstrip() if note else "no note yet"


def _show_gate(gate: state.Gate, needed: list[tuple[str, state.Note | None]]) -> None:
    print(f"\nGate #{gate.id}, session {gate.session}, run {gate.run} at {gate.state}:")
    print(gate.question)
    lines = len(gate.note_body.strip().splitlines())
    if lines:
        print(f"Note: {gate.note} (v: the full note, {lines} more line{'' if lines == 1 else 's'})")
    elif gate.note:
        print(f"Note: {gate.note}")
    for name, note in needed:
        print(f"Note from {name}: {note.summary if note else 'no note yet'}")
    print("Options:")
    for n, option in enumerate(gate.options, 1):
        print(f"  {n}) {option}")


def _page(text: str) -> None:
    """Show `text` in the pager, or print it when there is none."""
    pager = shutil.which(PAGER[0])
    if pager is None:
        print(text, end="")
        return
    subprocess.run([pager, *PAGER[1:]], input=text, text=True, check=False)


def format_duration(seconds: float) -> str:
    """A short duration: 45s, 12m, 3h05m, 2d4h (rounded down, never negative)."""
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h{s % 3600 // 60:02d}m"
    return f"{s // 86400}d{s % 86400 // 3600}h"


def cmd_log(args: argparse.Namespace) -> int:
    log.show(args.session, args.agent, args.n, args.follow)
    return 0


def cmd_attach(args: argparse.Namespace) -> int:
    name = args.name
    if name is None:
        sessions = [s for s in state.list_sessions() if not s.stopped_at]
        if len(sessions) != 1:
            print("Name the session: lado attach <name> (see lado ls)", file=sys.stderr)
            return 1
        name = sessions[0].name
    sess = state.get_session(name)
    if sess and not sess.stopped_at and tmux.has_session(name):
        loop.ensure(name)
    return _attach(name)


def cmd_stop(args: argparse.Namespace) -> int:
    stopped = runtime.stop_session(args.name)
    n = stopped.dropped
    dropped = f"; {n} undelivered message{'' if n == 1 else 's'} dropped" if n else ""
    print(f'Stopped session "{args.name}"{dropped}.')
    _kept(runtime.session_worktrees(state.get_session(args.name).repo, args.name), "kept")
    print(
        "History, open runs and gates are kept: lado start resumes the session, "
        f"lado forget {args.name} drops them."
    )
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    forgotten = runtime.forget_session(args.session, args.force)
    dropped = f"; dropped open runs: {', '.join(forgotten.runs)}" if forgotten.runs else ""
    print(f'Forgot session "{args.session}" and its history{dropped}.')
    _kept(forgotten.worktrees, "left on disk:")
    return 0


def _kept(worktrees: dict[str, str], what: str) -> None:
    for tree, branch in worktrees.items():
        print(f"  {what} worktree {tree} (branch {branch})")
    if worktrees:
        print("Remove a worktree with: git worktree remove <path>")


def cmd_finish(args: argparse.Namespace) -> int:
    print(runtime.finish_worker(args.session, args.agent, args.discard).text())
    return 0


def cmd_server(args: argparse.Namespace) -> int:
    from lado.server import run as server_run  # FastAPI loads only for the server

    if args.action == "stop":
        info = server_run.stop()
        print(
            f"Stopped the LADO server at {info['url']}."
            if info
            else "The LADO server is not running."
        )
        return 0
    return server_run.serve(args.host, args.port, args.new_token)


def cmd_ui(args: argparse.Namespace) -> int:
    import webbrowser

    from lado.server import app, auth
    from lado.server import run as server_run

    info = server_run.running()
    if info and args.port and info["port"] != args.port:
        raise runtime.LadoError(
            f"the LADO server already runs at {info['url']}, not on port {args.port}; "
            "stop it with `lado server stop` to start it on another port"
        )
    if info is None:
        info = server_run.wait_ready(server_run.start_background(args.port))
    elif info["version"] != __version__:
        # An old server would serve this LADO's bundle from disk against its own, older API.
        try:
            server_run.stop()
        except (OSError, runtime.LadoError) as error:
            raise runtime.LadoError(
                f"the running LADO server is version {info['version']}, this LADO is "
                f"{__version__}, and stopping it failed: {error}; "
                "stop it with `lado server stop`, then run `lado ui` again"
            ) from error
        old = info["version"]
        info = server_run.wait_ready(server_run.start_background(info["port"]))
        print(f"lado: restarted the LADO server: {old} -> {info['version']}", file=sys.stderr)
    if app.bundle_missing(app.STATIC):
        print(f"lado: warning: the web UI's bundle is missing: {app.BUILD_HINT}", file=sys.stderr)
    url = f"{info['url']}/?token={auth.token()}"
    if args.no_open:
        print(url)
    else:
        print(f"Opening {url}")
        webbrowser.open(url)
    return 0


def _port(value: str) -> int:
    n = int(value)
    if not 0 <= n <= 65535:
        raise argparse.ArgumentTypeError("a port is 0 to 65535")
    return n


def _attach(name: str) -> int:
    if not tmux.has_session(name):
        print(f'No running session "{name}" (see lado ls)', file=sys.stderr)
        return 1
    env = {k: v for k, v in os.environ.items() if k != "TMUX"}  # allow attaching from tmux
    argv = tmux.attach_argv(name)
    os.execvpe(argv[0], argv, env)


def _count(value: str) -> int:
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError("N must be 0 or more")
    return n


def _without_arg(parser: argparse.ArgumentParser, default: list[str] | None = None) -> None:
    parser.add_argument(
        "--without",
        action="append",
        default=default,
        metavar="KIND:NAME",
        help="switch off agent:<name>, skill:<name>, mcp:<name> or flow:<name>; repeatable",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lado",
        description="Layered Agent Delegation & Orchestration.",
    )
    parser.add_argument("--version", action="version", version=f"lado {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="<command>")

    commands.add_parser("doctor", help="check that tmux and the agent CLIs are installed")

    start = commands.add_parser("start", help="start a supervisor agent for a git repository")
    start.add_argument("path", nargs="?", default=".", help="repository (default: current dir)")
    start.add_argument("--name", help="session name (default: repository folder name)")
    start.add_argument(
        "--provider",
        help=f"agent CLI for the session's agents: {', '.join(providers.names())} "
        f"(default: {providers.DEFAULT})",
    )
    start.add_argument(
        "--permission-mode",
        help="permission mode for all agents, one their provider supports: "
        + "; ".join(
            f"{name}: {', '.join(providers.get(name).permission_modes)}"
            for name in providers.names()
        ),
    )
    start.add_argument(
        "--kit",
        action="append",
        help=f"kit to take agents, skills and MCP servers from; repeat to combine kits "
        f"(default: {kits.DEFAULT_KIT}; a resumed session keeps its kits)",
    )
    _without_arg(start)  # a resumed session keeps its own unless given
    start.add_argument("--no-attach", action="store_true", help="do not attach to the session")
    start.set_defaults(func=cmd_start)

    kits_cmd = commands.add_parser(
        "kits", help="list, show and check kits; add, update and remove installed ones"
    )
    kits_cmd.add_argument("--repo", default=".", help="repository for project kits")
    kits_cmd.set_defaults(func=cmd_kits)
    kits_sub = kits_cmd.add_subparsers(metavar="<command>")
    show = kits_sub.add_parser("show", help="what kits combine into: agents, skills, MCP")
    show.add_argument("names", nargs="+", metavar="name")
    _without_arg(show, [])
    show.set_defaults(func=cmd_kits_show)
    check = kits_sub.add_parser("check", help="validate a kit and fetch its skill packs")
    check.add_argument("kit", help="kit folder or name")
    check.set_defaults(func=cmd_kits_check)
    add = kits_sub.add_parser(
        "add", help=f"install the kits of a git repository or a folder in {kits.installed()}"
    )
    add.add_argument(
        "spec",
        metavar="<git-url@tag|commit|folder>",
        help="a git URL pinned to a tag or commit (cloned into the cache) or a folder (linked, "
        "read in place); its kit at the root or its kits in kits/<name>/",
    )
    add.add_argument(
        "--kit", action="append", metavar="NAME", help="only this kit of it; repeatable"
    )
    add.set_defaults(func=cmd_kits_add)
    update = kits_sub.add_parser("update", help="move a kit installed from git to another version")
    update.add_argument("name")
    update.add_argument("ref", metavar="<tag|commit>")
    update.set_defaults(func=cmd_kits_update)
    remove = kits_sub.add_parser("remove", help="remove an installed kit's link")
    remove.add_argument("name")
    remove.set_defaults(func=cmd_kits_remove)
    # Gone: says how to move to `lado kits add`.
    sources_cmd = commands.add_parser("sources", help="gone: see lado kits add")
    sources_cmd.add_argument("rest", nargs=argparse.REMAINDER)
    sources_cmd.set_defaults(func=cmd_sources)

    commands.add_parser("ls", help="list sessions and agents").set_defaults(func=cmd_ls)

    log_cmd = commands.add_parser("log", help="show a session's messages and agent events")
    log_cmd.add_argument("session")
    log_cmd.add_argument("--agent", help="only lines where this agent sends, gets or acts")
    log_cmd.add_argument("-n", type=_count, metavar="N", help="show only the last N entries")
    log_cmd.add_argument(
        "-f", "--follow", action="store_true", help="keep printing new entries until Ctrl-C"
    )
    log_cmd.set_defaults(func=cmd_log)

    attach = commands.add_parser("attach", help="attach to a session's tmux windows")
    attach.add_argument("name", nargs="?")
    attach.set_defaults(func=cmd_attach)

    stop = commands.add_parser(
        "stop", help="stop a session and all its agents; lado start resumes it"
    )
    stop.add_argument("name")
    stop.set_defaults(func=cmd_stop)

    forget = commands.add_parser(
        "forget", help="delete a stopped session with its history, runs and gates"
    )
    forget.add_argument("session")
    forget.add_argument("--force", action="store_true", help="also if it has open runs")
    forget.set_defaults(func=cmd_forget)

    finish = commands.add_parser(
        "finish", help="end a worker whose branch is merged: its window, worktree and branch"
    )
    finish.add_argument("session")
    finish.add_argument("agent")
    finish.add_argument(
        "--discard",
        action="store_true",
        help="also end it if its work is not merged or not committed, and throw that work away",
    )
    finish.set_defaults(func=cmd_finish)

    flow_set = commands.add_parser(
        "flow-set", help="put a flow run into a state, e.g. past a gate or a loop limit"
    )
    flow_set.add_argument("session")
    flow_set.add_argument("run", help="the run's name, <flow>/<name> (see lado ls)")
    flow_set.add_argument("state", help="a state of the run's flow")
    flow_set.add_argument("--reason", required=True, help="why; the next step is told")
    flow_set.set_defaults(func=cmd_flow_set)

    answer = commands.add_parser(
        "answer",
        help="answer a flow run that waits for the human; asks when options are left out",
    )
    answer.add_argument("session", nargs="?", help="default: open gates of all sessions")
    answer.add_argument("gate", nargs="?", help="the gate's number, or its run's name")
    answer.add_argument("option", nargs="?", help="e.g. approve, reject, continue, cancel")
    answer.add_argument("-m", dest="comment", metavar="COMMENT", help="for the next step")
    answer.set_defaults(func=cmd_answer)

    port_help = "exactly this port; 0 for any free one (default: 8000 or the next free to 8020)"
    server = commands.add_parser(
        "server", help="run the UI server of this LADO_HOME in the foreground; stop: end it"
    )
    server.add_argument("action", nargs="?", choices=["stop"], help="stop the running server")
    server.add_argument("--port", type=_port, help=port_help)
    server.add_argument("--host", default="127.0.0.1", help="only 127.0.0.1 or localhost for now")
    server.add_argument(
        "--new-token", action="store_true", help="make a new token; links with the old one stop"
    )
    server.set_defaults(func=cmd_server)

    ui = commands.add_parser(
        "ui", help="open the web UI; starts the UI server in the background if none runs"
    )
    ui.add_argument("--no-open", action="store_true", help="only print the link")
    ui.add_argument("--port", type=_port, help=f"for a server it starts: {port_help}")
    ui.set_defaults(func=cmd_ui)

    # Internal: started by the agent CLIs of LADO agents.
    commands.add_parser("mcp")
    hook = commands.add_parser("hook")
    hook.add_argument("event")
    hook.add_argument("--session", required=True)
    hook.add_argument("--agent", required=True)
    hook.add_argument("--instance", required=True)
    # Internal: started by `lado start`, one per session (lado.loop).
    loop_cmd = commands.add_parser("loop")
    loop_cmd.add_argument("session")

    args = parser.parse_args(argv)
    if args.command == "doctor":
        _sources_warning()
        return doctor.main()
    if args.command == "mcp":
        from lado import mcp_server

        return mcp_server.main()
    if args.command == "hook":
        from lado import hooks

        return hooks.main(args.event, args.session, args.agent, args.instance)
    if args.command == "loop":
        # No check_migration: the loop checks the schema itself and ends on another one.
        return loop.run(args.session)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        # `lado stop` is what the refusal asks for; it ends the session it migrates under.
        if args.command != "stop":
            runtime.check_migration()
        return args.func(args)
    except (runtime.LadoError, tmux.TmuxError, kits.KitError) as exc:
        print(f"lado: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
