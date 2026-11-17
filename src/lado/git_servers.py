"""The human's git servers (openspec capability `git-servers`): a GitLab or GitHub Enterprise
server, its kind told by its API, and the token agents and LADO's own git reach it with.

A server is identified by its host and port (`Address.key`), one per host name
(`check_host`: git's ssh addresses carry no port). It is saved in
lado.db (lado.state: `git_servers`) only after its probe: each kind of lado.git_kinds is
asked at once, through lado.model_servers' request path (no redirect followed, each request
cut at its TIMEOUT); `--kind` saves one that cannot be checked. Its token is kept in
`<LADO_HOME>/git-servers/<id>/token` alone, written and removed by the link-refusing writer
of LADO's secrets (lado.project_secrets), never in lado.db, a message or a git config file.
A save, a removal and a check's login write hold one lock of LADO_HOME (`_locked`), never
while a server is asked.

`variables` gives git, through `GIT_CONFIG_*` variables laid over a process's environment, an
empty helper then LADO's own (lado.git_credential) for each saved server's address, and
rewrites the server's ssh addresses to it; an agent gets them at its launch
(lado.runtime), LADO's own network git at each call (lado.agent_env.for_git). git reads
`GIT_CONFIG_COUNT` from 2.31 on: `check_git` refuses an older one where a server is needed.

A server may have a commit author (`set_author`, `clear_author`, checked by `check_author`),
kept in its row. An agent's launch writes it into a file of the agent's own config folder
(`author_files`: only `[user]` name and email) and `variables` adds, after the server's
entries, `includeIf "hasconfig:remote.*.url:…"` entries including it (`author_entries`): git
takes it in a repository with a remote on the server, and nowhere else. The condition exists
from git 2.36 (`check_author_git`); LADO's own git gets no author.
"""

from __future__ import annotations

import contextlib
import errno
import os
import re
import shlex
import subprocess
import time
import urllib.parse
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from lado import agent_env, git_kinds, interpreter, project_secrets, state
from lado.git_kinds import Kind
from lado.git_kinds.base import REFUSES

if TYPE_CHECKING:  # the HTTP client: loaded by `add` alone, never by a launch or a hook
    from lado import model_servers

TOKENS = "git-servers"  # under LADO_HOME: a folder per server, by its id
TOKEN = "token"  # the token's file in a server's folder
KIND_NAMES = tuple(kind.name for kind in git_kinds.KINDS)
GITHUB_COM = frozenset({"github.com", "www.github.com", "api.github.com"})
HELPER = "lado.git_credential"
ADD = "lado git-server add"
REMOVE = "lado git-server remove"
AUTHOR = "lado git-server author"
RESTART = "Agents started from now on reach it; restart running agents to give it to them."
AUTHOR_SET = "Agents commit to {address} as {author}."
AUTHOR_CLEARED = "Agents commit to {address} with your own git author again."
AUTHOR_RESTART = "Agents started from now on commit so; restart running agents to give it to them."
AUTHOR_MAX = 256  # characters of the author's name, and of its email
PLAIN_HTTP = (
    "the token goes to {host} over plain http://, unencrypted; use https:// if the server has it"
)


PAGE_KIND_HINT = "Choose its kind to save it without a check."  # why: the Kind field's ⓘ
# The fields of Settings → Git servers' form a refusal concerns ("" for none).
ADDRESS_FIELD, TOKEN_FIELD, KIND_FIELD = "address", "token", "kind"
NAME_FIELD, EMAIL_FIELD = "name", "email"  # of a server's commit author form


class Refused(Exception):
    """Why a git server is not saved, found or reached, one line; `hint` what the human can
    try ("" for none); `field` the field of the page's form it concerns; `page` and
    `page_hint` the line and the hint for the page, which name no command (None: the same as
    the command's); `choose_kind` for a server that gave no HTTP answer, which the page may
    save without a check once its kind is chosen. Never holds a token."""

    def __init__(
        self,
        text: str,
        hint: str = "",
        field: str = "",
        page: str | None = None,
        page_hint: str | None = None,
        choose_kind: bool = False,
    ):
        super().__init__(text)
        self.hint = hint
        self.field = field
        self.page = text if page is None else page
        self.page_hint = hint if page_hint is None else page_hint
        self.choose_kind = choose_kind


class BadAddress(ValueError):
    """An address LADO does not take; `page` the line for the page."""

    def __init__(self, text: str, page: str | None = None):
        super().__init__(text)
        self.page = text if page is None else page


class Address(NamedTuple):
    """A server's address: `root` its https:// or http:// URL without a trailing `/`, `key`
    its host and a port other than the scheme's (the server's identity), `host` alone."""

    root: str
    key: str
    host: str
    scheme: str


def address(text: str) -> Address:
    """The address of a server from what the human typed, `https://` when it has no scheme;
    BadAddress for one LADO does not take. The text of an error never holds the address: it
    may hold a password."""
    text = text.strip()
    if not text:
        raise BadAddress("no address given")
    if "://" not in text and "@" not in text.split("/", 1)[0]:
        text = "https://" + text
    try:
        parts = urllib.parse.urlsplit(text)
        host = parts.hostname
        port = parts.port
    except ValueError:
        raise BadAddress(
            "not an address of a server (https://host[:port][/path]), or its port is not a "
            "number from 0 to 65535"
        ) from None
    scheme = parts.scheme.lower()
    if scheme not in ("https", "http"):
        raise BadAddress("a git server's address starts with https:// or http://")
    if "@" in parts.netloc:
        no_user = "a git server's address holds no user or password"
        raise BadAddress(f"{no_user}; its token: --token", f"{no_user}; put the token in Token")
    if parts.query:
        raise BadAddress("a git server's address holds no query")
    if parts.fragment:
        raise BadAddress("a git server's address holds no fragment")
    # `host.` names the same host as `host` (the DNS root): one server per host sees one.
    host = (host or "").rstrip(".")
    if not host:
        raise BadAddress("the address names no host")
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
            "LADO keeps no token for it",
            field=ADDRESS_FIELD,
            page="github.com uses the GitHub CLI's login: it is not added here.",
        )


def _host_taken(at: Address, server: state.GitServer) -> Refused:
    host = f"[{at.host}]" if ":" in at.host else at.host
    return Refused(
        f"{host} already has a git server, {server.address}; LADO keeps one server per host "
        f"name, as git's ssh addresses (git@{host}:…) carry no port",
        f"remove it first: {REMOVE} {server.address}",
        ADDRESS_FIELD,
        page_hint="Remove it first if the server moved to this address.",
    )


def check_host(at: Address) -> None:
    """Refuse `at` when a saved server holds its host name on another port: git rewrites
    the host's ssh addresses to one server only (`_entries`)."""
    for server in state.git_servers():
        if server.host != at.key and urllib.parse.urlsplit(server.address).hostname == at.host:
            raise _host_taken(at, server)


def check_token(token: str) -> None:
    """Refuse an empty token, one no HTTP header can carry (nor git's credential protocol,
    one line), and one larger than its file may hold."""
    from lado import model_servers

    if not token:
        raise Refused("the token is empty", field=TOKEN_FIELD)
    if not model_servers.carriable(token):
        raise Refused("the token holds a character no HTTP header can carry", field=TOKEN_FIELD)
    if len(project_secrets.stored(token)) > agent_env.MAX_VALUE:
        raise Refused("the token is larger than 64 KiB", field=TOKEN_FIELD)


@dataclass(frozen=True)
class Checked:
    """What the probe found: the kind, the user the token signs in as (None: not checked),
    why it could not be checked ("" when it was), the rights agents need that the token
    lacks, and whether the server told the token's rights."""

    kind: Kind
    login: str | None
    unchecked: str = ""
    missing_scopes: tuple[str, ...] = ()
    rights_checked: bool = False

    def line(self) -> str | None:
        """`GitLab, signed in as <login>`; None for a server not checked."""
        return f"{self.kind.title}, signed in as {self.login}" if self.login else None

    def lacks(self) -> str | None:
        """`the token lacks <scopes>: agents can …`; None when it lacks none."""
        return lacks(self.kind, self.missing_scopes)

    def replace_hint(self, at: Address) -> str:
        return f"replace it with a token with the {self.kind.scopes}: {ADD} {at.root} --token"


def lacks(kind: Kind, missing: Sequence[str], page: bool = False) -> str | None:
    """What a token lacking the rights `missing` of `kind` leaves agents, in the command's
    words, or the page's (`page`: a sentence); None for none missing."""
    if not missing:
        return None
    can = _can(kind, missing)
    if page:
        return f"The token lacks {', '.join(missing)}: agents can {can}."
    return f"the token lacks {', '.join(missing)}: agents can {can}"


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


AGENT = {"User-Agent": "lado"}


def _opener():
    import urllib.request

    from lado import model_servers

    return urllib.request.build_opener(model_servers.NoRedirect())


def _no_answer_page(answer: model_servers.Answer) -> str:
    """Why a request got no HTTP answer, as the page's sentence."""
    if answer.why.startswith("no answer in "):
        return (
            f"No answer in {answer.why.removeprefix('no answer in ').removesuffix(' s')} seconds."
        )
    return f"No answer: {_silent(answer)}."


def _ask_kinds(at: Address, token: str | None) -> list[model_servers.Answer]:
    """Each kind's answer at `at`, in KINDS' order, all asked at once with `token` (None:
    no credential), following no redirect, each request cut at model_servers' TIMEOUT."""
    from lado import model_servers

    asked = []
    for kind in git_kinds.KINDS:
        url, headers = kind.request(at.root, token)
        asked.append((url, "GET", headers))
    return model_servers.ask_all(_opener(), asked, AGENT)


def _rights(
    at: Address, token: str, kind: Kind, answer: model_servers.Answer
) -> tuple[tuple[str, ...], bool]:
    """The rights `kind`'s token lacks by `answer`, the answer that gave its login, and
    whether the server told its rights: as `_ask_kinds` asks, one request at a time."""
    from lado import model_servers

    def ask(url: str, headers: dict[str, str]) -> model_servers.Answer:
        (found,) = model_servers.ask_all(_opener(), [(url, "GET", headers)], AGENT)
        return found

    told = kind.rights(at.root, token, answer, ask)
    if told is None:
        return (), False
    return kind.missing(told), True


def probe(at: Address, token: str, kind_name: str | None = None) -> Checked:
    """The kind of the server at `at` and the user `token` signs in as, every kind asked at
    once; with `kind_name`, that kind for a server no kind recognises (Checked.unchecked says
    why). Refused for a server that refuses the token, sends elsewhere, answers as two kinds
    without `kind_name` or as another, or cannot be checked without `kind_name`."""
    answers = _ask_kinds(at, token)
    by_kind = list(zip(git_kinds.KINDS, answers, strict=True))
    found = [(kind, login) for kind, answer in by_kind if (login := kind.login(answer))]
    chosen = git_kinds.by_name(kind_name) if kind_name else None

    def checked(kind: Kind, login: str) -> Checked:
        missing, told = _rights(at, token, kind, dict(by_kind)[kind])
        return Checked(kind, login, missing_scopes=missing, rights_checked=told)

    if len(found) == 1:
        kind, login = found[0]
        if chosen is not None and chosen is not kind:
            raise Refused(
                f"{at.root} answers as {kind.title}, not {chosen.title}", field=KIND_FIELD
            )
        return checked(kind, login)
    if found:
        if chosen is not None:
            return checked(chosen, dict(found)[chosen])
        titles = " and as ".join(kind.title for kind, _ in found)
        which = " or ".join(f"--kind {kind.name}" for kind, _ in found)
        raise Refused(
            f"{at.root} answers as {titles}; say which: {which}",
            field=KIND_FIELD,
            page=f"{at.root} answers as {titles}; choose its kind",
        )
    refusals = [(kind, why) for kind, answer in by_kind if (why := kind.refusal(answer))]
    if chosen is None and len(refusals) == len(by_kind) > 1:
        # Every kind refused: a gateway in front of the server, or a token cut short; naming
        # one kind would guess.
        titles = " and ".join(f"{kind.title}'s" for kind in git_kinds.KINDS)
        raise Refused(
            f"{at.root} refuses the token on {titles} API alike",
            "check that the token was copied whole; a sign-in gateway in front of the server "
            "refuses any token too",
            TOKEN_FIELD,
            page=f"The server refused this token on both {titles} API: copy it whole, or ask "
            "whether a sign-in gateway stands in front of it.",
            page_hint="",
        )
    if refusals:
        kind, why = next(((k, w) for k, w in refusals if k is chosen), refusals[0])
        page = kind.token_page(at.root)
        refused = why == REFUSES  # the page's Token field shows the token page beside it
        raise Refused(
            f"{kind.title} at {at.root} {why}",
            f"make a token at {page} ({kind.scopes})",
            TOKEN_FIELD,
            page=f"{kind.title} refused this token: copy it whole or make a new one."
            if refused
            else None,
            page_hint="" if refused else None,
        )
    unchecked, refusal = _unanswered(at, answers)
    if chosen is None:
        raise refusal
    return Checked(chosen, None, unchecked)


@dataclass(frozen=True)
class Hint:
    """What the server at an address looks like without a token: a kind (only a hint: a
    proxy may answer for any path; the probe with the token decides), or none, to be
    chosen (`choose`), with `why` it cannot be told (the warning, its page hint)."""

    kind: Kind | None
    why: Refused | None = None

    @property
    def choose(self) -> bool:
        return self.kind is None


def hint(at: Address) -> Hint:
    """Ask every kind's path of `at` at once with no credential, as the probe does: a kind
    when exactly one answers as that kind (its user, or its refusal of a missing token);
    none when none answers, or as neither or both. Refused for a server that sends
    elsewhere: no kind could save it from the page."""
    answers = _ask_kinds(at, None)
    told = [
        kind
        for kind, answer in zip(git_kinds.KINDS, answers, strict=True)
        if kind.login(answer) or kind.refusal(answer)
    ]
    if len(told) == 1:
        return Hint(told[0])
    if told:
        titles = " and as ".join(kind.title for kind in told)
        why = Refused(f"{at.root} answers as {titles}", field=KIND_FIELD, page_hint=PAGE_KIND_HINT)
        return Hint(None, why)
    _, refused = _unanswered(at, answers)
    if any(answer.location for answer in answers):
        raise refused
    return Hint(None, refused)


def _unanswered(at: Address, answers: Sequence[model_servers.Answer]) -> tuple[str, Refused]:
    """For answers of no kind: why the server could not be checked, as the end of "could
    not be checked (…)", and the refusal for an add that chose no kind."""
    moved = next((answer.location for answer in answers if answer.location), "")
    if moved:
        refused = Refused(
            f"{at.root} sends to {moved}; give the server's own address", field=ADDRESS_FIELD
        )
        return f"it sends to {moved}", refused
    if all(answer.status is None for answer in answers):
        silent = _silent(answers[0])
        refused = Refused(
            f"{at.key} does not answer: {silent}",
            _kind_hint(at.root),
            ADDRESS_FIELD,
            page=_no_answer_page(answers[0]),
            page_hint=PAGE_KIND_HINT,
            choose_kind=True,
        )
        return f"it does not answer: {silent}", refused
    titles = " nor ".join(kind.title for kind in git_kinds.KINDS)
    refused = Refused(
        f"{at.root} answers as neither {titles}",
        _kind_hint(at.root),
        ADDRESS_FIELD,
        page_hint=PAGE_KIND_HINT,
    )
    return f"it answers as neither {titles}", refused


OUTCOMES = (
    "ok",
    "token_refused",
    "scopes_missing",
    "no_answer",
    "cert_untrusted",
    "redirect",
    "other_kind",
    "unrecognised",
)
REACH_HINT = (
    "check that this computer reaches it: the company VPN or proxy; with LADO in Docker, its "
    "container"
)
PAGE_REACH_HINT = (
    "Check that LADO's computer reaches the server: the company VPN or proxy; with LADO in "
    "Docker, its container."
)
CERT_HINT = (
    "ask your IT department to make this computer trust it (with LADO in Docker, its "
    "container), then check again"
)
PAGE_CERT_HINT = (
    "Ask your IT department to make LADO's computer trust it (with LADO in Docker, its "
    "container), then check again."
)


@dataclass(frozen=True)
class Check:
    """What a check of a saved server found: `outcome` one of OUTCOMES, the saved `kind`,
    the `login` it saw (None but for ok and scopes_missing), the rights the token lacks,
    whether the server told them, whether the server had a login before (`was_checked`),
    one line and its hint in the command's words (`text`, `hint`) and in the page's
    (`page`, a sentence, and `page_hint`, its info tip's: "" for none). Never holds a
    token."""

    outcome: str
    kind: Kind
    login: str | None
    missing_scopes: tuple[str, ...]
    rights_checked: bool
    was_checked: bool
    text: str
    hint: str
    page: str
    page_hint: str = ""


def check(at: Address) -> Check:
    """Check the saved server of `at`'s host again with its saved token, as `add` asks it
    (every kind at once, no redirect followed, each request cut at TIMEOUT), judged by its
    saved kind; a passing check saves the login it saw (under the lock), nothing else is
    written. Refused, with no request sent, for no such server, a kind this LADO does not
    know or a token file it cannot read."""
    from lado import git_credential

    server = saved_server(at)
    at = address(server.address)
    kind = git_kinds.by_name(server.kind)
    if kind is None:
        raise Refused(f"{server.address} is saved as {server.kind}, a kind this LADO does not know")
    token = git_credential.read_token(server.id) if has_token(server) else None
    if token is None:
        raise Refused(
            f"the token file of {at.root} is missing",
            f"replace it: {ADD} {at.root} --token",
            TOKEN_FIELD,
            page="Its token file is missing.",
            page_hint="",
        )
    answers = _ask_kinds(at, token)
    by_kind = dict(zip(git_kinds.KINDS, answers, strict=True))
    own = by_kind[kind]
    was = server.login is not None

    if login := kind.login(own):
        missing, told = _rights(at, token, kind, own)
        if missing:
            return Check(
                "scopes_missing",
                kind,
                login,
                missing,
                told,
                was,
                lacks(kind, missing) or "",
                f"replace it with a token with the {kind.scopes}: {ADD} {at.root} --token",
                f"The token lacks {', '.join(missing)}.",
                f"Agents can {_can(kind, missing)} with it. Make one with the {kind.scopes}.",
            )
        _save_login(server, login)
        rights = ", may clone and push." if told else "; the token's rights are not checked."
        page = f"Works: signed in as {login}{rights}"
        if server.login is None:
            page = f"Works: {kind.title}, signed in as {login}."
        return Check(
            "ok",
            kind,
            login,
            (),
            told,
            was,
            f"Works: {kind.title}, signed in as {login}{rights}",
            "",
            page,
        )

    def failed(outcome: str, text: str, hint: str, page: str, page_hint: str = "") -> Check:
        return Check(outcome, kind, None, (), False, was, text, hint, page, page_hint)

    if kind.refusal(own):
        refused = f"{kind.title} refused the token: it expired or was revoked"
        return failed(
            "token_refused", refused, f"replace it: {ADD} {at.root} --token", refused + "."
        )
    moved = next((answer.location for answer in answers if answer.location), "")
    if moved:
        moves = f"redirects to {moved}: add that address instead"
        return failed("redirect", f"it {moves}", "", f"It {moves}.")
    if own.status is None:
        if own.tls and "certificate" in own.why:
            return failed(
                "cert_untrusted",
                f"the certificate of {at.root} is not trusted",
                CERT_HINT,
                "The server's certificate is not trusted.",
                PAGE_CERT_HINT,
            )
        return failed(
            "no_answer",
            f"{at.key} does not answer: {_silent(own)}",
            REACH_HINT,
            _no_answer_page(own),
            PAGE_REACH_HINT,
        )
    other = next((k for k, answer in by_kind.items() if k is not kind and k.login(answer)), None)
    if other is not None:
        answers_as = f"answers as {other.title}, not {kind.title}: remove it and add it again"
        return failed(
            "other_kind",
            f"it {answers_as}",
            f"{REMOVE} {at.root}, then {ADD} {at.root} --token",
            f"It {answers_as}.",
        )
    titles = " nor ".join(k.title for k in git_kinds.KINDS)
    return failed(
        "unrecognised", f"it answers as neither {titles}", "", f"It answers as neither {titles}."
    )


def _can(kind: Kind, missing: Sequence[str]) -> str:
    return "neither clone nor push" if kind.needs[0] in missing else "clone but not push"


def _save_login(server: state.GitServer, login: str) -> None:
    """Write `login` into the row of `server` under the lock, its address, kind and author
    kept; not when the server was removed or replaced by another meanwhile."""
    if login == server.login:
        return
    with _locked():
        now = state.git_server_by_host(server.host)
        if now is not None and now.id == server.id:
            state.save_git_server(now.id, now.address, now.host, now.kind, login)


def helper_command(server: state.GitServer) -> str:
    """git's `credential.<url>.helper` value for LADO's helper of `server`: LADO's own Python
    by its absolute path, so no `lado` on the PATH is needed, with all it needs as
    arguments, so it never opens lado.db; no token, only ids (a `ps` line shows them)."""
    kind = git_kinds.by_name(server.kind)
    user = kind.git_user if kind is not None else "token"  # a kind this LADO does not know
    command = interpreter.run_module(
        HELPER,
        "--home", str(state.home_path().absolute()),
        "--server", server.id,
        "--user", user,
        "--address", server.address,
    )  # fmt: skip
    return "!" + shlex.join(command)


def _entries(server: state.GitServer) -> list[tuple[str, str]]:
    """The git config entries of one server, in order: an empty helper for its origin, which
    drops every helper set before it there (the image's, the human's `store`), so none
    other is asked or stores the token; LADO's helper; its ssh addresses rewritten to its
    root (git's rewrite is a fixed prefix: the standard ssh port alone)."""
    parts = urllib.parse.urlsplit(server.address)
    origin = f"{parts.scheme}://{parts.netloc}"
    host = parts.hostname or ""
    host = f"[{host}]" if ":" in host else host
    rewrite = f"url.{server.address}/.insteadOf"
    return [
        (f"credential.{origin}.helper", ""),
        (f"credential.{origin}.helper", helper_command(server)),
        (rewrite, f"git@{host}:"),
        (rewrite, f"ssh://git@{host}/"),
        (rewrite, f"ssh://git@{host}:22/"),
    ]


def variables(
    env: Mapping[str, str],
    servers: Sequence[state.GitServer],
    authors: Mapping[str, Path] | None = None,
) -> dict[str, str]:
    """The `GIT_CONFIG_*` variables to lay over `env` for `servers`: the entries of `env`'s
    own `GIT_CONFIG_COUNT` are kept, LADO's coming after them (a count that is no number
    counts as none); after a server's own entries, those of its author file in `authors`
    (server id → file, `author_files`; an agent's only). Nothing for no server."""
    if not servers:
        return {}
    try:
        n = max(0, int(env.get("GIT_CONFIG_COUNT", "0")))
    except ValueError:
        n = 0
    found = {}
    for server in servers:
        entries = _entries(server)
        if authors and server.id in authors:
            entries += author_entries(server, authors[server.id])
        for key, value in entries:
            found[f"GIT_CONFIG_KEY_{n}"] = key
            found[f"GIT_CONFIG_VALUE_{n}"] = value
            n += 1
    found["GIT_CONFIG_COUNT"] = str(n)
    # What a process this one starts gets back once LADO's entries are dropped
    # (agent_env.without_launch).
    found[agent_env.GIT_CONFIG_BASE] = env.get("GIT_CONFIG_COUNT", "")
    return found


def server_for(remote: str, servers: Sequence[state.GitServer]) -> state.GitServer | None:
    """The server of `servers` git reaches for `remote` with `variables`: by its host and
    port for an https:// or http:// URL, by its host for an ssh address it rewrites
    (`git@host:`, `ssh://git@host[:22]/`); None for any other remote."""
    try:
        if "://" in remote:
            parts = urllib.parse.urlsplit(remote)
            scheme = parts.scheme.lower()
            if scheme in ("https", "http"):
                key = address(f"{scheme}://{parts.netloc.rsplit('@', 1)[-1]}").key
                return next((s for s in servers if s.host == key), None)
            if scheme != "ssh" or parts.username != "git" or parts.port not in (None, 22):
                return None
            host = parts.hostname
        else:
            found = re.match(r"git@([^:/]+):", remote)
            if found is None:
                return None
            host = found[1].lower()
    except ValueError:
        return None
    return next((s for s in servers if urllib.parse.urlsplit(s.address).hostname == host), None)


def _older_git(env: Mapping[str, str], need: tuple[int, int], what: str) -> str | None:
    """`git <version> is older than <need>, which <what> needs…` for a git on `env`'s PATH
    older than `need`; None for a newer one, or one that does not run (left to the folder
    check and git's own error)."""
    from lado import runtime  # runtime lays the variables: imported when asked

    try:
        result = subprocess.run(
            ["git", "--version"], env=dict(env), capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    line = result.stdout.strip()
    found = runtime.git_numbers(line)
    if result.returncode != 0 or found is None or found >= need:
        return None
    version = line.removeprefix("git version ").split()[0]
    return f"git {version} is older than {'.'.join(map(str, need))}, which {what}; update git"


def check_git(env: Mapping[str, str]) -> None:
    """Refuse a git on `env`'s PATH older than 2.31, which reads no `GIT_CONFIG_COUNT`."""
    from lado import runtime

    older = _older_git(env, runtime.GIT_MIN, "git servers need")
    if older:
        raise Refused(f"{older}, or remove the servers ({REMOVE} <address>)", page=older)


def check_author_git(env: Mapping[str, str], clear: Sequence[str] = ()) -> None:
    """Refuse a git on `env`'s PATH older than 2.36, which skips `includeIf hasconfig:`
    silently (`author_entries`); `clear` the addresses of the servers with an author, for a
    launch: the refusal says how to clear each."""
    from lado import runtime

    older = _older_git(env, runtime.GIT_AUTHOR_MIN, "a commit author of a git server needs")
    if older:
        text = older
        if clear:
            commands = ", ".join(f"{AUTHOR} {address} --clear" for address in clear)
            text += f", or clear the author{'s' if len(clear) > 1 else ''} ({commands})"
        raise Refused(text, page=older)


def author_text(server: state.GitServer) -> str | None:
    """`<name> <<email>>` of the server's commit author; None for none."""
    if server.author_name is None or server.author_email is None:
        return None
    return f"{server.author_name} <{server.author_email}>"


def _control(text: str) -> bool:
    return any(ord(c) < 0x20 or 0x7F <= ord(c) < 0xA0 for c in text)


def check_author(name: str, email: str) -> tuple[str, str]:
    """The commit author's name and email, trimmed; Refused (field `name` or `email`) for a
    name that is empty or holds `<`, `>` or a control character, an email that is not
    `local@domain` (one `@`, text on both sides, no space, `<`, `>` or control character),
    and a value over AUTHOR_MAX characters. git and the server decide the rest."""
    name, email = name.strip(), email.strip()
    if not name:
        raise Refused("the author's name is empty", field=NAME_FIELD)
    if len(name) > AUTHOR_MAX:
        raise Refused(f"the author's name is longer than {AUTHOR_MAX} characters", field=NAME_FIELD)
    if "<" in name or ">" in name or _control(name):
        raise Refused("the author's name holds no < or > or line break", field=NAME_FIELD)
    if len(email) > AUTHOR_MAX:
        raise Refused(
            f"the author's email is longer than {AUTHOR_MAX} characters", field=EMAIL_FIELD
        )
    local, at, domain = email.partition("@")
    if (
        not local
        or not at
        or not domain
        or "@" in domain
        or any(c.isspace() or c in "<>" for c in email)
        or _control(email)
    ):
        raise Refused("not an email address: name@host", field=EMAIL_FIELD)
    return name, email


def saved_server(at: Address) -> state.GitServer:
    """The saved server of `at`'s host; Refused for none."""
    known = state.git_server_by_host(at.key)
    if known is None:
        raise _not_saved(at.root)
    return known


def saved_address(key: str) -> Address:
    """The address of the saved server of the host `key` (`Address.key`), for the page,
    which names a server by its key; Refused for none."""
    known = state.git_server_by_host(key)
    if known is None:
        raise _not_saved(key)
    return address(known.address)


def _not_saved(named: str) -> Refused:
    return Refused(
        f"{named} is no saved git server",
        "see them: lado git-server list",
        ADDRESS_FIELD,
        page_hint="",
    )


def set_author(at: Address, name: str, email: str) -> state.GitServer:
    """Set the commit author of the saved server of `at`'s host, as `lado git-server author`
    does, for the command and the page alike: the server as saved. Refused for no such
    server, a name or email `check_author` refuses, or a git older than 2.36 here."""
    known = saved_server(at)
    name, email = check_author(name, email)
    check_author_git(os.environ)
    saved = state.set_git_server_author(known.id, name, email)
    if saved is None:  # removed meanwhile
        raise _not_saved(at.root)
    return saved


def clear_author(at: Address) -> state.GitServer:
    """Clear the commit author of the saved server of `at`'s host, also when it has none:
    the server as saved. Refused for no such server."""
    saved = state.set_git_server_author(saved_server(at).id, None, None)
    if saved is None:
        raise _not_saved(at.root)
    return saved


def _glob(text: str) -> str:
    """`text` matched literally by git's wildmatch."""
    return re.sub(r"([\\*?\[\]])", r"\\\1", text)


def _any_case(glob: str) -> str:
    """`glob` with each ASCII letter matched in either case (`a` → `[aA]`)."""
    return re.sub(r"[a-z]", lambda m: f"[{m[0]}{m[0].upper()}]", glob)


def author_entries(server: state.GitServer, path: Path) -> list[tuple[str, str]]:
    """The git config entries that include the author file `path` in a repository with a
    remote on `server`, in each form `server_for` takes: its address with or without a
    user, its host in any letter case and, without a port of its own, with the scheme's
    written out, as git's credentials and `url.*` take it; and the ssh addresses `_entries`
    rewrites to it, as written (so is their rewrite). git's `**` is a folder wildcard only
    next to `/`, so the scp form takes `git@host:*` and `git@host:*/**`."""
    parts = urllib.parse.urlsplit(server.address)
    path_part = _glob(parts.path)
    host = parts.hostname or ""
    host = _glob(f"[{host}]" if ":" in host else host)
    netlocs = [_any_case(host) + (f":{parts.port}" if parts.port else "")]
    if parts.port is None:
        netlocs.append(f"{netlocs[0]}:{443 if parts.scheme == 'https' else 80}")
    globs = [
        glob
        for netloc in netlocs
        for glob in (
            f"{parts.scheme}://{netloc}{path_part}/**",
            f"{parts.scheme}://*@{netloc}{path_part}/**",
        )
    ]
    globs += [
        f"git@{host}:*",
        f"git@{host}:*/**",
        f"ssh://git@{host}/**",
        f"ssh://git@{host}:22/**",
    ]
    return [(f"includeIf.hasconfig:remote.*.url:{glob}.path", str(path)) for glob in globs]


def _quoted(value: str) -> str:
    """A value of git's config syntax, in double quotes (check_author refuses line breaks)."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def author_files(folder: Path, servers: Sequence[state.GitServer]) -> dict[str, Path]:
    """Write `<folder>/<id>.gitconfig` for each of `servers` with a commit author, holding
    only its `[user]` name and email, mode 600, each whole by a rename: the files by server
    id, for `variables`' `authors`. Nothing, and no folder, when none has an author."""
    found = {}
    for server in servers:
        if author_text(server) is None:
            continue
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{server.id}.gitconfig"
        text = (
            f"[user]\n\tname = {_quoted(server.author_name or '')}\n"
            f"\temail = {_quoted(server.author_email or '')}\n"
        )
        temp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}")
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                file.write(text)
            os.replace(temp, path)
        finally:  # a failed write leaves no file of its own; why it failed goes on
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temp)
        found[server.id] = path
    return found


def token_folder(id: str) -> Path:
    return state.home_path() / TOKENS / id


def has_token(server: state.GitServer) -> bool:
    return os.path.lexists(token_folder(server.id) / TOKEN)


LOCK = "git-servers.lock"  # under LADO_HOME; it stays, as update.lock does
LOCK_WAIT = 10  # seconds a save or a removal waits for another one
LOCKED = "another change of the git servers is running; try again"


@contextlib.contextmanager
def _locked() -> Iterator[None]:
    """One save, removal or login write of a git server at a time in LADO_HOME, the
    command's and the page's alike: an exclusive flock on LOCK, tried every 50 ms for
    LOCK_WAIT seconds, then Refused. No server is asked while it is held."""
    import fcntl

    with open(state.home() / LOCK, "a+") as lock:
        deadline = time.monotonic() + LOCK_WAIT
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Refused(LOCKED) from None
                time.sleep(0.05)
        yield  # closing the file lets the lock go


def save(at: Address, checked: Checked, token: str) -> tuple[state.GitServer, bool]:
    """Save the server at `at` as `checked` with `token`, or replace the one of its host,
    keeping its id, under the lock: the server as saved, and whether one was replaced. A
    new server's token file comes first and goes again when its row fails; a replaced one's
    row comes first, then its token file is replaced whole, so it holds the old token or the
    new one."""
    with _locked():
        return _save(at, checked, token)


def _save(at: Address, checked: Checked, token: str) -> tuple[state.GitServer, bool]:
    known = state.git_server_by_host(at.key)
    if known is not None:
        try:
            saved = state.save_git_server(
                known.id, at.root, at.key, checked.kind.name, checked.login
            )
        except state.HostTaken as exc:
            raise _host_taken(at, exc.server) from None
        _write_token(saved.id, token)
        return saved, True
    id = uuid.uuid4().hex[:12]
    _write_token(id, token)
    try:
        saved = state.save_git_server(id, at.root, at.key, checked.kind.name, checked.login)
    except BaseException as exc:
        # A cleanup that fails leaves the folder over, never hides why.
        with contextlib.suppress(OSError, Refused):
            _remove_token(id)
        if isinstance(exc, state.HostTaken):  # another port saved since check_host
            raise _host_taken(at, exc.server) from None
        raise
    if saved.id != id:  # saved meanwhile by another add of the host: its row was replaced
        _write_token(saved.id, token)
        with contextlib.suppress(OSError, Refused):
            _remove_token(id)
        return saved, True
    return saved, False


class Removed(NamedTuple):
    """A server removed, and why a folder of it stayed (None when none did)."""

    server: state.GitServer
    warning: str | None


def remove(at: Address) -> Removed:
    """Remove the server of the host of `at` and its token folder. Refused for no such
    server; a folder the disk refuses to remove is a warning, the server being gone."""
    return remove_host(at.key, at.root)


def remove_host(key: str, named: str | None = None) -> Removed:
    """Remove the server of the host `key` (`Address.key`) and its token folder under the
    lock, as `remove` does; `named` the address the human gave, for the refusal (None: the
    key). The row goes first: a token folder left holds a token no row names."""
    with _locked():
        known = state.git_server_by_host(key)
        if known is None or not state.remove_git_server(known.id):
            raise _not_saved(named or key)
        try:
            _remove_token(known.id, last=not state.git_servers())
        except Refused as exc:  # a link on the way
            return Removed(known, str(exc))
        except _Left as exc:
            return Removed(known, f"could not remove {exc.path}: {exc.why}")
    return Removed(known, None)


def add(
    at: Address, token: Callable[[], str], kind_name: str | None, warn: Callable[[str], None]
) -> tuple[state.GitServer, bool, Checked]:
    """Add the server at `at` as `lado git-server add` does, for the command and the page
    alike: the checks of the address and of git, the plain-http warning through `warn`,
    then `token()` (read only once they pass), its check, the probe (`kind_name`: --kind)
    and the save. The server as saved, whether one was replaced, and the probe's finding."""
    if kind_name is not None and git_kinds.by_name(kind_name) is None:
        raise Refused(
            f"{kind_name} is no kind of git server LADO knows: {' or '.join(KIND_NAMES)}",
            field=KIND_FIELD,
        )
    check_not_github(at)
    check_host(at)
    check_git(os.environ)
    warning = plain_http_warning(at)
    if warning:
        warn(warning)
    value = token()
    check_token(value)
    checked = probe(at, value, kind_name)
    saved, replaced = save(at, checked, value)
    return saved, replaced, checked


def _link(path: Path) -> Refused:
    return Refused(
        f"{path} is a symbolic link: LADO keeps a server's token only in its own folders"
    )


def _write_token(id: str, token: str) -> None:
    state.home()
    try:
        try:
            project_secrets.write_at((TOKENS, id), token_folder(id), TOKEN, token)
        except FileNotFoundError:
            # The last server's removal took git-servers/ between its opening and the
            # making of this server's folder in it (`_remove_token`): once more, made anew.
            project_secrets.write_at((TOKENS, id), token_folder(id), TOKEN, token)
    except project_secrets.LinkRefused as exc:
        raise _link(exc.path) from None
    except OSError as exc:
        raise Refused(
            f"{token_folder(id) / TOKEN} cannot be written ({exc.strerror or type(exc).__name__})"
        ) from None


class _Left(OSError):
    """A folder or file of the tokens the disk refused to remove: its path and why."""

    def __init__(self, path: Path, exc: OSError):
        super().__init__(exc.errno, exc.strerror)
        self.path = path
        self.why = (exc.strerror or type(exc).__name__).lower()


def _remove_token(id: str, last: bool = False) -> None:
    """Remove the token file of the server `id` and its folder, then git-servers/ itself
    once it is empty: no server's folder is left in it; _Left (Refused for a link) when the
    disk refuses it, and for a git-servers/ holding something else when `last` (no server
    is left). Otherwise a server's folder made in it at the same moment keeps it."""
    folder = token_folder(id)
    try:
        try:
            project_secrets.remove_at((TOKENS, id), folder, TOKEN)
        except OSError as exc:
            raise _Left(folder / TOKEN, exc) from None
        with project_secrets.open_chain((TOKENS,), make=False) as fd:
            if fd is not None:
                try:
                    os.rmdir(id, dir_fd=fd)
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    raise _Left(folder, exc) from None
        with project_secrets.open_chain((), make=False) as fd:
            try:
                os.rmdir(TOKENS, dir_fd=fd)
            except OSError as exc:
                if exc.errno == errno.ENOENT:
                    return
                if exc.errno not in (errno.ENOTEMPTY, errno.EEXIST) or last:
                    raise _Left(folder.parent, exc) from None
    except project_secrets.LinkRefused as exc:
        raise _link(exc.path) from None
