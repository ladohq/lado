"""Kit marketplaces (lado.marketplaces): git repositories that list kits by name, kept in
lado.db, with a clone each in LADO_HOME/marketplaces. Local bare repos stand for remotes."""

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


def test_source_of_reads_the_clones_of_enabled_marketplaces_only(tmp_path, lado_home, official):
    url = publish(init_repo(tmp_path / "team"), listing(tool="https://example.com/tool.git"))
    marketplaces.add("team", url)
    assert marketplaces.source_of("https://example.com/tool.git") == "team"
    # Never the network: the official one has no clone yet, so it is not asked.
    assert marketplaces.source_of("https://example.com/kit-lado-dev.git") is None
    assert not (lado_home / "marketplaces" / "official").exists()
    marketplaces.kits("official")
    assert marketplaces.source_of("https://example.com/kit-lado-dev.git") == "official"
    marketplaces.set_enabled("team", False)
    assert marketplaces.source_of("https://example.com/tool.git") is None
