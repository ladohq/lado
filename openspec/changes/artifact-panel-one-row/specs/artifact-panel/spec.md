## Purpose

The artifact panel of the web UI: the viewer a chip or a row of the Artifacts tab opens on
the right over the session's page (docs/design/ui.md, Artifacts, The panel).

## ADDED Requirements

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
