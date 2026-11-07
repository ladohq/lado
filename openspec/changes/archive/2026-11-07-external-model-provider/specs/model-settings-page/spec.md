## ADDED Requirements

### Requirement: A request LADO's server did not answer promises nothing

A failed request of Settings → Models that got no answer from LADO's server SHALL read `LADO's server does not answer: your request may or may not have reached it.`, and SHALL NOT say that nothing was done.

#### Scenario: The server stops during a save
- **WHEN** a request of Settings → Models gets no answer from LADO's server
- **THEN** the page shows that line
