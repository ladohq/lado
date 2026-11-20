"""LADO's git credential helper: git runs it for a saved git server's address (the
`credential.<url>.helper` of lado.git_servers.variables) with LADO's own Python, and appends
the operation.

    python -c LOADER lado.git_credential --home H --server ID --user U --address R get

`get` answers with the user `U` and the token of `H/git-servers/ID/token`, read by the
link-refusing reader of LADO's secrets (lado.project_secrets); with no token it can read, it
tells git to stop (`quit=1`) and says so in one line on stderr, so git neither asks another
helper nor prompts. `store` and `erase` do nothing: the token is LADO's. `token` is the
GitLab CLI's header command (lado.git_servers.glab_command): it reads no stdin and prints
the token and a line break alone; with none it says so on stderr and exits 1. It never opens
lado.db, so a lado.db migrated under a running agent cannot break it, and never prints the
token but to git or glab on stdout.
"""

from __future__ import annotations

import argparse
import os
import stat
import sys

from lado import agent_env, project_secrets

TOKENS, TOKEN = "git-servers", "token"  # lado.git_servers' folder and file
HEADER = "token"  # the operation of glab's header command


def read_token(server: str) -> str | None:
    """The token of the server `server`, None for none LADO reads (missing, a link, not a
    regular file, too large, a disk error); also lado.git_servers' check's."""
    try:
        with project_secrets.open_chain((TOKENS, server), make=False) as fd:
            if fd is None:
                return None
            out = os.open(TOKEN, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            with os.fdopen(out, "rb") as file:
                if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                    return None
                data = file.read(agent_env.MAX_VALUE + 1)
    except (OSError, project_secrets.LinkRefused):
        return None
    if not data or len(data) > agent_env.MAX_VALUE:
        return None
    text = data.decode("utf-8", "surrogateescape")
    return text[:-1] if text.endswith("\n") else text  # project_secrets.stored's line break


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lado.git_credential", add_help=False)
    parser.add_argument("--home", required=True)
    parser.add_argument("--server", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--address", required=True)
    parser.add_argument("operation", nargs="?", default="")
    args = parser.parse_args(argv)
    if args.operation != HEADER:  # glab's header command gives no stdin to read
        sys.stdin.read()  # git's description of what it asks: the helper is per server already
    if args.operation not in ("get", HEADER):
        return 0
    os.environ["LADO_HOME"] = args.home  # where project_secrets looks, for this process only
    token = read_token(args.server)
    if token is None:
        if args.operation == "get":
            sys.stdout.write("quit=1\n")
        sys.stderr.write(
            f"lado: no token for {args.address}; add it again: "
            f"lado git-server add {args.address} --token\n"
        )
        return 1 if args.operation == HEADER else 0
    if args.operation == HEADER:
        sys.stdout.write(f"{token}\n")
        return 0
    sys.stdout.write(f"username={args.user}\npassword={token}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
