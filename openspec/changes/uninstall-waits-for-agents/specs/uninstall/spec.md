## MODIFIED Requirements

### Requirement: Everything of this LADO_HOME stops

After confirmation `lado uninstall` SHALL stop the UI server of this `LADO_HOME`, stop
every session not stopped yet as `lado stop --all` does, wait for each session's loop to
end, wait for the process of each tmux pane those sessions had to end (a zombie counts as
ended), and close this `LADO_HOME`'s terminal viewers. A loop or an agent's process that
does not end SHALL stop the uninstall before any repository or file is touched, saying so,
with exit 1; for an agent's process it SHALL name the session, the pids and the command
that ends them.

#### Scenario: A running session and the UI server
- **WHEN** a session with a supervisor and a worker runs, the UI server runs, and the
  human confirms the uninstall
- **THEN** no agent process, session loop or UI server of this `LADO_HOME` is left, and
  LADO's tmux server has ended

#### Scenario: An agent ends with its session-end hook
- **WHEN** the agents of a running session run their session-end hook when tmux kills
  them, and the human confirms the uninstall
- **THEN** the uninstall ends with no agent process left, and `LADO_HOME` does not exist
  afterwards

#### Scenario: An agent's process does not end
- **WHEN** an agent's process is still running 10 s after its session was stopped
- **THEN** the uninstall exits 1 naming the session, the pid and `kill <pid>`, and no
  repository, worktree or file of `LADO_HOME` was touched
