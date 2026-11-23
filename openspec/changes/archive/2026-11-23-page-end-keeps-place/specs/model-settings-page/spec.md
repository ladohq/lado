## MODIFIED Requirements

### Requirement: Nothing moves under the pointer

No change in the section SHALL scroll the page or move the element the human acts on or
holds the focus on, whatever it changes above or below it: a tick, a rename, × and Undo, a
default picked, a server added, changed or removed, the reload after any of them, and a list's
read ending. The page SHALL keep that element at its place on the screen; no row SHALL leave
the section on a timer.

#### Scenario: A tick adds a card above
- **WHEN** the human ticks an agent CLI under a model in the middle of a server's open list and the model adds a row to Your models below
- **THEN** the tick stays where it was on the screen, to the pixel

#### Scenario: A server added
- **WHEN** the human adds a server, and the page has room to scroll under the form
- **THEN** the new server takes the place of the form, and the form's place on the screen
  does not move

#### Scenario: The very end of the page
- **WHEN** the page is scrolled to its end and a form closes there (Add server, a server's
  Change, the Remove question), so the page would get shorter below what the human acted on
- **THEN** what the human acted on keeps its place on the screen, and blank room as tall as
  what was lost shows under the section

#### Scenario: The blank room goes as the human scrolls
- **WHEN** blank room was left under the section and the human scrolls up
- **THEN** the room shrinks to the part of it still in view, nothing on the screen moves, and
  scrolled back down the page ends at its last block

#### Scenario: Nothing acted on
- **WHEN** the human opens `/settings` and presses nothing on Model servers while Servers and Your models render their rows
- **THEN** the page stays where it is: only what the human acts on is held in place

#### Scenario: A section above grows
- **WHEN** the human opened a source and a server above it grows while its list is read
- **THEN** the list's read ending scrolls nothing to make up for the server above

#### Scenario: The focus out of view
- **WHEN** the focus is on a server's row, the human scrolled up so that the first server shows and that server is below the view, and the servers between them grow
- **THEN** the page scrolls nothing: what shows stays where it is

#### Scenario: Undo runs out while the human is below
- **WHEN** the human pressed × on a model, then works in Servers, and ten seconds pass
- **THEN** nothing under the pointer moves: only the Undo of that row goes
