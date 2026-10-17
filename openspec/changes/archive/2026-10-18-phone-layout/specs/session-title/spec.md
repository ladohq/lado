## MODIFIED Requirements

### Requirement: The human sets the title in place, in the head and in the list

The session's head SHALL have a button **Rename session** (a pencil) after the title,
shown on the title's hover and the button's focus and always on a device without hover;
it and a double click on the title SHALL turn the title into a text field holding the
title (empty without one, the name as its placeholder). The list row's ⋯ menu SHALL hold
**Rename…** first, which turns the row's title into the same field. In the field, Enter
and leaving it SHALL save through `PUT /api/sessions/{name}/title`, Esc SHALL cancel and
change nothing, and an empty field SHALL clear the title. A text over `Limits.max_title`
SHALL be shown as too long under the field and not sent; a refusal of the server SHALL
show under the field (`role="alert"`) with the field kept open and the text kept. After a
save or a cancel the focus SHALL go back to the button that opened the field (the pencil,
or the row's ⋯). In the phone layout (capability phone-layout) the head SHALL have no
pencil and its title SHALL open the session's details instead, whose **Rename** SHALL turn
the sheet's title into the same field, the focus going back to Rename.

#### Scenario: Rename in the head
- **WHEN** the human presses the pencil in the head of `lado-2`, types `Review`, and
  presses Enter
- **THEN** the title is saved, the head and the row show `Review`, and the focus is on
  the pencil

#### Scenario: Rename from the row's menu and cancel
- **WHEN** the human chooses Rename… in the ⋯ of the row of `lado-2`, types `x`, and
  presses Esc
- **THEN** nothing is sent, the row shows what it showed before, and the focus is on ⋯

#### Scenario: Too long
- **WHEN** the human types 81 characters into the field
- **THEN** the field says it is too long and Enter sends nothing

