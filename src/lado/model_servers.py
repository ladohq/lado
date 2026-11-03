"""What a model server is, from its address: its type, its models and the agent CLIs that
can use it (`lado model-server probe`).

A probe sends at most one request per check and none that generates: the model list
first, alone; when it got an HTTP answer, at once Ollama's and LM Studio's own endpoints,
the model list in Anthropic's way, one POST with the body `{}` per API and a control POST
to a path no server has, eight at most. Only the POSTs and the list in Anthropic's way carry
`anthropic-version`: the type and the models come from the list asked without it, and the
other only fills a gap, as a gateway of both APIs lists in Anthropic's shape with it. A POST
proves its API when the server refuses the empty body with 400 or 422 and a JSON object,
unless the control is refused the same way: then the server answers every POST alike and
proves nothing. Each request is cut at TIMEOUT, its name lookup included; no redirect is
followed, so neither a request nor the key reaches another host. The CLIs that suit a
server follow from the APIs it proved, by each provider's `server_api`; its type is only
shown. The key goes in the requests' headers and nowhere else: no message is built from
a request's headers.
"""

from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass

import lado
from lado import providers, update
from lado import text as visible
from lado.providers import base

TIMEOUT = 5  # seconds per request, its name lookup included
MAX_ANSWER = 4 * 1024 * 1024  # bytes of an answer read; a longer list is no list
TOO_LARGE = "the answer is larger than 4 MiB"

OLLAMA = "Ollama"
LMSTUDIO = "LM Studio"
OPENAI = "OpenAI-compatible"
ANTHROPIC = "Anthropic-compatible"

MODELS = "/v1/models"
OLLAMA_VERSION = "/api/version"
LMSTUDIO_MODELS = "/api/v0/models"
API_PATHS = {
    base.CHAT_COMPLETIONS: "/v1/chat/completions",
    base.RESPONSES: "/v1/responses",
    base.ANTHROPIC_MESSAGES: "/v1/messages",
}
CONTROL = "/v1/lado-no-such-api"  # no server has it: an API's answer here proves nothing
# Anthropic's API wants it; a gateway of both APIs (LiteLLM) lists its models in Anthropic's
# shape when it is sent, so the plain list request goes without it.
ANTHROPIC_VERSION = {"anthropic-version": "2023-06-01"}

PROBE_COMMAND = "lado model-server probe"
CONTAINER_HINT = (
    "LADO runs in a container, where localhost is the container itself; a server on your "
    "machine: {command} {address} (not tried)"
)
# Hosts a key may go to over plain http://: the human's own machine (seen from LADO's
# container too) and, by address, loopback, private and link-local networks. A name is never
# resolved for the rule: it would depend on the network and send the name out.
LOCAL_HOSTS = ("localhost", "host.docker.internal")
PLAIN_HTTP = (
    "the key goes to {host} over plain http://, unencrypted; use https:// if the server has it"
)


ADDRESS, KEY = "address", "key"  # the field a ProbeError concerns


class ProbeError(Exception):
    """Why a probe found no server, one line; `hint` what the human can try ("" for none);
    `field` the field of a form it concerns (ADDRESS or KEY), for the UI; `page` and
    `page_hint` the line and the hint for the UI, which name no command (None: the same)."""

    def __init__(
        self,
        text: str,
        hint: str = "",
        field: str = ADDRESS,
        page: str | None = None,
        page_hint: str | None = None,
    ):
        super().__init__(text)
        self.hint = hint
        self.field = field
        self.page = text if page is None else page
        self.page_hint = hint if page_hint is None else page_hint


@dataclass(frozen=True)
class Answer:
    """One request's answer: its status, or why there is none (`why`, `tls`)."""

    status: int | None = None
    body: object = None  # the JSON it held; None for none or one too large
    too_large: bool = False
    location: str = ""  # a redirect's, without its query
    why: str = ""
    tls: bool = False

    def said(self) -> str:
        """The answer in a message: its status, a redirect with where it points."""
        if self.location:
            return f"{self.status} to {self.location}"
        return str(self.status)

    def refuses_as_an_api(self) -> bool:
        return self.status in (400, 422) and isinstance(self.body, dict)


@dataclass(frozen=True)
class Probe:
    """A server a probe recognised. `models` is None for no list, with why in `models_why`;
    `apis_why` says why no API could be told, "" when they could; `embeddings` the models the
    server types as embeddings (LM Studio's own list), none for a server that types none."""

    address: str
    added_scheme: bool
    kind: str
    apis: frozenset[str]
    models: tuple[str, ...] | None
    models_why: str = ""
    apis_why: str = ""
    embeddings: frozenset[str] = frozenset()

    def clis(self) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        return clis(self.apis)


Suiting = list[tuple[providers.Provider, str]]


def suiting(apis: Iterable[str]) -> tuple[Suiting, Suiting]:
    """The (provider, API) of each CLI that can use a server proving `apis` and of each that
    cannot, by the API its provider declares, in the order of base.SERVER_APIS, then of the
    registry; a provider that declares none is left out."""
    apis = frozenset(apis)
    suits: Suiting = []
    not_suits: Suiting = []
    for api in base.SERVER_APIS:
        for name in providers.names():
            provider = providers.get(name)
            if provider.server_api == api:
                (suits if api in apis else not_suits).append((provider, api))
    return suits, not_suits


def clis(apis: Iterable[str]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """`suiting` with each CLI's title: (title, API)."""
    suits, not_suits = suiting(apis)
    return [(p.title, api) for p, api in suits], [(p.title, api) for p, api in not_suits]


def address(text: str) -> tuple[str, bool]:
    """The root of a server's address, and whether `http://` was added to it; ValueError
    for one LADO does not probe. The text of an error never holds the address: it may hold a
    password."""
    text = text.strip()
    if not text:
        raise ValueError("no address given")
    added = "://" not in text
    if added:
        text = "http://" + text
    try:
        # urllib's own refusals (a bad bracketed host, a character NFKC changes) name the
        # address: a fixed text instead.
        parts = urllib.parse.urlsplit(text)
        hostname = parts.hostname
    except ValueError:
        raise ValueError("not an address of a server (http://host:port/path)") from None
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError("a server's address starts with http:// or https://")
    if "@" in parts.netloc:
        raise ValueError(
            "a server's address holds no user or password (it would be printed); its key: --key"
        )
    if parts.query:
        raise ValueError("a server's address holds no query")
    if parts.fragment:
        raise ValueError("a server's address holds no fragment")
    if not hostname:
        raise ValueError("the address names no host")
    try:
        parts.port  # noqa: B018 - raises for a port out of range
    except ValueError:
        raise ValueError("the address's port is not a number from 0 to 65535") from None
    path = parts.path.rstrip("/").removesuffix("/v1").rstrip("/")
    return f"{scheme}://{parts.netloc}{path}", added


NOT_CARRIABLE = "the key holds a character no HTTP header can carry"


def carriable(key: str) -> bool:
    """Whether every character of `key` can go in an HTTP header (printable Latin-1): not a
    control character, nor one of no Latin-1 byte (a surrogate for a byte of no UTF-8)."""
    return all(" " <= c <= "~" or "\xa0" <= c <= "\xff" for c in key)


def plain_http_warning(root: str, key: str | None) -> str | None:
    """The warning for a key sent over plain http:// to the server at `root` (an
    `address`'s root) that is not on the human's machine or network; None for none."""
    parts = urllib.parse.urlsplit(root)
    if key is None or parts.scheme != "http":
        return None
    host = parts.hostname or ""
    if host in LOCAL_HOSTS:
        return None
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return PLAIN_HTTP.format(host=host)
    if ip.is_loopback or ip.is_private or ip.is_link_local:
        return None
    return PLAIN_HTTP.format(host=host)


def probe(
    text: str,
    key: str | None = None,
    command: str = PROBE_COMMAND,
    key_where: str = "enter it in Key",
) -> Probe:
    """What the server at `text` is; ValueError for an address LADO does not probe,
    ProbeError for one that does not answer, asks for a key, refuses it, or is no model
    server LADO knows. `command` is the command run, without its address, for the messages
    that name one to run again; `key_where` where the UI takes a key, for its line."""
    root, added = address(text)
    if key is not None and not carriable(key):
        raise ProbeError(NOT_CARRIABLE, field=KEY)
    headers = {"Accept": "application/json", "User-Agent": f"lado/{lado.__version__}"}
    if key is not None:
        headers |= {"Authorization": f"Bearer {key}", "x-api-key": key}
    opener = urllib.request.build_opener(_NoRedirect())
    (listed,) = _all(opener, [(root + MODELS, "GET", {})], headers)
    if listed.status is None:
        if listed.tls:
            raise ProbeError(
                f"{root}: TLS failed ({listed.why}); a company's CA goes in the file "
                "SSL_CERT_FILE names"
            )
        raise ProbeError(
            f"{root} does not answer ({listed.why})",
            _container_hint(root, command),
            page_hint=_container_hint(root, None),
        )
    asked = [
        (root + OLLAMA_VERSION, "GET", {}),
        (root + LMSTUDIO_MODELS, "GET", {}),
        (root + MODELS, "GET", ANTHROPIC_VERSION),
    ]
    asked += [(root + path, "POST", ANTHROPIC_VERSION) for path in [*API_PATHS.values(), CONTROL]]
    version, lmstudio, versioned, *posts, control = _all(opener, asked, headers)
    for answer in (listed, version, lmstudio, versioned, *posts, control):
        if answer.status in (401, 403):
            if key is None:
                raise ProbeError(
                    f"{root} asks for a key ({answer.status}): run {command} {root} --key",
                    field=KEY,
                    page=f"{root} asks for a key ({answer.status}): {key_where}",
                )
            raise ProbeError(f"{root} refused the key ({answer.status})", field=KEY)
    apis = frozenset(api for api, a in zip(API_PATHS, posts, strict=True) if a.refuses_as_an_api())
    apis_why = ""
    if control.refuses_as_an_api():
        apis, apis_why = frozenset(), f"{root} answers {control.status} to any POST"
    models, models_why = _models(listed)
    if models is None and _anthropic_shaped(versioned):
        models, models_why = _models(versioned)
    kind = _kind(listed, versioned, version, lmstudio, apis)
    if kind is None:
        why = f"GET {MODELS}: {listed.said()}"
        if apis_why:
            why += f"; it answers {control.status} to any POST, so its APIs cannot be told"
        raise ProbeError(
            f"unknown server: {root} answered, but not as an OpenAI-compatible, "
            f"Anthropic-compatible, Ollama or LM Studio server ({why})"
        )
    return Probe(root, added, kind, apis, models, models_why, apis_why, _embeddings(lmstudio))


def lines(found: Probe) -> list[str]:
    """What `lado model-server probe` prints for a server it recognised."""
    out = [
        found.address + (" (added http://)" if found.added_scheme else ""),
        f"type: {found.kind}",
    ]
    if found.models is None:
        out.append(f"models: no list ({found.models_why})")
    else:
        shown = [m + (" (embeddings)" if m in found.embeddings else "") for m in found.models]
        out.append(f"models: {', '.join(shown) or 'none'}")
    if found.apis_why:
        out.append(f"APIs: cannot be told: {found.apis_why}")
    suits, not_suits = found.clis()
    groups = []
    for api in base.SERVER_APIS:
        titles = [title for title, of in suits if of == api]
        if titles:
            groups.append(f"{', '.join(titles)} ({api})")
    out.append(f"CLIs: {'; '.join(groups) or 'none'}")
    if not_suits:
        out.append("not: " + ", ".join(f"{title} (no {api})" for title, api in not_suits))
    return out


def _models(listed: Answer) -> tuple[tuple[str, ...] | None, str]:
    """The models of a list's answer, or None and why there is none."""
    if listed.status != 200:
        return None, f"GET {MODELS}: {listed.said()}"
    if listed.too_large:
        return None, TOO_LARGE
    data = listed.body.get("data") if isinstance(listed.body, dict) else None
    if not isinstance(data, list):
        return None, f"GET {MODELS}: 200, not a list of models"
    ids = (item.get("id") for item in data if isinstance(item, dict))
    # The server's words: one line of visible text each, so none forges a line or drives
    # the terminal (lado.text).
    return tuple(visible.one_line(i) for i in ids if isinstance(i, str)), ""


def _embeddings(lmstudio: Answer) -> frozenset[str]:
    """The ids LM Studio's own list types `embeddings`, one line of visible text each as
    `_models` makes them; none for any other answer."""
    data = _listing(lmstudio) or []
    return frozenset(
        visible.one_line(i["id"])
        for i in data
        if isinstance(i, dict) and i.get("type") == "embeddings" and isinstance(i.get("id"), str)
    )


def _listing(answer: Answer) -> list | None:
    """The items of a model list's answer, None for no list."""
    if answer.status == 200 and isinstance(answer.body, dict):
        data = answer.body.get("data")
        if isinstance(data, list):
            return data
    return None


def _anthropic_shaped(answer: Answer) -> bool:
    """Whether a model list's answer is a list in Anthropic's shape: an item of `"type":
    "model"`, or `has_more`."""
    data = _listing(answer)
    if data is None:
        return False
    typed = any(isinstance(i, dict) and i.get("type") == "model" for i in data)
    return typed or "has_more" in answer.body


def _kind(
    listed: Answer, versioned: Answer, version: Answer, lmstudio: Answer, apis: frozenset[str]
) -> str | None:
    """The server's type, None for none LADO knows: by the list asked without
    anthropic-version (`listed`) first; the one asked with it (`versioned`) only when that
    gives none, so a gateway of both APIs is not read as Anthropic's."""
    if version.status == 200 and isinstance(version.body, dict):
        if isinstance(version.body.get("version"), str):
            return OLLAMA
    if _listing(lmstudio) is not None:
        return LMSTUDIO
    if _listing(listed) is not None:
        return ANTHROPIC if _anthropic_shaped(listed) else OPENAI
    if _anthropic_shaped(versioned):
        return ANTHROPIC
    if base.ANTHROPIC_MESSAGES in apis:
        return ANTHROPIC
    if apis:
        return OPENAI
    return None


def _container_hint(root: str, command: str | None) -> str:
    """In LADO's container, for a localhost address: the host's address to try instead with
    `command` (None: the address alone, for the UI)."""
    if not update.in_container():
        return ""
    parts = urllib.parse.urlsplit(root)
    host = parts.hostname or ""
    if host != "localhost":
        try:
            if not ipaddress.ip_address(host).is_loopback:
                return ""
        except ValueError:
            return ""
    port = parts.port or (443 if parts.scheme == "https" else 80)
    address = f"{parts.scheme}://host.docker.internal:{port}{parts.path}"
    if command is None:
        return CONTAINER_HINT.replace("{command} ", "").format(address=address)
    return CONTAINER_HINT.format(command=command, address=address)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Follows nothing: a redirect is an answer (urllib's own handler would send the key's
    headers on to the host it names). It does not read the location either, which urllib's
    would refuse with an error of its own: the 3xx goes on to be an HTTPError."""

    def http_error_302(self, *args, **kwargs):
        return None

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def _all(
    opener, asked: list[tuple[str, str, dict[str, str]]], headers: dict[str, str]
) -> list[Answer]:
    """The answers to `asked` (url, method, headers of its own beside `headers`), all at
    once, each within TIMEOUT: a request still waiting then, on its name lookup too, is left
    to its daemon thread."""
    answers: list[Answer | None] = [None] * len(asked)

    def ask(i: int, url: str, method: str, own: dict[str, str]) -> None:
        answers[i] = _ask(opener, url, method, headers | own)

    threads = [
        threading.Thread(target=ask, args=(i, url, method, own), daemon=True)
        for i, (url, method, own) in enumerate(asked)
    ]
    deadline = time.monotonic() + TIMEOUT
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(max(0, deadline - time.monotonic()))
    late = Answer(why=f"no answer in {TIMEOUT:g} s")
    return [answer or late for answer in answers]


def _ask(opener, url: str, method: str, headers: dict[str, str]) -> Answer:
    """One request's answer; never raises. A POST's body is `{}`."""
    data = b"{}" if method == "POST" else None
    sent = dict(headers, **({"Content-Type": "application/json"} if data else {}))
    request = urllib.request.Request(url, data=data, method=method, headers=sent)
    try:
        with opener.open(request, timeout=TIMEOUT) as answer:
            return _read(answer.status, answer, "")
    except urllib.error.HTTPError as e:
        location = ""
        if 300 <= e.code < 400 and e.headers.get("Location"):
            try:
                parts = urllib.parse.urlsplit(e.headers["Location"])
                location = visible.one_line(parts._replace(query="", fragment="").geturl())
            except ValueError:
                location = "a location that is not a URL"
        with e:
            return _read(e.code, e, location)
    except urllib.error.URLError as e:
        return _no_answer(e.reason)
    except Exception as e:  # noqa: BLE001 - a broken answer is no answer, never a crash
        return _no_answer(e)


def _read(status: int, answer, location: str) -> Answer:
    try:
        raw = answer.read(MAX_ANSWER + 1)
    except (OSError, http.client.HTTPException):
        raw = b""
    if len(raw) > MAX_ANSWER:
        return Answer(status, too_large=True, location=location)
    try:
        body = json.loads(raw)
    except ValueError:
        body = None
    return Answer(status, body, location=location)


def _no_answer(reason: object) -> Answer:
    """Why there is no HTTP answer, in words: never from a request's headers."""
    if isinstance(reason, ssl.SSLCertVerificationError):
        return Answer(why=reason.verify_message or "certificate verify failed", tls=True)
    if isinstance(reason, ssl.SSLError):
        return Answer(why=(reason.reason or "handshake failed").lower().replace("_", " "), tls=True)
    if isinstance(reason, ConnectionRefusedError):
        return Answer(why="connection refused")
    if isinstance(reason, socket.gaierror):
        return Answer(why="unknown host")
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return Answer(why=f"no answer in {TIMEOUT:g} s")
    if isinstance(reason, ConnectionResetError):
        return Answer(why="connection reset")
    if isinstance(reason, http.client.HTTPException):
        return Answer(why="not an HTTP answer")
    if isinstance(reason, OSError) and reason.strerror:
        return Answer(why=reason.strerror.lower())
    return Answer(why=type(reason).__name__)
