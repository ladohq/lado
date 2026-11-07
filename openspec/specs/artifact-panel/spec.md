# artifact-panel Specification

## Purpose
The artifact panel of the web UI: the viewer a chip or a row of the Artifacts tab opens on
the right over the session's page (docs/design/ui.md, Artifacts, The panel).

## Requirements

### Requirement: The artifact panel shows its buttons in one row

Except on a phone (see "A phone's artifact panel moves the rest to a menu"), the artifact panel
SHALL show all its buttons in one row, its top bar: Open in Artifacts tab (Full page over that
tab), Open in new tab (only for a record the browser can show), Download and Copy link, then
Expand (only with an edge) and Close at the right end. The viewer's name line in the panel SHALL
hold no button. The artifact's page SHALL keep its buttons in its name line.

#### Scenario: A panel of 620 px
- **WHEN** the human opens the Markdown artifact `task/lad-41/ledger` in a panel 620 px
  wide
- **THEN** its top bar shows "Open in Artifacts tab", "Open in new tab", "Download", the
  Copy link button, Expand and Close in one row, the first three with their labels, and its
  name line shows only the type's icon and `task/lad-41/ledger`

#### Scenario: A type the browser cannot show
- **WHEN** the human opens an artifact of type `application/octet-stream` in the panel
- **THEN** its top bar has no "Open in new tab", and Download and Copy link are there

#### Scenario: The artifact's page
- **WHEN** the human follows "Open in Artifacts tab"
- **THEN** the artifact's page shows Open in new tab, Download and Copy link in its name
  line, as before

#### Scenario: Over the Artifacts tab
- **WHEN** the human opens a row of the Artifacts tab in a panel 620 px wide
- **THEN** the bar's first button says "Full page", with the tooltip "Open as a page in this tab",
  and goes to the artifact's page; Expand keeps its name, with the tooltip "Widen the panel"

### Requirement: A narrow artifact panel shows its actions as icons

When the panel is narrower than 560 px, the
action buttons SHALL show their icons without a visible label, each with the UI's
tooltip, and keep their accessible names.

#### Scenario: A panel of 400 px
- **WHEN** the human narrows that panel to 400 px
- **THEN** the same buttons stay in one row of the top bar, the four actions as icons with
  no visible label, and hovering Download shows the tooltip "Download"

#### Scenario: A phone's panel
- **WHEN** the human opens the artifact on a window 390 px wide, where the panel takes the
  whole screen
- **THEN** the top bar shows Download, Copy link, "⋯" and Close in one row, with no Expand

### Requirement: A chip on Needs you opens the artifact panel over the page

A chip on Needs you SHALL open the artifact panel over the Needs you page, as a step of
the browser's history, without leaving the page: its cards and their picks SHALL stay as they
were. ×, Esc, a click on the scrim and Back SHALL close it, the focus going back to the chip. The
address SHALL name the record and its session, so a reload shows the same panel over Needs you.

#### Scenario: A chip in a card on Needs you
- **WHEN** the human has picked "Делай сам в ветке" in lad-46's card on Needs you and
  clicks its chip `lad-46-plan`
- **THEN** the panel shows `lad-46-plan` over Needs you, and after × the page shows the
  card with that choice still picked and the focus on the chip

#### Scenario: Back
- **WHEN** the panel is open over Needs you and the human goes Back
- **THEN** the panel closes and Needs you stays

### Requirement: A phone's artifact panel moves the rest to a menu

In a window of 600 px or less the panel's top bar SHALL show Download, Copy link, "⋯" and Close, as
icons with their accessible names. "⋯" SHALL open a menu with labelled items: Open in new tab (only
for a record the browser can show), and Open in Artifacts tab, or Full page over the Artifacts tab.

#### Scenario: The menu
- **WHEN** the human presses "⋯" over the Activity tab
- **THEN** the menu says "Open in new tab" and "Open in Artifacts tab", and Esc closes it with the
  focus back on "⋯"

#### Scenario: A type the browser cannot show on a phone
- **WHEN** the record is `application/octet-stream`
- **THEN** the menu has no "Open in new tab"

### Requirement: The viewer says its title once

The viewer's head SHALL show no title line when a Markdown record's first non-blank line is an H1
equal to the title, ignoring case and outer spaces. While the text loads a Markdown record SHALL
show no title line; when the read fails it SHALL show the title.

#### Scenario: The same heading
- **WHEN** `plan`, titled "The plan", starts with `# The plan`
- **THEN** the panel and the artifact's page show the name and that H1, and no title line

#### Scenario: Another heading
- **WHEN** the record starts with `# Plan of the week`
- **THEN** the title line shows

### Requirement: The viewer's pill says what it names

The pill of the viewer's facts SHALL say "session" for a session's record and "step <state>" for a
run's.

#### Scenario: A run's record
- **WHEN** the record was written in the state `review`
- **THEN** the pill says "step review"

#### Scenario: A session's record
- **WHEN** the record is the session's
- **THEN** the pill says "session"
