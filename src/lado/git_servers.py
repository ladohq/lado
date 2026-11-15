"""The human's git servers (openspec capability `git-servers`): a GitLab or GitHub Enterprise
server, its kind told by its API, and the token agents and LADO's own git reach it with.

A server is identified by its host and port (`Address.key`), one per host. It is saved in
lado.db (lado.state: `git_servers`) only after its probe: each kind of lado.git_kinds is
asked at once, through lado.model_servers' request path (no redirect followed, each request
cut at its TIMEOUT); `--kind` saves one that cannot be checked. Its token is kept in
`<LADO_HOME>/git-servers/<id>/token` alone, written and removed by the link-refusing writer
of LADO's secrets (lado.project_secrets), never in lado.db, a message or a git config file.

`variables` gives git, through `GIT_CONFIG_*` variables laid over a process's environment, an
empty helper then LADO's own (lado.git_credential) for each saved server's address, and
rewrites the server's ssh addresses to it; an agent gets them at its launch
(lado.runtime), LADO's own network git at each call (lado.agent_env.for_git). git reads
`GIT_CONFIG_COUNT` from 2.31 on: `check_git` refuses an older one where a server is needed.
"""

from __future__ import annotations

import contextlib
import os
import shlex
import subprocess
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from lado import agent_env, git_kinds, interpreter, model_servers, project_secrets, state
from lado import text as visible
from lado.git_kinds import Kind

TOKENS = "git-servers"  # under LADO_HOME: a folder per server, by its id
TOKEN = "token"  # the token's file in a server's folder
KIND_NAMES = tuple(kind.name for kind in git_kinds.KINDS)
GITHUB_COM = frozenset({"github.com", "www.github.com", "api.github.com"})
HELPER = "lado.git_credential"
ADD = "lado git-server add"
REMOVE = "lado git-server remove"
RESTART = "Agents started from now on reach it; restart running agents to give it to them."
PLAIN_HTTP = (
    "the token goes to {host} over plain http://, unencrypted; use https:// if the server has it"
)


class Refused(Exception):
    """Why a git server is not saved, found or reached, one line; `hint` what the human can
    try ("" for none). Never holds a token."""

    def __init__(self, text: str, hint: str = ""):
        super().__init__(text)
        self.hint = hint


class Address(NamedTuple):
    """A server's address: `root` its https:// or http:// URL without a trailing `/`, `key`
    its host and a port other than the scheme's (the server's identity), `host` alone."""

    root: str
    key: str
    host: str
    scheme: str


def address(text: str) -> Address:
    """The address of a server from what the human typed, `https://` when it has no scheme;
    ValueError for one LADO does not take. The text of an error never holds the address: it
    may hold a password."""
    text = text.strip()
    if not text:
        raise ValueError("no address given")
    if "://" not in text and "@" not in text.split("/", 1)[0]:
        text = "https://" + text
    try:
        parts = urllib.parse.urlsplit(text)
        host = parts.hostname
        port = parts.port
    except ValueError:
        raise ValueError(
            "not an address of a server (https://host[:port][/path]), or its port is not a "
            "number from 0 to 65535"
        ) from None
    scheme = parts.scheme.lower()
    if scheme not in ("https", "http"):
        raise ValueError("a git server's address starts with https:// or http://")
    if "@" in parts.netloc:
        raise ValueError("a git server's address holds no user or password; its token: --token")
    if parts.query:
        raise ValueError("a git server's address holds no query")
    if parts.fragment:
        raise ValueError("a git server's address holds no fragment")
    if not host:
        raise ValueError("the address names no host")
    shown = f"[{host}]" if ":" in host else host
    if port is not None and port != (443 if scheme == "https" else 80):
        shown += f":{port}"
    path = parts.path.rstrip("/")
    return Address(f"{scheme}://{shown}{path}", shown, host, scheme)


def plain_http_warning(at: Address) -> str | None:
    return PLAIN_HTTP.format(host=at.host) if at.scheme == "http" else None


def check_not_github(at: Address) -> None:
    """Refuse github.com: it is reached through gh's login, as in LADO's image."""
    if at.host in GITHUB_COM:
        raise Refused(
            "github.com is reached through gh's login (GH_TOKEN or gh auth login); "
            "LADO keeps no token for it"
        )


def check_token(token: str) -> None:
    """Refuse an empty token, one no HTTP header can carry (nor git's credential protocol,
    one line), and one larger than its file may hold."""
    if not token:
        raise Refused("the token is empty")
    if not model_servers.carriable(token):
        raise Refused("the token holds a character no HTTP header can carry")
    if len(project_secrets.stored(token)) > agent_env.MAX_VALUE:
        raise Refused("the token is larger than 64 KiB")


@dataclass(frozen=True)
class Checked:
    """What the probe found: the kind, the user the token signs in as (None: not checked),
    and why it could not be checked ("" when it was)."""

    kind: Kind
    login: str | None
    unchecked: str = ""

    def line(self) -> str | None:
        """`GitLab, signed in as <login>`; None for a server not checked."""
        return f"{self.kind.title}, signed in as {self.login}" if self.login else None


def _kind_hint(root: str) -> str:
    return (
        "if the server is there for git but its API is not reachable from here, save it "
        f"unchecked: {ADD} {root} --token --kind {'|'.join(KIND_NAMES)}"
    )


def _silent(answer: model_servers.Answer) -> str:
    """Why a request got no HTTP answer, in the human's words."""
    why = answer.why
    if answer.tls:
        if "certificate" in why:
            return f"its certificate is not trusted on this machine ({why})"
        return f"TLS failed ({why})"
    if why == "unknown host":
        return "the name is not found"
    if why == "connection refused":
        return "the connection is refused"
    if why.startswith("no answer in "):
        return "it did not answer in " + why.removeprefix("no answer in ")
    return why


def probe(at: Address, token: str, kind_name: str | None = None) -> Checked:
    """The kind of the server at `at` and the user `token` signs in as, every kind asked at
    once; with `kind_name`, that kind for a server no kind recognises (Checked.unchecked says
    why). Refused for a server that refuses the token, sends elsewhere, answers as two kinds
    without `kind_name` or as another, or cannot be checked without `kind_name`."""
    opener = urllib.request.build_opener(model_servers.NoRedirect())
    asked = []
    for kind in git_kinds.KINDS:
        url, headers = kind.request(at.root, token)
        asked.append((url, "GET", headers))
    answers = model_servers.ask_all(opener, asked, {"User-Agent": "lado"})
    by_kind = list(zip(git_kinds.KINDS, answers, strict=True))
    found = [(kind, login) for kind, answer in by_kind if (login := kind.login(answer))]
    chosen = git_kinds.by_name(kind_name) if kind_name else None
    if len(found) == 1:
        kind, login = found[0]
        if chosen is not None and chosen is not kind:
            raise Refused(f"{at.root} answers as {kind.title}, not {chosen.title}")
        return Checked(kind, login)
    if found:
        if chosen is not None:
            return Checked(chosen, dict(found)[chosen])
        titles = " and as ".join(kind.title for kind, _ in found)
        which = " or ".join(f"--kind {kind.name}" for kind, _ in found)
        raise Refused(f"{at.root} answers as {titles}; say which: {which}")
    refusals = [(kind, why) for kind, answer in by_kind if (why := kind.refusal(answer))]
    if refusals:
        kind, why = next(((k, w) for k, w in refusals if k is chosen), refusals[0])
        page = kind.token_page(at.root)
        raise Refused(f"{kind.title} at {at.root} {why}", f"make a token at {page} ({kind.scopes})")
    moved = next((answer.location for answer in answers if answer.location), "")
    if moved:
        unchecked = f"it sends to {moved}"
        refusal = Refused(f"{at.root} sends to {moved}; give the server's own address")
    elif all(answer.status is None for answer in answers):
        unchecked = f"it does not answer: {_silent(answers[0])}"
        refusal = Refused(f"{at.key} does not answer: {_silent(answers[0])}", _kind_hint(at.root))
    else:
        titles = " nor ".join(kind.title for kind in git_kinds.KINDS)
        unchecked = f"it answers as neither {titles}"
        refusal = Refused(f"{at.root} answers as neither {titles}", _kind_hint(at.root))
    if chosen is None:
        raise refusal
    return Checked(chosen, None, unchecked)
