"""Command-line entry point for LADO."""

import argparse
import os
import sys

from lado import __version__, doctor, runtime, state, tmux


def cmd_start(args: argparse.Namespace) -> int:
    sess = runtime.start_session(args.path, args.name, args.permission_mode)
    print(f'Started session "{sess.name}" in {sess.repo}')
    if args.no_attach or not sys.stdout.isatty():
        print(f"Attach with: lado attach {sess.name}")
        return 0
    return _attach(sess.name)


def cmd_ls(args: argparse.Namespace) -> int:
    sessions = state.list_sessions()
    if not sessions:
        print("No sessions. Start one with: lado start <repo>")
    for sess in sessions:
        alive = "" if tmux.has_session(sess.name) else "  (tmux session is gone)"
        print(f"{sess.name}  {sess.repo}{alive}")
        for agent in state.list_agents(sess.name):
            branch = f"  {agent.branch}" if agent.branch else ""
            print(f"  {agent.name:<12} {agent.role:<10} {agent.status:<9}{branch}")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lado",
        description="Layered Agent Delegation & Orchestration.",
    )
    parser.add_argument("--version", action="version", version=f"lado {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="<command>")

    commands.add_parser("doctor", help="check that tmux and Claude Code are installed")

    start = commands.add_parser("start", help="start a supervisor agent for a git repository")
    start.add_argument("path", nargs="?", default=".", help="repository (default: current dir)")
    start.add_argument("--name", help="session name (default: repository folder name)")
    start.add_argument(
        "--permission-mode",
        help="Claude Code permission mode for all agents, e.g. acceptEdits",
    )
    start.add_argument("--no-attach", action="store_true", help="do not attach to the session")
    start.set_defaults(func=cmd_start)

    commands.add_parser("ls", help="list sessions and agents").set_defaults(func=cmd_ls)

    attach = commands.add_parser("attach", help="attach to a session's tmux windows")
    attach.add_argument("name", nargs="?")
    attach.set_defaults(func=cmd_attach)

    stop = commands.add_parser("stop", help="stop a session and all its agents")
    stop.add_argument("name")
    stop.set_defaults(func=cmd_stop)

    # Internal: started by Claude Code for LADO agents.
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
    except (runtime.LadoError, tmux.TmuxError) as exc:
        print(f"lado: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
