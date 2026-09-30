"""Command-line entry point for LADO."""

import argparse
import sys

from lado import __version__, doctor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lado",
        description="Layered Agent Delegation & Orchestration.",
    )
    parser.add_argument("--version", action="version", version=f"lado {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="<command>")
    commands.add_parser("doctor", help="check that tmux and Claude Code are installed")

    args = parser.parse_args(argv)
    if args.command == "doctor":
        return doctor.main()
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
