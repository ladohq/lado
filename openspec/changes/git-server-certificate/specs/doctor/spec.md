## ADDED Requirements

### Requirement: lado doctor names a git server's certificate

doctor's line of a saved server SHALL be `warn` with the check's line for a certificate not
trusted, changed or one trust cannot fix, with the hint `trust it: lado git-server check
<address>, or Check in Settings → Git servers` (the check's own hint for one trust cannot
fix), never asking to trust; a GitHub server with a certificate SHALL get an `info` line that
`gh` does not get it.

#### Scenario: Not trusted
- **WHEN** `https://gitlab.corp.example`'s certificate is not trusted
- **THEN** doctor prints `[warn] git server https://gitlab.corp.example: the certificate of
  https://gitlab.corp.example is not trusted` with the hint, and saves nothing

#### Scenario: GitHub Enterprise with a certificate
- **WHEN** `https://ghe.corp.example` (GitHub) works with its certificate
- **THEN** doctor prints its `ok` line and `[info] gh: does not get the certificate of
  https://ghe.corp.example: agents' gh cannot reach it; git can`
