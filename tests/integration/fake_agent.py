"""A fake agent CLI for the integration tests: behaves like an agent in a terminal, no LLM.

Usage: fake_agent.py <config.json> (written by fake_provider.FakeProvider). Like a real agent
under LADO, it gets no input on its command line: its task comes as a message from LADO.

It reports its lifecycle through the hooks in the config and works on each input typed or
pasted into its terminal. In its first input (a worker's task, a resumed supervisor's
messages), a line from "lado" that has more to read makes it call read_messages and work on
the body of each message from "lado" it gets, as an agent reads its task and does it; the
bodies of later messages, and of other senders, it only reads when told to (`read`).
Every input line is a command, after an optional "[from <name>] ":
    send <to> <summary>[ | <body>][ --artifacts <name>,<name>...]  call the LADO MCP tool
                       send_message; "\\n" in the body is a line break
    artifact_write <name> <path>  call the LADO MCP tool write_artifact with the file at
                       <path> (relative: to the agent's folder, as an agent passes it)
    artifact_read <name>  call the LADO MCP tool read_artifact; "seen" gets its result and
                       the type (and mimeType) of each content block
    read               call the LADO MCP tool read_messages
    askhuman <question>[ | <choice>, <choice>...][ --artifacts <name>,<name>...]  call the
                       LADO MCP tool ask_human
    start_session <name> <question id>  call the LADO MCP tool start_session; "seen" gets
                       its result ("start_session") and its text ("start_session_text")
    spawn <task>       call the LADO MCP tool spawn_worker
    finish <name> [discard]  call the LADO MCP tool finish_worker
    flow_start <flow> <task>  call the LADO MCP tool flow_start
    spawnrun <run>     call the LADO MCP tool spawn_worker for a flow run
    advance <run> <outcome>[ <note summary>[ | <body>]]  call the LADO MCP tool
                       flow_advance; "\\n" in the body is a line break
    sleep <seconds>    work that long
    pause              print "paused <n>" (the n-th pause), write a file "paused-<n>" beside
                       "inputs", and work until the test releases it: a file "release-<n>"
                       there (agent_helpers.paused, .release); it reads no input meanwhile,
                       as a CLI busy in a turn
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
    lose               pause, then drop what the turn-end hook prints, as a CLI that does
                       not take it
    background         end this turn with work it started still running: its turn-end
                       hook says so, as Claude Code's Stop with background_tasks
With FAKE_AGENT_CRASH_AT_START=1 in its environment it exits before its first hook, as a
CLI that fails at once (a bad flag). With FAKE_AGENT_ASKS_FIRST=1 in its environment it asks
the human before any hook, like Claude Code's "trust this folder?": a typed "yes" goes on,
any other input exits at once with no hook. With FAKE_AGENT_HANGUP_HOOK=1 in its environment, when
its tmux window is killed (SIGHUP) it runs its session-end hook before it exits, as Claude
Code does, and writes {"hung_up": <what the hook printed>} to "seen" once the hook is done;
else it exits at once.
A typed "switch" is no input but a command of the CLI itself, like Claude Code's /resume: the
agent leaves its conversation, picks another while it pauses (as `pause`), and goes on in
the same process; no prompt-submit and no turn-end hook run for it. A typed "dialog" opens a
modal dialog, like Claude Code's folder-trust dialog: it swallows the next input, and no hook
runs for either.
Other lines are ignored. Each input is logged to the config's "inputs" file, and the output
of `run`, the messages from `read` and the results of `flow_start` and `advance` to its
"seen" file. At start the agent writes what it was given (prompt, skills found in its
skills folder, MCP servers, its environment) to "seen", as a real agent CLI would load them,
and starts its LADO MCP server and lists its tools while its session-start hook runs; like a
real CLI, it keeps that one server for all its tool calls. It talks to that server through
its own small MCP client (LadoMcp), not the MCP SDK.
"""

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import traceback

PASTE_START, PASTE_END = "\x1b[200~", "\x1b[201~"
TO_READ = re.compile(r" \(#\d+, [^)]*: call read_messages\)$")

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


class McpError(Exception):
    """The LADO MCP server answered a request with a JSON-RPC error, or could not serve it."""


class LadoMcp:
    """A minimal MCP client of the LADO MCP server: stdio, one JSON-RPC message per line. Not
    the MCP SDK's client, whose import alone takes about a third of a second per launch.

    Like Claude Code, Kilo and OpenCode, the server gets the agent's whole environment and
    its config's env on top (so a session its `lado mcp` starts gets the test's
    environment, LADO_AGENT_ENV=inherit); its stderr goes to the agent's terminal.
    A tool's error comes back as a result with isError; a JSON-RPC error, or a server that
    did not start or ended, raises McpError."""

    PROTOCOL = "2025-06-18"

    def __init__(self):
        self.ready = threading.Event()  # set once connected, or once that failed
        self.error: BaseException | None = None
        self.server: subprocess.Popen | None = None
        self.last_id = 0
        self.last_content: list[dict] = []  # the content blocks of the latest tool call

    def connect(self) -> None:
        """Start the server, initialize the session and list the tools, in a thread (as the
        session-start hook runs)."""
        threading.Thread(target=self._connect, daemon=True).start()

    def _connect(self) -> None:
        try:
            lado = config["mcp"]["lado"]
            self.server = subprocess.Popen(
                lado["command"],
                env={**os.environ, **lado["env"]},
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
            )
            client = {"name": "fake-agent", "version": "0"}
            params = {"protocolVersion": self.PROTOCOL, "capabilities": {}, "clientInfo": client}
            self._request("initialize", params)
            self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            self._request("tools/list", {})
        except BaseException as exc:
            self.error = exc
        self.ready.set()

    def _send(self, message: dict) -> None:
        self.server.stdin.write(json.dumps(message) + "\n")
        self.server.stdin.flush()

    def _request(self, method: str, params: dict) -> dict:
        """Send a request and return its result, passing over the server's notifications."""
        self.last_id += 1
        self._send({"jsonrpc": "2.0", "id": self.last_id, "method": method, "params": params})
        while True:
            line = self.server.stdout.readline()
            if not line:
                raise McpError(f"the LADO MCP server ended before it answered {method}")
            message = json.loads(line)
            if message.get("id") != self.last_id or "method" in message:
                continue
            if "error" in message:
                raise McpError(f"{method}: {message['error'].get('message')}")
            return message["result"]

    def call_tool(self, name: str, arguments: dict) -> dict:
        """The result of a tool call: {content, structuredContent?, isError?}."""
        self.ready.wait()
        if self.error:
            raise McpError("the LADO MCP server did not start") from self.error
        return self._request("tools/call", {"name": name, "arguments": arguments})


# Started once and kept, as an agent CLI does: it lists the tools at start, then serves
# every tool call. If it cannot start, every call fails.
lado_mcp = LadoMcp()


def call_tool(name: str, arguments: dict):
    """Call a tool of the LADO MCP server. Returns its structured result."""
    result = lado_mcp.call_tool(name, arguments)
    content = result.get("content", [])
    lado_mcp.last_content = content
    print(f"{name}: {[c.get('text') for c in content]}", flush=True)
    if result.get("structuredContent") is None:  # a dict comes as JSON text
        return json.loads(content[0]["text"]) if not result.get("isError") else None
    return result["structuredContent"].get("result")


def send(to: str, text: str) -> None:
    text = TO_READ.sub("", text)  # LADO's note on the line it got: no part of the command
    text, _, attached = text.partition(" --artifacts ")
    summary, _, body = text.partition(" | ")
    arguments = {"to": to, "summary": summary}
    if body:
        arguments["body"] = body.replace("\\n", "\n")
    if attached:
        arguments["artifacts"] = attached.split(",")
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


pauses = 0  # how often `pause` ran


def pause() -> None:
    """Work until the test releases the n-th pause: a file "release-<n>" beside "inputs"
    (agent_helpers.release). It reads nothing meanwhile, as a CLI busy in a turn. A file
    "paused-<n>" there says it is in it (agent_helpers.paused)."""
    global pauses
    pauses += 1
    logs = os.path.dirname(config["inputs"])
    open(os.path.join(logs, f"paused-{pauses}"), "w").close()
    print(f"paused {pauses}", flush=True)
    release = os.path.join(logs, f"release-{pauses}")
    while not os.path.exists(release):
        time.sleep(0.02)


holds = 0  # how often `hold` ran
turn_error = ""  # the error the turn ends on (`fail`)
always_error = ""  # the error every turn ends on (`failing`)
lose_output = False  # drop what the turn-end hook prints (`lose`)
in_background = False  # work goes on after this turn (`background`)


def work(text: str) -> bool:
    """Act on the commands in `text`. Returns True for exit."""
    global holds, turn_error, always_error, lose_output, in_background
    for line in text.splitlines():
        command = re.sub(r"^\[from [^\]]*\] ", "", line.strip()).split(" ", 2)
        if command[0] == "exit":
            return True
        if command[0] == "die":
            os._exit(3)
        if command[0] == "background":
            in_background = True
        elif command[0] == "fail":
            turn_error = " ".join(command[1:])
        elif command[0] == "failing":
            always_error = " ".join(command[1:])
        elif command[0] == "lose":
            pause()
            lose_output = True
        elif command[0] == "pause":
            pause()
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
        elif command[0] == "artifact_write":
            written = call_tool("write_artifact", {"name": command[1], "file": command[2]})
            report(artifact_write=written)
        elif command[0] == "artifact_read":
            read = call_tool("read_artifact", {"name": command[1]})
            blocks = lado_mcp.last_content
            kinds = [{"type": b.get("type"), "mimeType": b.get("mimeType")} for b in blocks]
            report(artifact_read=read, artifact_read_blocks=kinds)
        elif command[0] == "askhuman":
            asked, _, attached = " ".join(command[1:]).partition(" --artifacts ")
            question, _, choices = asked.partition(" | ")
            arguments = {"question": question}
            if choices:
                arguments["choices"] = choices.split(", ")
            if attached:
                arguments["artifacts"] = attached.split(",")
            call_tool("ask_human", arguments)
        elif command[0] == "start_session":
            started = call_tool("start_session", {"name": command[1], "question": int(command[2])})
            texts = [c.get("text") for c in lado_mcp.last_content]
            report(start_session=started, start_session_text=texts)
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
    return False


def lado_bodies(text: str) -> str:
    """The bodies of LADO's messages whose lines in `text` say there is more to read, read
    with read_messages (reported as "first_read"); "" when there are none."""
    if not any(
        line.startswith("[from lado] ") and TO_READ.search(line) for line in text.splitlines()
    ):
        return ""
    read = call_tool("read_messages", {})
    report(first_read=read)
    return "\n".join(m["body"] for m in read if m["from"] == "lado" and m["body"])


def hung_up(*_) -> None:
    """Its tmux window was killed: like Claude Code, it ends its session with the hook."""
    if os.environ.get("FAKE_AGENT_HANGUP_HOOK") == "1":
        report(hung_up=hook("session_end"))
    os._exit(0)


def main() -> None:
    global turn_error, lose_output, in_background
    if os.environ.get("FAKE_AGENT_CRASH_AT_START") == "1":
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
    lado_mcp.connect()
    hook("session_start")
    text = None
    first = True  # the next input is its first
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
        if text == "switch":
            hook("conversation_end")
            pause()
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
            if first:  # its task: read it and do it
                first = False
                text = "\n".join(filter(None, [text, lado_bodies(text)]))
            if work(text):
                break
        except Exception:
            traceback.print_exc()
        turn_error = turn_error or always_error
        background, in_background = in_background, False
        if turn_error:
            # Its output goes nowhere.
            hook("turn_end", error=turn_error, output_ignored=True, background=background)
            turn_error, text, continued = "", None, False
            continue
        output = hook(
            "turn_end",
            continued=continued and config.get("says_continued", False),
            background=background,
        )
        if lose_output:
            output, lose_output = "", False
        text = output if output and config["continue_on_turn_end"] else None
        continued = text is not None
    hook("session_end")


if __name__ == "__main__":
    main()
