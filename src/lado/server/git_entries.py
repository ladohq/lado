"""What the routes of Settings → Git servers do (openspec capability git-servers-page): the
human's git servers through lado.git_servers, with the rules and lines of `lado git-server`;
each refusal a model_entries.Refusal holding the page's line, its hint and the field of the
form it concerns, which lado.server.app answers as a 400.

Nothing here asks a server but the check of an address the human typed (no token sent) and
Add. A server's token comes in only in `GitServerAdd` and leaves in no answer: the refusals
are the core's lines, which never hold it.
"""

from __future__ import annotations

import os

from lado import git_kinds, git_servers, state
from lado.server import models
from lado.server.model_entries import Refusal


def _entry(exc: git_servers.Refused | git_servers.BadAddress) -> models.GitEntryRefused:
    if isinstance(exc, git_servers.BadAddress):
        return models.GitEntryRefused(
            message=exc.page,
            hint="",
            field=git_servers.ADDRESS_FIELD,
            warnings=[],
            choose_kind=False,
        )
    return models.GitEntryRefused(
        message=exc.page,
        hint=exc.page_hint,
        field=exc.field,
        warnings=[],
        choose_kind=exc.choose_kind,
    )


def _refusal(
    exc: git_servers.Refused | git_servers.BadAddress, warnings: list[str] | None = None
) -> Refusal:
    entry = _entry(exc)
    entry.warnings = warnings or []
    return Refusal(entry)


def server_info(server: state.GitServer) -> models.GitServerInfo:
    kind = git_kinds.by_name(server.kind)
    return models.GitServerInfo(
        address=server.address,
        host=server.host,
        kind=server.kind,
        kind_title=kind.title if kind else server.kind,
        login=server.login,
        has_token=git_servers.has_token(server),
        author_name=server.author_name,
        author_email=server.author_email,
    )


def listing(has_db: bool = True) -> models.GitServers:
    """The saved servers, asking none, as `lado git-server list` lists them; none with no
    lado.db, which is not made."""
    servers = state.git_servers() if has_db else []
    return models.GitServers(
        servers=[server_info(server) for server in servers],
        kinds=[
            models.GitKindInfo(
                name=kind.name, title=kind.title, token_path=kind.token_path, scopes=kind.scopes
            )
            for kind in git_kinds.KINDS
        ],
    )


def check(given: models.GitServerCheckAsked, has_db: bool = True) -> models.GitServerCheck:
    """What the add form says of the address as the human types, saving nothing: the
    refusals of the address, of its host name and of git, which ask no server; else the
    plain-http warning, whether it is saved, and what the server looks like asked with no
    token (git_servers.hint, TIMEOUT a request)."""
    found = models.GitServerCheck(
        address=None,
        hint=None,
        token_page=None,
        scopes=None,
        choose_kind=False,
        unchecked=None,
        saved=False,
        refusals=[],
        warnings=[],
    )
    if not given.address.strip():
        return found
    try:
        at = git_servers.address(given.address)
    except git_servers.BadAddress as exc:
        found.refusals.append(_entry(exc))
        return found
    found.address = at.root
    try:
        if has_db:
            git_servers.check_host(at)
        git_servers.check_git(os.environ)
    except git_servers.Refused as exc:
        found.refusals.append(_entry(exc))
        return found
    warning = git_servers.plain_http_warning(at)
    if warning:
        found.warnings.append(warning)
    found.saved = has_db and state.git_server_by_host(at.key) is not None
    try:
        hint = git_servers.hint(at)
    except git_servers.Refused as exc:
        found.refusals.append(_entry(exc))
        return found
    if hint.kind is not None:
        found.hint = hint.kind.name
        found.token_page = hint.kind.token_page(at.root)
        found.scopes = hint.kind.scopes
    found.choose_kind = hint.choose
    found.unchecked = _entry(hint.why) if hint.why else None
    return found


def add(given: models.GitServerAdd) -> models.GitServerAdded:
    """Check and save the server as `lado git-server add` does (`given.kind`: --kind)."""
    warnings: list[str] = []
    try:
        at = git_servers.address(given.address)
        saved, replaced, checked = git_servers.add(
            at, lambda: given.token, given.kind, warnings.append
        )
    except (git_servers.Refused, git_servers.BadAddress) as exc:
        raise _refusal(exc, warnings) from None
    info = server_info(saved)
    done = "Replaced" if replaced else "Saved"
    if checked.login:
        line = f"{done} git server {saved.address}: {checked.line()}."
    else:
        line = f"{done} git server {saved.address} as {info.kind_title} without a check "
        line += f"({checked.unchecked})."
    return models.GitServerAdded(
        server=info,
        line=line,
        replaced=replaced,
        warnings=warnings,
        warning=git_servers.lacks(checked.kind, checked.missing_scopes, page=True),
        missing_scopes=list(checked.missing_scopes),
    )


def check_saved(host: str) -> models.GitServerChecked:
    """Check the saved server of `host` (its key) again as `lado git-server check` does: a
    404 for no such server, a 422 for a token file it cannot read, asking nothing."""
    try:
        at = git_servers.saved_address(host)
        found = git_servers.check(at)
    except git_servers.Refused as exc:
        if exc.field == git_servers.ADDRESS_FIELD:  # no such server
            raise Refusal(_entry(exc), 404) from None
        entry = _entry(exc)
        entry.field = ""  # the panel's line, under no field of a form
        raise Refusal(entry, 422) from None
    saved = state.git_server_by_host(at.key)
    return models.GitServerChecked(
        outcome=found.outcome,
        kind=found.kind.name,
        login=found.login,
        missing_scopes=list(found.missing_scopes),
        rights_checked=found.rights_checked,
        was_checked=found.was_checked,
        message=found.page,
        hint=found.page_hint,
        server=server_info(saved) if saved else None,
    )


def set_author(host: str, given: models.GitServerAuthor) -> models.GitServerAuthorDone:
    """Set the commit author of the server of `host` (its key) as `lado git-server author
    --name --email` does."""
    try:
        saved = git_servers.set_author(git_servers.saved_address(host), given.name, given.email)
    except git_servers.Refused as exc:
        raise _refusal(exc) from None
    author = git_servers.author_text(saved)
    line = git_servers.AUTHOR_SET.format(address=saved.address, author=author)
    return models.GitServerAuthorDone(server=server_info(saved), line=line)


def clear_author(host: str) -> models.GitServerAuthorDone:
    """Clear the commit author of the server of `host` as `lado git-server author --clear`."""
    try:
        saved = git_servers.clear_author(git_servers.saved_address(host))
    except git_servers.Refused as exc:
        raise _refusal(exc) from None
    line = git_servers.AUTHOR_CLEARED.format(address=saved.address)
    return models.GitServerAuthorDone(server=server_info(saved), line=line)


def remove(host: str) -> models.GitServerRemoved:
    """Remove the server of `host` (its key) and its token as `lado git-server remove` does:
    the servers left, and why a folder of it stayed."""
    try:
        _, warning = git_servers.remove_host(host)
    except git_servers.Refused as exc:
        raise _refusal(exc) from None
    left = listing()
    return models.GitServerRemoved(servers=left.servers, kinds=left.kinds, warning=warning)
