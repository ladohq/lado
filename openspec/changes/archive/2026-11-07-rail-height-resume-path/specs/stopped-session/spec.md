## ADDED Requirements

### Requirement: The Resume window shows the session's folder whole

The Resume window SHALL show the session's folder under Where as text that cannot be edited and
wraps onto as many lines as it needs, with nothing cut and no sideways scroll, at any window
width. New session's Where SHALL stay an input.

#### Scenario: A long path on a phone
- **WHEN** the Resume window opens in a window 402 px wide for a session whose folder's path is
  longer than one line
- **THEN** the whole path shows on several lines, and the page has no sideways scroll

#### Scenario: A path with no place to break
- **WHEN** the session's folder has a name longer than the line, with no slash or hyphen in it
- **THEN** the name breaks at the line's end and shows whole

#### Scenario: New session
- **WHEN** the New session window opens
- **THEN** Where is an input the human can type in
