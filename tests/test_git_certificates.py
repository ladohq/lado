"""lado.git_certificates: a server's chain from a bare TLS handshake, the authority it offers
to trust (root, by an issuer link, the highest sent, the server's own), the check that it
works, what trust cannot fix, and a certificate file's checks. Servers run in process under
test authorities made by tests/certificates.py; no process trusts them."""

from __future__ import annotations

import datetime
import socket
import ssl
import sys

import certificates as made
import pytest

from lado import git_certificates


@pytest.fixture
def start():
    started = []

    def run(server):
        started.append(server)
        return server

    yield run
    for server in started:
        server.close()


@pytest.fixture
def corp():
    root = made.authority("Corp Root CA")
    issuing = made.authority("Corp Issuing CA 2", issuer=root)
    return root, issuing


def _tls(start, tmp_path, leaf, *sent):
    return start(made.TLSServer(made.write_chain(tmp_path / "chain", leaf, *sent)))


def test_python_gives_the_unverified_chain_on_this_version():
    """The chain is read through a private method before 3.13: pinned on every CI Python."""
    if sys.version_info >= (3, 13):
        assert hasattr(ssl.SSLSocket, "get_unverified_chain")
    else:
        assert hasattr(ssl._ssl._SSLSocket, "get_unverified_chain")
        assert hasattr(ssl._ssl, "ENCODING_DER")


def test_the_chain_is_read_from_a_handshake_and_nothing_is_sent_after_it(start, tmp_path, corp):
    root, issuing = corp
    leaf = made.server("localhost", issuing)
    server = _tls(start, tmp_path, leaf, issuing, root)
    chain = git_certificates.chain("localhost", server.port)
    assert chain == [leaf.der, issuing.der, root.der]
    assert server.done.wait(5)
    assert server.handshakes == 1
    assert server.received == b""


def test_a_root_the_server_sends_is_offered(start, tmp_path, corp):
    root, issuing = corp
    server = _tls(start, tmp_path, made.server("localhost", issuing), issuing, root)
    offer = git_certificates.offer("localhost", server.port)
    assert offer.pem == root.pem
    assert (offer.subject, offer.issuer) == ("Corp Root CA", "Corp Example Ltd")
    assert not offer.own and not offer.intermediate
    assert offer.not_after.date() == root.certificate.not_valid_after_utc.date()
    fingerprint = root.certificate.fingerprint(git_certificates.hashes.SHA256())
    assert offer.sha256 == ":".join(f"{b:02X}" for b in fingerprint)
    assert server.received == b""


def test_a_root_is_found_by_the_issuer_link_without_a_token(start, tmp_path, corp):
    root, _ = corp
    files: dict[str, bytes] = {}
    pki = start(made.HTTPServer(files=files))
    issuing = made.authority("Corp Issuing CA 2", issuer=root, issuers_url=f"{pki.url}/root.crt")
    files["/root.crt"] = root.der
    server = _tls(start, tmp_path, made.server("localhost", issuing), issuing)
    offer = git_certificates.offer("localhost", server.port)
    assert offer.pem == root.pem
    assert not offer.intermediate
    assert [r.path for r in pki.requests] == ["/root.crt"]
    headers = {name.lower() for name in pki.requests[0].headers}
    assert "authorization" not in headers and "private-token" not in headers
    assert pki.requests[0].headers["User-Agent"] == "lado"


def test_an_issuer_link_in_pem_is_taken_too(start, tmp_path, corp):
    root, _ = corp
    files: dict[str, bytes] = {}
    pki = start(made.HTTPServer(files=files))
    issuing = made.authority("Corp Issuing CA 2", issuer=root, issuers_url=f"{pki.url}/root.pem")
    files["/root.pem"] = root.pem.encode()
    server = _tls(start, tmp_path, made.server("localhost", issuing), issuing)
    assert git_certificates.offer("localhost", server.port).pem == root.pem


def test_a_certificate_at_the_link_that_did_not_sign_is_not_taken(start, tmp_path, corp):
    root, _ = corp
    other = made.authority("Other Root")
    files: dict[str, bytes] = {}
    pki = start(made.HTTPServer(files=files))
    issuing = made.authority("Corp Issuing CA 2", issuer=root, issuers_url=f"{pki.url}/root.crt")
    files["/root.crt"] = other.der
    server = _tls(start, tmp_path, made.server("localhost", issuing), issuing)
    offer = git_certificates.offer("localhost", server.port)
    assert offer.pem == issuing.pem
    assert offer.intermediate


def test_an_offer_through_two_links_reaches_the_server(start, tmp_path):
    files: dict[str, bytes] = {}
    pki = start(made.HTTPServer(files=files))
    root = made.authority("Corp Root CA")
    middle = made.authority("Corp Policy CA", issuer=root, issuers_url=f"{pki.url}/root")
    issuing = made.authority("Corp Issuing CA", issuer=middle, issuers_url=f"{pki.url}/middle")
    files["/root"], files["/middle"] = root.der, middle.der
    server = _tls(start, tmp_path, made.server("localhost", issuing), issuing, middle)
    offer = git_certificates.offer("localhost", server.port)
    assert offer.subject == "Corp Root CA"
    assert [r.path for r in pki.requests] == ["/root"]  # the middle one was sent


def test_the_issuer_links_are_followed_three_times_at_most(start, tmp_path):
    files: dict[str, bytes] = {}
    pki = start(made.HTTPServer(files=files))
    top = made.authority("CA 0")
    chain = [top]
    for i in range(1, 6):  # each links its issuer
        chain.append(made.authority(f"CA {i}", issuer=chain[-1], issuers_url=f"{pki.url}/{i - 1}"))
        files[f"/{i - 1}"] = chain[-2].der
    lowest = chain[-1]
    server = _tls(start, tmp_path, made.server("localhost", lowest), lowest)
    # CA 2, three links up, does not reach the server: CA 3 and CA 4 are not sent.
    with pytest.raises(git_certificates.NoOffer) as raised:
        git_certificates.offer("localhost", server.port)
    assert raised.value.outcome == git_certificates.TLS
    assert [r.path for r in pki.requests] == ["/4", "/3", "/2"]


def test_an_issuer_link_larger_than_64_kb_is_not_taken(start, tmp_path, corp):
    root, _ = corp
    files: dict[str, bytes] = {}
    pki = start(made.HTTPServer(files=files))
    issuing = made.authority("Corp Issuing CA 2", issuer=root, issuers_url=f"{pki.url}/root.pem")
    files["/root.pem"] = root.pem.encode() + b"#" * (64 * 1024)
    server = _tls(start, tmp_path, made.server("localhost", issuing), issuing)
    assert git_certificates.offer("localhost", server.port).pem == issuing.pem


def test_an_issuer_link_that_does_not_answer_is_cut(start, tmp_path, corp, monkeypatch):
    root, _ = corp
    silent = socket.create_server(("127.0.0.1", 0))
    start(silent)
    url = f"http://127.0.0.1:{silent.getsockname()[1]}/root.crt"
    issuing = made.authority("Corp Issuing CA 2", issuer=root, issuers_url=url)
    server = _tls(start, tmp_path, made.server("localhost", issuing), issuing)
    monkeypatch.setattr(git_certificates, "LINK_TIMEOUT", 0.5)
    assert git_certificates.offer("localhost", server.port).pem == issuing.pem


def test_only_an_intermediate_is_offered_as_the_highest_sent(start, tmp_path, corp):
    _, issuing = corp
    server = _tls(start, tmp_path, made.server("localhost", issuing), issuing)
    offer = git_certificates.offer("localhost", server.port)
    assert offer.pem == issuing.pem
    assert offer.subject == "Corp Issuing CA 2"
    assert offer.intermediate and not offer.own


def test_a_self_signed_server_offers_its_own_certificate(start, tmp_path):
    own = made.server("localhost", None)
    server = _tls(start, tmp_path, own)
    offer = git_certificates.offer("localhost", server.port)
    assert offer.pem == own.pem
    assert offer.own and not offer.intermediate
    assert offer.subject == "localhost"


def test_a_server_sending_its_certificate_alone_offers_it_as_the_highest_sent(
    start, tmp_path, corp
):
    """Signed by an authority it does not send: not the server's own, which it did not sign."""
    root, _ = corp
    leaf = made.server("localhost", root)
    server = _tls(start, tmp_path, leaf)
    offer = git_certificates.offer("localhost", server.port)
    assert offer.pem == leaf.pem
    assert offer.intermediate and not offer.own


def test_cross_signed_authorities_end_the_walk(start, tmp_path):
    """R1 signed by R2 and R2 by R1, both sent: the walk stops at the first one seen again."""
    r1, r2 = made.authority("R1"), made.authority("R2")
    r1x = made.authority("R1", issuer=r2, key=r1.key)
    r2x = made.authority("R2", issuer=r1, key=r2.key)
    server = _tls(start, tmp_path, made.server("localhost", r1), r1x, r2x)
    offer = git_certificates.offer("localhost", server.port)
    assert offer.subject in ("R1", "R2")
    assert offer.intermediate


def test_an_expired_authority_from_an_issuer_link_gets_no_offer_but_a_reason(start, tmp_path):
    ended = made.NOW - made.DAY
    root = made.authority("Corp Root CA", not_before=ended - 30 * made.DAY, not_after=ended)
    files: dict[str, bytes] = {}
    pki = start(made.HTTPServer(files=files))
    issuing = made.authority("Corp Issuing CA 2", issuer=root, issuers_url=f"{pki.url}/root.crt")
    files["/root.crt"] = root.der
    server = _tls(start, tmp_path, made.server("localhost", issuing), issuing)
    with pytest.raises(git_certificates.NoOffer) as raised:
        git_certificates.offer("localhost", server.port)
    assert raised.value.outcome == git_certificates.EXPIRED
    assert raised.value.expired_on == ended.date()


def test_a_python_that_gives_no_chain_is_a_plain_reason(start, tmp_path, corp, monkeypatch):
    root, _ = corp
    server = _tls(start, tmp_path, made.server("localhost", root), root)

    def missing(tls):
        raise AttributeError("'_ssl._SSLSocket' object has no attribute 'get_unverified_chain'")

    monkeypatch.setattr(git_certificates, "_unverified", missing)
    with pytest.raises(git_certificates.NoOffer) as raised:
        git_certificates.offer("localhost", server.port)
    assert raised.value.outcome == git_certificates.TLS
    assert raised.value.why == "this Python cannot read the server's certificates"


def test_an_expired_file_is_taken_when_expired_ones_are_allowed():
    ended = made.NOW - 10 * made.DAY
    old = made.authority("Old CA", not_before=ended - 30 * made.DAY, not_after=ended)
    assert git_certificates.from_file(old.pem.encode(), "old", expired_ok=True) == old.pem


def test_a_certificate_of_another_host_gets_no_offer(start, tmp_path, corp):
    root, _ = corp
    server = _tls(start, tmp_path, made.server("other.corp.example", root), root)
    with pytest.raises(git_certificates.NoOffer) as raised:
        git_certificates.offer("localhost", server.port)
    assert raised.value.outcome == git_certificates.NAME
    assert not raised.value.common_name_only


def test_a_common_name_alone_gets_no_offer(start, tmp_path):
    server = _tls(start, tmp_path, made.server("localhost", None, names=()))
    with pytest.raises(git_certificates.NoOffer) as raised:
        git_certificates.offer("localhost", server.port)
    assert raised.value.outcome == git_certificates.NAME
    assert raised.value.common_name_only


def test_an_expired_server_certificate_gets_no_offer(start, tmp_path, corp):
    root, _ = corp
    ended = made.NOW - 10 * made.DAY
    leaf = made.server("localhost", root, not_before=ended - 30 * made.DAY, not_after=ended)
    server = _tls(start, tmp_path, leaf, root)
    with pytest.raises(git_certificates.NoOffer) as raised:
        git_certificates.offer("localhost", server.port)
    assert raised.value.outcome == git_certificates.EXPIRED
    assert raised.value.expired_on == leaf.certificate.not_valid_after_utc.date()


def test_a_server_that_is_not_there_gets_no_offer():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(git_certificates.NoOffer) as raised:
        git_certificates.offer("127.0.0.1", port)
    assert raised.value.outcome == git_certificates.TLS


# The context LADO's requests use.


def test_the_context_trusts_the_certificate_alone(start, tmp_path, corp):
    root, issuing = corp
    leaf = made.server("localhost", issuing)
    server = _tls(start, tmp_path, leaf, issuing)

    def connects(pem: str) -> bool:
        context = git_certificates.context(pem)
        try:
            with (
                socket.create_connection(("127.0.0.1", server.port), 5) as raw,
                context.wrap_socket(raw, server_hostname="localhost"),
            ):
                return True
        except ssl.SSLCertVerificationError:
            return False

    assert connects(root.pem)
    assert connects(issuing.pem)  # an intermediate as the last authority
    assert not connects(made.authority("Other Root").pem)


# A file's checks.


def test_a_file_of_text_holds_no_certificate():
    with pytest.raises(git_certificates.BadFile, match=r"^notes.txt holds no certificate$"):
        git_certificates.from_file(b"just some notes\n", "notes.txt")


def test_a_file_larger_than_1_mb_is_refused(corp):
    root, _ = corp
    data = root.pem.encode() + b"\n" * (1024 * 1024)
    with pytest.raises(git_certificates.BadFile, match=r"^big.pem is larger than 1 MB$"):
        git_certificates.from_file(data, "big.pem")


def test_a_file_whose_certificates_all_expired_is_refused():
    ended = datetime.datetime(2024, 5, 1, tzinfo=datetime.timezone.utc)
    old = made.authority("Old CA", not_before=ended - 30 * made.DAY, not_after=ended)
    with pytest.raises(
        git_certificates.BadFile, match=r"^old.pem: the certificate expired on 2024-05-01$"
    ):
        git_certificates.from_file(old.pem.encode(), "old.pem")


def test_a_chain_is_kept_whole_as_pem_alone(corp):
    root, issuing = corp
    data = b"Bag Attributes\n" + issuing.pem.encode() + b"some text\n" + root.pem.encode()
    pem = git_certificates.from_file(data, "chain.pem")
    assert pem == issuing.pem + root.pem
    assert [c.subject for c in git_certificates.parse(pem)] == ["Corp Issuing CA 2", "Corp Root CA"]


def test_a_key_in_the_file_is_not_kept(corp):
    root, _ = corp
    leaf = made.server("localhost", root)
    key = leaf.key.private_bytes(
        made.serialization.Encoding.PEM,
        made.serialization.PrivateFormat.PKCS8,
        made.serialization.NoEncryption(),
    )
    pem = git_certificates.from_file(key + root.pem.encode(), "both.pem")
    assert "PRIVATE KEY" not in pem
    assert pem == root.pem


def test_a_file_with_one_valid_certificate_of_two_is_taken(corp):
    root, _ = corp
    ended = made.NOW - 10 * made.DAY
    old = made.authority("Old CA", not_before=ended - 30 * made.DAY, not_after=ended)
    assert git_certificates.from_file((old.pem + root.pem).encode(), "x.pem") == old.pem + root.pem


def test_a_described_certificate_says_whether_it_expired():
    ended = made.NOW - 10 * made.DAY
    old = made.authority("Old CA", not_before=ended - 30 * made.DAY, not_after=ended)
    (found,) = git_certificates.parse(old.pem)
    assert found.expired
    assert found.subject == "Old CA"
