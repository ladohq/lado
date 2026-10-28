## MODIFIED Requirements

### Requirement: The guide's first session names Claude Code's trust question

The guide's "Your first session" SHALL say that LADO records Claude Code's trust in the
repository a session is started in, so Claude Code does not ask; that the repository's own
Claude Code settings and MCP servers then run without a question; and that when LADO
cannot record it, the agent waits in Needs you for Claude Code's question, whose answers
the scenario names.

#### Scenario: The guide on the trust question
- **WHEN** the human reads the guide's Docker "Your first session"
- **THEN** it says that LADO trusts the repository for Claude Code itself and that the
  repository's own Claude Code settings and MCP servers run, and that when LADO cannot,
  the agent waits in Needs you and "Yes, I trust this folder" answers it while Enter alone
  answers "No, exit" and closes the agent

### Requirement: The guide quotes the trust answers as LADO's reason words them

The guide's two answers to Claude Code's trust question SHALL be quoted as LADO's own
reason for that wait words them.

#### Scenario: The first session names Claude Code's trust question
- **WHEN** `tests/test_docker.py` reads the guide's Docker "Your first session"
- **THEN** it names Needs you and quotes "Yes, I trust this folder" and "No, exit", and
  each quoted answer is in the reason `ClaudeProvider.first_hook_blocker` gives for a folder
  Claude Code does not trust when LADO cannot record the trust (a config folder it cannot
  write)
