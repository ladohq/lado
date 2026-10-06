"""Claude Code as a LADO provider."""

import hashlib
import json
import shutil

from lado import state
from lado.providers import base

# `lado doctor` warns when the installed Claude Code is not this version, the one
# `make test-live PROVIDER=claude` last passed on. Checked with 2.1.287 (and 2.1.286) by
# hand: a server with alwaysLoad in --mcp-config has its tools loaded up front when it is
# connected before the first turn; one that connects later has its tools
# deferred behind ToolSearch all the same. The interactive first turn does not wait for
# MCP servers (CLAUDE_CODE_MCP_STARTUP_WAIT_MS, MCP_CONNECTION_NONBLOCKING=false and
# CLAUDE_CODE_MCP_PREWAIT_SERVERS change nothing there), but it does wait for the
# SessionStart hooks. So LADO's SessionStart hook waits for LADO's MCP server
# (hold_first_turn, lado.hooks). The live test checks this in w1's transcript.
# AgentSpec.read (the lead's lead-files, lado.runtime) checked by hand with 2.1.289 in mode
# default (`claude -p`): a SKILL.md folder in an --add-dir directory without .claude/skills
# is not listed as a skill, and the Read tool reads it with no permission denial.
TESTED_VERSION = "2.1.289"

# Claude Code hook events and the neutral events they stand for.
#
# A dialog for the human: PermissionRequest runs just before Claude Code shows one, also
# for an AskUserQuestion question (with bypassPermissions only for that) and never for a
# call that dontAsk refuses; Elicitation before an MCP server's form. Checked in the modes
# default, bypassPermissions and dontAsk; not in auto (Claude Code offers it to no Haiku,
# BACKLOG.md): if its classifier refuses a call after PermissionRequest, no hook ends the
# wait before the turn's end. Their answer: the tool call's PostToolUse or PostToolUseFailure, or
# ElicitationResult. The pair has the same key (_request_key), so a subagent's tool or the
# next tool after a refusal does not end the wait. When the human refuses a permission or
# dismisses a question, no hook runs at all: the agent stays waiting until the human types
# (BACKLOG.md); when the human refuses with a comment, until its turn ends. Notification
# says the same as these, about 6 s later, so it is not used. Checked by hand with Claude
# Code 2.1.289.
#
# StopFailure runs instead of Stop when an API error ended the turn (rate_limit, overloaded,
# authentication_failed, billing_error, server_error, also for "your computer went to
# sleep", max_output_tokens, unknown, ...), with `error` and `error_details`; Claude Code
# ignores its output and exit code (read in the binary of 2.1.291, not triggered by hand).
EVENTS = {
    "SessionStart": base.SESSION_START,
    "UserPromptSubmit": base.PROMPT_SUBMIT,
    "Stop": base.TURN_END,
    "StopFailure": base.TURN_END,
    "SessionEnd": base.SESSION_END,
    "PermissionRequest": base.WAITING,
    "Elicitation": base.WAITING,
    "PostToolUse": base.RESUMED,
    "PostToolUseFailure": base.RESUMED,
    "ElicitationResult": base.RESUMED,
}
# Hooks that run without holding Claude Code up: one runs after every tool call.
ASYNC = ("PostToolUse", "PostToolUseFailure", "ElicitationResult")

# /clear and /resume end Claude Code's session (SessionEnd with this reason) and start
# another one in the same process (SessionStart with it as source); /exit ends it with
# "prompt_input_exit". Checked with Claude Code 2.1.287. /resume opens its picker without a
# hook and Esc cancels it without one; both events come only once a conversation is chosen.
SWITCHES = ("clear", "resume")

# Claude Code's own tools for messaging and listing agents (its subagents, teammates and
# other local sessions). An agent that picks them instead of LADO's send_message and
# list_agents talks to nobody, so they are denied. A deny rule removes them from the
# agent's tool list, also with --permission-mode bypassPermissions (checked with 2.1.286).
BUILT_IN_MESSAGING = ["SendMessage", "ListAgents"]


class ClaudeProvider(base.Provider):
    name = "claude"
    title = "Claude Code"
    command = "claude"
    install_hint = "install it: https://docs.anthropic.com/en/docs/claude-code"
    tested_version = TESTED_VERSION
    capabilities = base.Capabilities(
        status_events=True,
        permission_event=True,
        deliver_on_turn_end=True,
        skills=True,
        hold_first_turn=True,
    )
    # Passed on as --permission-mode: the choices of Claude Code 2.1.287, which also takes
    # "default" without listing it.
    permission_modes = (
        "default",
        "acceptEdits",
        "auto",
        "bypassPermissions",
        "manual",
        "dontAsk",
        "plan",
    )

    def launch_command(
        self,
        agent: state.Agent,
        session: state.Session,
        spec: base.AgentSpec,
        first_message: str | None = None,
    ) -> base.Launch:
        config_dir = base.config_dir(agent)

        mcp_config = config_dir / "mcp.json"
        servers = {
            name: {"command": s.command[0], "args": s.command[1:], "env": s.env}
            for name, s in spec.mcp.items()
        }
        # Claude Code defers MCP tools behind its ToolSearch tool; a weak model then may not
        # find send_message and never report. alwaysLoad puts LADO's tools in the prompt,
        # if the server is connected before the first turn (see TESTED_VERSION).
        if "lado" in servers:
            servers["lado"]["alwaysLoad"] = True
        mcp_config.write_text(json.dumps({"mcpServers": servers}, indent=2))

        def hook(event: str) -> list[dict]:
            command: dict = {"type": "command", "command": base.hook_command(agent, event)}
            if event in ASYNC:
                command["async"] = True
            return [{"hooks": [command]}]

        settings = config_dir / "settings.json"
        config = {
            "hooks": {e: hook(e) for e in EVENTS},
            "permissions": {"deny": BUILT_IN_MESSAGING},
        }
        settings.write_text(json.dumps(config, indent=2))

        cmd = [
            self.command,
            "--mcp-config",
            str(mcp_config),
            "--settings",
            str(settings),
            "--append-system-prompt",
            spec.prompt,
        ]
        # Claude Code loads the skills in <dir>/.claude/skills of every --add-dir directory
        # (checked with Claude Code 2.1.286; symlinked skill folders work, and their scripts
        # run from there). Nothing is written into the worktree or ~/.claude.
        skills_root = config_dir / "skills"
        if spec.skills:
            base.link_skills(skills_root / ".claude" / "skills", spec.skills)
            cmd += ["--add-dir", str(skills_root)]
        elif skills_root.exists():
            shutil.rmtree(skills_root)
        # Files in an --add-dir directory are read without asking; with no .claude/skills
        # in it, nothing there is loaded as a skill.
        for folder in spec.read:
            cmd += ["--add-dir", str(folder)]
        if session.permission_mode:
            cmd += ["--permission-mode", session.permission_mode]
        if first_message:
            cmd += ["--", first_message]
        return base.Launch(cmd)

    def parse_event(self, native: str, payload: str) -> base.Event | None:
        if native not in EVENTS:
            return None
        data = json.loads(payload) if payload.strip() else {}
        if native == "SessionEnd" and data.get("reason") in SWITCHES:
            return base.Event(base.CONVERSATION_END)
        if native == "SessionStart" and data.get("source") in SWITCHES:
            return base.Event(base.CONVERSATION_START)
        if native == "StopFailure":
            error = base.error_line(data.get("error") or "unknown", data.get("error_details", ""))
            return base.Event(base.TURN_END, error=error, output_ignored=True)
        neutral = EVENTS[native]
        if neutral in (base.WAITING, base.RESUMED):
            return base.Event(neutral, key=_request_key(data))
        return base.Event(neutral, data.get("prompt", ""))

    def continue_output(self, text: str) -> str | None:
        # Blocking the stop makes Claude Code continue with `reason` as its next input.
        return json.dumps({"decision": "block", "reason": text})


def _request_key(data: dict) -> str:
    """The key of the dialog a hook is about: the tool call (its tool and input), or the MCP
    server whose form it is. PermissionRequest has no tool_use_id (2.1.289), but the input
    it shows is the one the tool's PostToolUse gets; an AskUserQuestion's answer adds its
    answers to it, so only the questions count."""
    if "mcp_server_name" in data and "tool_name" not in data:
        about = ["elicitation", data["mcp_server_name"]]
    else:
        tool_input = data.get("tool_input") or {}
        if data.get("tool_name") == "AskUserQuestion":
            tool_input = {"questions": tool_input.get("questions")}
        about = ["tool", data.get("tool_name", ""), tool_input]
    return hashlib.sha256(json.dumps(about, sort_keys=True).encode()).hexdigest()[:16]
