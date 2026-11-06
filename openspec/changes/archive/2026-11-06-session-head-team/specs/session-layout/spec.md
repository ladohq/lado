## ADDED Requirements

### Requirement: On Activity the feed starts right under the tabs

Outside the phone layout the Activity tab SHALL have no gap under the tabs and no row between
them and the feed, and the composer's line SHALL take no height of the page. In a window 1440×900
the feed SHALL start at y = 88 and be 742 px high, whatever the agents, the runs and the terminals.

#### Scenario: A laptop
- **WHEN** a session of 4 agents and a run is open on Activity in a window 1440×900, with the
  terminals open or folded
- **THEN** the feed starts at y = 88 and is 742 px high

#### Scenario: Another tab
- **WHEN** the human opens Artifacts
- **THEN** the gap under the tabs is as before

### Requirement: The keys hint shows only in an empty field with the focus

Outside the phone layout the line under the composer SHALL show `Enter to send · Shift+Enter for
a new line · paste or drop files` only while the composer's field is empty and has the focus,
without `paste or drop files` while files are attached. Neither the hint nor the line SHALL move
the composer or the feed. A line too long for the column SHALL be cut with "…".

#### Scenario: The focus comes
- **WHEN** the human clicks in the empty field
- **THEN** the hint shows and the field, the paperclip and the feed stay where they were

#### Scenario: Text in the field
- **WHEN** the human types a letter
- **THEN** the hint goes and the room it had stays empty

#### Scenario: A narrow column
- **WHEN** the composer's column is narrower than 560 px
- **THEN** no hint shows, as before

#### Scenario: A problem under the composer
- **WHEN** a file over the limit is refused
- **THEN** the words lie under the line, clear of it, and the composer rises as before

### Requirement: The composer names only an agent the human chose

The line under the composer SHALL show `to <agent>` only when it writes to an agent other than the
supervisor; on an agent's page it SHALL stay in the flow, the hint only turning visible. The files'
line SHALL show as before. With neither `to` nor files the line SHALL be empty.

#### Scenario: The supervisor
- **WHEN** the composer of Activity writes to the supervisor with no files
- **THEN** the line has no `to supervisor`

#### Scenario: An agent's page
- **WHEN** the human opens developer-2's page
- **THEN** the line shows `to developer-2`

#### Scenario: Files
- **WHEN** 3 files are attached in the composer of Activity
- **THEN** the line shows `3 files, 228.5 KB` and no `to supervisor`

## MODIFIED Requirements

### Requirement: A session's tabs give way in levels

When a session's tabs do not fit their bar, a tool's word at the bar's end SHALL go first; then they
SHALL lose their icons, then their counts.
When they still do not fit, the bar SHALL scroll sideways with a fade of 56 px at its right end and
a button › of 26 px; once scrolled, the same ‹ SHALL show at its left end, and each SHALL go at
its end of the bar. The level SHALL follow the bar's width without a reload. The tab shown SHALL be
in view.

#### Scenario: A little short
- **WHEN** the tabs with icons and counts are wider than the bar and fit without icons
- **THEN** the tabs show no icons and keep their counts

#### Scenario: Very short
- **WHEN** the tabs without icons and counts are wider than the bar
- **THEN** a fade and › show at the right, and › scrolls the tabs until Artifacts is seen, when ›
  goes and ‹ shows

#### Scenario: The word goes first
- **WHEN** the tabs with icons and counts fit the bar beside `Yours | All` but not beside the
  word `Messages`
- **THEN** the word goes and the tabs keep their icons and counts

### Requirement: The terminal strip has a button per agent

The terminals' strip SHALL be 32 px wide. It SHALL hold, top to bottom, a button that opens the
panel, a button of 24×24 per agent of the session, and the caption Terminals. An agent's button
SHALL show the agent's avatar colour and its mark, as in the head, and a status mark of 8 px in its
corner on a ring of 1.5 px in `--panel`, and SHALL be named `Open <agent>'s terminal`. It SHALL open
the panel on that agent's terminal. With more agents than fit the strip SHALL scroll.

#### Scenario: Opening an agent's terminal
- **WHEN** the human presses `Open critic's terminal` on the strip
- **THEN** the panel opens with critic's terminal shown

#### Scenario: A waiting agent
- **WHEN** an agent waits for the human
- **THEN** its button shows the waiting diamond in its corner

#### Scenario: One mark on one screen
- **WHEN** the team has `developer-2` and `developer-3`
- **THEN** their buttons on the strip show `D2` and `D3`, as in the head

### Requirement: At 601 to 900 px a session's page stands still

In a window 601 to 900 px wide that is not the phone layout, a session's page SHALL not scroll as
a window; it SHALL be the window's height. Top to bottom it SHALL show the top bar, the session
strip as a row of 48 px, the tabs, the feed that scrolls inside and stays at its
end, the waiting card and the composer. Other pages SHALL scroll as before.

#### Scenario: A tablet
- **WHEN** the window is 768 or 880 px wide with a gate open on a session's page
- **THEN** the window does not scroll, and the card and the composer are in sight at once

#### Scenario: Needs you
- **WHEN** the window is 768 px wide and the human opens Needs you
- **THEN** the page scrolls as before and its card is whole
