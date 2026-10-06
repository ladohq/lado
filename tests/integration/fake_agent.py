"""A fake agent CLI for the integration tests: behaves like an agent in a terminal, no LLM.

Usage: fake_agent.py <config.json> [<first message>] (written by fake_provider.FakeProvider).
The first message is on the command line, as real agent CLIs take it.

It reports its lifecycle through the hooks in the config and works on each input typed or
pasted into its terminal. Every input line is a command, after an optional "[from <name>] ":
    send <to> <summary>[ | <body>]  call the LADO MCP tool send_message; "\\n" in the body
                       is a line break
    read               call the LADO MCP tool read_messages
    askhuman <question>[ | <choice>, <choice>...]  call the LADO MCP tool ask_human
    spawn <task>       call the LADO MCP tool spawn_worker
    finish <name> [discard]  call the LADO MCP tool finish_worker
    flow_start <flow> <task>  call the LADO MCP tool flow_start
    spawnrun <run>     call the LADO MCP tool spawn_worker for a flow run
    advance <run> <outcome>[ <note summary>[ | <body>]]  call the LADO MCP tool
                       flow_advance; "\\n" in the body is a line break
    sleep <seconds>    work that long
    ask                ask the human for a permission: run the waiting hook, and take the
                       next input as the answer (logged as {"answer": <text>})
    wait <key>         run the waiting hook for request <key>, as a dialog for the human
                       opens
    resume <key>       run the resumed hook for request <key>, as the human answered it
    hold               print "holding <n>" (the n-th hold) and take the next input, with
                       no hook (logged as {"held": <text>}): the turn goes on after it
    run <skill> <file> run a file of one of its skills, e.g. "run notes scripts/hello.sh"
    mcp <server>       start a kit's MCP server as a CLI does and wait for it to exit
                       (logged as {"mcp_run": {server, code, stderr}})
    lines <n>          print the lines "line 1" to "line <n>"
    fullscreen         switch to the alternate screen and read the mouse, as a full-screen
                       CLI does
    exit               end the session
    die                exit at once, with no hook, as a CLI that crashes in a turn
    fail <error>       end the turn on an error: its turn-end hook gets <error>, and its
                       output is ignored, as Claude Code's StopFailure
    failing <error>    as fail, and every later turn ends on <error> too, as an API that
                       stays down
    lose <seconds>     work that long, then drop what the turn-end hook prints, as a CLI that
                       does not take it
A first message that starts with "crash at start" makes it exit before its first hook, as a
CLI that fails at once (a bad flag). With FAKE_AGENT_ASKS_FIRST=1 in its environment it asks
the human before any hook, like Claude Code's "trust this folder?": a typed "yes" goes on,
any other input exits at once with no hook. With FAKE_AGENT_HANGUP_HOOK=1 in its environment, when
its tmux window is killed (SIGHUP) it runs its session-end hook before it exits, as Claude
Code does, and writes {"hung_up": <what the hook printed>} to "seen" once the hook is done;
else it exits at once.
A typed "switch <seconds>" is no input but a command of the CLI itself, like Claude Code's
/resume: the agent leaves its conversation, takes that long to pick another, and goes on in
the same process; no prompt-submit and no turn-end hook run for it. A typed "dialog" opens a
modal dialog, like Claude Code's folder-trust dialog: it swallows the next input, and no hook
runs for either.
Other lines are ignored. Each input is logged to the config's "inputs" file, and the output
of `run`, the messages from `read` and the results of `flow_start` and `advance` to its
"seen" file. At start the agent writes what it was given (prompt, skills found in its
skills folder, MCP servers, its environment) to "seen", as a real agent CLI would load them,
and starts its LADO MCP server and lists its tools while its session-start hook runs; like a
real CLI, it keeps that one server for all its tool calls.
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


def hook(event: str, prompt: str = "", key: str = "", **more) -> str:
    """Run the agent's hook for `event`; returns what it printed."""
    payload = json.dumps({"prompt": prompt, "key": key, **more})
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


def run_mcp_server(name: str) -> None:
    """Start a kit's MCP server as an agent CLI does: its command, its env from the config
    on top of the agent's own environment. The test's server does its work and exits."""
    server = config["mcp"][name]
    result = subprocess.run(
        server["command"],
        env={**os.environ, **server["env"]},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
    )
    report(mcp_run={"server": name, "code": result.returncode, "stderr": result.stderr})


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


def log_input(text) -> None:
    with open(config["inputs"], "a") as log:
        log.write(json.dumps(text) + "\n")


def read_input() -> str | None:
    """The next input from the terminal; None at end of input.

    The terminal turns pasted line breaks into separate lines; the paste markers (bracketed
    paste mode, enabled in main) keep a pasted text in one piece. Like Claude Code, a
    backslash before Enter is a line break in the input, not its end.
    """
    text = ""
    while True:
        line = sys.stdin.readline()
        if not line:
            return text or None
        text += _read_paste(line)
        if not text.endswith("\\"):
            return text
        text = text[:-1] + "\n"


def _read_paste(line: str) -> str:
    """The input of one Enter that began with `line`: the text before it, a paste whole."""
    if PASTE_START not in line:
        return line.rstrip("\n")
    text = line.split(PASTE_START, 1)[1]
    while PASTE_END not in text:
        more = sys.stdin.readline()
        if not more:
            break
        text += more
    before, _, after = text.partition(PASTE_END)
    return before + after.rstrip("\n")


holds = 0  # how often `hold` ran
turn_error = ""  # the error the turn ends on (`fail`)
always_error = ""  # the error every turn ends on (`failing`)
lose_output = False  # drop what the turn-end hook prints (`lose`)


def work(text: str) -> bool:
    """Act on the commands in `text`. Returns True for exit."""
    global holds, turn_error, always_error, lose_output
    for line in text.splitlines():
        command = re.sub(r"^\[from [^\]]*\] ", "", line.strip()).split(" ", 2)
        if command[0] == "exit":
            return True
        if command[0] == "die":
            os._exit(3)
        if command[0] == "fail":
            turn_error = " ".join(command[1:])
        elif command[0] == "failing":
            always_error = " ".join(command[1:])
        elif command[0] == "lose":
            time.sleep(float(command[1]))
            lose_output = True
        elif command[0] == "sleep":
            time.sleep(float(command[1]))
        elif command[0] == "ask":
            hook("waiting")
            log_input({"answer": read_input()})
        elif command[0] == "wait":
            hook("waiting", key=command[1])
        elif command[0] == "resume":
            hook("resumed", key=command[1])
        elif command[0] == "hold":
            holds += 1
            print(f"holding {holds}", flush=True)
            log_input({"held": read_input()})
        elif command[0] == "send":
            send(command[1], command[2])
        elif command[0] == "read":
            report(read=call_tool("read_messages", {}))
        elif command[0] == "askhuman":
            question, _, choices = " ".join(command[1:]).partition(" | ")
            arguments = {"question": question}
            if choices:
                arguments["choices"] = choices.split(", ")
            call_tool("ask_human", arguments)
        elif command[0] == "run":
            run_skill_file(command[1], command[2])
        elif command[0] == "mcp":
            run_mcp_server(command[1])
        elif command[0] == "lines":
            print("\n".join(f"line {n}" for n in range(1, int(command[1]) + 1)), flush=True)
        elif command[0] == "fullscreen":
            print("\x1b[?1049h\x1b[?1000h\x1b[?1006h\x1b[Hfull screen", flush=True)
        elif command[0] == "spawn":
            call_tool("spawn_worker", {"task": " ".join(command[1:])})
        elif command[0] == "finish":
            call_tool("finish_worker", {"name": command[1], "discard": command[2:] == ["discard"]})
        elif command[0] == "flow_start":
            report(flow_start=call_tool("flow_start", {"flow": command[1], "task": command[2]}))
        elif command[0] == "spawnrun":
            call_tool("spawn_worker", {"run": command[1]})
        elif command[0] == "advance":
            outcome, _, note = command[2].partition(" ")
            summary, _, body = note.partition(" | ")
            args = {"run": command[1], "outcome": outcome}
            if summary:
                args["note_summary"] = summary
            if body:
                args["note_body"] = body.replace("\\n", "\n")
            report(advance=call_tool("flow_advance", args))
    time.sleep(0.05)  # think
    return False


def hung_up(*_) -> None:
    """Its tmux window was killed: like Claude Code, it ends its session with the hook."""
    if os.environ.get("FAKE_AGENT_HANGUP_HOOK") == "1":
        report(hung_up=hook("session_end"))
    os._exit(0)


def main() -> None:
    global turn_error, lose_output
    if len(sys.argv) > 2 and sys.argv[2].startswith("crash at start"):
        os._exit(3)
    signal.signal(signal.SIGHUP, hung_up)
    print("\x1b[?2004h", end="", flush=True)  # bracketed paste mode
    report(
        prompt=config["prompt"], skills=load_skills(), mcp=config["mcp"], environ=dict(os.environ)
    )
    if os.environ.get("FAKE_AGENT_ASKS_FIRST") == "1":
        print("Go on? Type yes; Enter alone exits", flush=True)
        if read_input() != "yes":
            os._exit(1)
    # Like Claude Code: the MCP server connects while the session-start hook runs.
    connect_mcp()
    hook("session_start")
    text = sys.argv[2] if len(sys.argv) > 2 else None  # the first message
    continued = False  # this turn goes on from what the turn-end hook printed
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
        if text == "dialog":
            print(f"> swallowed {read_input()!r}", flush=True)
            text = None
            continue
        log_input(text)
        if not (continued and config.get("says_continued")):
            hook("prompt_submit", text)
        try:
            if work(text):
                break
        except Exception:
            traceback.print_exc()
        turn_error = turn_error or always_error
        if turn_error:
            hook("turn_end", error=turn_error, output_ignored=True)  # its output goes nowhere
            turn_error, text, continued = "", None, False
            continue
        output = hook("turn_end", continued=continued and config.get("says_continued", False))
        if lose_output:
            output, lose_output = "", False
        text = output if output and config["continue_on_turn_end"] else None
        continued = text is not None
    hook("session_end")


if __name__ == "__main__":
    main()
