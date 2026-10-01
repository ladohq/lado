"""Command-line entry point for LADO."""

import argparse
import os
import sys
from pathlib import Path

from lado import __version__, doctor, kits, providers, runtime, state, tmux


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
    for name, where, path, shadowed in found:
        note = "  (shadowed by the one above)" if shadowed else ""
        try:
            kit = kits.load(path, where)
            about = f"{kit.version:<8} {kit.description}"
        except kits.KitError:
            about = "invalid; see: lado kits check " + str(path)
        print(f"{name:<16} {where:<9} {path}{note}\n  {about}")
    if not found:
        print("No kits found.")
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
    for skill in env.skills.values():
        print(f"  {skill.name}  from {skill.kit}: {skill.path}")
    if env.without:
        print(f"Switched off: {', '.join(env.without)}")
    env.supervisor()  # a session needs exactly one
    return 0


def cmd_kits_check(args: argparse.Namespace) -> int:
    target = Path(args.kit)
    repo = _repo_or_none(str(target) if target.is_dir() else args.repo)
    try:
        kit = (
            kits.load(target)
            if target.is_dir()
            else kits.load(*reversed(kits.find(args.kit, repo)))
        )
        env = kits.resolve(repo, [kit])
        problems = [p for k in env.kits for p in kits.lint(k)]
    except kits.KitError as exc:
        print(exc, file=sys.stderr)
        return 1
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    agents, skills = len(env.agents), len(env.skills)
    print(f"{kit.name}: OK ({agents} agents and {skills} skills with what it includes)")
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
        for agent in state.list_agents(sess.name):
            branch = f"  {agent.branch}" if agent.branch else ""
            print(
                f"  {agent.name:<12} {agent.role:<10} {agent.provider:<8} {agent.status:<9}{branch}"
            )
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
    workers = runtime.stop_session(args.name)
    print(f'Stopped session "{args.name}".')
    for w in workers:
        print(f"  kept worktree {w.cwd} (branch {w.branch})")
    if workers:
        print("Remove a worktree with: git worktree remove <path>")
    return 0


def _attach(name: str) -> int:
    if not tmux.has_session(name):
        print(f'No running session "{name}" (see lado ls)', file=sys.stderr)
        return 1
    env = {k: v for k, v in os.environ.items() if k != "TMUX"}  # allow attaching from tmux
    argv = tmux.attach_argv(name)
    os.execvpe(argv[0], argv, env)


def _without_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--without",
        action="append",
        default=[],
        metavar="KIND:NAME",
        help="switch off agent:<name>, skill:<name> or mcp:<name>; repeatable",
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

    commands.add_parser("ls", help="list sessions and agents").set_defaults(func=cmd_ls)

    attach = commands.add_parser("attach", help="attach to a session's tmux windows")
    attach.add_argument("name", nargs="?")
    attach.set_defaults(func=cmd_attach)

    stop = commands.add_parser("stop", help="stop a session and all its agents")
    stop.add_argument("name")
    stop.set_defaults(func=cmd_stop)

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
    except (runtime.LadoError, tmux.TmuxError, kits.KitError) as exc:
        print(f"lado: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
