## MODIFIED Requirements

### Requirement: A session's tabs give way in levels

When a session's tabs do not fit their bar, a tool's word at the bar's end SHALL go first; then they
SHALL lose their icons, then their counts, and then a tool with a short form SHALL take it.
When they still do not fit, the bar SHALL scroll sideways with a fade of 56 px at its right end and
a button › of 26 px; once scrolled, the same ‹ SHALL show at its left end, and each SHALL go at
its end of the bar. The level SHALL follow the bar's width without a reload. The tab shown SHALL be
in view.

#### Scenario: A little short
- **WHEN** the tabs with icons and counts are wider than the bar and fit without icons
- **THEN** the tabs show no icons and keep their counts

#### Scenario: Very short
- **WHEN** the tabs without icons and counts are wider than the bar beside the tool's short form
- **THEN** a fade and › show at the right, and › scrolls the tabs until Artifacts is seen, when ›
  goes and ‹ shows

#### Scenario: The word goes first
- **WHEN** the tabs with icons and counts fit the bar beside `Yours | All` but not beside the
  word `Messages`
- **THEN** the word goes and the tabs keep their icons and counts

#### Scenario: A chat of 420 px on Activity
- **WHEN** nothing is stored and the window is 1100, 1120 or 1140 px wide, or the human opened the
  terminals beside a chat of 420 px
- **THEN** the four tabs stand whole without counts, no › shows, and the icon stands for
  `Yours | All`

#### Scenario: A tab with no short form
- **WHEN** the tabs without counts do not fit beside Find on Flows
- **THEN** Find stays as it is and the bar scrolls

## ADDED Requirements

### Requirement: A focused tab stands clear of the bar's ends

When the bar scrolls, a tab that gets the focus, and the tab shown, SHALL stand whole and clear of
the 56 px at each end that has more, as far as the row can scroll. The row SHALL move by its own
scroll, so that the next Tab goes on from the focused tab.

#### Scenario: Tab to a tab under the button
- **WHEN** the bar scrolls, Artifacts lies partly under › and the human moves the focus to it by Tab
- **THEN** the row scrolls until Artifacts is whole, › goes and ‹ shows

#### Scenario: Back with Shift+Tab
- **WHEN** the row is scrolled to its end and the human moves the focus to the first tab by Shift+Tab
- **THEN** the first tab stands whole and ‹ goes
