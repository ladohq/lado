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
proves nothing. Each request is cut at TIMEOUT, its name lookup included; a POST with no
answer then goes once more, cut at LATE_TIMEOUT, and an API still silent is neither proven
nor missing (`Probe.late`). No redirect is
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
from collections.abc import Collection, Iterable
from dataclasses import dataclass

import lado
from lado import providers, update
from lado import text as visible
from lado.providers import base

TIMEOUT = 5  # seconds per request, its name lookup included
LATE_TIMEOUT = 15  # seconds for a POST asked again: a first TLS connection, a model being loaded
LIMIT_TIMEOUT = 2  # seconds for a model's context at a start, which waits for it
MAX_ANSWER = 4 * 1024 * 1024  # bytes of an answer read; a longer list is no list
TOO_LARGE = "the answer is larger than 4 MiB"
LATE = "did not answer in time"  # an API whose POST got no answer even the second time

OLLAMA = "Ollama"
LMSTUDIO = "LM Studio"
OPENAI = "OpenAI-compatible"
ANTHROPIC = "Anthropic-compatible"

API_BASE = "/v1"
MODELS = f"{API_BASE}/models"
OLLAMA_VERSION = "/api/version"
LMSTUDIO_MODELS = "/api/v0/models"
OLLAMA_RUNNING = "/api/ps"
API_PATHS = {
    base.CHAT_COMPLETIONS: "/v1/chat/completions",
    base.RESPONSES: "/v1/responses",
    base.ANTHROPIC_MESSAGES: "/v1/messages",
}
CONTROL = "/v1/lado-no-such-api"  # no server has it: an API's answer here proves nothing
# A context in a model list, first what a gateway says of the prompt alone (LiteLLM), then
# cloud.ru's and OpenRouter's field, then vLLM's.
LISTED_CONTEXT = ("max_input_tokens", "context_length", "max_model_len")
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
    `page_hint` the line and the hint for the UI, which name no command (None: the same);
    `silent` why the server does not answer ("" for one that does)."""

    def __init__(
        self,
        text: str,
        hint: str = "",
        field: str = ADDRESS,
        page: str | None = None,
        page_hint: str | None = None,
        silent: str = "",
    ):
        super().__init__(text)
        self.silent = silent
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
    server types as embeddings (LM Studio's own list), none for a server that types none; `late`
    the APIs whose POST got no answer either time."""

    address: str
    added_scheme: bool
    kind: str
    apis: frozenset[str]
    models: tuple[str, ...] | None
    models_why: str = ""
    apis_why: str = ""
    embeddings: frozenset[str] = frozenset()
    late: frozenset[str] = frozenset()

    def clis(self) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        return clis(self.apis)

    def late_warning(self) -> str | None:
        """What to tell of the `late` APIs when the server is saved; None for none."""
        if not self.late:
            return None
        return f"{late_words(self.late)} of {self.address} {LATE}: try again"


def late_words(apis: Collection[str]) -> str:
    """The APIs that did not answer, in a sentence."""
    return "the " + ", ".join(api for api in API_PATHS if api in apis)


Suiting = list[tuple[providers.Provider, str]]


def suiting(apis: Iterable[str]) -> tuple[Suiting, Suiting]:
    """The (provider, API) of each CLI that can use a server proving `apis` and of each that
    cannot, by the API its provider declares, in the registry's order (LADO's one order of
    the CLIs); a provider that declares none of base.SERVER_APIS is left out."""
    apis = frozenset(apis)
    suits: Suiting = []
    not_suits: Suiting = []
    for name in providers.names():
        provider = providers.get(name)
        api = provider.server_api
        if api in base.SERVER_APIS:
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


def base_url(root: str) -> str:
    """The OpenAI-compatible base URL of the server at `root` (an `address`'s root)."""
    return root + API_BASE


def is_local(root: str) -> bool:
    """Whether the server at `root` (an `address`'s root) is on the human's machine or network."""
    host = urllib.parse.urlsplit(root).hostname or ""
    if host in LOCAL_HOSTS:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


def plain_http_warning(root: str, key: str | None) -> str | None:
    """The warning for a key sent over plain http:// to the server at `root` (an
    `address`'s root) that is not on the human's machine or network; None for none."""
    parts = urllib.parse.urlsplit(root)
    if key is None or parts.scheme != "http" or is_local(root):
        return None
    return PLAIN_HTTP.format(host=parts.hostname or "")


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
    headers = _headers(key)
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
            silent=listed.why,
        )
    asked = [
        (root + OLLAMA_VERSION, "GET", {}),
        (root + LMSTUDIO_MODELS, "GET", {}),
        (root + MODELS, "GET", ANTHROPIC_VERSION),
    ]
    asked += [(root + path, "POST", ANTHROPIC_VERSION) for path in [*API_PATHS.values(), CONTROL]]
    version, lmstudio, versioned, *posts = _all(opener, asked, headers)
    *posts, control = _with_late_posts(opener, asked[-len(posts) :], posts, headers)
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
    late = frozenset(api for api, a in zip(API_PATHS, posts, strict=True) if a.status is None)
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
        if late:
            why += f"; {late_words(late)} {LATE}"
        raise ProbeError(
            f"unknown server: {root} answered, but not as an OpenAI-compatible, "
            f"Anthropic-compatible, Ollama or LM Studio server ({why})"
        )
    return Probe(root, added, kind, apis, models, models_why, apis_why, _embeddings(lmstudio), late)


def _with_late_posts(
    opener, asked: list[tuple[str, str, dict[str, str]]], posts: list[Answer], headers
) -> list[Answer]:
    """`posts`, the answers to `asked`, with each that got none asked once more."""
    late = [i for i, answer in enumerate(posts) if answer.status is None]
    if not late:
        return posts
    answers = _all(opener, [asked[i] for i in late], headers, LATE_TIMEOUT)
    again = dict(zip(late, answers, strict=True))
    return [again.get(i, answer) for i, answer in enumerate(posts)]


def context_limits(root: str, key: str | None) -> dict[str, base.Limit]:
    """What the server at `root` reports of its models' context, by model, in three GETs at once
    within LIMIT_TIMEOUT; none for a model it says nothing of, or a server that does not answer.
    Each answer is read by its shape, as a gateway hides what it fronts: LM Studio's loaded
    context and Ollama's running model, what a model has now and not what it could take, and
    a gateway's list. A start waits for this: it never raises."""
    asked = [(root + path, "GET", {}) for path in (MODELS, OLLAMA_RUNNING, LMSTUDIO_MODELS)]
    opener = urllib.request.build_opener(_NoRedirect())
    listed, running, lmstudio = _all(opener, asked, _headers(key), LIMIT_TIMEOUT)
    return {**_listed_limits(listed), **_running_limits(running), **_loaded_limits(lmstudio)}


def _tokens(value: object) -> int | None:
    """A number of tokens, None for anything else; LiteLLM may give a whole float."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _output(item: dict) -> int | None:
    """The output a list's `item` reports: a gateway's field, else OpenRouter's."""
    top = item.get("top_provider")
    nested = top.get("max_completion_tokens") if isinstance(top, dict) else None
    return _tokens(item.get("max_output_tokens")) or _tokens(nested)


def _limits(items: list, name: str, *contexts: str) -> dict[str, base.Limit]:
    """The limits of a list's `items`: a model's id under `name`, as `_models` makes it, its
    context the first of `contexts` that is a number of tokens."""
    found = {}
    for item in items:
        if isinstance(item, dict) and isinstance(item.get(name), str):
            tokens = next(filter(None, (_tokens(item.get(c)) for c in contexts)), None)
            if tokens is not None:
                found[visible.one_line(item[name])] = base.Limit(tokens, _output(item))
    return found


def _listed_limits(listed: Answer) -> dict[str, base.Limit]:
    return _limits(_listing(listed) or [], "id", *LISTED_CONTEXT)


def _running_limits(running: Answer) -> dict[str, base.Limit]:
    models = running.body.get("models") if isinstance(running.body, dict) else None
    if running.status != 200 or not isinstance(models, list):
        return {}
    return _limits(models, "name", "context_length")


def _loaded_limits(lmstudio: Answer) -> dict[str, base.Limit]:
    loaded = [
        i for i in _listing(lmstudio) or [] if isinstance(i, dict) and i.get("state") == "loaded"
    ]
    return _limits(loaded, "id", "loaded_context_length")


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
    for api in dict.fromkeys(of for _, of in suits):  # each API where its first CLI comes
        titles = [title for title, of in suits if of == api]
        groups.append(f"{', '.join(titles)} ({api})")
    out.append(f"CLIs: {'; '.join(groups) or 'none'}")
    if not_suits:
        said = [
            f"{title} ({api} {LATE})" if api in found.late else f"{title} (no {api})"
            for title, api in not_suits
        ]
        out.append("not: " + ", ".join(said))
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


def _headers(key: str | None) -> dict[str, str]:
    headers = {"Accept": "application/json", "User-Agent": f"lado/{lado.__version__}"}
    if key is not None:
        headers |= {"Authorization": f"Bearer {key}", "x-api-key": key}
    return headers


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Follows nothing: a redirect is an answer (urllib's own handler would send the key's
    headers on to the host it names). It does not read the location either, which urllib's
    would refuse with an error of its own: the 3xx goes on to be an HTTPError."""

    def http_error_302(self, *args, **kwargs):
        return None

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def _all(
    opener,
    asked: list[tuple[str, str, dict[str, str]]],
    headers: dict[str, str],
    timeout: float | None = None,
) -> list[Answer]:
    """The answers to `asked` (url, method, headers of its own beside `headers`), all at
    once, each within `timeout` (None: TIMEOUT): a request still waiting then, on its name
    lookup too, is left to its daemon thread."""
    timeout = TIMEOUT if timeout is None else timeout
    answers: list[Answer | None] = [None] * len(asked)

    def ask(i: int, url: str, method: str, own: dict[str, str]) -> None:
        answers[i] = _ask(opener, url, method, headers | own, timeout)

    threads = [
        threading.Thread(target=ask, args=(i, url, method, own), daemon=True)
        for i, (url, method, own) in enumerate(asked)
    ]
    deadline = time.monotonic() + timeout
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(max(0, deadline - time.monotonic()))
    late = Answer(why=f"no answer in {timeout:g} s")
    return [answer or late for answer in answers]


def _ask(opener, url: str, method: str, headers: dict[str, str], timeout: float) -> Answer:
    """One request's answer; never raises. A POST's body is `{}`."""
    data = b"{}" if method == "POST" else None
    sent = dict(headers, **({"Content-Type": "application/json"} if data else {}))
    request = urllib.request.Request(url, data=data, method=method, headers=sent)
    try:
        with opener.open(request, timeout=timeout) as answer:
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
