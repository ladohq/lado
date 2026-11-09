## ADDED Requirements

### Requirement: A default saved says so

Each save of a CLI's default that succeeds from its row on Agent CLIs SHALL show `✓ Saved` in
the done colour beside the field (at the right of the `Default model` line in a row too narrow
for both), in a place the row keeps for it, so nothing moves or narrows; it SHALL stay until the human's next save on the
page, a login sheet opened, ↻ or leaving the page, never on a timer. A refused save SHALL show
no `✓ Saved`.

#### Scenario: A model of the list
- **WHEN** the human picks `Рабочая Qwen` in OpenCode's field and the save succeeds
- **THEN** `✓ Saved` shows beside the field, and neither the field nor the row below it moves

#### Scenario: Every way of saving
- **WHEN** the human picks `Kilo CLI's settings`, uses `Other name…`, presses `Use Kilo CLI's
  settings` under a warning, or picks the value the field already holds
- **THEN** each save that succeeds shows `✓ Saved` in Kilo CLI's row

#### Scenario: A refusal
- **WHEN** the server refuses a pick
- **THEN** the refusal shows under the field, and the row shows no `✓ Saved`

#### Scenario: The next change
- **WHEN** `✓ Saved` shows in OpenCode's row and the human then saves Kilo CLI's default
- **THEN** `✓ Saved` shows in Kilo CLI's row only

#### Scenario: No timer
- **WHEN** `✓ Saved` shows and the human does nothing for a minute
- **THEN** it still shows; opening a login sheet, ↻ or leaving the page removes it

#### Scenario: A screen reader
- **WHEN** a save succeeds
- **THEN** a screen reader hears `Saved` once from the row's status region
