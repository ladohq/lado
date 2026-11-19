"""A git server's certificates (openspec capability `git-servers`): the authority LADO offers
to trust for a server whose certificate this computer does not trust, and the checks of a
certificate file the human gives.

`chain` reads the certificates a server shows from a bare TLS handshake, checking nothing and
writing nothing after it, so no request and no token leaves (the private
`_sslobj.get_unverified_chain` before Python 3.13, pinned by a test). `offer` takes from it
the authority to trust: the chain's top when it signed itself, else its issuer found by the
`CA Issuers` link of each certificate (at most LINKS links, each cut at LINK_TIMEOUT and
LINK_MAX bytes, with no header but `User-Agent`, no redirect followed), a certificate kept
only when it signed the one below it; else the highest certificate held (`intermediate`), or
the server's own (`own`). It offers it only once a connection trusting it alone reaches the
server with its host name checked; a failure trust cannot fix is NoOffer with its outcome.

`context` is the TLS context of LADO's own requests to a server with a certificate: that
certificate alone, an intermediate taken as the last authority, as git's curl takes it.
`from_file` checks a file (at most MAX_FILE, a PEM certificate in it, not all expired) and
gives back the PEM LADO keeps: the certificates alone. Loaded by a check, an add and the
listing, never by an agent's launch.
"""

from __future__ import annotations

import datetime
import socket
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import AuthorityInformationAccessOID, ExtensionOID, NameOID

TIMEOUT = 5  # seconds of a handshake, its connection included
LINKS = 3  # issuer links followed at most
LINK_TIMEOUT = 5  # seconds per issuer link
LINK_MAX = 64 * 1024  # bytes of an issuer link's answer
MAX_FILE = 1024 * 1024  # bytes of a certificate file
NAME, EXPIRED, TLS = "cert_name", "cert_expired", "tls"  # NoOffer's outcomes
HOSTNAME_MISMATCH = 62  # X509_V_ERR_HOSTNAME_MISMATCH
CERT_HAS_EXPIRED = 10  # X509_V_ERR_CERT_HAS_EXPIRED


@dataclass(frozen=True)
class Certificate:
    """A certificate as the human sees it: its subject (its Common Name, else its
    organization, else its whole name), its issuer's organization ("" for none), its
    validity, the SHA-256 of its DER as colon hex, its PEM; offered, whether it is the
    server's own (`own`) or an authority below the root (`intermediate`)."""

    subject: str
    issuer: str
    not_before: datetime.datetime
    not_after: datetime.datetime
    sha256: str
    pem: str
    own: bool = False
    intermediate: bool = False

    @property
    def expired(self) -> bool:
        return self.not_after < datetime.datetime.now(datetime.timezone.utc)


class NoOffer(Exception):
    """Why no authority is offered: `outcome` NAME (the certificate is not issued for the
    host; `common_name_only` when it names it in the Common Name alone), EXPIRED (on
    `expired_on`) or TLS (`why`, the connection's or the handshake's failure)."""

    def __init__(
        self,
        outcome: str,
        why: str = "",
        common_name_only: bool = False,
        expired_on: datetime.date | None = None,
    ):
        super().__init__(why or outcome)
        self.outcome = outcome
        self.why = why
        self.common_name_only = common_name_only
        self.expired_on = expired_on


class BadFile(ValueError):
    """A certificate file LADO does not take, one line naming the file."""


def _text(name: x509.Name, oid: x509.ObjectIdentifier) -> str:
    found = name.get_attributes_for_oid(oid)
    return str(found[0].value) if found else ""


def describe(cert: x509.Certificate, own: bool = False, intermediate: bool = False) -> Certificate:
    subject = (
        _text(cert.subject, NameOID.COMMON_NAME)
        or _text(cert.subject, NameOID.ORGANIZATION_NAME)
        or cert.subject.rfc4514_string()
    )
    return Certificate(
        subject,
        _text(cert.issuer, NameOID.ORGANIZATION_NAME),
        cert.not_valid_before_utc,
        cert.not_valid_after_utc,
        ":".join(f"{byte:02X}" for byte in cert.fingerprint(hashes.SHA256())),
        cert.public_bytes(serialization.Encoding.PEM).decode(),
        own,
        intermediate,
    )


def parse(pem: str) -> list[Certificate]:
    """The certificates of a PEM text LADO wrote (`from_file`); none for one it cannot read."""
    try:
        return [describe(cert) for cert in x509.load_pem_x509_certificates(pem.encode())]
    except ValueError:
        return []


def from_file(data: bytes, name: str) -> str:
    """The PEM LADO keeps of the file `name` holding `data`: its certificates alone, in its
    order. BadFile for one larger than MAX_FILE, one with no PEM certificate, or one whose
    certificates all expired."""
    if len(data) > MAX_FILE:
        raise BadFile(f"{name} is larger than 1 MB")
    try:
        found = x509.load_pem_x509_certificates(data)
    except ValueError:
        raise BadFile(f"{name} holds no certificate") from None
    now = datetime.datetime.now(datetime.timezone.utc)
    if all(cert.not_valid_after_utc < now for cert in found):
        last = max(cert.not_valid_after_utc for cert in found)
        raise BadFile(f"{name}: the certificate expired on {last.date().isoformat()}")
    return "".join(cert.public_bytes(serialization.Encoding.PEM).decode() for cert in found)


def context(pem: str) -> ssl.SSLContext:
    """A client context trusting the certificates of `pem` alone, host names checked; the
    last authority may be below a root (an intermediate), as git's curl takes it. Python's
    strict checks of 3.13 are off, as curl has none; a host named in the Common Name alone
    is refused."""
    made = ssl.create_default_context(cadata=pem)
    made.hostname_checks_common_name = False
    made.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
    made.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)
    return made


def _unverified(tls: ssl.SSLSocket) -> list[bytes]:
    if hasattr(tls, "get_unverified_chain"):  # Python 3.13 on
        return [bytes(der) for der in tls.get_unverified_chain() or []]
    found = tls._sslobj.get_unverified_chain() or []  # type: ignore[union-attr]
    return [cert.public_bytes(ssl._ssl.ENCODING_DER) for cert in found]  # type: ignore[attr-defined]


def chain(host: str, port: int, timeout: float | None = None) -> list[bytes]:
    """The DER certificates the server at `host`:`port` shows, its own first, from a TLS
    handshake that checks nothing; nothing is written after it. OSError (ssl.SSLError among
    them) for a server not reached."""
    unchecked = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    unchecked.check_hostname = False
    unchecked.verify_mode = ssl.CERT_NONE
    with (
        socket.create_connection((host, port), TIMEOUT if timeout is None else timeout) as raw,
        unchecked.wrap_socket(raw, server_hostname=host) as tls,
    ):
        return _unverified(tls)


def _signed(cert: x509.Certificate, issuer: x509.Certificate) -> bool:
    try:
        cert.verify_directly_issued_by(issuer)
    except Exception:  # noqa: BLE001 - another name, signature or key type: not its issuer
        return False
    return True


def _self_signed(cert: x509.Certificate) -> bool:
    return cert.issuer == cert.subject and _signed(cert, cert)


def _link(cert: x509.Certificate) -> str | None:
    try:
        access = cert.extensions.get_extension_for_oid(
            ExtensionOID.AUTHORITY_INFORMATION_ACCESS
        ).value
    except x509.ExtensionNotFound:
        return None
    for item in access:
        if item.access_method == AuthorityInformationAccessOID.CA_ISSUERS:
            url = str(item.access_location.value)
            if url.lower().startswith(("http://", "https://")):
                return url
    return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _fetch(url: str) -> list[x509.Certificate]:
    """The certificates at an issuer link, DER or PEM; none for no answer, one larger than
    LINK_MAX, a redirect or anything else (a PKCS#7 bundle)."""
    opener = urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": "lado"})
    try:
        with opener.open(request, timeout=LINK_TIMEOUT) as answer:
            data = answer.read(LINK_MAX + 1)
    except (OSError, ValueError, urllib.error.URLError):
        return []
    if len(data) > LINK_MAX:
        return []
    try:
        return [x509.load_der_x509_certificate(data)]
    except ValueError:
        pass
    try:
        return x509.load_pem_x509_certificates(data)
    except ValueError:
        return []


def _top(sent: list[x509.Certificate]) -> x509.Certificate:
    """The highest authority found above the server's certificate: through the certificates
    it sent, then issuer links, each kept only when it signed the one below."""
    current = sent[0]
    links = 0
    while not _self_signed(current):
        above = next((c for c in sent if c is not current and _signed(current, c)), None)
        if above is None and links < LINKS and (url := _link(current)):
            links += 1
            above = next((c for c in _fetch(url) if _signed(current, c)), None)
        if above is None:
            break
        current = above
    return current


def _reaches(host: str, port: int, found: Certificate, sent: list[x509.Certificate]) -> None:
    """Connect to the server trusting `found` alone, host name checked; NoOffer, in the words
    of what trust cannot fix, when it fails."""
    try:
        with (
            socket.create_connection((host, port), TIMEOUT) as raw,
            context(found.pem).wrap_socket(raw, server_hostname=host),
        ):
            return
    except ssl.SSLCertVerificationError as exc:
        why = exc.verify_message or "certificate verify failed"
        leaf = sent[0]
        if exc.verify_code == HOSTNAME_MISMATCH:
            try:
                leaf.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                only_cn = False
            except x509.ExtensionNotFound:
                only_cn = True
            raise NoOffer(NAME, why, common_name_only=only_cn) from None
        if exc.verify_code == CERT_HAS_EXPIRED:
            now = datetime.datetime.now(datetime.timezone.utc)
            ended = [c.not_valid_after_utc for c in sent if c.not_valid_after_utc < now]
            when = leaf.not_valid_after_utc if leaf.not_valid_after_utc < now else min(ended)
            raise NoOffer(EXPIRED, why, expired_on=when.date()) from None
        raise NoOffer(TLS, why) from None
    except (OSError, ValueError) as exc:
        raise NoOffer(TLS, _why(exc)) from None


def _why(exc: BaseException) -> str:
    if isinstance(exc, ssl.SSLError):
        return (exc.reason or "handshake failed").lower().replace("_", " ")
    if isinstance(exc, ConnectionRefusedError):
        return "connection refused"
    if isinstance(exc, socket.gaierror):
        return "unknown host"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return f"no answer in {TIMEOUT:g} s"
    if isinstance(exc, OSError) and exc.strerror:
        return exc.strerror.lower()
    return type(exc).__name__


def offer(host: str, port: int) -> Certificate:
    """The authority to trust for the server at `host`:`port`, checked to reach it trusted
    alone. NoOffer when the server is not reached, its certificate is not issued for `host`
    or expired, or a connection trusting the authority fails otherwise."""
    try:
        ders = chain(host, port)
    except (OSError, ValueError) as exc:
        raise NoOffer(TLS, _why(exc)) from None
    try:
        sent = [x509.load_der_x509_certificate(der) for der in ders]
    except ValueError:
        sent = []
    if not sent:
        raise NoOffer(TLS, "the server sent no certificate")
    leaf = sent[0]
    top = _top(sent)
    found = describe(top, own=top is leaf, intermediate=top is not leaf and not _self_signed(top))
    _reaches(host, port, found, sent)
    return found
