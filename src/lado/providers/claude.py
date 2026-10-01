"""Claude Code as a LADO provider."""

import json
import shutil

from lado import state
from lado.providers import base

# Claude Code hook events and the neutral events they stand for. Notification is mapped
# in parse_event: only permission prompts mean the agent waits for the human.
EVENTS = {
    "SessionStart": base.SESSION_START,
    "UserPromptSubmit": base.PROMPT_SUBMIT,
    "Stop": base.TURN_END,
    "SessionEnd": base.SESSION_END,
}


class ClaudeProvider(base.Provider):
    name = "claude"
    title = "Claude Code"
    command = "claude"
    install_hint = "install it: https://docs.anthropic.com/en/docs/claude-code"
    capabilities = base.Capabilities(
        status_events=True, permission_event=True, deliver_on_turn_end=True, skills=True
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
        mcp_config.write_text(json.dumps({"mcpServers": servers}, indent=2))

        def hook(event: str) -> list[dict]:
            command = base.hook_command(agent, event)
            return [{"hooks": [{"type": "command", "command": command}]}]

        settings = config_dir / "settings.json"
        events = [*EVENTS, "Notification"]
        settings.write_text(json.dumps({"hooks": {e: hook(e) for e in events}}, indent=2))

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
        return base.Event(EVENTS[native], data.get("prompt", ""))

    def continue_output(self, text: str) -> str | None:
        # Blocking the stop makes Claude Code continue with `reason` as its next input.
        return json.dumps({"decision": "block", "reason": text})
