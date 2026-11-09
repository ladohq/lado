## MODIFIED Requirements

### Requirement: Resume session is the head's Resume

Resume session SHALL open the Resume window, as Resume in the head does, and send no request of its
own. While the connection is lost it SHALL be disabled and say "Waiting for connection" in a tooltip.
What the composer held when the session stopped SHALL be there after the resume.

#### Scenario: Resume
- **WHEN** the human presses Resume session, then `Resume <name>` in the window, and the
  session runs
- **THEN** the composer stands in the bar's place

#### Scenario: A draft
- **WHEN** the composer holds text, the session stops and is resumed
- **THEN** the composer holds the same text

#### Scenario: No connection
- **WHEN** the connection is lost
- **THEN** Resume session is disabled and its tooltip reads "Waiting for connection"

### Requirement: The Resume window shows the session's folder whole

The Resume window SHALL show Where fixed: the folder's name, then its whole path as text that
cannot be edited and wraps onto as many lines as it needs, with nothing cut and no sideways
scroll, at any window width. New session's Where SHALL stay a combobox the human can type in.

#### Scenario: A long path on a phone
- **WHEN** the Resume window opens in a window 402 px wide for a session whose folder's path is
  longer than one line
- **THEN** the whole path shows on several lines, and the page has no sideways scroll

#### Scenario: A path with no place to break
- **WHEN** the session's folder has a name longer than the line, with no slash or hyphen in it
- **THEN** the name breaks at the line's end and shows whole

#### Scenario: New session
- **WHEN** the New session window opens
- **THEN** Where is a combobox the human can type a path in
