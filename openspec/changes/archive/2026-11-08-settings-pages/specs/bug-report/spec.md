## MODIFIED Requirements

### Requirement: The UI shows Report a bug on every page

The rail's Help menu SHALL have a **Report a bug** item with a bug icon, on every page (the
capability `rail-help`), and the rail SHALL have no item of its own for it. It SHALL open the
page `/report` (title "Report a bug"). A failed load SHALL show its reason. The page SHALL load
the report anew on each visit; the change feed does not carry it.

#### Scenario: The collapsed rail
- **WHEN** the rail is collapsed and the human opens Help
- **THEN** its menu shows Report a bug with its bug icon and name, and the rail itself has no
  bug icon

### Requirement: The Report a bug page shows the report, its link and Copy text

The page `/report` SHALL load `GET
/api/bug-report?browser=<line>` with its browser line, and show the warning, the whole
report, **Open a new issue on GitHub ↗** (the report's link, opened in a new tab) and
**Copy text** (copies the report; "Report copied").

#### Scenario: From a session's page
- **WHEN** the human is on a session's page and chooses Report a bug in the rail's Help menu
- **THEN** the Report a bug page shows the report with a `- Browser:` line, and Open a new issue on GitHub links to `https://github.com/ladohq/lado/issues/new?…`
