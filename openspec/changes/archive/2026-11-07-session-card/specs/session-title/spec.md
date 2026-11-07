## MODIFIED Requirements

### Requirement: Where the UI shows a title it shows the name too

Where the UI shows a session's title,
it SHALL also show the name: in the row, first in its grey line (`lado-2 · ran
1 h 12 min`); in the session's details, as `id <name>`; in the cards, after the title. The
head's line SHALL show the title alone. A session without a title SHALL look as it does
without this change, but for the `id <name>` the details show for every session.

#### Scenario: The list and the head
- **WHEN** the session `lado-2` has the title `Rename sessions (LAD-66)`
- **THEN** its row reads `Rename sessions (LAD-66)` over `lado-2 · …`, its head reads
  `Rename sessions (LAD-66)`, its details `id lado-2`, and the browser tab's title names
  `Rename sessions (LAD-66)`
