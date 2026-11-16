## MODIFIED Requirements

### Requirement: Settings is a page per section beside a list

Settings SHALL show each section on a page of its own at `/settings/<section>`: General
`/settings/general`, Agent CLIs `/settings/agent-clis`, Model servers `/settings/model-servers`,
Git servers `/settings/git-servers` and Statistics `/settings/statistics`, in that order, with
the list of sections beside the page above 600 px. The list, the routes and the pages' headings
SHALL come from one list of sections. `/settings` SHALL open General above 600 px.

#### Scenario: Settings from the rail on a computer
- **WHEN** the human clicks Settings on the rail in a window 1440 px wide
- **THEN** the address is `/settings/general`, the list shows General as the current item and
  the page's heading reads `General`

#### Scenario: Another section
- **WHEN** the human clicks Model servers in the list
- **THEN** the address is `/settings/model-servers`, the page's heading reads `Model servers`, and
  the focus is on that heading

#### Scenario: Git servers
- **WHEN** the human clicks Git servers in the list
- **THEN** the address is `/settings/git-servers` and the page's heading reads `Git servers`
