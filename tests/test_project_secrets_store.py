"""The secrets store of a project (lado.project_secrets): files written atomically, never
through a symbolic link."""

import builtins
import os
import stat
import threading

import pytest

from lado import agent_env, project_secrets


@pytest.fixture
def home(tmp_path, monkeypatch):
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("LADO_HOME", str(folder))
    return folder


def mode(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


def secrets_of(home, id="shop"):
    return home / "projects" / id / "secrets"


@pytest.fixture(params=[0o000, 0o022, 0o077])
def umask(request):
    old = os.umask(request.param)
    yield request.param
    os.umask(old)


def test_a_write_makes_private_folders_and_a_private_file(home, umask):
    project_secrets.write("shop", "GH_TOKEN", "ghp_1")
    folder = secrets_of(home)
    assert (folder / "GH_TOKEN").read_bytes() == b"ghp_1"
    assert mode(folder / "GH_TOKEN") == 0o600
    for path in (home / "projects", home / "projects" / "shop", folder):
        assert mode(path) == 0o700, path
    assert project_secrets.folder("shop") == folder
    assert project_secrets.data_folder("shop") == home / "projects" / "shop"


def test_the_value_is_stored_byte_for_byte(home):
    value = "a=b c\nd\r\n é ✓ \t" + "x" * 1000
    project_secrets.write("shop", "V", value)
    assert (secrets_of(home) / "V").read_bytes() == value.encode()


def test_a_write_replaces_the_value_and_leaves_no_other_file(home):
    project_secrets.write("shop", "GH_TOKEN", "ghp_1")
    project_secrets.write("shop", "GH_TOKEN", "ghp_4")
    folder = secrets_of(home)
    assert (folder / "GH_TOKEN").read_text() == "ghp_4"
    assert mode(folder / "GH_TOKEN") == 0o600
    assert os.listdir(folder) == ["GH_TOKEN"]


@pytest.mark.parametrize(
    "value", ["x", "x\n", "\n", "x\n\n", "x\r\n", "x\r", "\r\n", "a\nb", " x \t"]
)
def test_the_reader_gives_back_exactly_the_value_written(home, value):
    """The reader drops one line break at a file's end (the outside folder's rule): a value
    ending in one is written with one more, so no line break of the value is lost."""
    project_secrets.write("shop", "V", value)
    assert project_secrets.read("shop").values == {"V": value}


def test_the_stored_form_of_a_value(home):
    assert project_secrets.stored("x") == b"x"
    assert project_secrets.stored("x\n") == b"x\n\n"
    assert project_secrets.stored("é\r") == "é\r".encode()


def test_a_failed_write_keeps_the_old_value_and_no_temporary_file(home, monkeypatch):
    project_secrets.write("shop", "GH_TOKEN", "ghp_1")

    def full(fd, data):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(project_secrets.os, "write", full)
    with pytest.raises(OSError) as raised:
        project_secrets.write("shop", "GH_TOKEN", "ghp_new")
    assert "ghp_new" not in str(raised.value)
    folder = secrets_of(home)
    assert (folder / "GH_TOKEN").read_text() == "ghp_1"
    assert os.listdir(folder) == ["GH_TOKEN"]


def test_a_reader_sees_the_old_or_the_new_value_never_a_part(home):
    values = {"a" * 30000, "b" * 50000}
    project_secrets.write("shop", "BIG", "a" * 30000)
    path = secrets_of(home) / "BIG"
    seen, done = [], threading.Event()

    def read():
        while not done.is_set():
            seen.append(path.read_text())

    reader = threading.Thread(target=read)
    reader.start()
    try:
        for i in range(200):
            project_secrets.write("shop", "BIG", "b" * 50000 if i % 2 else "a" * 30000)
    finally:
        done.set()
        reader.join()
    assert seen and set(seen) <= values


def test_remove_removes_a_secret_and_tells_a_missing_one(home):
    project_secrets.write("shop", "GH_TOKEN", "ghp_1")
    assert project_secrets.remove("shop", "GH_TOKEN") is True
    assert os.listdir(secrets_of(home)) == []
    assert project_secrets.remove("shop", "GH_TOKEN") is False
    assert project_secrets.remove("acme", "GH_TOKEN") is False  # no data folder


NOT_A_SECRETS_NAME = ["../x", "../../../victim", "..", ".", "a/b", "/abs", ".GH_TOKEN.abc.tmp", ""]


@pytest.mark.parametrize("name", NOT_A_SECRETS_NAME)
def test_a_name_that_is_no_variable_name_touches_nothing(home, name):
    """Only a variable name can be a secret's file: anything else is no secret, so a path
    never leads out of the folder, and a file being written is never removed."""
    project_secrets.write("shop", "GH_TOKEN", "g")
    folder = secrets_of(home)
    (folder / ".GH_TOKEN.abc.tmp").write_text("partial")
    (folder / "x").write_text("in the folder")
    (home / "projects" / "shop" / "x").write_text("beside")
    (home / "victim").write_text("v")
    (folder / "b").write_text("b")
    before = snapshot(home)
    assert project_secrets.remove("shop", name) is False
    assert project_secrets.held("shop", name) is False
    with pytest.raises(ValueError, match="not a variable name"):
        project_secrets.write("shop", name, "new")
    assert snapshot(home) == before


def test_names_lists_without_opening_any_file(home, monkeypatch, tmp_path):
    project_secrets.write("shop", "YOUGILE_API_KEY", "k")
    project_secrets.write("shop", "GH_TOKEN", "g")
    folder = secrets_of(home)
    (folder / "bad-name").write_text("x")
    (folder / "CODEX_HOME").write_text("x")
    (folder / "PATH").write_text("x")
    (folder / ".GH_TOKEN.abc.tmp").write_text("x")
    (tmp_path / "t").write_text("x")
    (folder / "LINKED").symlink_to(tmp_path / "t")

    def no_open(*args, **kwargs):
        raise AssertionError("a file was opened")

    monkeypatch.setattr(builtins, "open", no_open)
    monkeypatch.setattr(project_secrets.os, "open", no_open)
    assert project_secrets.names("shop") == ["GH_TOKEN", "YOUGILE_API_KEY"]
    assert project_secrets.names("acme") == []


def test_names_of_a_loose_or_linked_folder_are_none(home, tmp_path):
    project_secrets.write("shop", "GH_TOKEN", "g")
    secrets_of(home).chmod(0o755)
    assert project_secrets.names("shop") == []


def test_read_gives_the_secrets_by_the_one_reader(home):
    project_secrets.write("shop", "GH_TOKEN", "g\n")
    (secrets_of(home) / "CODEX_HOME").write_text("x")
    (secrets_of(home) / "CODEX_HOME").chmod(0o600)
    found = project_secrets.read("shop")
    assert found == agent_env.Folder({"GH_TOKEN": "g\n"}, [("CODEX_HOME", "a reserved name")])
    assert project_secrets.read("acme") == agent_env.Folder({}, [])


def test_the_layer_is_the_plain_variables_with_the_secrets_over_them(lado_home):
    from lado import projects, state

    projects.create("shop", None)
    state.set_project_variable("shop", "BOARD_URL", "plain")
    state.set_project_variable("shop", "GH_TOKEN", "plain")
    project_secrets.write("shop", "GH_TOKEN", "secret")
    assert project_secrets.layer("shop") == {"BOARD_URL": "plain", "GH_TOKEN": "secret"}
    assert project_secrets.layer("acme") == {}


def test_remove_all_removes_the_data_folder_and_nothing_else(home):
    project_secrets.write("shop", "GH_TOKEN", "g")
    project_secrets.write("acme", "GH_TOKEN", "a")
    project_secrets.remove_all("shop")
    assert not os.path.lexists(home / "projects" / "shop")
    assert (secrets_of(home, "acme") / "GH_TOKEN").read_text() == "a"
    project_secrets.remove_all("shop")  # already gone: nothing to do
    project_secrets.remove_all("none")


# A link on the way: projects/, <id>/, secrets/ or the file, for each writer.

LINKED = ["projects", "id", "secrets", "file"]


def make_link(home, tmp_path, where):
    """Put a link at `where` on the way to shop's GH_TOKEN; the link's path and target."""
    project_secrets.write("shop", "GH_TOKEN", "g")
    target = tmp_path / "elsewhere"
    path = {
        "projects": home / "projects",
        "id": home / "projects" / "shop",
        "secrets": secrets_of(home),
        "file": secrets_of(home) / "GH_TOKEN",
    }[where]
    os.rename(path, target)
    path.symlink_to(target)
    return path, target


def snapshot(path):
    if path.is_dir():
        return sorted(
            (str(p.relative_to(path)), p.read_bytes() if p.is_file() else None)
            for p in path.rglob("*")
        )
    return path.read_bytes()


OPERATIONS = {
    "replace": lambda: project_secrets.write("shop", "GH_TOKEN", "new"),
    "write": lambda: project_secrets.write("shop", "OTHER", "new"),
    "remove": lambda: project_secrets.remove("shop", "GH_TOKEN"),
    "check_removable": lambda: project_secrets.check_removable("shop"),
    "remove_all": lambda: project_secrets.remove_all("shop"),
}


@pytest.mark.parametrize(
    ("where", "operation"),
    # GH_TOKEN's link is not on the way of OTHER: test_a_link_to_another_file_beside...
    [(w, o) for w in LINKED for o in OPERATIONS if (w, o) != ("file", "write")],
)
def test_a_link_on_the_way_is_refused_and_nothing_is_touched(home, tmp_path, where, operation):
    path, target = make_link(home, tmp_path, where)
    before = snapshot(target)
    with pytest.raises(project_secrets.LinkRefused) as raised:
        OPERATIONS[operation]()
    assert str(raised.value) == (
        f"{path} is a symbolic link: LADO writes and removes a project's secrets only in "
        "its own folders"
    )
    assert path.is_symlink()
    assert snapshot(target) == before


def test_a_link_to_another_file_beside_is_not_on_the_way(home, tmp_path):
    make_link(home, tmp_path, "file")
    project_secrets.write("shop", "OTHER", "o")
    assert (secrets_of(home) / "OTHER").read_text() == "o"


def test_lado_home_itself_may_be_a_link(tmp_path, monkeypatch):
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "home").symlink_to(real)
    monkeypatch.setenv("LADO_HOME", str(tmp_path / "home"))
    project_secrets.write("shop", "GH_TOKEN", "g")
    assert (real / "projects" / "shop" / "secrets" / "GH_TOKEN").read_text() == "g"


def test_unused_names_the_files_agents_do_not_get_without_a_value(home, tmp_path):
    project_secrets.write("shop", "GH_TOKEN", "canary-good")
    project_secrets.write("shop", "SENTRY_DSN", "canary-loose")
    (secrets_of(home) / "SENTRY_DSN").chmod(0o644)
    (tmp_path / "t").write_text("canary-link")
    (secrets_of(home) / "LINKED").symlink_to(tmp_path / "t")
    found = project_secrets.unused("shop")
    assert found == [
        ("LINKED", "a symbolic link"),
        ("SENTRY_DSN", "readable or writable by others: chmod 600 it"),
    ]
    assert "canary-" not in repr(found)
    assert project_secrets.unused("acme") == []
    secrets_of(home).chmod(0o755)
    assert project_secrets.unused("shop") == [
        (None, "readable or writable by others: chmod 700 it")
    ]


def test_names_hold_a_loose_file_its_agents_do_not_get(home):
    """A loose mode is the human's to mend by a replace: the name stays a secret (the page
    shows it with Replace), as it stays taken (`held`)."""
    project_secrets.write("shop", "SENTRY_DSN", "s")
    (secrets_of(home) / "SENTRY_DSN").chmod(0o644)
    assert project_secrets.names("shop") == ["SENTRY_DSN"]
