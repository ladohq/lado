## ADDED Requirements

### Requirement: Claude Code's sheet refuses a value that is not a token or key

The sheet's Save SHALL refuse with 400, writing nothing, a value for Claude Code that is not
of its choice's format after spaces and line breaks around it are dropped: a subscription
token is `sk-ant-oat<digits>-` and an API key `sk-ant-api<digits>-`, each followed by
letters, digits, `-` or `_` only. The refusal SHALL say what is expected and where it comes
from, or name the other choice for a value of the other kind, and SHALL quote no part of
the value.

#### Scenario: A string that is no token
- **WHEN** the human saves a value without the `sk-ant-` prefix under "Subscription —
  Claude Pro or Max"
- **THEN** the server answers 400 and writes no secret, and the sheet stays open with "This
  is not a Claude subscription token: a token starts with sk-ant-oat01-. Run claude
  setup-token and paste the whole token it prints."

#### Scenario: An API key under Subscription
- **WHEN** the human saves `sk-ant-api03-…` under "Subscription — Claude Pro or Max"
- **THEN** the sheet says "This is an API key (sk-ant-api03-…), not a subscription token:
  to pay per use with it, choose “Pay per use — API billing”." and nothing is saved

#### Scenario: A token under Pay per use
- **WHEN** the human saves `sk-ant-oat01-…` under "Pay per use — API billing"
- **THEN** the sheet says "This is a subscription token (sk-ant-oat01-…), not an API key: to
  use your subscription, choose “Subscription — Claude Pro or Max”." and nothing is saved

#### Scenario: A string that is no key
- **WHEN** the human saves a value without the `sk-ant-` prefix under "Pay per use — API
  billing"
- **THEN** the sheet says "This is not an Anthropic API key: a key starts with
  sk-ant-api03-. Create one at console.anthropic.com → API keys and paste it whole." and
  nothing is saved

#### Scenario: A token broken by a space
- **WHEN** the human saves `sk-ant-oat01-` followed by characters with a space inside them
- **THEN** the sheet says "This token or key has characters it cannot have (a space or a
  line break?): copy it again as one line." and nothing is saved

#### Scenario: A valid token with a line break around it
- **WHEN** the human saves a subscription token followed by a line break
- **THEN** `<LADO_HOME>/secrets/CLAUDE_CODE_OAUTH_TOKEN` holds the token without the line
  break and the row shows "Logged in · Subscription (token) · LADO's secret"

#### Scenario: A newer version of the prefix
- **WHEN** the human saves `sk-ant-oat02-` followed by letters and digits under
  Subscription
- **THEN** it is saved as a token today is

#### Scenario: Another CLI's login
- **WHEN** the human saves a Codex access token or an OpenAI API key in Codex's sheet
- **THEN** it is checked and saved as before this rule
