## MODIFIED Requirements

### Requirement: The New session window starts Where in the workspace

The server SHALL answer `GET /api/repos-folder` with `{path, made}`: the workspace and
whether it exists as a folder. The New session window's **Where** placeholder SHALL be
`<path>/…`, **Clone into**'s `<path>/<repo>` and **Create in**'s `<path>/<name>`. With
`made`, Where, while empty, SHALL suggest that folder's subfolders when it has the focus,
and picking one SHALL put its full path (`<folder>/<name>`) in the field. Without `made`
the window SHALL suggest nothing for an empty field.

#### Scenario: A first session in the container
- **WHEN** `LADO_REPOS=/Users/me/repos` holds `app`, `api` and `site`, and the human opens
  New session and clicks into Where
- **THEN** the list shows `api/`, `app/`, `site/`, and picking `app/` puts
  `/Users/me/repos/app` into Where, which is checked as any folder

#### Scenario: Without the variable
- **WHEN** the server runs without `LADO_REPOS`, the home folder is `/Users/ann` and
  `/Users/ann/workspace` does not exist
- **THEN** `GET /api/repos-folder` gives `{"path": "/Users/ann/workspace", "made": false}`,
  and the window has the placeholder `/Users/ann/workspace/…`, no Workspace row, and
  suggests nothing for an empty field

#### Scenario: The default workspace made
- **WHEN** `/Users/ann/workspace` holds `app` and the human clicks into an empty Where
- **THEN** the list shows `app/`, and the Workspace row shows `/Users/ann/workspace`

#### Scenario: The focus before the server's answer
- **WHEN** `LADO_REPOS=/Users/me/repos` holds `app` and `api`, and the human clicks into
  Where before `GET /api/repos-folder` has answered
- **THEN** the list shows `api/` and `app/` as soon as the answer comes, while Where keeps
  the focus; a Where left before the answer shows no list
