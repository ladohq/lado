"""glab in LADO's image (openspec capability container): at the Dockerfile's pin, its layer
at most 60 MB, and an agent's glab signed in to a saved GitLab (a GitLab API inside the
container under a test authority) by LADO's configuration alone: logged in, trusting the
server's certificate for that server, another host of the same authority refused, the
human's glab configuration and ~/.gitconfig as they were."""

import json
import re
import shlex

import certificates as made
import pytest
from container_helpers import IMAGE, PYTHON, ROOT, docker
from test_toolchains import CLEAN

pytestmark = pytest.mark.container

LIMIT = 60 * 1000 * 1000  # bytes the glab layer may add to the image
TOKEN = "glpat-CANARY-container-7d21"
WORK = "/tmp/glabtest"
LISTED, OTHER = 8711, 8712  # the GitLab APIs on the container's own loopback

# A GitLab user API over https: the user for the token in PRIVATE-TOKEN, else GitLab's 401;
# each request's path and whether it carried the token kept in <log>.
API = r"""
import json, ssl, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

port, chain, key, token, log = sys.argv[1:]

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        carried = self.headers.get("PRIVATE-TOKEN")
        with open(log, "a") as out:
            out.write(json.dumps([self.path, carried == token, carried is not None]) + "\n")
        if carried != token:
            status, body = 401, {"message": "401 Unauthorized"}
        elif self.path.split("?")[0] == "/api/v4/user":
            status, body = 200, {"id": 7, "username": "ivan.petrov", "name": "Ivan Petrov"}
        else:
            status, body = 404, {"message": "404 Not Found"}
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(("127.0.0.1", int(port)), Handler)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(chain, key)
server.socket = context.wrap_socket(server.socket, server_side=True)
server.serve_forever()
"""

# LADO saves the GitLab and writes an agent's glab configuration, as a launch does.
SAVE = f"""
import json, os
os.environ["LADO_HOME"] = "{WORK}/home"
from pathlib import Path
from lado import git_kinds, git_servers, state
pem = Path("{WORK}/ca.pem").read_text()
checked = git_servers.Checked(git_kinds.by_name("gitlab"), "ivan.petrov")
git_servers.save(git_servers.address("https://localhost:{LISTED}"), checked, "{TOKEN}", pem)
print(json.dumps(git_servers.glab_variables(state.git_servers(), Path("{WORK}/agent-glab"))))
"""


def pin() -> str:
    dockerfile = (ROOT / "docker" / "Dockerfile").read_text()
    return re.search(r"^ARG GLAB_VERSION=(\S+)$", dockerfile, re.M)[1]


def layer_size() -> int:
    """The bytes of the image's glab layer, by `docker history`."""
    history = docker(
        "history", "--no-trunc", "--human=false", "--format", "{{.Size}}\t{{.CreatedBy}}", IMAGE
    ).stdout
    sizes = [int(line.split("\t")[0]) for line in history.splitlines() if "glab_${GLAB" in line]
    assert len(sizes) == 1, history
    return sizes[0]


def test_glab_is_the_pins_and_its_layer_at_most_60_mb(container):
    login = container.exec(*CLEAN, "bash", "-lc", "glab --version").stdout
    assert login.split()[:2] == ["glab", pin()], login
    assert container.exec("stat", "-c", "%U", "/opt/tools/bin/glab").stdout.strip() == "lado"
    assert 0 < layer_size() <= LIMIT


def test_an_agents_glab_is_signed_in_to_the_saved_gitlab_alone(container, tmp_path):
    root = made.authority("LADO Test CA", "LADO Tests")
    for name, host in (("listed", "localhost"), ("other", "127.0.0.1")):
        chain, key = made.write_chain(tmp_path / name, made.server(host, root), root)
        container.write(f"{WORK}/{name}.pem", chain.read_text())
        container.write(f"{WORK}/{name}.key", key.read_text())
    container.write(f"{WORK}/ca.pem", made.write_pem(tmp_path / "ca.pem", root).read_text())
    container.write(f"{WORK}/api.py", API)
    for name, port in (("listed", LISTED), ("other", OTHER)):
        docker(
            "exec", "-d", container.name, PYTHON, "-I", f"{WORK}/api.py", str(port),
            f"{WORK}/{name}.pem", f"{WORK}/{name}.key", TOKEN, f"{WORK}/{name}.log",
        )  # fmt: skip
    snapshot = "{ ls -la ~/.config/glab-cli 2>&1; git config --global --list --show-origin 2>&1; }"
    before = container.exec(*CLEAN, "bash", "-lc", snapshot, check=False).stdout
    variables = json.loads(container.python(SAVE))
    folder = variables["GLAB_CONFIG_DIR"]
    assert TOKEN not in container.exec("cat", f"{folder}/config.yml").stdout
    env = [f"GLAB_CONFIG_DIR={folder}"]
    repo = f"{WORK}/repo"
    script = (
        f"git init -q {repo} && cd {repo} "
        f"&& git remote add origin https://localhost:{LISTED}/team/app.git "
        "&& for i in 1 2 3 4 5 6 7 8 9 10; do "
        f"python3 -c 'import socket; socket.create_connection((\"127.0.0.1\", {LISTED}), 1)' "
        "2>/dev/null && break; sleep 0.5; done"
    )
    container.exec(*CLEAN, *env, "bash", "-lc", script)

    def glab(*args: str):
        command = f"cd {repo} && glab {shlex.join(args)}"
        return container.exec(*CLEAN, *env, "bash", "-lc", command, check=False, timeout=60)

    status = glab("auth", "status")
    said = status.stdout + status.stderr
    assert status.returncode == 0, said
    assert f"Logged in to localhost:{LISTED} as ivan.petrov" in said
    user = glab("api", "user")
    assert user.returncode == 0 and '"ivan.petrov"' in user.stdout, user.stdout + user.stderr
    other = glab("api", "--hostname", f"127.0.0.1:{OTHER}", "user")
    assert other.returncode != 0

    listed_log = container.exec("cat", f"{WORK}/listed.log").stdout.splitlines()
    assert listed_log and all(json.loads(line)[1] for line in listed_log)
    other_log = container.exec("cat", f"{WORK}/other.log", check=False).stdout.splitlines()
    assert not any(json.loads(line)[2] for line in other_log)  # no token went there
    after = container.exec(*CLEAN, "bash", "-lc", snapshot, check=False).stdout
    assert after == before
