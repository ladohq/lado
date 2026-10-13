# artifact-panel Specification

## Purpose
The artifact panel of the web UI: the viewer a chip or a row of the Artifacts tab opens on
the right over the session's page (docs/design/ui.md, Artifacts, The panel).

## Requirements

### Requirement: The artifact panel shows its buttons in one row

The artifact panel SHALL show all its buttons in one row, its top bar: Open in Artifacts
tab, Open in new tab (only for a record the browser can show), Download and Copy link, then
Expand (only when the panel has an edge) and Close at the bar's right end. The viewer's
name line in the panel SHALL hold no button. When the panel is narrower than 560 px, the
four action buttons SHALL show their icons without a visible label, each with the UI's
tooltip, and keep their accessible names. The artifact's page in the Artifacts tab SHALL
keep its buttons in its name line.

#### Scenario: A panel of 620 px
- **WHEN** the human opens the Markdown artifact `task/lad-41/ledger` in a panel 620 px
  wide
- **THEN** its top bar shows "Open in Artifacts tab", "Open in new tab", "Download", the
  Copy link button, Expand and Close in one row, the first three with their labels, and its
  name line shows only the type's icon and `task/lad-41/ledger`

#### Scenario: A panel of 400 px
- **WHEN** the human narrows that panel to 400 px
- **THEN** the same buttons stay in one row of the top bar, the four actions as icons with
  no visible label, and hovering Download shows the tooltip "Download"

#### Scenario: A phone's panel
- **WHEN** the human opens the artifact on a window 390 px wide, where the panel takes the
  whole screen
- **THEN** the top bar shows the four actions as icons and Close in one row, with no
  Expand

#### Scenario: A type the browser cannot show
- **WHEN** the human opens an artifact of type `application/octet-stream` in the panel
- **THEN** its top bar has no "Open in new tab", and Download and Copy link are there

#### Scenario: The artifact's page
- **WHEN** the human follows "Open in Artifacts tab"
- **THEN** the artifact's page shows Open in new tab, Download and Copy link in its name
  line, as before

### Requirement: A chip on Needs you opens the artifact panel over Needs you

A chip on Needs you SHALL open the artifact panel over the Needs you page, as a step of
the browser's history, without leaving the page: its cards, their picks and an expanded
card SHALL stay as they were. ×, Esc, a click on the scrim and Back SHALL close it, the
focus going back to the chip. The address SHALL name the record and its session, so a
reload shows the same panel over Needs you.

#### Scenario: A chip in a card on Needs you
- **WHEN** the human has picked "Делай сам в ветке" in lad-46's card on Needs you and
  clicks its chip `lad-46-plan`
- **THEN** the panel shows `lad-46-plan` over Needs you, and after × the page shows the
  card with that choice still picked and the focus on the chip

#### Scenario: Back
- **WHEN** the panel is open over Needs you and the human goes Back
- **THEN** the panel closes and Needs you stays

#### Scenario: From an expanded card
- **WHEN** lad-46's card is expanded on Needs you and the human clicks its chip
- **THEN** the panel shows over the expanded card, and the card stays expanded after the
  panel closes
