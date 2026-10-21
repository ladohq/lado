## MODIFIED Requirements

### Requirement: Start is off while a refusal shows under the fields

While a refusal (`field-note bad`) shows under a field of the New session window, in its
New and its Resume mode, the window's start button (Start session, Clone and start,
Create and start, Resume session) SHALL be off; a note that does not keep the session
from starting SHALL NOT be a refusal.

#### Scenario: A folder that is not a repository keeps Start off

- **WHEN** Where names a folder outside any git repository
- **THEN** its refusal shows and Start session is disabled

#### Scenario: The kits list does not load

- **WHEN** `/api/kits` answers with an error while the window has kits chosen
- **THEN** its error shows as a warning, not as a refusal, and Start stays on when the
  rest of the window is ready

#### Scenario: A stopped session's provider cannot run

- **WHEN** the Resume window opens for a stopped session whose provider is not among
  `/api/providers`, or is listed as not installed
- **THEN** the provider's refusal shows under Provider and Resume session is disabled;
  once the human picks an installed provider the refusal is gone and Resume session is
  on
