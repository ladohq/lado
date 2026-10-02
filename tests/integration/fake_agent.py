"""A fake agent CLI for the integration tests: behaves like an agent in a terminal, no LLM.

Usage: fake_agent.py <config.json> [<first message>] (written by fake_provider.FakeProvider).
The first message is on the command line, as real agent CLIs take it.

It reports its lifecycle through the hooks in the config and works on each input typed or
pasted into its terminal. Every input line is a command, after an optional "[from <name>] ":
    send <to> <summary>[ | <body>]  call the LADO MCP tool send_message; "\\n" in the body
                       is a line break
    read               call the LADO MCP tool read_messages
    spawn <task>       call the LADO MCP tool spawn_worker
    finish <name> [discard]  call the LADO MCP tool finish_worker
    flow_start <flow> <task>  call the LADO MCP tool flow_start
    spawnrun <run>     call the LADO MCP tool spawn_worker for a flow run
    advance <run> <outcome>  call the LADO MCP tool flow_advance
    sleep <seconds>    work that long
    run <skill> <file> run a file of one of its skills, e.g. "run notes scripts/hello.sh"
    exit               end the session
A typed "switch <seconds>" is no input but a command of the CLI itself, like Claude Code's
/resume: the agent leaves its conversation, takes that long to pick another, and goes on in
the same process; no prompt-submit and no turn-end hook run for it.
Other lines are ignored. Each input is logged to the config's "inputs" file, and the output
of `run`, the messages from `read` and the results of `flow_start` and `advance` to its
"seen" file. At start the agent writes what it
was given (prompt, skills found in its skills folder, MCP servers) to "seen", as a real agent
CLI would load them, and starts its LADO MCP server and lists its tools while its
session-start hook runs; like a real CLI, it keeps that one server for all its tool calls.
"""

import asyncio
import concurrent.futures
import json
import os
import re
import signal
import subprocess
import sys
import threading
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


def report(**seen) -> None:
    path = config["seen"]
    data = json.load(open(path)) if os.path.exists(path) else {}
    with open(path + ".new", "w") as out:
        json.dump({**data, **seen}, out, indent=2)
    os.replace(path + ".new", path)  # a test polling the file never reads half of it


def load_skills() -> dict[str, str]:
    """Skill name -> description, read from <skills>/<folder>/SKILL.md."""
    skills = {}
    for folder in sorted(os.listdir(config["skills"])):
        text = open(os.path.join(config["skills"], folder, "SKILL.md")).read()
        meta = dict(re.findall(r"^(name|description): *(.*)$", text.split("---")[1], re.M))
        skills[meta["name"]] = meta["description"]
    return skills


def run_skill_file(skill: str, file: str) -> None:
    path = os.path.join(config["skills"], skill, file)
    result = subprocess.run([path], capture_output=True, text=True)
    report(run={"file": f"{skill}/{file}", "output": result.stdout.strip()})


def lado_server() -> StdioServerParameters:
    mcp = config["mcp"]["lado"]
    return StdioServerParameters(command=mcp["command"][0], args=mcp["command"][1:], env=mcp["env"])


mcp_loop = asyncio.new_event_loop()  # runs in a daemon thread: it never holds up the exit
mcp_client: concurrent.futures.Future = concurrent.futures.Future()  # the connected Client


def connect_mcp() -> None:
    """Start the LADO MCP server over stdio once and keep it, as an agent CLI does: list its
    tools at start, then serve every tool call. If it cannot start, every call fails."""

    async def connect():
        try:
            async with Client(lado_server()) as client:
                await client.list_tools()
                mcp_client.set_result(client)
                await asyncio.Event().wait()  # keep the connection until the process ends
        except Exception as exc:
            if not mcp_client.done():
                mcp_client.set_exception(exc)
            raise

    threading.Thread(target=mcp_loop.run_forever, daemon=True).start()
    asyncio.run_coroutine_threadsafe(connect(), mcp_loop)


def call_tool(name: str, arguments: dict):
    """Call a tool of the LADO MCP server. Returns its structured result."""

    async def call():
        client = await asyncio.wrap_future(mcp_client)  # once connected
        return await client.call_tool(name, arguments)

    result = asyncio.run_coroutine_threadsafe(call(), mcp_loop).result()
    print(f"{name}: {result.content}", flush=True)
    if result.structured_content is None:  # a dict comes as JSON text
        return json.loads(result.content[0].text) if not result.is_error else None
    return result.structured_content.get("result")


def send(to: str, text: str) -> None:
    summary, _, body = text.partition(" | ")
    arguments = {"to": to, "summary": summary}
    if body:
        arguments["body"] = body.replace("\\n", "\n")
    call_tool("send_message", arguments)


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
            send(command[1], command[2])
        elif command[0] == "read":
            report(read=call_tool("read_messages", {}))
        elif command[0] == "run":
            run_skill_file(command[1], command[2])
        elif command[0] == "spawn":
            call_tool("spawn_worker", {"task": " ".join(command[1:])})
        elif command[0] == "finish":
            call_tool("finish_worker", {"name": command[1], "discard": command[2:] == ["discard"]})
        elif command[0] == "flow_start":
            report(flow_start=call_tool("flow_start", {"flow": command[1], "task": command[2]}))
        elif command[0] == "spawnrun":
            call_tool("spawn_worker", {"run": command[1]})
        elif command[0] == "advance":
            args = {"run": command[1], "outcome": command[2]}
            report(advance=call_tool("flow_advance", args))
    time.sleep(0.05)  # think
    return False


def main() -> None:
    signal.signal(signal.SIGHUP, lambda *_: os._exit(0))  # its tmux session was killed
    print("\x1b[?2004h", end="", flush=True)  # bracketed paste mode
    report(prompt=config["prompt"], skills=load_skills(), mcp=config["mcp"])
    # Like Claude Code: the MCP server connects while the session-start hook runs.
    connect_mcp()
    hook("session_start")
    text = sys.argv[2] if len(sys.argv) > 2 else None  # the first message
    while True:
        if text is None:
            text = read_input()
            if text is None:
                break
        if not text.strip():
            text = None
            continue
        print(f"> {text!r}", flush=True)
        if text.startswith("switch "):
            hook("conversation_end")
            time.sleep(float(text.split()[1]))
            hook("conversation_start")
            text = None
            continue
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
