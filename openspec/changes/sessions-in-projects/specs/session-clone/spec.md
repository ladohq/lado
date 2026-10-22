## ADDED Requirements

### Requirement: A folder inside LADO's projects/ is no target of a clone

The target folder's check SHALL also give this state, which lets no clone start, checked
before the others:

| State | When | Text |
|---|---|---|
| `in_project` | the folder, by its real path, is inside LADO's `<workspace>/projects` (capability `projects`) | the refusal of a new session there, with its hint |

#### Scenario: A clone into a project's folder
- **WHEN** the target is `<ws>/projects/shop/web` and `shop` is a project
- **THEN** the state is `in_project`, the text names the project, the hint offers `lado
  start --project shop --repo web`, and no clone starts
