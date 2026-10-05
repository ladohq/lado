"""Kit marketplaces: git repositories that list kits by name.

A marketplace has marketplace.yaml at its root:

    kits:
      lado-dev: https://github.com/ladohq/kit-lado-dev.git

Each name must be the name in that kit's kit.yaml (lado.kits checks it at install). The
marketplaces are kept in lado.db (state.Marketplace: name, url, enabled, when it was last
updated); the official one is a row too, made with the table, with no url: its address is
OFFICIAL_URL. It can be disabled, never removed.

Each marketplace has a clone of its main branch in LADO_HOME/marketplaces/<name>/, a cache
only: made on first use, brought up to date by `update`, and made again when its origin is
not the marketplace's address. `lado kits add <kit> -m <marketplace>` looks a kit up in that
clone (resolve); without -m LADO never looks in a marketplace. The kit's row in lado.db
keeps the marketplace it was added from (lado.kits).

What the UI shows of each kit (its Available list) comes from index.json at the
marketplace's root, which the marketplace's CI builds from the kits; LADO only reads it,
from the clone, never the network (index). Version 1:

    {
      "index": 1,
      "kits": {
        "lado-dev": {
          "address": "https://github.com/ladohq/kit-lado-dev.git",
          "latest": "v0.9.1",                  # the latest release, no pre-release
          "commit": "4be21c0...",              # that release's commit
          "lado": ">=0.20",                    # dependencies.lado of the kit
          "description": "...",
          "agents": {"supervisor": "the first line of its description"},
          "skills": ["lado-checks"],
          "flows": ["feature", "fix"],
          "mcp": {"playwright": "npx @playwright/mcp"}   # name -> command, one line
        }
      }
    }

Only `address` is required of an entry; keys LADO does not know, of an entry or at the top,
are passed over, so the CI may add some without a new version. A higher `index` needs a
newer LADO. marketplace.yaml stays the list of names and addresses: an entry of a kit it does
not list is left out, and one whose address is not the list's is not used (the
marketplace's `problem` says so). A marketplace without index.json shows names and addresses
only.
"""

import datetime
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

from lado import gitcache, state

OFFICIAL = state.OFFICIAL_MARKETPLACE
OFFICIAL_URL = "https://github.com/ladohq/marketplace.git"
LIST_FILE = "marketplace.yaml"
INDEX_FILE = "index.json"
INDEX_VERSION = 1  # the highest version of index.json this LADO reads
NOT_FETCHED = "not fetched yet: update it"
NAME = re.compile(r"[a-z0-9-]+")
# A kit's name, here and in kit.yaml (lado.kits.NAME is this one).
KIT_NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")


class MarketplaceError(RuntimeError):
    pass


@dataclass(frozen=True)
class IndexEntry:
    """A kit as index.json describes it; only its address is sure to be there."""

    address: str
    latest: str | None = None
    commit: str | None = None
    lado: str | None = None
    description: str | None = None
    agents: dict[str, str] | None = None
    skills: list[str] | None = None
    flows: list[str] | None = None
    mcp: dict[str, str] | None = None


@dataclass(frozen=True)
class Index:
    """A marketplace's index.json: the entries of the kits its list has, and why some or all
    could not be used (None when nothing is wrong). `present`: the file is there."""

    kits: dict[str, IndexEntry]
    problem: str | None
    present: bool = True


@dataclass(frozen=True)
class Offer:
    """A kit an enabled marketplace lists, with its index.json entry if there is one."""

    name: str
    marketplace: str
    address: str
    entry: IndexEntry | None


# The optional fields of an entry and what each must be.
_TEXT = "a text"
_NAMES = "a list of names"
_MAP = "a map of names to texts"
ENTRY_FIELDS = {
    "latest": _TEXT,
    "commit": _TEXT,
    "lado": _TEXT,
    "description": _TEXT,
    "agents": _MAP,
    "skills": _NAMES,
    "flows": _NAMES,
    "mcp": _MAP,
}


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


def update_each(names: list[str] | None = None) -> list[tuple[str, state.Marketplace | str]]:
    """Update each of `names`, or each enabled marketplace, one after the other: one that
    fails does not stop the others. Per name, the marketplace updated or why it was not."""
    if names is None:
        names = [m.name for m in list_() if m.enabled]
    done: list[tuple[str, state.Marketplace | str]] = []
    for name in names:
        try:
            (market,) = update(name)
        except MarketplaceError as exc:
            done.append((name, str(exc)))
            continue
        done.append((name, market))
    return done


def listed(name: str) -> dict[str, str] | None:
    """The kits marketplace `name` lists, from the clone there is, never the network; None
    when there is no clone of its address yet. A list LADO cannot read is MarketplaceError."""
    market = _get(name)
    folder = _clone_of(market)
    return None if folder is None else _read(folder, url(market))


def index(name: str) -> Index:
    """Marketplace `name`'s index.json from its clone, never the network: the entries of the
    kits its list has, checked as the module's docstring says."""
    market = _get(name)
    folder = _clone_of(market)
    if folder is None:
        return Index({}, NOT_FETCHED, present=False)
    path = folder / INDEX_FILE
    if not path.is_file():
        return Index({}, None, present=False)
    try:
        data = json.loads(path.read_text())
    except (ValueError, OSError) as exc:
        return Index({}, f"{INDEX_FILE} is invalid: {exc}")
    version = data.get("index") if isinstance(data, dict) else None
    if not isinstance(version, int) or isinstance(version, bool):
        return Index({}, f"{INDEX_FILE} is invalid: index must be a whole number")
    if version > INDEX_VERSION:
        return Index({}, f"{INDEX_FILE} is version {version}: it needs a newer LADO")
    entries = data.get("kits")
    if not isinstance(entries, dict):
        return Index({}, f"{INDEX_FILE} is invalid: kits must map kit names to entries")
    names = _read(folder, url(market))
    kits_, problems = {}, []
    for kit, entry in entries.items():
        if kit not in names:
            continue
        problem = _entry_problem(entry, names[kit])
        if problem:
            problems.append(f'kit "{kit}": {problem}')
            continue
        known = {key: entry[key] for key in ENTRY_FIELDS if key in entry}
        kits_[kit] = IndexEntry(address=entry["address"], **known)
    problem = f"{INDEX_FILE}: {'; '.join(problems)}" if problems else None
    return Index(kits_, problem)


def _entry_problem(entry: object, address: str) -> str | None:
    if not isinstance(entry, dict):
        return "not a map"
    given = entry.get("address")
    if not isinstance(given, str):
        return "no address"
    if given != address:
        return f"its address {given} is not the one {LIST_FILE} gives, {address}"
    for key, kind in ENTRY_FIELDS.items():
        if key in entry and not _is(entry[key], kind):
            return f"{key} must be {kind}"
    return None


def _is(value: object, kind: str) -> bool:
    if kind == _TEXT:
        return isinstance(value, str)
    if kind == _NAMES:
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    return isinstance(value, dict) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    )


def available() -> list[Offer]:
    """Every kit the enabled marketplaces with a clone list, with its index.json entry, by
    name, then marketplace; no network. A marketplace whose list LADO cannot read gives
    none (its problem is shown with it)."""
    offers = []
    for market in list_():
        if not market.enabled:
            continue
        try:
            names = listed(market.name)
        except MarketplaceError:
            continue
        if names is None:
            continue
        entries = index(market.name).kits
        for kit, address in names.items():
            offers.append(Offer(kit, market.name, address, entries.get(kit)))
    return sorted(offers, key=lambda o: (o.name, o.marketplace))


def kits_from(name: str) -> list[str]:
    """The installed kits added from marketplace `name`; they stay when it is removed."""
    return [kit.name for kit in state.list_kits() if kit.marketplace == name]


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


def _get(name: str) -> state.Marketplace:
    market = state.get_marketplace(name)
    if market is None:
        raise MarketplaceError(f'no marketplace "{name}"; lado marketplaces lists them')
    return market


def _folder(market: state.Marketplace) -> Path:
    """The clone of `market`, made when there is none or its origin is another address."""
    clone = _clone_of(market)
    if clone is not None:
        return clone
    folder = root() / market.name
    shutil.rmtree(folder, ignore_errors=True)
    _clone(url(market), folder)
    state.update_marketplace(market.name, updated_at=_now())
    return folder


def _clone_of(market: state.Marketplace) -> Path | None:
    """The clone of `market` if there is one of its address; never makes one."""
    folder = root() / market.name
    if not folder.is_dir():
        return None
    try:
        return folder if gitcache.address(folder) == url(market) else None
    except gitcache.GitError:
        return None


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
