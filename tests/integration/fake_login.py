"""The login command of the fake providers "fake-window" and "fake-login" (fake_provider.py),
as an agent CLI's login without a browser goes: it prints a link, waits for a code on one
line, then writes the file FAKE_AGENT_LOGIN names (the fake CLI's login) with it and ends.
With `--logout` it removes that file and ends.

With `--code` it signs in as Codex's device code does (fake-login's sign-in code): it
prints a link and a code in Codex's words and waits until the code is "entered on the
site", which a test does by writing it into FAKE_AGENT_LOGIN + ".entered"; then it writes
the login file and ends with 0, or, for another code, says why and ends with 1.
FAKE_AGENT_LOGIN_END changes that: "fail" ends at once with an error, "other" prints text
LADO does not know and waits for a line."""

import os
import sys
import time
from pathlib import Path

CODE = "FAKE-C0DE7"
LINK = "https://login.example.invalid/device"

if sys.argv[1:] == ["--logout"]:
    Path(os.environ["FAKE_AGENT_LOGIN"]).unlink(missing_ok=True)
    print("Logged out", flush=True)
    sys.exit(0)
if sys.argv[1:] == ["--code"]:
    end = os.environ.get("FAKE_AGENT_LOGIN_END", "")
    if end == "other":
        print("Sign in somewhere else, somehow", flush=True)
        sys.stdin.readline()
        sys.exit(1)
    print(
        "Follow these steps to sign in to the fake agent:\n\n"
        "1. Open this link in your browser and sign in to your account\n"
        f"   {LINK}\n\n"
        "2. Enter this one-time code (expires in 15 minutes)\n"
        f"   {CODE}\n\n"
        "Continue only if you started this login in Codex. If a website or another person "
        "gave you this code, cancel.\n",
        flush=True,
    )
    if end == "fail":
        print("Error: device code login is not enabled for this fake server.", flush=True)
        sys.exit(1)
    login = Path(os.environ["FAKE_AGENT_LOGIN"])
    entered = login.with_name(login.name + ".entered")
    # Its content, not only the file: the test's write may not have ended yet.
    while not (code := entered.read_text().strip() if entered.exists() else ""):
        time.sleep(0.1)
    entered.unlink()
    if code != CODE:
        print(f"Error: the code {code} is not the one given", flush=True)
        sys.exit(1)
    login.write_text(code)
    print("Successfully logged in", flush=True)
    sys.exit(0)
print("If the browser didn't open, visit: https://login.example.invalid/oauth?state=fake")
print("Paste code here if prompted > ", end="", flush=True)
code = sys.stdin.readline().strip()
if not code:
    print("No code given", flush=True)
    sys.exit(1)
Path(os.environ["FAKE_AGENT_LOGIN"]).write_text(code)
print("Logged in", flush=True)
