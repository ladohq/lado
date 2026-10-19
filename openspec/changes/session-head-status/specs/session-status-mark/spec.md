## ADDED Requirements

### Requirement: A session's mark comes from one rule

The session list's row, the session strip's icon, the session's card and the session's
head SHALL take the session's mark and its words from one rule of the web UI, on the
session's `SessionInfo` alone: `stopped`, `tmux_gone` or `loop_down` by its status; else
`needs-you` when a gate, a question or an agent waits for the human; else `working` when an
agent works, and `idle` when none does.

#### Scenario: A question waits while the agents idle
- **WHEN** a running session has one open question and no agent at work
- **THEN** its mark is `needs-you` and its words are `needs you · 1 question`, in its row
  and in its head alike

#### Scenario: Agents at work
- **WHEN** a running session has 2 of its 3 agents at work and nothing waits
- **THEN** its mark is `working` and its words are `running · 2 of 3 agents working`

#### Scenario: All agents free
- **WHEN** a running session has 3 agents, none at work, and nothing waits
- **THEN** its mark is `idle` and its words are `running · idle · 3 agents`

### Requirement: The list's group follows what waits, not the mark

The session list's group and the strip icon's "needs you" SHALL follow what waits for the
human, also in a session in trouble (`tmux_gone`, `loop_down`), whose mark stays its
trouble.

#### Scenario: Trouble while a gate waits
- **WHEN** a session's tmux is gone and a gate waits in it
- **THEN** its row is under **Needs you**, its strip icon is named `<name>, needs you`, and
  its head's dot is the `--danger` dot named `tmux session is gone`

### Requirement: The session's head shows the list's mark

The session's head, on a computer and on a phone, SHALL show the session's mark as a dot
before its name: `needs-you` an orange diamond (`--human`, a waiting agent's shape);
`working` the list's full `--done` dot with its pulse (none under
`prefers-reduced-motion: reduce`); `idle` the list's ring in `--muted`; `stopped` the
`--muted` dot; `tmux_gone` and `loop_down` the `--danger` dot with their status in words
after the name. The dot's tooltip and accessible name SHALL be the mark's words.

#### Scenario: The screenshot's case
- **WHEN** the human opens a session in which a question waits and the agents idle
- **THEN** the head's dot is the orange diamond named `needs you · 1 question`, and no
  green dot is in the head

#### Scenario: The head follows the session
- **WHEN** the session's last busy agent ends its turn while the session is open
- **THEN** the head's dot turns from the pulsing green dot into the muted ring, as the
  session's row does, with no reload

#### Scenario: A stopped session
- **WHEN** the human opens a stopped session
- **THEN** the head's dot is the muted dot named `stopped`, as before
