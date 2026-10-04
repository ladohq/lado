"""Kit marketplaces: git repositories that list kits by name.

A marketplace has marketplace.yaml at its root:

    kits:
      lado-dev: https://github.com/ladohq/lado-dev-kit.git

Each name must be the name in that kit's kit.yaml (lado.kits checks it at install). The
marketplaces are kept in lado.db (state.Marketplace: name, url, enabled, when it was last
updated); the official one is a row too, made with the table, with no url: its address is
OFFICIAL_URL. It can be disabled, never removed.

Each marketplace has a clone of its main branch in LADO_HOME/marketplaces/<name>/, a cache
only: made on first use, brought up to date by `update`, and made again when its origin is
not the marketplace's address. `lado kits add <kit> -m <marketplace>` looks a kit up in that
clone (resolve); without -m LADO never looks in a marketplace. source_of reads the clones
there are, never the network.
"""

import datetime
import re
import shutil
from pathlib import Path

import yaml

from lado import gitcache, state

OFFICIAL = state.OFFICIAL_MARKETPLACE
OFFICIAL_URL = "https://github.com/ladohq/marketplace.git"
LIST_FILE = "marketplace.yaml"
NAME = re.compile(r"[a-z0-9-]+")
KIT_NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")  # as lado.kits.NAME


class MarketplaceError(RuntimeError):
    pass


def root() -> Path:
    return state.home() / "marketplaces"


def url(market: state.Marketplace) -> str:
    """The address of a marketplace: its own, or OFFICIAL_URL for the official one."""
    return market.url or OFFICIAL_URL


def list_() -> list[state.Marketplace]:
    return state.list_marketplaces()


def add(name: str, address: str) -> state.Marketplace:
    """Add a marketplace: its clone is made and its list read first, so a repository that is
    no marketplace leaves nothing behind."""
    if not NAME.fullmatch(name):
        raise MarketplaceError(f'marketplace name "{name}": use lowercase letters, digits and -')
    if not gitcache.is_git(address):
        raise MarketplaceError(f'"{address}" is no git address')
    if state.get_marketplace(name):
        raise MarketplaceError(f'marketplace "{name}" exists already; lado marketplaces lists them')
    folder = root() / name
    shutil.rmtree(folder, ignore_errors=True)  # a clone left from a marketplace removed
    try:
        _clone(address, folder)
        _read(folder, address)
    except MarketplaceError:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    if not state.add_marketplace(name, address):
        raise MarketplaceError(f'marketplace "{name}" exists already; lado marketplaces lists them')
    state.update_marketplace(name, updated_at=_now())
    return _get(name)


def remove(name: str) -> None:
    """Remove a marketplace and its clone; the kits installed from it stay."""
    if name == OFFICIAL:
        raise MarketplaceError(
            "the official marketplace cannot be removed; disable it: "
            f"lado marketplaces disable {OFFICIAL}"
        )
    _get(name)
    state.delete_marketplace(name)
    shutil.rmtree(root() / name, ignore_errors=True)


def set_enabled(name: str, enabled: bool) -> state.Marketplace:
    _get(name)
    state.update_marketplace(name, enabled=enabled)
    return _get(name)


def update(name: str | None = None) -> list[state.Marketplace]:
    """Bring the clone of marketplace `name`, or of each enabled one, up to date."""
    markets = [_get(name)] if name else [m for m in list_() if m.enabled]
    for market in markets:
        folder = _folder(market)
        try:
            gitcache.refresh(folder)
        except gitcache.GitError as exc:
            raise MarketplaceError(f'marketplace "{market.name}": {exc}') from None
        _read(folder, url(market))
        state.update_marketplace(market.name, updated_at=_now())
    return [_get(m.name) for m in markets]


def kits(name: str) -> dict[str, str]:
    """The kits marketplace `name` lists (kit name -> git address), from its clone; the
    clone is made when there is none."""
    market = _get(name)
    return _read(_folder(market), url(market))


def resolve(name: str, kit: str) -> str:
    """The git address of `kit` in marketplace `name`, which must be enabled."""
    market = _get(name)
    if not market.enabled:
        raise MarketplaceError(f'marketplace "{name}" is disabled; lado marketplaces enable {name}')
    listed = kits(name)
    if kit not in listed:
        raise MarketplaceError(
            f'no kit "{kit}" in marketplace "{name}"; to get its latest list: '
            f"lado marketplaces update {name}"
        )
    return listed[kit]


def source_of(address: str) -> str | None:
    """The first enabled marketplace whose clone lists `address`, or None. Reads only the
    clones there are: never the network."""
    for market in list_():
        folder = root() / market.name
        if not market.enabled or not (folder / LIST_FILE).is_file():
            continue
        try:
            listed = _read(folder, url(market))
        except MarketplaceError:
            continue  # a broken list is reported where it is read on purpose
        if address in listed.values():
            return market.name
    return None


def _get(name: str) -> state.Marketplace:
    market = state.get_marketplace(name)
    if market is None:
        raise MarketplaceError(f'no marketplace "{name}"; lado marketplaces lists them')
    return market


def _folder(market: state.Marketplace) -> Path:
    """The clone of `market`, made when there is none or its origin is another address."""
    folder = root() / market.name
    address = url(market)
    if folder.is_dir():
        try:
            if gitcache.address(folder) == address:
                return folder
        except gitcache.GitError:
            pass
        shutil.rmtree(folder)
    _clone(address, folder)
    state.update_marketplace(market.name, updated_at=_now())
    return folder


def _clone(address: str, folder: Path) -> None:
    try:
        gitcache.clone_branch(address, folder)
    except gitcache.GitError as exc:
        raise MarketplaceError(str(exc)) from None


def _read(folder: Path, address: str) -> dict[str, str]:
    path = folder / LIST_FILE
    if not path.is_file():
        raise MarketplaceError(f"{address} is no marketplace: it has no {LIST_FILE} at its root")
    try:
        data = yaml.safe_load(path.read_text())
    except (yaml.YAMLError, OSError) as exc:
        raise MarketplaceError(f"{path}: {exc}") from None
    listed = (data.get("kits") or {}) if isinstance(data, dict) else None
    if not isinstance(listed, dict):
        raise MarketplaceError(f"{path}: kits must map kit names to git addresses")
    for kit, where in listed.items():
        if not isinstance(kit, str) or not KIT_NAME.fullmatch(kit):
            raise MarketplaceError(f'{path}: kit name "{kit}": lowercase letters, digits, - or _')
        if not isinstance(where, str) or not gitcache.is_git(where):
            raise MarketplaceError(f'{path}: kit "{kit}": "{where}" is no git address')
    return dict(listed)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
