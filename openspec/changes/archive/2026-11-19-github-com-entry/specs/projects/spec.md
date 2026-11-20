## ADDED Requirements

### Requirement: A project's GitHub variable is said to be unused

`lado project set <id> <NAME>` SHALL save `GH_TOKEN`,
`GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN`, `GITHUB_ENTERPRISE_TOKEN`, `GH_HOST` or
`GH_CONFIG_DIR` as any variable, and say `<NAME> is not given to agents: github.com and
GitHub Enterprise take their token from Settings → Git servers.`

#### Scenario: A project's GH_TOKEN
- **WHEN** the human runs `printf x | lado project set shop GH_TOKEN --secret`
- **THEN** the secret is saved, the output says `GH_TOKEN is not given to agents: github.com
  and GitHub Enterprise take their token from Settings → Git servers.`, and the exit status
  is 0

