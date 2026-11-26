"""The human's git servers (openspec capability `git-servers`): a GitLab, github.com or
GitHub Enterprise server, its kind told by its API, and the token agents and LADO's own git
reach it with.

A server is identified by its host and port (`Address.key`), one per host name
(`check_host`: git's ssh addresses carry no port). github.com is one like any other, at
`https://github.com` alone (www. and api. taken as it), asked as GitHub only (`kinds`). It
is saved in
lado.db (lado.state: `git_servers`) only after its probe: each kind of lado.git_kinds is
asked at once, through lado.model_servers' request path (no redirect followed, each request
cut at its TIMEOUT); `--kind` saves one that cannot be checked. Its token is kept in
`<LADO_HOME>/git-servers/<id>/token` alone, written and removed by the link-refusing writer
of LADO's secrets (lado.project_secrets), never in lado.db, a message or a git config file.
A save, a removal and a check's login write hold one lock of LADO_HOME (`locked`), never
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

An agent's GitLab CLI gets a configuration folder of its own (`glab_variables`), with an
entry per saved GitLab server whose token header comes from LADO's helper at each call
(`glab_command`): no token is written there. The server of the session repository's origin
names its kind's tool to every agent (`tool_line`), from one check of that tool on the
agents' PATH (`tool_state`), which also gives the launch's warning (`tool_warning`).
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
from lado.git_kinds import Kind, github, gitlab
from lado.git_kinds.base import REFUSES

if TYPE_CHECKING:  # the HTTP client: loaded by `add` alone, never by a launch or a hook
    from lado import git_certificates, model_servers

TOKENS = "git-servers"  # under LADO_HOME: a folder per server, by its id
TOKEN = "token"  # the token's file in a server's folder
CERTIFICATE = "ca.pem"  # the certificate trusted for a server, in its folder
KIND_NAMES = tuple(kind.name for kind in git_kinds.KINDS)
GITHUB_COM = frozenset({"github.com", "www.github.com", "api.github.com"})
HELPER = "lado.git_credential"
ADD = "lado git-server add"
REMOVE = "lado git-server remove"
AUTHOR = "lado git-server author"
RESTART = "Agents started from now on reach it; restart running agents to give it to them."
AUTHOR_SET = "Agents commit to {address} as {author}."
# Without a server's own author: LADO's, else the human's git config (lado.commit_authors).
FALLBACK = "LADO's commit author, or your own git author without one"
AUTHOR_CLEARED = "Agents commit to {address} with " + FALLBACK + "."
AUTHOR_NONE = "{address} has no commit author: agents commit there with " + FALLBACK + "."
# With neither LADO's author nor git's own (lado.commit_authors.unsigned).
AUTHOR_CLEARED_NOBODY = (
    "Agents cannot commit to {address} now: it has no commit author, LADO has none and git "
    "knows none."
)
AUTHOR_NOBODY = (
    "{address} has no commit author, LADO has none and git knows none: agents cannot commit "
    "there."
)
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
    save without a check once its kind is chosen; `offer` the authority to trust of a server
    whose certificate is not trusted (lado.git_certificates), `before` the one given that
    did not fit. Never holds a token."""

    def __init__(
        self,
        text: str,
        hint: str = "",
        field: str = "",
        page: str | None = None,
        page_hint: str | None = None,
        choose_kind: bool = False,
        offer: git_certificates.Certificate | None = None,
        before: git_certificates.Certificate | None = None,
    ):
        super().__init__(text)
        self.hint = hint
        self.field = field
        self.page = text if page is None else page
        self.page_hint = hint if page_hint is None else page_hint
        self.choose_kind = choose_kind
        self.offer = offer
        self.before = before


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
    if any(char.isspace() or not char.isprintable() for char in text):
        raise BadAddress("a git server's address holds no space, tab or control character")
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
    if ":" not in host and not all(char.isalnum() or char in "-._" for char in host):
        raise BadAddress("a host name holds only letters, digits, '-', '.' and '_'")
    shown = f"[{host}]" if ":" in host else host
    if port is not None and port != (443 if scheme == "https" else 80):
        shown += f":{port}"
    path = parts.path.rstrip("/")
    if host.lower() in GITHUB_COM:
        if scheme != "https" or shown.lower() != host.lower() or path:
            raise BadAddress(f"github.com is signed in to at {github.DOTCOM}")
        return Address(github.DOTCOM, "github.com", "github.com", "https")
    return Address(f"{scheme}://{shown}{path}", shown, host, scheme)


def plain_http_warning(at: Address) -> str | None:
    return PLAIN_HTTP.format(host=at.host) if at.scheme == "http" else None


def kinds(at: Address) -> tuple[Kind, ...]:
    """The kinds asked at `at`: GitHub alone for github.com, whose API is elsewhere
    (api.github.com) and which is no GitLab; every kind for any other server."""
    return (github.KIND,) if at.root == github.DOTCOM else git_kinds.KINDS


def check_kind(at: Address, kind_name: str | None) -> None:
    """Refuse `--kind` for github.com: its kind is known."""
    if kind_name is not None and at.root == github.DOTCOM:
        raise Refused(
            "github.com's kind is GitHub: add it without --kind",
            field=KIND_FIELD,
            page="github.com's kind is GitHub: add it without a kind.",
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
    lacks, whether the server told the token's rights, and the rights of the kind's tool it
    lacks (told, not required)."""

    kind: Kind
    login: str | None
    unchecked: str = ""
    missing_scopes: tuple[str, ...] = ()
    rights_checked: bool = False
    tool_missing: tuple[str, ...] = ()

    def line(self) -> str | None:
        """`GitLab, signed in as <login>`, and what the token leaves its tool without;
        None for a server not checked."""
        if not self.login:
            return None
        line = f"{self.kind.title}, signed in as {self.login}"
        if self.tool_missing:
            line += f"; {tool_cannot(self.kind, self.tool_missing)}"
        return line

    def lacks(self) -> str | None:
        """`the token lacks <scopes>: agents can …`; None when it lacks none."""
        return lacks(self.kind, self.missing_scopes)

    def replace_hint(self, at: Address) -> str:
        return replace_hint(self.kind, at)


def replace_hint(kind: Kind, at: Address) -> str:
    """How to replace a token that lacks a right agents need."""
    return f"replace it with a token with the {kind.scopes}: {ADD} {at.root} --token"


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


def _opener(certificate: str | None = None):
    """The opener of LADO's requests to a server: no redirect followed; with `certificate`
    (PEM), trusting it alone (lado.git_certificates.context), else this computer's
    authorities."""
    import urllib.request

    from lado import model_servers

    if certificate is None:
        return urllib.request.build_opener(model_servers.NoRedirect())
    from lado import git_certificates

    tls = urllib.request.HTTPSHandler(context=git_certificates.context(certificate))
    return urllib.request.build_opener(model_servers.NoRedirect(), tls)


def _no_answer_page(answer: model_servers.Answer) -> str:
    """Why a request got no HTTP answer, as the page's sentence."""
    if answer.why.startswith("no answer in "):
        return (
            f"No answer in {answer.why.removeprefix('no answer in ').removesuffix(' s')} seconds."
        )
    return f"No answer: {_silent(answer)}."


def _ask_kinds(
    at: Address, token: str | None, certificate: str | None = None
) -> list[model_servers.Answer]:
    """Each kind's answer at `at`, in KINDS' order, all asked at once with `token` (None:
    no credential), following no redirect, each request cut at model_servers' TIMEOUT;
    trusting `certificate` alone when given."""
    from lado import model_servers

    asked = []
    for kind in kinds(at):
        url, headers = kind.request(at.root, token)
        asked.append((url, "GET", headers))
    return model_servers.ask_all(_opener(certificate), asked, AGENT)


def _rights(
    at: Address,
    token: str,
    kind: Kind,
    answer: model_servers.Answer,
    certificate: str | None = None,
) -> tuple[tuple[str, ...], bool, tuple[str, ...]]:
    """The rights `kind`'s token lacks by `answer`, the answer that gave its login, whether
    the server told its rights, and the rights of its tool the token lacks: as `_ask_kinds`
    asks, one request at a time."""
    from lado import model_servers

    def ask(url: str, headers: dict[str, str]) -> model_servers.Answer:
        (found,) = model_servers.ask_all(_opener(certificate), [(url, "GET", headers)], AGENT)
        return found

    told = kind.rights(at.root, token, answer, ask)
    if told is None:
        return (), False, ()
    return kind.missing(told), True, kind.tool_missing(told)


def tool_cannot(kind: Kind, missing: Sequence[str]) -> str:
    """`glab cannot open merge requests: the token lacks api`, for the rights `missing` of
    the kind's `tool_needs`."""
    return f"{kind.tool} cannot open {kind.changes}: the token lacks {', '.join(missing)}"


def probe(
    at: Address, token: str, kind_name: str | None = None, certificate: str | None = None
) -> Checked:
    """The kind of the server at `at` and the user `token` signs in as, every kind asked at
    once; with `kind_name`, that kind for a server no kind recognises (Checked.unchecked says
    why); trusting `certificate` (PEM) alone when given. Refused for a server that refuses
    the token, sends elsewhere, answers as two kinds without `kind_name` or as another, or
    cannot be checked without `kind_name`."""
    answers = _ask_kinds(at, token, certificate)
    by_kind = list(zip(kinds(at), answers, strict=True))
    found = [(kind, login) for kind, answer in by_kind if (login := kind.login(answer))]
    chosen = git_kinds.by_name(kind_name) if kind_name else None

    def checked(kind: Kind, login: str) -> Checked:
        missing, told, tool = _rights(at, token, kind, dict(by_kind)[kind], certificate)
        return Checked(kind, login, missing_scopes=missing, rights_checked=told, tool_missing=tool)

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
        titles = " and ".join(f"{kind.title}'s" for kind in kinds(at))
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
    unchecked, refusal = _unanswered(at, answers, certificate)
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


def hint(at: Address, certificate: str | None = None) -> Hint:
    """Ask every kind's path of `at` at once with no credential, as the probe does
    (trusting `certificate` alone when given): a kind when exactly one answers as that kind
    (its user, or its refusal of a missing token); none when none answers, or as neither or
    both. Refused for a server that sends elsewhere: no kind could save it from the page."""
    answers = _ask_kinds(at, None, certificate)
    told = [
        kind
        for kind, answer in zip(kinds(at), answers, strict=True)
        if kind.login(answer) or kind.refusal(answer)
    ]
    if len(told) == 1:
        return Hint(told[0])
    if told:
        titles = " and as ".join(kind.title for kind in told)
        why = Refused(f"{at.root} answers as {titles}", field=KIND_FIELD, page_hint=PAGE_KIND_HINT)
        return Hint(None, why)
    _, refused = _unanswered(at, answers, certificate)
    if any(answer.location for answer in answers):
        raise refused
    return Hint(None, refused)


def _unanswered(
    at: Address, answers: Sequence[model_servers.Answer], certificate: str | None = None
) -> tuple[str, Refused]:
    """For answers of no kind: why the server could not be checked, as the end of "could
    not be checked (…)", and the refusal for an add that chose no kind; for a certificate
    not trusted (by `certificate`, when the add gave one), with the authority to trust."""
    moved = next((answer.location for answer in answers if answer.location), "")
    if moved:
        refused = Refused(
            f"{at.root} sends to {moved}; give the server's own address", field=ADDRESS_FIELD
        )
        return f"it sends to {moved}", refused
    if all(answer.status is None for answer in answers):
        silent = _silent(answers[0])
        if _untrusted(answers[0]):
            command = f"{ADD} {at.root} --token --certificate <file>"
            found = _trust(at, certificate, command, answers[0].why, given=True)
            refused = Refused(
                found.text,
                found.hint,
                ADDRESS_FIELD,
                page=found.page,
                page_hint=found.page_hint,
                choose_kind=True,
                offer=found.offer,
                before=found.before,
            )
            return f"it does not answer: {silent}", refused
        refused = Refused(
            f"{at.key} does not answer: {silent}",
            _kind_hint(at.root),
            ADDRESS_FIELD,
            page=_no_answer_page(answers[0]),
            page_hint=PAGE_KIND_HINT,
            choose_kind=True,
        )
        return f"it does not answer: {silent}", refused
    titles = " nor ".join(kind.title for kind in kinds(at))
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
    "cert_changed",
    "cert_name",
    "cert_expired",
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
TRUST_HINT = "trust it in Settings → Git servers (Check), or give its certificate: {command}"
CERTIFICATE_COMMAND = "lado git-server certificate"
ABOUT_TRUST = (
    "The server's certificate is signed by an authority LADO's computer does not know, often "
    "your company's own. If you trust it, LADO and agents' git trust it for this server only; "
    "nothing else on the computer changes."
)
ABOUT_CHANGED = (
    "LADO and agents' git trusted the old certificate for this server. Until you trust the new "
    "one, they cannot clone or push here."
)


def _untrusted(answer: model_servers.Answer) -> bool:
    """Whether a request got no answer because the server's certificate was not trusted."""
    return answer.status is None and answer.tls and "certificate" in answer.why


@dataclass(frozen=True)
class _Trust:
    """What a check or an add found of a certificate not trusted: one of OUTCOMES, its lines
    as Check holds them, the authority to trust and the saved one that no longer fits."""

    outcome: str
    text: str
    hint: str
    page: str
    page_hint: str
    offer: git_certificates.Certificate | None = None
    before: git_certificates.Certificate | None = None


def _trust(at: Address, trusted: str | None, command: str, why: str, given: bool = False) -> _Trust:
    """What to say of `at`'s certificate, not trusted by this computer or by `trusted` (the
    PEM saved for the server, or given to its add with `given`): the authority to trust
    when trusting it alone reaches the server (lado.git_certificates.offer), else why trust
    would not help. `command` the hint's way to give a file; `why` the request's failure."""
    from lado import git_certificates

    port = urllib.parse.urlsplit(at.root).port or 443
    try:
        offer = git_certificates.offer(at.host, port)
    except git_certificates.NoOffer as exc:
        of = f"the certificate of {at.root}"
        if exc.outcome == git_certificates.NAME and exc.common_name_only:
            names = "names its host only in the old Common Name field, which LADO refuses"
            return _Trust(
                "cert_name",
                f"{of} {names}",
                "ask the server's administrator to reissue it",
                f"The server's certificate {names}: ask the server's administrator to reissue it.",
                "",
            )
        if exc.outcome == git_certificates.NAME:
            issued = f"is not issued for {at.host}: trusting it would not help"
            return _Trust(
                "cert_name",
                f"{of} {issued}",
                "ask the server's administrator",
                f"The server's certificate {issued}. Ask the server's administrator.",
                "",
            )
        if exc.outcome == git_certificates.EXPIRED and exc.expired_on is not None:
            expired = f"expired on {exc.expired_on.isoformat()}"
            return _Trust(
                "cert_expired",
                f"{of} {expired}",
                "ask the server's administrator to renew it",
                f"The server's certificate {expired}: ask the server's administrator to renew it.",
                "",
            )
        return _tls_failed(at, exc.why or why)
    hint = TRUST_HINT.format(command=command)
    if trusted is None:
        return _Trust(
            "cert_untrusted",
            f"the certificate of {at.root} is not trusted",
            hint,
            "The server's certificate is not trusted.",
            ABOUT_TRUST,
            offer,
        )
    saved = git_certificates.parse(trusted)
    before = saved[0] if saved else None
    if given:
        return _Trust(
            "cert_untrusted",
            f"the certificate of {at.root} is not signed by the given certificate",
            hint,
            "The server's certificate is not signed by the given certificate.",
            ABOUT_TRUST,
            offer,
            before,
        )
    if all(offer.sha256 != cert.sha256 for cert in saved):
        return _Trust(
            "cert_changed",
            f"the certificate of {at.root} has changed since you trusted it",
            hint,
            "The server's certificate has changed since you trusted it.",
            ABOUT_CHANGED,
            offer,
            before,
        )
    return _tls_failed(at, why)  # the saved authority reaches it now: a passing failure


def _tls_failed(at: Address, why: str) -> _Trust:
    failed = f"TLS failed ({why})"
    return _Trust(
        "no_answer",
        f"{at.key} does not answer: {failed}",
        REACH_HINT,
        f"No answer: {failed}.",
        PAGE_REACH_HINT,
    )


@dataclass(frozen=True)
class Check:
    """What a check of a saved server found: `outcome` one of OUTCOMES, the saved `kind`,
    the `login` it saw (None but for ok and scopes_missing), the rights the token lacks,
    whether the server told them, whether the server had a login before (`was_checked`),
    one line and its hint in the command's words (`text`, `hint`) and in the page's
    (`page`, a sentence, and `page_hint`, its info tip's: "" for none); for a certificate
    not trusted, the authority to trust (`offer`) and the saved one that no longer fits
    (`before`). Never holds a token."""

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
    offer: git_certificates.Certificate | None = None  # cert_untrusted, cert_changed
    before: git_certificates.Certificate | None = None  # cert_changed: the saved one
    tool_missing: tuple[str, ...] = ()  # ok: the rights of the kind's tool the token lacks


def check(at: Address, save_login: bool = True) -> Check:
    """Check the saved server of `at`'s host again with its saved token, as `add` asks it
    (every kind at once, no redirect followed, each request cut at TIMEOUT), judged by its
    saved kind; a passing check saves the login it saw (under the lock) unless `save_login`
    is False (lado doctor, which writes nothing), nothing else is written. Refused, with no
    request sent, for no such server, a kind this LADO does not know or a token file it
    cannot read."""
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
    trusted = certificate(server)
    answers = _ask_kinds(at, token, trusted)
    by_kind = dict(zip(kinds(at), answers, strict=True))
    own = by_kind[kind]
    was = server.login is not None

    if login := kind.login(own):
        missing, told, tool = _rights(at, token, kind, own, trusted)
        if missing:
            return Check(
                "scopes_missing",
                kind,
                login,
                missing,
                told,
                was,
                lacks(kind, missing) or "",
                replace_hint(kind, at),
                f"The token lacks {', '.join(missing)}.",
                f"Agents can {_can(kind, missing)} with it. Make one with the {kind.scopes}.",
            )
        if save_login:
            _save_login(server, login)
        rights = ", may clone and push." if told else "; the token's rights are not checked."
        page = f"Works: signed in as {login}{rights}"
        if server.login is None:
            page = f"Works: {kind.title}, signed in as {login}."
        text = f"Works: {kind.title}, signed in as {login}{rights}"
        if tool:  # git works: the outcome stays ok, the lines say what the tool cannot
            cannot = f"; {tool_cannot(kind, tool)}."
            text, page = text[:-1] + cannot, page[:-1] + cannot
        return Check("ok", kind, login, (), told, was, text, "", page, tool_missing=tool)

    def failed(outcome: str, text: str, hint: str, page: str, page_hint: str = "") -> Check:
        return Check(outcome, kind, None, (), False, was, text, hint, page, page_hint)

    why = kind.refusal(own)
    if why and why != REFUSES:  # GitLab's user API refuses a token without read_api
        return Check(
            "scopes_missing",
            kind,
            None,
            ("read_api",),
            True,
            was,
            f"{kind.title} {why}",
            replace_hint(kind, at),
            "The token lacks read_api.",
            f"LADO asks the server's API with it. Make one with the {kind.scopes}.",
        )
    if why:
        refused = f"{kind.title} refused the token: it expired or was revoked"
        return failed(
            "token_refused", refused, f"replace it: {ADD} {at.root} --token", refused + "."
        )
    moved = next((answer.location for answer in answers if answer.location), "")
    if moved:
        moves = f"redirects to {moved}: add that address instead"
        return failed("redirect", f"it {moves}", "", f"It {moves}.")
    if own.status is None:
        if _untrusted(own):
            command = f"{CERTIFICATE_COMMAND} {at.root} <file>"
            found = _trust(at, trusted, command, own.why)
            return Check(
                found.outcome,
                kind,
                None,
                (),
                False,
                was,
                found.text,
                found.hint,
                found.page,
                found.page_hint,
                found.offer,
                found.before,
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
    titles = " nor ".join(k.title for k in kinds(at))
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
    with locked():
        now = state.git_server_by_host(server.host)
        if now is not None and now.id == server.id:
            state.save_git_server(now.id, now.address, now.host, now.kind, login)


def helper_command(server: state.GitServer) -> str:
    """git's `credential.<url>.helper` value for LADO's helper of `server`: LADO's own Python
    by its absolute path, so no `lado` on the PATH is needed, with all it needs as
    arguments, so it never opens lado.db; no token, only ids (a `ps` line shows them)."""
    return "!" + shlex.join(_helper(server))


def _helper(server: state.GitServer, *operation: str) -> list[str]:
    """LADO's helper of `server` (lado.git_credential), with `operation` when one is given
    (git appends its own)."""
    kind = git_kinds.by_name(server.kind)
    user = kind.git_user if kind is not None else "token"  # a kind this LADO does not know
    return interpreter.run_module(
        HELPER,
        "--home", str(state.home_path().absolute()),
        "--server", server.id,
        "--user", user,
        "--address", server.address,
        *operation,
    )  # fmt: skip


def _entries(server: state.GitServer) -> list[tuple[str, str]]:
    """The git config entries of one server, in order: an empty helper for its origin, which
    drops every helper set before it there (the image's, the human's `store`), so none
    other is asked or stores the token; LADO's helper; its ssh addresses rewritten to its
    root (git's rewrite is a fixed prefix: the standard ssh port alone); with a certificate
    file, git's authority for the server's address alone (`http.<url>.*` matches the URL
    after the rewrite; the trailing `/` keeps `/git` from matching `/gitlab`)."""
    parts = urllib.parse.urlsplit(server.address)
    origin = f"{parts.scheme}://{parts.netloc}"
    host = parts.hostname or ""
    host = f"[{host}]" if ":" in host else host
    rewrite = f"url.{server.address}/.insteadOf"
    found = [
        (f"credential.{origin}.helper", ""),
        (f"credential.{origin}.helper", helper_command(server)),
        (rewrite, f"git@{host}:"),
        (rewrite, f"ssh://git@{host}/"),
        (rewrite, f"ssh://git@{host}:22/"),
    ]
    ca = certificate_file(server.id)
    if ca.is_file():
        found.append((f"http.{server.address}/.sslCAInfo", str(ca)))
    return found


def variables(
    env: Mapping[str, str],
    servers: Sequence[state.GitServer],
    authors: Mapping[str, Path] | None = None,
    lado: state.Author | None = None,
    project: state.Author | None = None,
) -> dict[str, str]:
    """The `GIT_CONFIG_*` variables to lay over `env` for `servers`: the entries of `env`'s
    own `GIT_CONFIG_COUNT` are kept, LADO's coming after them (a count that is no number
    counts as none): LADO's commit author `lado` first, then each server's entries, after
    its own those of its author file in `authors` (server id → file, `author_files`), then
    the project's author `project`; the later entry wins, so a project's author wins over a
    server's and a server's over LADO's (lado.commit_authors). The authors are an agent's
    only. Nothing for no server and no author."""
    if not servers and lado is None and project is None:
        return {}
    from lado import commit_authors  # it builds on this module

    try:
        n = max(0, int(env.get("GIT_CONFIG_COUNT", "0")))
    except ValueError:
        n = 0
    laid = commit_authors.entries(lado) if lado else []
    for server in servers:
        laid += _entries(server)
        if authors and server.id in authors:
            laid += author_entries(server, authors[server.id])
    if project:
        laid += commit_authors.entries(project)
    found = {}
    for key, value in laid:
        found[f"GIT_CONFIG_KEY_{n}"] = key
        found[f"GIT_CONFIG_VALUE_{n}"] = value
        n += 1
    found["GIT_CONFIG_COUNT"] = str(n)
    # What a process this one starts gets back once LADO's entries are dropped
    # (agent_env.without_launch).
    found[agent_env.GIT_CONFIG_BASE] = env.get("GIT_CONFIG_COUNT", "")
    return found


GH_LOGIN_FILE = "hosts.yml"  # where gh keeps a login in its config folder


def gh_variables(
    servers: Sequence[state.GitServer], config: Path, remote: Callable[[], str | None]
) -> dict[str, str]:
    """The GitHub CLI's variables of an agent's launch, from the saved servers alone:
    `GH_CONFIG_DIR` its own folder `config`, made, with no login of gh's own in it; `GH_TOKEN`
    the github.com server's token; `GH_ENTERPRISE_TOKEN` the token of the GitHub Enterprise
    server of the repository's origin (`remote()`, asked only while one is saved), else of
    the only one saved, and `GH_HOST` its host for the origin's server only. A token is in
    the launch's environment alone, as an API key is."""
    from lado import git_credential

    config.mkdir(parents=True, exist_ok=True, mode=0o700)
    with contextlib.suppress(FileNotFoundError):
        (config / GH_LOGIN_FILE).unlink()  # a login made by hand there is no saved server's
    found = {"GH_CONFIG_DIR": str(config)}

    def token(server: state.GitServer) -> str | None:
        return git_credential.read_token(server.id) if has_token(server) else None

    dotcom = next((s for s in servers if s.address == github.DOTCOM), None)
    if dotcom is not None and (value := token(dotcom)):
        found["GH_TOKEN"] = value
    enterprise = [s for s in servers if s.kind == github.KIND.name and s is not dotcom]
    if not enterprise:
        return found
    url = remote()
    origin = server_for(url, servers) if url else None
    chosen = origin if origin in enterprise else None
    if chosen is None and len(enterprise) == 1:
        chosen = enterprise[0]
    if chosen is not None and (value := token(chosen)):
        found["GH_ENTERPRISE_TOKEN"] = value
        if chosen is origin:
            found["GH_HOST"] = chosen.host
    return found


GLAB_CONFIG_FILE = "config.yml"  # glab's configuration in its folder (GLAB_CONFIG_DIR)
GLAB_HEADER = "PRIVATE-TOKEN"  # GitLab's header of a token


def glab_command(server: state.GitServer) -> str:
    """The command glab runs for the token header of `server` (`valueFromCommand`): LADO's
    helper in its `token` mode, LADO's own Python by its absolute path, with ids only, one
    string glab splits as a shell does."""
    from lado import git_credential

    return shlex.join(_helper(server, git_credential.HEADER))


def glab_config(servers: Sequence[state.GitServer]) -> str:
    """glab's `config.yml` for the GitLab servers of `servers`: its update check and usage
    statistics off, git over https, no prompt, and per server (by `host[:port]`) its scheme,
    its path (`subfolder`), its certificate file when there is one and the token header from
    `glab_command`. Never a token."""
    import yaml  # only a launch writes it

    hosts = {}
    for server in servers:
        if server.kind != gitlab.KIND.name:
            continue
        parts = urllib.parse.urlsplit(server.address)
        entry: dict[str, object] = {"api_protocol": parts.scheme}
        if path := parts.path.strip("/"):
            entry["subfolder"] = path
        if (ca := certificate_file(server.id)).is_file():
            entry["ca_cert"] = str(ca)
        entry["custom_headers"] = [{"name": GLAB_HEADER, "valueFromCommand": glab_command(server)}]
        hosts[server.host] = entry
    config = {
        "check_update": False,
        "telemetry": False,
        "git_protocol": "https",
        "no_prompt": True,
        "hosts": hosts,
    }
    return yaml.safe_dump(config, sort_keys=False, allow_unicode=True, width=10**6)


def glab_variables(servers: Sequence[state.GitServer], folder: Path) -> dict[str, str]:
    """The GitLab CLI's variables of an agent's launch: `GLAB_CONFIG_DIR` its own `folder`
    (700), where `glab_config` is written whole (600: glab refuses another mode), even with
    no GitLab saved, so the human's own glab configuration is never read."""
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder.chmod(0o700)
    _write_whole(folder / GLAB_CONFIG_FILE, glab_config(servers))
    return {"GLAB_CONFIG_DIR": str(folder)}


TOOL_TIMEOUT = 10.0  # seconds a tool's `--version` may take, as lado doctor's VERSION_TIMEOUT


class ToolState(NamedTuple):
    """A server's tool on the agents' PATH: whether it is there, its version ("" when it
    tells none), whether that is older than its kind's oldest, and its `--version` line."""

    found: bool
    version: str
    too_old: bool
    line: str = ""


def _numbers(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def tool_state(kind: Kind, env: Mapping[str, str]) -> ToolState:
    """`kind`'s tool on `env`'s PATH, by `<tool> --version` and its first x.y.z, cut at
    TOOL_TIMEOUT, with an empty configuration folder of the call's own (glab writes into
    its configuration at any call: never the human's). A version it cannot read (no x.y.z,
    a failure, no answer in time) counts as fit: the tool is there, and a guess would be a
    false alarm."""
    import shutil
    import tempfile

    path = shutil.which(kind.tool, path=env.get("PATH", os.defpath))
    if path is None:
        return ToolState(False, "", False)
    try:
        with tempfile.TemporaryDirectory(prefix="lado-tool-") as folder:
            result = subprocess.run(
                [path, "--version"],
                env={**env, kind.config_variable: folder},
                capture_output=True,
                text=True,
                timeout=TOOL_TIMEOUT,
                check=False,
            )
    except (OSError, subprocess.TimeoutExpired):
        return ToolState(True, "", False)
    lines = result.stdout.strip().splitlines()
    line = lines[0] if lines else ""
    found = re.search(r"\d+\.\d+\.\d+", line) if result.returncode == 0 else None
    if found is None:
        return ToolState(True, "", False, line)
    version = found[0]
    too_old = bool(kind.tool_oldest) and _numbers(version) < _numbers(kind.tool_oldest)
    return ToolState(True, version, too_old, line)


def tool_line(server: state.GitServer, found: ToolState) -> str | None:
    """The line of an agent's instructions about its repository's server `server`: its
    kind and host, its tool and what for, and that the tool is logged in, or why not (no
    token, the tool missing or too old by `found`, gh without the server's certificate);
    None for a kind this LADO does not know."""
    kind = git_kinds.by_name(server.kind)
    if kind is None:
        return None
    tool = f"`{kind.tool}`"
    start = (
        f"The repository's origin is on {kind.title} ({server.host}), a git server LADO signs "
        "you in to"
    )
    if not has_token(server):
        return (
            f"{start}, but LADO has no token for it, so {tool} is not logged in and git cannot "
            "push there; tell the human."
        )
    if not found.found:
        return (
            f"{start}, but its tool {tool} is not installed here, so you cannot open its "
            f"{kind.changes}; tell the human."
        )
    if found.too_old:
        return (
            f"{start}, but {tool} here is {found.version}, older than {kind.tool_oldest}, which "
            f"LADO needs to sign it in, so you cannot open its {kind.changes}; tell the human."
        )
    line = f"{start}: use {tool} for its {kind.changes}; it is logged in already."
    if gh_without_certificate([server]):
        line += f" {tool} does not get the server's certificate and cannot reach it; git can."
    return line


def tool_problem(kind: Kind, found: ToolState, addresses: Sequence[str]) -> tuple[str, str]:
    """What is wrong with `kind`'s tool by `found`, for its servers `addresses`, and what to
    do, as lado doctor says them; ("", "") when it is fit."""
    if not found.found:
        newer = f" {kind.tool_oldest} or newer" if kind.tool_oldest else ""
        return (
            f"not on the agents' PATH: agents cannot open {kind.changes} on {', '.join(addresses)}",
            f"install {kind.tool}{newer}",
        )
    if found.too_old:
        return (
            f"{kind.tool} {found.version} is older than {kind.tool_oldest}, which LADO needs "
            "to sign it in",
            f"update {kind.tool}",
        )
    return "", ""


def tool_warning(server: state.GitServer, found: ToolState) -> str | None:
    """What a launch says when the tool of the repository's server `server` is missing or
    too old by `found` (`tool_problem` in one line); None when it is fit, or for a kind this
    LADO does not know."""
    kind = git_kinds.by_name(server.kind)
    if kind is None:
        return None
    what, hint = tool_problem(kind, found, [server.address])
    if not what:
        return None
    if not found.found:
        return f"{kind.tool} is {what}; {hint}"
    return f"{what} to {server.address}; {hint}"


def gh_without_certificate(servers: Sequence[state.GitServer]) -> list[str]:
    """What an agent's launch and lado doctor say of each GitHub server of `servers` with a
    certificate: `gh` reads no authority per host, and one for the whole agent
    (`SSL_CERT_FILE`) would take this computer's from its own CLI, so gh does not get it."""
    return [
        f"does not get the certificate of {server.address}: agents' gh cannot reach it; git can"
        for server in servers
        if server.kind == github.KIND.name and certificate_file(server.id).is_file()
    ]


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


def check_author(name: str, email: str) -> tuple[str, str]:
    """lado.commit_authors.check: every commit author's check, a server's among them."""
    from lado import commit_authors  # it builds on this module's Refused

    return commit_authors.check(name, email)


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
        _write_whole(path, text)
        found[server.id] = path
    return found


def _write_whole(path: Path, text: str) -> None:
    """Write `text` into `path` whole, mode 600, by a rename of a file of its own."""
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}")
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(text)
        os.replace(temp, path)
    finally:  # a failed write leaves no file of its own; why it failed goes on
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp)


def token_folder(id: str) -> Path:
    return state.home_path() / TOKENS / id


def has_token(server: state.GitServer) -> bool:
    return os.path.lexists(token_folder(server.id) / TOKEN)


def certificate_file(id: str) -> Path:
    return token_folder(id) / CERTIFICATE


def certificate(server: state.GitServer) -> str | None:
    """The PEM of the certificate trusted for `server` (`ca.pem` in its folder); None for
    none, or one the disk does not give."""
    try:
        return certificate_file(server.id).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def certificate_info(server: state.GitServer) -> git_certificates.Certificate | None:
    """The first certificate of the server's file, as the list and the page name it (its
    name and expiry); None for none, or a file LADO cannot read."""
    pem = certificate(server)
    if pem is None:
        return None
    from lado import git_certificates

    found = git_certificates.parse(pem)
    return found[0] if found else None


def set_certificate(at: Address, pem: str) -> state.GitServer:
    """Trust `pem` (checked by lado.git_certificates) for the saved server of `at`'s host,
    under the lock, replacing its certificate whole: the server. Refused for no such
    server, a link on the way or a disk that refuses it."""
    with locked():
        server = saved_server(at)
        _write(server.id, CERTIFICATE, pem)
    return server


def clear_certificate(at: Address) -> str | None:
    """Remove the certificate of the saved server of `at`'s host under the lock: the PEM it
    held (the page's Undo puts it back), None for none. Refused for no such server."""
    with locked():
        server = saved_server(at)
        pem = certificate(server)
        try:
            _remove_certificate(server.id)
        except project_secrets.LinkRefused as exc:
            raise _link(exc.path) from None
        except OSError as exc:
            raise Refused(
                f"{certificate_file(server.id)} cannot be removed "
                f"({exc.strerror or type(exc).__name__})"
            ) from None
    return pem


LOCK = "git-servers.lock"  # under LADO_HOME; it stays, as update.lock does
LOCK_WAIT = 10  # seconds a save or a removal waits for another one
LOCKED = "another change of the git servers is running; try again"


@contextlib.contextmanager
def locked() -> Iterator[None]:
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


def save(
    at: Address, checked: Checked, token: str, certificate: str | None = None
) -> tuple[state.GitServer, bool]:
    """Save the server at `at` as `checked` with `token`, or replace the one of its host,
    keeping its id, under the lock: the server as saved, and whether one was replaced. A
    new server's token file comes first and goes again when its row fails; a replaced one's
    row comes first, then its token file is replaced whole, so it holds the old token or the
    new one. `certificate` (PEM) is written beside the token; without one a replaced
    server keeps its own."""
    with locked():
        return save_locked(at, checked, token, certificate)


def save_locked(
    at: Address, checked: Checked, token: str, certificate: str | None = None
) -> tuple[state.GitServer, bool]:
    """`save` inside `locked`, held by the caller (lado.github_takeover)."""
    known = state.git_server_by_host(at.key)
    if known is not None:
        try:
            saved = state.save_git_server(
                known.id, at.root, at.key, checked.kind.name, checked.login
            )
        except state.HostTaken as exc:
            raise _host_taken(at, exc.server) from None
        _write_token(saved.id, token)
        if certificate is not None:
            _write(saved.id, CERTIFICATE, certificate)
        return saved, True
    id = uuid.uuid4().hex[:12]
    _write_token(id, token)
    if certificate is not None:
        try:
            _write(id, CERTIFICATE, certificate)
        except BaseException:
            with contextlib.suppress(OSError, Refused):
                _remove_token(id)
            raise
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
        if certificate is not None:
            _write(saved.id, CERTIFICATE, certificate)
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
    with locked():
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
    at: Address,
    token: Callable[[], str],
    kind_name: str | None,
    warn: Callable[[str], None],
    certificate: str | None = None,
) -> tuple[state.GitServer, bool, Checked]:
    """Add the server at `at` as `lado git-server add` does, for the command and the page
    alike: the checks of the address and of git, the plain-http warning through `warn`,
    then `token()` (read only once they pass), its check, the probe (`kind_name`: --kind;
    trusting `certificate` alone when given, which is saved with it) and the save. The
    server as saved, whether one was replaced, and the probe's finding."""
    if kind_name is not None and git_kinds.by_name(kind_name) is None:
        raise Refused(
            f"{kind_name} is no kind of git server LADO knows: {' or '.join(KIND_NAMES)}",
            field=KIND_FIELD,
        )
    check_kind(at, kind_name)
    check_host(at)
    check_git(os.environ)
    warning = plain_http_warning(at)
    if warning:
        warn(warning)
    value = token()
    check_token(value)
    checked = probe(at, value, kind_name, certificate)
    saved, replaced = save(at, checked, value, certificate)
    return saved, replaced, checked


def _link(path: Path) -> Refused:
    return Refused(
        f"{path} is a symbolic link: LADO keeps a server's token and certificate only in its "
        "own folders"
    )


def _write_token(id: str, token: str) -> None:
    _write(id, TOKEN, token)


def _write(id: str, name: str, value: str) -> None:
    """Write the file `name` (TOKEN, CERTIFICATE) of the server `id` whole, mode 600, by
    LADO's secrets writer, which refuses a link on the way; the token as a secret's value
    (lado.git_credential reads it so), the certificate as it is."""
    state.home()
    fixed = name != TOKEN
    try:
        try:
            project_secrets.write_at((TOKENS, id), token_folder(id), name, value, fixed=fixed)
        except FileNotFoundError:
            # The last server's removal took git-servers/ between its opening and the
            # making of this server's folder in it (`_remove_token`): once more, made anew.
            project_secrets.write_at((TOKENS, id), token_folder(id), name, value, fixed=fixed)
    except project_secrets.LinkRefused as exc:
        raise _link(exc.path) from None
    except OSError as exc:
        raise Refused(
            f"{token_folder(id) / name} cannot be written ({exc.strerror or type(exc).__name__})"
        ) from None


def _remove_certificate(id: str) -> None:
    """Remove the certificate file of the server `id`, if any; OSError (LinkRefused for a
    link) when the disk refuses it."""
    project_secrets.remove_at((TOKENS, id), token_folder(id), CERTIFICATE, fixed=True)


class _Left(OSError):
    """A folder or file of the tokens the disk refused to remove: its path and why."""

    def __init__(self, path: Path, exc: OSError):
        super().__init__(exc.errno, exc.strerror)
        self.path = path
        self.why = (exc.strerror or type(exc).__name__).lower()


def _remove_token(id: str, last: bool = False) -> None:
    """Remove the token and certificate files of the server `id` and its folder, then
    git-servers/ itself once it is empty: no server's folder is left in it; _Left (Refused
    for a link) when the disk refuses it, and for a git-servers/ holding something else when
    `last` (no server is left). Otherwise a server's folder made in it at the same moment
    keeps it."""
    folder = token_folder(id)
    try:
        try:
            project_secrets.remove_at((TOKENS, id), folder, TOKEN)
        except OSError as exc:
            raise _Left(folder / TOKEN, exc) from None
        try:
            _remove_certificate(id)
        except OSError as exc:
            raise _Left(folder / CERTIFICATE, exc) from None
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
