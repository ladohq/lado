## MODIFIED Requirements

### Requirement: A secret's value is typed into a hidden field emptied after use

A secret's value SHALL be typed into a text field drawn as dots by a font of dots (no
autocomplete, autocorrect, autocapitalize or spellcheck, copy and cut refused) that is
empty after a save, after Cancel and after the page is left; the Secrets block SHALL hold
no password field and no field styled as one, so that no browser offers to save a secret.
Replace SHALL open an empty field with the placeholder `New value (the old one is not
shown)`.

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
  with `autocomplete="off"` whose computed `-webkit-text-security` is `none` and whose
  font is the font of dots

#### Scenario: Every character is a dot
- **WHEN** the human types `sk_live Пароль 秘密 🔑` into the field
- **THEN** the field shows only dots, one per character and all of one size (the space
  too), and no letter

#### Scenario: The placeholder is in letters
- **WHEN** the human opens `+ Add secret` or a secret's Replace and has typed nothing
- **THEN** the placeholder (`value (not shown after saving)`, `New value (the old one is
  not shown)`) shows in the UI's font, not as dots

#### Scenario: Copy takes nothing out
- **WHEN** the human types a value into the field, selects it and copies or cuts it
- **THEN** the clipboard does not get the value and the field keeps it
