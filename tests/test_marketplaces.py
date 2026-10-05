"""Kit marketplaces (lado.marketplaces): git repositories that list kits by name, kept in
lado.db, with a clone each in LADO_HOME/marketplaces. Local bare repos stand for remotes."""

import json
import shutil

import pytest
from agent_helpers import init_repo, publish

from lado import marketplaces, state


def listing(**kits: str) -> dict[str, str]:
    return {"marketplace.yaml": "kits:\n" + "".join(f"  {k}: {u}\n" for k, u in kits.items())}


@pytest.fixture
def official(tmp_path, monkeypatch):
    """The official marketplace, at a local bare repo instead of github.com."""
    work = init_repo(tmp_path / "official")
    url = publish(work, listing(**{"lado-dev": "https://example.com/kit-lado-dev.git"}))
    monkeypatch.setattr(marketplaces, "OFFICIAL_URL", url)
    return work


def test_the_official_marketplace_is_there_and_can_only_be_disabled(lado_home, official):
    (market,) = marketplaces.list_()
    assert (market.name, market.url, market.enabled) == ("official", None, True)
    assert marketplaces.url(market) == marketplaces.OFFICIAL_URL
    with pytest.raises(
        marketplaces.MarketplaceError,
        match="the official marketplace cannot be removed; disable it: "
        "lado marketplaces disable official",
    ):
        marketplaces.remove("official")
    marketplaces.set_enabled("official", False)
    assert not state.get_marketplace("official").enabled
    marketplaces.set_enabled("official", True)
    assert marketplaces.kits("official") == {"lado-dev": "https://example.com/kit-lado-dev.git"}
    assert (lado_home / "marketplaces" / "official" / "marketplace.yaml").is_file()
    assert state.get_marketplace("official").updated_at  # its first clone


def test_add_clones_and_reads_its_list_remove_drops_both(tmp_path, lado_home):
    url = publish(init_repo(tmp_path / "team"), listing(tool="https://example.com/tool.git"))
    market = marketplaces.add("team", url)
    assert (market.name, market.url, market.enabled) == ("team", url, True)
    assert market.updated_at
    assert marketplaces.kits("team") == {"tool": "https://example.com/tool.git"}
    with pytest.raises(marketplaces.MarketplaceError, match='marketplace "team" exists already'):
        marketplaces.add("team", url)
    marketplaces.remove("team")
    assert state.get_marketplace("team") is None
    assert not (lado_home / "marketplaces" / "team").exists()
    with pytest.raises(
        marketplaces.MarketplaceError,
        match='no marketplace "team"; lado marketplaces lists them',
    ):
        marketplaces.remove("team")


@pytest.mark.parametrize(
    ("name", "files", "error"),
    [
        ("Team", None, 'marketplace name "Team": use lowercase letters, digits and -'),
        ("team", {"README": "x"}, "is no marketplace: it has no marketplace.yaml at its root"),
        ("team", {"marketplace.yaml": "kits: [a]\n"}, "kits must map kit names to git addresses"),
        ("team", {"marketplace.yaml": "kits:\n  Bad: x.git\n"}, 'kit name "Bad"'),
        ("team", {"marketplace.yaml": "kits:\n  a: ./here\n"}, 'kit "a": "./here" is no git'),
    ],
)
def test_add_refuses_what_is_no_marketplace(tmp_path, lado_home, name, files, error):
    url = publish(init_repo(tmp_path / "team"), files or listing())
    with pytest.raises(marketplaces.MarketplaceError, match=error):
        marketplaces.add(name, url)
    assert state.get_marketplace(name) is None
    assert not (lado_home / "marketplaces" / name).exists()


def test_add_refuses_an_address_that_is_not_git(lado_home):
    with pytest.raises(marketplaces.MarketplaceError, match='"./team" is no git address'):
        marketplaces.add("team", "./team")


def test_update_fetches_the_latest_list(tmp_path, lado_home):
    work = init_repo(tmp_path / "team")
    url = publish(work, listing(a="https://example.com/a.git"))
    marketplaces.add("team", url)
    state.update_marketplace("team", updated_at="2000-01-01 00:00:00")
    publish(work, listing(a="https://example.com/a.git", b="https://example.com/b.git"))
    assert list(marketplaces.kits("team")) == ["a"]  # the clone, until it is updated
    (updated,) = marketplaces.update("team")
    assert updated.name == "team" and updated.updated_at > "2000-01-01 00:00:00"
    assert list(marketplaces.kits("team")) == ["a", "b"]


def test_update_without_a_name_updates_each_enabled_one(tmp_path, lado_home, official):
    marketplaces.add("team", publish(init_repo(tmp_path / "team"), listing()))
    marketplaces.add("off", publish(init_repo(tmp_path / "off"), listing()))
    marketplaces.set_enabled("off", False)
    assert [m.name for m in marketplaces.update()] == ["official", "team"]


def test_a_folder_with_another_origin_is_cloned_again(tmp_path, lado_home):
    url = publish(init_repo(tmp_path / "team"), listing(a="https://example.com/a.git"))
    other = publish(init_repo(tmp_path / "other"), listing(z="https://example.com/z.git"))
    marketplaces.add("team", url)
    folder = lado_home / "marketplaces" / "team"
    # The marketplace was removed and added again with another address meanwhile.
    state.delete_marketplace("team")
    state.add_marketplace("team", other)
    assert list(marketplaces.kits("team")) == ["z"]
    assert (folder / "marketplace.yaml").read_text() == listing(z="https://example.com/z.git")[
        "marketplace.yaml"
    ]


def test_resolve_names_the_way_out_of_each_refusal(tmp_path, lado_home):
    url = publish(init_repo(tmp_path / "team"), listing(tool="https://example.com/tool.git"))
    marketplaces.add("team", url)
    assert marketplaces.resolve("team", "tool") == "https://example.com/tool.git"
    with pytest.raises(
        marketplaces.MarketplaceError,
        match='no kit "nope" in marketplace "team"; to get its latest list: '
        "lado marketplaces update team",
    ):
        marketplaces.resolve("team", "nope")
    marketplaces.set_enabled("team", False)
    with pytest.raises(
        marketplaces.MarketplaceError,
        match='marketplace "team" is disabled; lado marketplaces enable team',
    ):
        marketplaces.resolve("team", "tool")
    with pytest.raises(marketplaces.MarketplaceError, match='no marketplace "far"'):
        marketplaces.resolve("far", "tool")


A = "https://example.com/a.git"
B = "https://example.com/b.git"


def team(tmp_path, files=None, **kits: str) -> str:
    """Marketplace "team" added from a local repo listing `kits`, with `files` beside."""
    url = publish(init_repo(tmp_path / "team"), {**listing(**kits), **(files or {})})
    marketplaces.add("team", url)
    return url


def index_file(kits: dict, version=1, **extra) -> dict[str, str]:
    return {"index.json": json.dumps({"index": version, "kits": kits, **extra})}


def test_listed_reads_the_clone_without_the_network(tmp_path, lado_home, monkeypatch):
    team(tmp_path, a=A)
    assert marketplaces.listed("official") is None  # never cloned: nothing is fetched
    monkeypatch.setattr(marketplaces.gitcache, "clone_branch", no_network)
    monkeypatch.setattr(marketplaces.gitcache, "refresh", no_network)
    assert marketplaces.listed("team") == {"a": A}
    assert marketplaces.listed("official") is None
    assert not (lado_home / "marketplaces" / "official").exists()


def no_network(*args, **kwargs):
    raise AssertionError("the network was used")


def test_index_without_a_clone_or_a_file(tmp_path, lado_home):
    assert marketplaces.index("official") == marketplaces.Index(
        {}, "not fetched yet: update it", present=False
    )
    team(tmp_path, a=A)
    assert marketplaces.index("team") == marketplaces.Index({}, None, present=False)


def test_index_gives_each_listed_kits_entry(tmp_path, lado_home):
    entry = {
        "address": A,
        "latest": "v0.9.1",
        "commit": "4be21c0",
        "lado": ">=0.20",
        "description": "Develop LADO",
        "agents": {"supervisor": "leads"},
        "skills": ["lado-checks"],
        "flows": ["feature"],
        "mcp": {"playwright": "npx @playwright/mcp"},
        "stars": 5,  # a key LADO does not know is passed over
    }
    files = index_file({"a": entry, "b": {"address": B}, "stray": {"address": A}}, built="x")
    team(tmp_path, files, a=A, b=B)
    found = marketplaces.index("team")
    assert found.problem is None and found.present
    assert list(found.kits) == ["a", "b"]  # a kit marketplace.yaml does not list is left out
    assert found.kits["a"] == marketplaces.IndexEntry(
        address=A,
        latest="v0.9.1",
        commit="4be21c0",
        lado=">=0.20",
        description="Develop LADO",
        agents={"supervisor": "leads"},
        skills=["lado-checks"],
        flows=["feature"],
        mcp={"playwright": "npx @playwright/mcp"},
    )
    assert found.kits["b"] == marketplaces.IndexEntry(address=B)  # only the address


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("{not json", "index.json is invalid: "),
        ('{"index": "1", "kits": {}}', "index.json is invalid: index must be a whole number"),
        ('{"index": 1, "kits": []}', "index.json is invalid: kits must map kit names to entries"),
        ('{"index": 2, "kits": {}}', "index.json is version 2: it needs a newer LADO"),
    ],
)
def test_an_index_lado_cannot_read_is_a_problem(tmp_path, lado_home, text, problem):
    team(tmp_path, {"index.json": text}, a=A)
    found = marketplaces.index("team")
    assert found.kits == {} and found.present
    assert found.problem.startswith(problem)


def test_an_entry_that_does_not_agree_is_not_used(tmp_path, lado_home):
    entries = {"a": {"address": B}, "b": {"latest": "v1.0.0"}, "c": {"address": A, "skills": "x"}}
    team(tmp_path, index_file(entries), a=A, b=B, c=A)
    found = marketplaces.index("team")
    assert found.kits == {}
    assert found.problem == (
        f'index.json: kit "a": its address {B} is not the one marketplace.yaml gives, {A}; '
        'kit "b": no address; kit "c": skills must be a list of names'
    )


def test_available_lists_the_kits_of_enabled_marketplaces_with_a_clone(tmp_path, lado_home):
    team(tmp_path, index_file({"a": {"address": A, "latest": "v1.0.0"}}), a=A, b=B)
    other = publish(init_repo(tmp_path / "other"), listing(a=A))
    marketplaces.add("other", other)
    offers = marketplaces.available()
    assert [(o.name, o.marketplace, o.address) for o in offers] == [
        ("a", "other", A),  # one kit in two marketplaces: two offers
        ("a", "team", A),
        ("b", "team", B),
    ]
    assert offers[1].entry == marketplaces.IndexEntry(address=A, latest="v1.0.0")
    assert offers[0].entry is None and offers[2].entry is None
    marketplaces.set_enabled("other", False)
    assert [o.marketplace for o in marketplaces.available()] == ["team", "team"]


def test_update_each_goes_on_past_a_marketplace_that_fails(tmp_path, lado_home, official):
    team(tmp_path, a=A)
    shutil.rmtree(tmp_path / "team.git")  # its remote is gone
    marketplaces.add("other", publish(init_repo(tmp_path / "other"), listing(b=B)))
    done = marketplaces.update_each()
    assert [name for name, _ in done] == ["official", "other", "team"]
    assert isinstance(done[0][1], state.Marketplace) and isinstance(done[1][1], state.Marketplace)
    assert isinstance(done[2][1], str) and done[2][1].startswith('marketplace "team": ')
    (one,) = marketplaces.update_each(["nope"])
    assert one == ("nope", 'no marketplace "nope"; lado marketplaces lists them')


def test_kits_from_names_the_installed_kits_added_from_a_marketplace(lado_home):
    state.add_kit(state.InstalledKit("x", A, "v1.0.0", "c1", marketplace="team"))
    state.add_kit(state.InstalledKit("y", B, "v1.0.0", "c2"))
    state.add_kit(state.InstalledKit("z", B, "v1.0.0", "c3", marketplace="team"))
    assert marketplaces.kits_from("team") == ["x", "z"]
    assert marketplaces.kits_from("official") == []
