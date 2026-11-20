## MODIFIED Requirements

### Requirement: One git server per host

A server SHALL be identified by its host and port: a second `add` of the same host and
port SHALL replace the saved server's address, kind, login and token once its check
passes, saying `Replaced`, and keep the server's id. A server whose host name is already
held by a saved server on another port SHALL be refused before any request is sent,
naming that server, because git's ssh addresses of a host name carry no port; the command
and the Settings page SHALL apply this rule alike.

#### Scenario: A new token for a saved server
- **WHEN** `https://gitlab.corp.ru` is saved and the human adds `gitlab.corp.ru` with a
  new token that the server accepts
- **THEN** the list still has one server for that host, holding the new token, and the
  output says `Replaced git server https://gitlab.corp.ru.`

#### Scenario: The same host name on another port
- **WHEN** `https://git.corp.example` is saved and the human runs `lado git-server add
  git.corp.example:8443 --token`
- **THEN** it is refused with exit 1 before a token is asked, saying that
  `git.corp.example` already has the git server `https://git.corp.example`, with the hint
  `remove it first: lado git-server remove https://git.corp.example`, and nothing is saved

#### Scenario: Plain http on another port of a saved host name
- **WHEN** `https://git.corp.example` is saved and the human adds `http://git.corp.example:8080`
- **THEN** it is refused the same way and no request reaches the server

### Requirement: lado git-server remove removes a server and its token

`lado git-server remove <address>` SHALL find the server by the host and port of the
address, remove it from `lado.db` and remove its token file and folder, and
`<LADO_HOME>/git-servers/` itself once no server is left; an address that is no saved
server's SHALL be refused with exit 1.

#### Scenario: Removing a server
- **WHEN** the human runs `lado git-server remove gitlab.corp.ru`
- **THEN** the server is no longer listed and `<LADO_HOME>/git-servers/<id>/` is gone

#### Scenario: Removing the last server
- **WHEN** `https://gitlab.corp.ru` is the only saved server and the human removes it
- **THEN** `<LADO_HOME>/git-servers/` is gone too

#### Scenario: Removing one of two servers
- **WHEN** two servers are saved and the human removes one
- **THEN** `<LADO_HOME>/git-servers/` stays with the other server's folder
