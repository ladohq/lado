"""docs/git-servers.md, the plain-words guide to connecting a git server (openspec change
git-servers-guide): its links resolve, and every answer of Check it quotes is in the guide
whole and, by its fixed fragments, in the code that gives it, so the guide cannot drift from
the page unnoticed."""

import ast
import re
from pathlib import Path

import pytest
from test_docker import anchors

ROOT = Path(__file__).parents[1]
GUIDE = ROOT / "docs" / "git-servers.md"
PY = ROOT / "src" / "lado" / "git_servers.py"
GITLAB = ROOT / "src" / "lado" / "git_kinds" / "gitlab.py"
TSX = ROOT / "web" / "src" / "GitServers.tsx"


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def strings(path: Path) -> str:
    """The string constants of a Python module, f-strings' fixed parts included, one per line:
    adjacent literals are one constant, so a sentence split over lines is found whole."""
    found = [
        node.value
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    return "\n".join(flat(s) for s in found)


def source(path: Path) -> str:
    return strings(path) if path.suffix == ".py" else flat(path.read_text())


def links(markdown: str) -> list[str]:
    return re.findall(r"\]\(([^)\s]+)\)", markdown)


def test_every_link_of_the_guide_resolves():
    found = links(GUIDE.read_text())
    assert found
    for link in found:
        if re.match(r"[a-z]+://", link):
            continue
        name, _, anchor = link.partition("#")
        target = (GUIDE.parent / name) if name else GUIDE
        assert target.is_file(), link
        if anchor:
            assert anchor in anchors(target.read_text()), link


def test_the_guide_names_no_plan():
    assert "epics" not in GUIDE.read_text()


# The texts the guide quotes, each with where the code gives it and its fixed fragments
# there (None: the text whole, a constant of the code).
QUOTES = [
    # Check's lines (git_servers.check, _trust, _no_answer_page; checkLine shows them).
    (
        "Works: signed in as <login>, may clone and push.",
        PY,
        ["Works: signed in as ", ", may clone and push."],
    ),
    ("Works: GitLab, signed in as <login>.", PY, ["Works: ", ", signed in as "]),
    (
        "Works: signed in as <login>, may clone and push; glab cannot open merge requests: "
        "the token lacks api.",
        PY,
        ["Works: signed in as ", " cannot open ", ": the token lacks "],
    ),
    ("glab cannot open merge requests", GITLAB, ["glab", "merge requests"]),
    (
        "Works: signed in as <login>; the token's rights are not checked.",
        PY,
        ["; the token's rights are not checked."],
    ),
    (
        "GitHub refused the token: it expired or was revoked.",
        PY,
        [" refused the token: it expired or was revoked"],
    ),
    ("The token lacks <scopes>.", PY, ["The token lacks "]),
    (
        "Agents can clone but not push with it. Make one with the scope api.",
        PY,
        ["Agents can ", "clone but not push", " with it. Make one with the "],
    ),
    ("The token lacks read_api.", PY, None),
    (
        "LADO asks the server's API with it. Make one with the scope api.",
        PY,
        ["LADO asks the server's API with it. Make one with the "],
    ),
    ("Its token file is missing.", PY, None),
    ("⚠ No answer in 5 seconds.", PY, ["No answer in ", " seconds."]),
    ("⚠ No answer: the name is not found.", PY, ["No answer: ", "the name is not found"]),
    (
        "⚠ No answer: the connection is refused.",
        PY,
        ["No answer: ", "the connection is refused"],
    ),
    ("⚠ No answer: TLS failed (<why>).", PY, ["No answer: ", "TLS failed ("]),
    (
        "Check that LADO's computer reaches the server: the company VPN or proxy; with LADO "
        "in Docker, its container.",
        PY,
        None,
    ),
    (
        "⚠ The server's certificate is not trusted.",
        PY,
        ["The server's certificate is not trusted."],
    ),
    (
        "⚠ The server's certificate has changed since you trusted it.",
        PY,
        ["The server's certificate has changed since you trusted it."],
    ),
    (
        "The server's certificate is not issued for <host>: trusting it would not help. Ask "
        "the server's administrator.",
        PY,
        [
            "The server's certificate ",
            "is not issued for ",
            ": trusting it would not help",
            ". Ask the server's administrator.",
        ],
    ),
    (
        "The server's certificate names its host only in the old Common Name field, which "
        "LADO refuses: ask the server's administrator to reissue it.",
        PY,
        [
            "names its host only in the old Common Name field, which LADO refuses",
            ": ask the server's administrator to reissue it.",
        ],
    ),
    (
        "The server's certificate expired on <date>: ask the server's administrator to renew it.",
        PY,
        ["expired on ", ": ask the server's administrator to renew it."],
    ),
    (
        "It redirects to <address>: add that address instead.",
        PY,
        ["redirects to ", ": add that address instead"],
    ),
    (
        "It answers as GitHub, not GitLab: remove it and add it again.",
        PY,
        ["answers as ", ", not ", ": remove it and add it again"],
    ),
    ("It answers as neither GitHub nor GitLab.", PY, ["It answers as neither "]),
    # Add server's and Replace token's lines.
    (
        "GitLab refused this token: copy it whole or make a new one.",
        PY,
        [" refused this token: copy it whole or make a new one."],
    ),
    (
        "The token lacks write_repository: agents can clone but not push.",
        PY,
        ["The token lacks ", ": agents can ", "clone but not push"],
    ),
    ("✓ Saved: GitLab, signed in as <login>.", TSX, ["Saved: ", ", signed in as "]),
    ("✓ Token replaced: signed in as <login>.", TSX, ["Token replaced: signed in as "]),
    (
        "⚠ Plain http://: the token travels unencrypted.",
        TSX,
        ["Plain http://", ": the token travels unencrypted."],
    ),
    # The trust card (TrustCard, NOT_TRUSTED, KEPT_OLD, ADD_NOT_TRUSTED).
    (
        "Trust it only if you expected this authority. In a company network your IT "
        "department can confirm the fingerprint.",
        TSX,
        None,
    ),
    ("If your IT department did not announce a new certificate, do not trust it", TSX, None),
    ("Not trusted: LADO and agents cannot clone or push here over https.", TSX, None),
    (
        "The saved certificate does not fit the server: LADO and agents cannot clone or push "
        "here over https.",
        TSX,
        None,
    ),
    (
        "⚠ Not trusted, so LADO cannot ask the server. Choose its kind to save it without a check.",
        TSX,
        None,
    ),
    ("Certificate trusted.", TSX, None),
    ("✕ check failed: token refused", TSX, None),
    # The buttons the guide names.
    ("**Trust this server**", TSX, ["Trust this server"]),
    ("**Don't trust**", TSX, ["Don't trust"]),
    ("**Trust the new certificate**", TSX, ["Trust the new certificate"]),
    ("**Keep the old one**", TSX, ["Keep the old one"]),
    ("**Add without a check**", TSX, ["Add without a check"]),
    ("**Replace token**", TSX, ["Replace token"]),
    ("**Save token**", TSX, ["Save token"]),
    ("**Remove server**", TSX, ["Remove server"]),
    ("**Set author**", TSX, ["Set author"]),
    ("**Check again**", TSX, ["Check again"]),
]


@pytest.mark.parametrize(("quote", "path", "fragments"), QUOTES, ids=[q[0][:40] for q in QUOTES])
def test_the_guide_quotes_checks_answers_as_the_code_gives_them(quote, path, fragments):
    assert quote in flat(GUIDE.read_text())
    code = source(path)
    for fragment in fragments or [quote]:
        assert fragment in quote, fragment
        assert fragment in code, f"{fragment!r} is not in {path.name}"
