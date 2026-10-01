"""A fake agent CLI for the integration tests: behaves like an agent in a terminal, no LLM.

Usage: fake_agent.py <config.json> (written by fake_provider.FakeProvider).

It reports its lifecycle through the hooks in the config and works on each input typed or
pasted into its terminal. Every input line is a command, after an optional "[from <name>] ":
    send <to> <text>   call the LADO MCP tool send_message
    spawn <task>       call the LADO MCP tool spawn_worker
    sleep <seconds>    work that long
    exit               end the session
Other lines are ignored. Each input is logged to the config's "inputs" file.
"""

import asyncio
import json
import os
import re
import signal
import subprocess
import sys
import time
import traceback

from mcp import Client, StdioServerParameters

PASTE_START, PASTE_END = "\x1b[200~", "\x1b[201~"

config = json.load(open(sys.argv[1]))


def hook(event: str, prompt: str = "") -> str:
    """Run the agent's hook for `event`; returns what it printed."""
    payload = json.dumps({"prompt": prompt})
    result = subprocess.run(config["hooks"][event], input=payload, capture_output=True, text=True)
    return result.stdout.strip()


def call_tool(name: str, arguments: dict) -> None:
    """Call a tool of the LADO MCP server, started over stdio like an agent CLI does."""
    mcp = config["mcp"]
    server = StdioServerParameters(
        command=mcp["command"][0], args=mcp["command"][1:], env=mcp["env"]
    )

    async def call():
        async with Client(server) as client:
            return await client.call_tool(name, arguments)

    result = asyncio.run(call())
    print(f"{name}: {result.content}", flush=True)


def read_input() -> str | None:
    """The next input from the terminal; None at end of input.

    The terminal turns pasted line breaks into separate lines; the paste markers (bracketed
    paste mode, enabled in main) keep a pasted text in one piece.
    """
    line = sys.stdin.readline()
    if not line:
        return None
    if PASTE_START not in line:
        return line.rstrip("\n")
    text = line.split(PASTE_START, 1)[1]
    while PASTE_END not in text:
        more = sys.stdin.readline()
        if not more:
            break
        text += more
    return text.split(PASTE_END, 1)[0]


def work(text: str) -> bool:
    """Act on the commands in `text`. Returns True for exit."""
    for line in text.splitlines():
        command = re.sub(r"^\[from [^\]]*\] ", "", line.strip()).split(" ", 2)
        if command[0] == "exit":
            return True
        if command[0] == "sleep":
            time.sleep(float(command[1]))
        elif command[0] == "send":
            call_tool("send_message", {"to": command[1], "text": command[2]})
        elif command[0] == "spawn":
            call_tool("spawn_worker", {"task": " ".join(command[1:])})
    time.sleep(0.05)  # think
    return False


def main() -> None:
    signal.signal(signal.SIGHUP, lambda *_: os._exit(0))  # its tmux session was killed
    print("\x1b[?2004h", end="", flush=True)  # bracketed paste mode
    hook("session_start")
    text = config["first_message"]
    while True:
        if text is None:
            text = read_input()
            if text is None:
                break
        if not text.strip():
            text = None
            continue
        print(f"> {text!r}", flush=True)
        with open(config["inputs"], "a") as log:
            log.write(json.dumps(text) + "\n")
        hook("prompt_submit", text)
        try:
            if work(text):
                break
        except Exception:
            traceback.print_exc()
        output = hook("turn_end")
        text = output if output and config["continue_on_turn_end"] else None
    hook("session_end")


if __name__ == "__main__":
    main()
