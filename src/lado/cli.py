"""Command-line entry point for LADO."""

import argparse
import datetime
import os
import sys
from pathlib import Path

from lado import __version__, doctor, kits, log, providers, runs, runtime, sources, state, tmux


def cmd_start(args: argparse.Namespace) -> int:
    sess = runtime.start_session(
        args.path, args.name, args.permission_mode, args.provider, args.kit, args.without
    )
    print(f'Started session "{sess.name}" in {sess.repo}')
    if args.no_attach or not sys.stdout.isatty():
        print(f"Attach with: lado attach {sess.name}")
        return 0
    return _attach(sess.name)


def cmd_kits(args: argparse.Namespace) -> int:
    repo = _repo_or_none(args.repo)
    found = kits.available(repo)
    for kit, shadowed_by in found:
        note = f"  (shadowed by {shadowed_by})" if shadowed_by else ""
        try:
            about = _about(kit.load())
        except kits.KitError:
            about = "invalid; see: lado kits check " + str(kit.path)
        print(f"{kit.name:<16} {kit.where:<9} {kit.path}{note}\n  {about}")
    if not found:
        print("No kits found.")
    return 0


def _about(kit: kits.Kit) -> str:
    return f"{kit.version or '-':<8} {kit.description}"


def cmd_sources_list(args: argparse.Namespace) -> int:
    found = sources.registered()
    for source in found:
        revision = source.revision()
        at = f"  at {revision}" if revision else ""
        print(f"{source.name:<16} {source.describe()}{at}")
    if not found:
        print("No sources. Add one with: lado sources add <git-url|folder>[@ref]")
    return 0


def cmd_sources_add(args: argparse.Namespace) -> int:
    source = sources.add(args.source, args.name, args.skills)
    try:
        found = kits.in_source(source)
        if not found:
            raise kits.KitError(f"no kits and no skills found in {source.path()}")
    except kits.KitError as exc:
        sources.remove(source.name)
        raise kits.KitError(f"{exc}\nsource not added") from None
    revision = source.revision()
    at = f" at {revision}" if revision else ""
    print(f'Added source "{source.name}": {source.describe()}{at}, {source.path()}')
    for item in found:
        try:
            kit = item.load()
            what = f"skill pack with {len(kit.skills)} skills" if kit.pack else _about(kit)
        except kits.KitError:
            what = f"invalid; see: lado kits check {item.name}"
        print(f"  {item.name:<16} {what}")
    return 0


def cmd_sources_update(args: argparse.Namespace) -> int:
    for source in [sources.get(args.name)] if args.name else sources.registered():
        print(f"{source.name}: {source.update()}")
    return 0


def cmd_sources_remove(args: argparse.Namespace) -> int:
    source, files = sources.remove(args.name)
    print(f'Removed source "{source.name}"; {files}.')
    return 0


def cmd_kits_show(args: argparse.Namespace) -> int:
    repo = _repo_or_none(args.repo)
    env = kits.resolve(repo, args.names, args.without)
    print("Kits:")
    for kit in env.kits:
        print(f"  {kit.name} {kit.version}  ({kit.source})")
    print("Agents:")
    for agent in env.agents.values():
        resolved = env.resolve(agent.name)
        flag = "  [supervisor]" if agent.supervisor else ""
        default = "  [default]" if agent.name == env.default_agent else ""
        print(f"  {agent.name}{flag}{default}  from {agent.kit}: {agent.path}")
        skills = ", ".join(resolved.skills) or "none"
        print(f"    skills{' (all)' if agent.skills is None else ''}: {skills}")
        for mcp in resolved.mcp.values():
            print(f"    mcp {mcp.name}: {' '.join(mcp.command)}")
    print("Skills:")
    where = {kit.name: kit.where for kit in env.kits}
    for skill in env.skills.values():
        print(f"  {skill.name}  from {skill.kit} ({where[skill.kit]}): {skill.path}")
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
        kit = (
            kits.load(target, named_folder=False)
            if target.is_dir()
            else kits.find(args.kit, repo).load()
        )
        env = kits.resolve(repo, [kit])
        for name in kit.flows:
            env.flow(name)  # its roles exist in the kit with what it includes
        # What it includes is checked on its own; here its problems are only warnings.
        problems = kits.lint(kit)
        doubts = [w for k in env.kits for w in kits.warnings(k)]
        doubts += [p for k in env.kits if k.path != kit.path for p in kits.lint(k)]
    except kits.KitError as exc:
        print(exc, file=sys.stderr)
        return 1
    for doubt in doubts:
        print(f"warning: {doubt}", file=sys.stderr)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    counts = f"{len(env.agents)} agents, {len(env.skills)} skills and {len(env.flows)} flows"
    print(f"{kit.name}: OK ({counts} with what it includes)")
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
        alive = "" if tmux.has_session(sess.name) else "  (tmux session is gone)"
        print(f"{sess.name}  {sess.repo}{alive}")
        since = state.status_since(sess.name)
        now = datetime.datetime.now(datetime.timezone.utc)
        for agent in state.list_agents(sess.name):
            when = since.get(agent.name)
            took = format_duration((now - when).total_seconds()) if when else "-"
            line = f"  {agent.name:<12} {agent.role:<10} {agent.provider:<8} {agent.status:<9}"
            print(f"{line} {took:<6}  {agent.branch or ''}".rstrip())
        run_since = state.run_since(sess.name)
        for run in state.list_runs(sess.name, open_only=True):
            when = run_since.get(run.name)
            took = format_duration((now - when).total_seconds()) if when else "-"
            print(f"  run {run.name}  {run.state}  {_run_now(run)}  {took}")
            gate = state.open_gate(sess.name, run.name)
            if gate:
                print(f"    gate #{gate.id} waiting: {gate.question}")
    return 0


def _run_now(run: state.Run) -> str:
    """Where the run is now: who acts, the gate it waits at, or how it closed."""
    if run.status == state.WAITING:
        gate = state.open_gate(run.session, run.name)
        return f"waiting for human: {f'gate #{gate.id}' if gate else run.reason}"
    if run.status == state.ACTIVE:
        return f"→ {runs.acting(run)}"
    return f"{run.status}: {run.reason}" if run.reason else run.status


def _human_only(command: str) -> None:
    """Agents have LADO_AGENT set: they must not answer for the human."""
    agent = os.environ.get("LADO_AGENT")
    if agent:
        raise runtime.LadoError(f'lado {command} is for the human; agent "{agent}" cannot use it')


def cmd_flow_set(args: argparse.Namespace) -> int:
    _human_only("flow-set")
    before = state.get_run(args.session, args.run)
    run = runs.force(args.session, args.run, args.state, args.reason)
    print(f"{run.name}: {before.state} -> {run.state} ({_run_now(run)})")
    return 0


def cmd_answer(args: argparse.Namespace) -> int:
    _human_only("answer")
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
    while True:
        gates = [first] if first else state.open_gates(session)
        first = None
        if not gates:
            print("No more open gates." if answered else "No open gates.")
            return failed
        gate = gates[0] if len(gates) == 1 else _pick(gates)
        if gate is None:
            return failed
        option = _choose(gate)
        comment, args.comment = args.comment, None  # -m is for the first answer only
        if option is not None and comment is None:
            comment = _input("Comment for the next step (Enter for none): ")
        if option is None or comment is None:
            print(f"Gate #{gate.id} stays open.")
            return failed
        try:
            _answer(gate.session, str(gate.id), option, comment)
            answered = True
        except runtime.LadoError as exc:
            print(f"lado: {exc}")
            failed = 1
            first = gate if state.get_gate(gate.id).answer is None else None
        # Then the session's other open gates: a popup asks about them all.
        session = gate.session


def _answer(session: str, ref: str, option: str, comment: str | None) -> None:
    gate = runs.find_gate(session, ref)
    before = state.get_run(session, gate.run)
    run = runs.answer(session, str(gate.id), option, comment)
    word = state.get_gate(gate.id).answer
    print(f"gate #{gate.id}: {word}. {run.name}: {before.state} -> {run.state} ({_run_now(run)})")


def _input(prompt: str) -> str | None:
    """A line the human typed; None when they end the input or press Ctrl-C."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


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
    """The option the human picks for the gate, by number or name; None to leave it."""
    print(f"\nGate #{gate.id}, session {gate.session}, run {gate.run} at {gate.state}:")
    print(gate.question)
    if gate.note or gate.note_body:
        body = "".join(f"\n  {line}" for line in gate.note_body.splitlines())
        print(f"Note: {gate.note}{body}")
    print("Options:")
    for n, option in enumerate(gate.options, 1):
        print(f"  {n}) {option}")
    while True:
        chosen = _input("Answer (number or name, Enter to leave it open): ")
        if not chosen:
            return None
        if chosen.isdigit() and 1 <= int(chosen) <= len(gate.options):
            return gate.options[int(chosen) - 1]
        try:
            return runs.canonical_option(gate, chosen)
        except runtime.LadoError as exc:
            print(f"lado: {exc}")


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
        sessions = state.list_sessions()
        if len(sessions) != 1:
            print("Name the session: lado attach <name> (see lado ls)", file=sys.stderr)
            return 1
        name = sessions[0].name
    return _attach(name)


def cmd_stop(args: argparse.Namespace) -> int:
    run_trees = {r.worktree: r.branch for r in state.list_runs(args.name)}
    workers = runtime.stop_session(args.name)
    print(f'Stopped session "{args.name}".')
    # A run's workers share its worktree; a run may keep one with no workers left.
    kept = {w.cwd: w.branch for w in workers}
    kept.update({tree: branch for tree, branch in run_trees.items() if Path(tree).exists()})
    for tree, branch in kept.items():
        print(f"  kept worktree {tree} (branch {branch})")
    if kept:
        print("Remove a worktree with: git worktree remove <path>")
    return 0


def cmd_finish(args: argparse.Namespace) -> int:
    finished = runtime.finish_worker(args.session, args.agent, args.discard)
    worker = finished.worker
    if finished.removed_worktree:
        removed = f"removed window, worktree {worker.cwd} and branch {worker.branch}"
    else:
        removed = f"closed its window; run {worker.run} keeps {worker.cwd}"
    print(f'Finished worker "{worker.name}" ({finished.detail()}): {removed}')
    return 0


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


def _without_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--without",
        action="append",
        default=[],
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
        help="permission mode for all agents: default, acceptEdits, bypassPermissions or plan",
    )
    start.add_argument(
        "--kit",
        action="append",
        help=f"kit to take agents, skills and MCP servers from; repeat to combine kits "
        f"(default: {kits.DEFAULT_KIT})",
    )
    _without_arg(start)
    start.add_argument("--no-attach", action="store_true", help="do not attach to the session")
    start.set_defaults(func=cmd_start)

    kits_cmd = commands.add_parser("kits", help="list, show and check kits")
    kits_cmd.add_argument("--repo", default=".", help="repository for project kits")
    kits_cmd.set_defaults(func=cmd_kits)
    kits_sub = kits_cmd.add_subparsers(metavar="<command>")
    show = kits_sub.add_parser("show", help="what kits combine into: agents, skills, MCP")
    show.add_argument("names", nargs="+", metavar="name")
    _without_arg(show)
    show.set_defaults(func=cmd_kits_show)
    check = kits_sub.add_parser("check", help="validate a kit and what it includes")
    check.add_argument("kit", help="kit folder or name")
    check.set_defaults(func=cmd_kits_check)
    sources_cmd = commands.add_parser(
        "sources", help="kit sources: git repositories and local folders that hold kits"
    )
    sources_cmd.set_defaults(func=cmd_sources_list)
    sources_sub = sources_cmd.add_subparsers(metavar="<command>")
    sources_sub.add_parser("list", help="list kit sources").set_defaults(func=cmd_sources_list)
    add = sources_sub.add_parser("add", help="add a git repository or a local folder")
    add.add_argument(
        "source",
        metavar="<git-url|folder>[@ref]",
        help="a git URL (cloned; ref: tag, branch or commit) or a folder (read in place)",
    )
    add.add_argument("--name", help="source name (default: repository or folder name)")
    add.add_argument(
        "--skills",
        action="append",
        metavar="FOLDER",
        help="for a skill pack: take skills only from this folder inside it, e.g. "
        "skills/engineering; repeatable (default: all of skills/)",
    )
    add.set_defaults(func=cmd_sources_add)
    update = sources_sub.add_parser("update", help="fetch sources again (default: all)")
    update.add_argument("name", nargs="?")
    update.set_defaults(func=cmd_sources_update)
    remove = sources_sub.add_parser("remove", help="remove a source (and its clone)")
    remove.add_argument("name")
    remove.set_defaults(func=cmd_sources_remove)

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

    stop = commands.add_parser("stop", help="stop a session and all its agents")
    stop.add_argument("name")
    stop.set_defaults(func=cmd_stop)

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

    # Internal: started by the agent CLIs of LADO agents.
    commands.add_parser("mcp")
    hook = commands.add_parser("hook")
    hook.add_argument("event")
    hook.add_argument("--session", required=True)
    hook.add_argument("--agent", required=True)
    hook.add_argument("--instance", required=True)

    args = parser.parse_args(argv)
    if args.command == "doctor":
        return doctor.main()
    if args.command == "mcp":
        from lado import mcp_server

        return mcp_server.main()
    if args.command == "hook":
        from lado import hooks

        return hooks.main(args.event, args.session, args.agent, args.instance)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except (runtime.LadoError, tmux.TmuxError, kits.KitError, sources.SourceError) as exc:
        print(f"lado: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
