## ADDED Requirements

### Requirement: A session's scrolled tabs keep their tab clear when widths change

When a session's tabs scroll behind the fade and the tabs or their bar change width (the page's
font arriving, the window or a panel resized), the row SHALL bring the tab the keyboard reached,
else the tab shown, clear of the fade at each end that has more, and ‹ and › SHALL follow the
row's new ends. Focus given by a press SHALL not by itself scroll the row.

#### Scenario: The font arrives after Tab reached the last tab
- **WHEN** the bar scrolls, Tab has reached Artifacts, and then the page's font arrives and
  the tabs grow wider
- **THEN** the row ends at Artifacts again, › goes and ‹ shows

#### Scenario: The tabs grow while a tab is shown
- **WHEN** the bar scrolls, Flows is shown by a click, and the tabs grow wider
- **THEN** Flows stands clear of the fade at each end that has more
