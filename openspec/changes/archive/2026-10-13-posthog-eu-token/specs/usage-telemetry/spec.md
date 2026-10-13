## ADDED Requirements

### Requirement: The project token belongs to the endpoint's region

LADO's built-in PostHog project token (`telemetry.PROJECT_TOKEN`) SHALL be a token of a
project in the region of its built-in endpoint (`telemetry.ENDPOINT`), and a release SHALL
NOT be published while that endpoint's host does not accept the token. The Release
workflow SHALL run `scripts/check_telemetry.py` before it builds and publishes; the script
SHALL ask the endpoint's own host about the token with one request that stores no event,
exit 0 only on a 2xx answer, and otherwise exit 1 with one line saying whether the host
refused the token (401 or 403) or the check could not be made.

#### Scenario: A token of another region
- **WHEN** a tag `vX.Y.Z` is pushed and `eu.i.posthog.com` answers 401 to the project token
- **THEN** the Release workflow fails at the check with `telemetry: eu.i.posthog.com
  refuses the project token: it is not a token of a project in this region`, and nothing
  is built or published

#### Scenario: The region knows the token
- **WHEN** the endpoint's host answers 200 to the project token
- **THEN** the script prints `telemetry: eu.i.posthog.com accepts the project token`,
  exits 0, and the release goes on to build and publish

#### Scenario: PostHog cannot be reached
- **WHEN** the endpoint's host does not answer within 10 seconds
- **THEN** the script prints `telemetry: cannot check the project token: <reason>` and
  exits 1, and nothing is published until a rerun passes
