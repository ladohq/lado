"""Check that the region of LADO's telemetry endpoint accepts its project token.

PostHog's `/batch/` takes any token and drops the events of a project its region does not
know, so a token of another region's project fails silently. This asks the endpoint's own
host about `telemetry.PROJECT_TOKEN` through `/flags/?v=2`, which answers 401 to a token
it does not know and stores no event. The Release workflow runs it before it builds and
publishes; run it locally the same way: `uv run python scripts/check_telemetry.py`.
Exit 0 when the host accepts the token, 1 with one line saying why otherwise.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from lado import telemetry

TIMEOUT = 10  # seconds
DISTINCT_ID = "lado-release-check"
CANNOT = "telemetry: cannot check the project token: "


def check(endpoint: str, token: str, timeout: float = TIMEOUT) -> tuple[bool, str]:
    """Whether `endpoint`'s host accepts `token`, and the line that says so."""
    if not token:
        return False, CANNOT + "the token is empty"
    parts = urllib.parse.urlsplit(endpoint)
    host = parts.hostname or endpoint
    url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, "/flags/", "v=2", ""))
    body = json.dumps({"api_key": token, "distinct_id": DISTINCT_ID}).encode()
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
    except urllib.error.HTTPError as e:
        status = e.code
    except (OSError, ValueError) as e:  # URLError, a timeout, a bad URL
        return False, CANNOT + str(getattr(e, "reason", None) or e)
    if 200 <= status < 300:
        return True, f"telemetry: {host} accepts the project token"
    if status in (401, 403):
        return False, (
            f"telemetry: {host} refuses the project token: "
            "it is not a token of a project in this region"
        )
    return False, CANNOT + f"{host} answered HTTP {status}"


def main() -> int:
    ok, line = check(telemetry.ENDPOINT, telemetry.PROJECT_TOKEN)
    print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
