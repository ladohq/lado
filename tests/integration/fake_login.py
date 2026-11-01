"""The login command of the fake providers "fake-window" and "fake-login" (fake_provider.py),
as an agent CLI's login without a browser goes: it prints a link, waits for a code on one
line, then writes the file FAKE_AGENT_LOGIN names (the fake CLI's login) with it and ends.
With `--logout` it removes that file and ends."""

import os
import sys
from pathlib import Path

if sys.argv[1:] == ["--logout"]:
    Path(os.environ["FAKE_AGENT_LOGIN"]).unlink(missing_ok=True)
    print("Logged out", flush=True)
    sys.exit(0)
print("If the browser didn't open, visit: https://login.example.invalid/oauth?state=fake")
print("Paste code here if prompted > ", end="", flush=True)
code = sys.stdin.readline().strip()
if not code:
    print("No code given", flush=True)
    sys.exit(1)
Path(os.environ["FAKE_AGENT_LOGIN"]).write_text(code)
print("Logged in", flush=True)
