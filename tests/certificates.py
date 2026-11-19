"""Certificates of test authorities made with `cryptography`, and small servers to show them:
a company's root, its intermediate and the server certificates they sign, a self-signed
server, one naming its host in the Common Name alone, an expired one, and an issuer link
(`CA Issuers`). No process trusts any of them: a test gives them to LADO itself.

`TLSServer` does a TLS handshake with each connection and keeps every byte the client sends
after it (`received`), answering nothing; `HTTPServer` serves an issuer link's file over
plain http, keeping each request's headers; tests/fake_git_api.py's server takes
`write_chain`'s files for a git server's API. Standard library and `cryptography` only.
"""

from __future__ import annotations

import datetime
import ipaddress
import socket
import ssl
import threading
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NamedTuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import AuthorityInformationAccessOID, ExtendedKeyUsageOID, NameOID

NOW = datetime.datetime.now(datetime.timezone.utc)
DAY = datetime.timedelta(days=1)


class Made(NamedTuple):
    """A certificate and its private key."""

    certificate: x509.Certificate
    key: ec.EllipticCurvePrivateKey

    @property
    def pem(self) -> str:
        return self.certificate.public_bytes(serialization.Encoding.PEM).decode()

    @property
    def der(self) -> bytes:
        return self.certificate.public_bytes(serialization.Encoding.DER)


def _name(common: str, organization: str | None) -> x509.Name:
    parts = [x509.NameAttribute(NameOID.COMMON_NAME, common)]
    if organization:
        parts.append(x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization))
    return x509.Name(parts)


def authority(
    common: str,
    organization: str | None = "Corp Example Ltd",
    issuer: Made | None = None,
    issuers_url: str | None = None,
    not_before: datetime.datetime | None = None,
    not_after: datetime.datetime | None = None,
    key: ec.EllipticCurvePrivateKey | None = None,
) -> Made:
    """An authority: a root signed by itself, or an intermediate signed by `issuer`, with
    its issuer's link `issuers_url` (`CA Issuers`) when given; `key` another authority's
    key, for a cross-signed one."""
    key = key or ec.generate_private_key(ec.SECP256R1())
    subject = _name(common, organization)
    signer = issuer.key if issuer else key
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer.certificate.subject if issuer else subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before or NOW - DAY)
        .not_valid_after(not_after or NOW + 3650 * DAY)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
    )
    if issuer:
        builder = builder.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer.key.public_key()),
            critical=False,
        )
    if issuers_url:
        builder = builder.add_extension(_issuers(issuers_url), critical=False)
    return Made(builder.sign(signer, hashes.SHA256()), key)


def _issuers(url: str) -> x509.AuthorityInformationAccess:
    return x509.AuthorityInformationAccess(
        [
            x509.AccessDescription(
                AuthorityInformationAccessOID.CA_ISSUERS, x509.UniformResourceIdentifier(url)
            )
        ]
    )


def server(
    host: str,
    issuer: Made | None,
    *,
    names: tuple[str, ...] | None = None,
    issuers_url: str | None = None,
    not_before: datetime.datetime | None = None,
    not_after: datetime.datetime | None = None,
) -> Made:
    """A server's certificate for `host` (its Common Name), signed by `issuer` (None: by
    itself); `names` its subjectAltName (None: `host`; empty: none, the Common Name alone)."""
    key = ec.generate_private_key(ec.SECP256R1())
    subject = _name(host, None)
    names = (host,) if names is None else names
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer.certificate.subject if issuer else subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before or NOW - DAY)
        .not_valid_after(not_after or NOW + 365 * DAY)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
    )
    if names:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([_general_name(name) for name in names]), critical=False
        )
    if issuer:
        builder = builder.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer.key.public_key()),
            critical=False,
        )
    if issuers_url:
        builder = builder.add_extension(_issuers(issuers_url), critical=False)
    return Made(builder.sign(issuer.key if issuer else key, hashes.SHA256()), key)


def _general_name(name: str) -> x509.GeneralName:
    try:
        return x509.IPAddress(ipaddress.ip_address(name))
    except ValueError:
        return x509.DNSName(name)


def write_chain(folder: Path, leaf: Made, *sent: Made) -> tuple[Path, Path]:
    """The server's certificate followed by the authorities it sends, and its key, as files
    for `ssl.SSLContext.load_cert_chain`."""
    folder.mkdir(parents=True, exist_ok=True)
    cert, key = folder / "server.pem", folder / "server.key"
    cert.write_text(leaf.pem + "".join(made.pem for made in sent))
    key.write_bytes(
        leaf.key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert, key


def write_pem(path: Path, *made: Made) -> Path:
    path.write_text("".join(m.pem for m in made))
    return path


def _server_context(chain: tuple[Path, Path]) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(*chain)
    return context


class TLSServer:
    """A TLS server on 127.0.0.1, a free port, that shows `chain` (write_chain's files) to
    each connection and keeps what the client writes after the handshake in `received`."""

    def __init__(self, chain: tuple[Path, Path]):
        self.context = _server_context(chain)
        self.received = b""
        self.handshakes = 0
        self.done = threading.Event()  # a connection ended
        self._listener = socket.create_server(("127.0.0.1", 0))
        self.port = self._listener.getsockname()[1]
        self._closing = threading.Event()
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while not self._closing.is_set():
            try:
                client, _ = self._listener.accept()
            except OSError:
                return
            threading.Thread(target=self._one, args=(client,), daemon=True).start()

    def _one(self, client: socket.socket) -> None:
        client.settimeout(5)
        try:
            with self.context.wrap_socket(client, server_side=True) as tls:
                self.handshakes += 1
                while data := tls.recv(4096):
                    self.received += data
        except (OSError, ssl.SSLError):
            pass
        finally:
            self.done.set()

    def close(self) -> None:
        self._closing.set()
        self._listener.close()


class Request(NamedTuple):
    path: str
    headers: Message


class HTTPServer:
    """A plain http server on 127.0.0.1, a free port, serving `files` (path → bytes, filled
    after the start too) as an issuer link does; each request in `requests`."""

    def __init__(self, *, files: dict[str, bytes]):
        self.requests: list[Request] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                fake.requests.append(Request(self.path, self.headers))
                data, status = (files[self.path], 200) if self.path in files else (b"", 404)
                self.send_response(status)
                self.send_header("Content-Type", "application/pkix-cert")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
