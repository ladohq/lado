"""Command-line entry point for LADO."""

import argparse

from lado import __version__

NOTICE = (
    "LADO (Layered Agent Delegation & Orchestration) is in early development.\n"
    "Follow progress at https://github.com/ladohq/lado"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lado",
        description="Layered Agent Delegation & Orchestration.",
    )
    parser.add_argument("--version", action="version", version=f"lado {__version__}")
    parser.parse_args()
    print(NOTICE)


if __name__ == "__main__":
    main()
