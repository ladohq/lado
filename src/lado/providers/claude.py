"""Claude Code as a LADO provider."""

import json
import shutil

from lado import state
from lado.providers import base

# `lado doctor` warns when the installed Claude Code is not this version. Checked with it
# (and 2.1.286) by hand: a server with alwaysLoad in --mcp-config has its tools loaded up
# front when it is connected before the first turn; one that connects later has its tools
# deferred behind ToolSearch all the same. The interactive first turn does not wait for
# MCP servers (CLAUDE_CODE_MCP_STARTUP_WAIT_MS, MCP_CONNECTION_NONBLOCKING=false and
# CLAUDE_CODE_MCP_PREWAIT_SERVERS change nothing there), but it does wait for the
# SessionStart hooks. So LADO's SessionStart hook waits for LADO's MCP server
# (hold_first_turn, lado.hooks). The live test checks this in w1's transcript.
TESTED_VERSION = "2.1.287"

# Claude Code hook events and the neutral events they stand for. Notification is mapped
# in parse_event: only permission prompts mean the agent waits for the human.
EVENTS = {
    "SessionStart": base.SESSION_START,
    "UserPromptSubmit": base.PROMPT_SUBMIT,
    "Stop": base.TURN_END,
    "SessionEnd": base.SESSION_END,
}

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
            command = base.hook_command(agent, event)
            return [{"hooks": [{"type": "command", "command": command}]}]

        settings = config_dir / "settings.json"
        events = [*EVENTS, "Notification"]
        config = {
            "hooks": {e: hook(e) for e in events},
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
        if session.permission_mode:
            cmd += ["--permission-mode", session.permission_mode]
        if first_message:
            cmd += ["--", first_message]
        return base.Launch(cmd)

    def parse_event(self, native: str, payload: str) -> base.Event | None:
        data = json.loads(payload) if payload.strip() else {}
        if native == "Notification":
            kind = data.get("notification_type") or data.get("message", "")
            return base.Event(base.WAITING) if "permission" in kind.lower() else None
        if native not in EVENTS:
            return None
        if native == "SessionEnd" and data.get("reason") in SWITCHES:
            return base.Event(base.CONVERSATION_END)
        if native == "SessionStart" and data.get("source") in SWITCHES:
            return base.Event(base.CONVERSATION_START)
        return base.Event(EVENTS[native], data.get("prompt", ""))

    def continue_output(self, text: str) -> str | None:
        # Blocking the stop makes Claude Code continue with `reason` as its next input.
        return json.dumps({"decision": "block", "reason": text})
