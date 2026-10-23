"""A kit's MCP server for the smoke (test_smoke.py): it writes what it sees of the project's
variable and secret to the file PROBE_OUT names, as JSON, and exits without serving
anything. The CLI takes it for a failed server and goes on: no model is needed.

`template` is PROBE_VALUE, filled by lado.mcp_exec from the kit's `${SMOKE_PROBE_VALUE}`;
`inherited` is SMOKE_PROBE_VALUE as the server's own environment has it from the agent;
`secret` is PROBE_SECRET, filled from the kit's `${SMOKE_PROBE_TOKEN}`, the project's
secret."""

import json
import os
from pathlib import Path

Path(os.environ["PROBE_OUT"]).write_text(
    json.dumps(
        {
            "template": os.environ.get("PROBE_VALUE"),
            "inherited": os.environ.get("SMOKE_PROBE_VALUE"),
            "secret": os.environ.get("PROBE_SECRET"),
        }
    )
)
