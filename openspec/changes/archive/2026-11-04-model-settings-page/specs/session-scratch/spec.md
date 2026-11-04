## MODIFIED Requirements

### Requirement: From scratch shows the name, the folder and the author

From scratch SHALL show **Name** (a text field) with the note `folder and session:
<name>` and, with a title, ` · title: <title>`, or the name's refusal; **Create in**, the
default folder until the human edits it, with its state (`✓ a new folder`, `✓ an empty
folder`, or the refusal); the author's refusal with its hint and Copy; then Kits,
Agent CLI, Permission mode, the first message and Advanced as for a folder, and no separate
session Name field.

#### Scenario: The first window
- **WHEN** a human with no sessions opens New session
- **THEN** From scratch is chosen, and typing `Сайт кофейни` shows `folder and session:
  sait-kofeini · title: Сайт кофейни` and `✓ a new folder`
