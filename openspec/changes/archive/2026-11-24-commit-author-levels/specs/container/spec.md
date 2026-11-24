## MODIFIED Requirements

### Requirement: A container without the git identity warns in its log

When `user.name` or `user.email` is still missing from git's config after the entrypoint wrote the identity, `docker logs` SHALL get
one line: `lado: warning: git has no user.name or user.email; set LADO_GIT_NAME and
LADO_GIT_EMAIL, or the commit author in Settings → Git servers`.

#### Scenario: No identity
- **WHEN** the container runs without either variable on a fresh home volume
- **THEN** `docker logs` has the warning line, and the server starts

## ADDED Requirements

### Requirement: A clean container starts a project with LADO's author alone

In LADO's container without `LADO_GIT_NAME` and `LADO_GIT_EMAIL`, a commit author set
through LADO's API SHALL let LADO make a repository from scratch, with git's global config
left without `user.name`.

#### Scenario: No terminal needed
- **WHEN** the container runs without either variable, LADO's author `Ann Lee
  <ann@example.com>` is set through `PUT /api/git-author`, a project is made and a repository
  `site` is made in it from scratch through `POST /api/projects/{id}/repos`
- **THEN** the repository's first commit carries `Ann Lee <ann@example.com>`, and `git
  config --global user.name` in the container prints nothing
