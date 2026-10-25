## MODIFIED Requirements

### Requirement: A secret's value is typed into a hidden field emptied after use

A secret's value SHALL be typed into a masked text field (`type="text"`, no
autocomplete, drawn as dots by `-webkit-text-security: disc`, copy and cut refused) that
is empty after a save, after Cancel and after the page is left; the Secrets block SHALL
hold no password field (`type="password"`), so that no browser's password manager offers
to save a secret. Replace SHALL open an empty field with the placeholder `New value (the
old one is not shown)`.

#### Scenario: Replace
- **WHEN** the human replaces `GH_TOKEN` with `ghp_2`
- **THEN** agents started after it get `ghp_2`, and the field is closed and empty

#### Scenario: A name held by a plain variable
- **WHEN** `BOARD_URL` is a plain variable and the human adds the secret `BOARD_URL`
- **THEN** `BOARD_URL is a plain variable of shop; remove it first with lado project unset
  shop BOARD_URL` shows

#### Scenario: No password field to save
- **WHEN** the human opens `+ Add secret` or a secret's Replace
- **THEN** the page holds no `input[type=password]`, and the value field is a text field
  with `autocomplete="off"` whose computed `-webkit-text-security` is `disc`

#### Scenario: Copy takes nothing out
- **WHEN** the human types a value into the field, selects it and copies or cuts it
- **THEN** the clipboard does not get the value and the field keeps it
