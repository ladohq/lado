"""lado.scratch: a session from scratch in a new or empty folder (openspec change
start-from-scratch)."""

import os
import subprocess
from pathlib import Path

import pytest

from lado import scratch

# The spec's table: each Cyrillic letter and its Latin letters.
TABLE = (
    "а a, б b, в v, г g, ґ g, д d, е e, ё e, є ie, ж zh, з z, и i, і i, ї i, й i, к k, л l, "
    "м m, н n, о o, п p, р r, с s, т t, у u, ф f, х kh, ц ts, ч ch, ш sh, щ shch, ъ , ы y, "
    "ь , э e, ю iu, я ia"
)
LETTERS = [tuple((pair + " ").split(" ")[:2]) for pair in TABLE.split(", ")]


def test_a_cyrillic_name():
    assert scratch.names("Сайт кофейни") == scratch.Names("sait-kofeini", "Сайт кофейни")


def test_a_name_that_is_already_a_name():
    assert scratch.names("coffee-site") == scratch.Names("coffee-site", None)


def test_a_name_with_accents():
    assert scratch.names("Café Noël") == scratch.Names("cafe-noel", "Café Noël")


def test_another_script():
    with pytest.raises(scratch.ScratchError) as refused:
        scratch.names("東京")
    assert str(refused.value) == "the name needs a Latin letter or digit for its folder: type one"


def test_the_table_is_the_specs():
    assert scratch.CYRILLIC == dict(LETTERS)


@pytest.mark.parametrize("letter,latin", LETTERS)
def test_each_letter_of_the_table(letter, latin):
    for text in (letter, letter.upper()):
        assert scratch.names(f"x{text}x").name == f"x{latin}x"


def test_the_text_is_trimmed():
    assert scratch.names("  Сайт  ") == scratch.Names("sait", "Сайт")


@pytest.mark.parametrize("text", ["", "   "])
def test_an_empty_name_is_refused(text):
    with pytest.raises(scratch.ScratchError, match="^type a name$"):
        scratch.names(text)


def test_a_name_is_at_most_80_characters():
    assert scratch.names("a" * 80).name == "a" * 80
    with pytest.raises(scratch.ScratchError, match="^a name is at most 80 characters$"):
        scratch.names("a" * 81)


def test_a_hidden_character_is_refused_by_its_name():
    with pytest.raises(scratch.ScratchError) as refused:
        scratch.names("shop‮")
    assert str(refused.value) == (
        "a name is one line of visible text: U+202E RIGHT-TO-LEFT OVERRIDE is not allowed"
    )


def git_init(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def test_a_missing_folder_is_new(tmp_path):
    path = str(tmp_path / "a" / "shop")
    assert scratch.check_target(path) == scratch.Target(path, "new", "a new folder")


def test_an_empty_folder(tmp_path):
    assert scratch.check_target(str(tmp_path)).state == "empty"
    assert scratch.check_target(str(tmp_path)).text == "an empty folder"


def test_a_folder_finder_made(tmp_path):
    (tmp_path / ".DS_Store").write_bytes(b"\0")
    assert scratch.check_target(str(tmp_path)).state == "empty"


def test_a_folder_with_a_file_beside_finders_is_not_empty(tmp_path):
    (tmp_path / ".DS_Store").write_bytes(b"\0")
    (tmp_path / "notes.txt").write_text("x")
    target = scratch.check_target(str(tmp_path))
    assert (target.state, target.text) == (
        "not_empty",
        f"{tmp_path} is not empty: choose a new or empty folder",
    )


def test_a_file_is_not_a_folder(tmp_path):
    (tmp_path / "notes.txt").write_text("x")
    target = scratch.check_target(str(tmp_path / "notes.txt"))
    assert (target.state, target.text) == (
        "not_folder",
        f"{tmp_path / 'notes.txt'} is a file, not a folder",
    )


def test_a_path_below_a_file_is_not_a_folder(tmp_path):
    (tmp_path / "notes.txt").write_text("x")
    target = scratch.check_target(str(tmp_path / "notes.txt" / "shop"))
    assert (target.state, target.text) == (
        "not_folder",
        f"{tmp_path / 'notes.txt'} is a file, not a folder",
    )


def test_a_folder_of_a_repository(tmp_path):
    root = git_init(tmp_path / "app")
    (root / "site").mkdir()
    path = str(root / "site")
    target = scratch.check_target(path)
    real = os.path.realpath(root)
    assert target == scratch.Target(
        path,
        "inside_repo",
        f"{path} is inside the git repository {real}: choose a folder outside it",
        real,
    )


def test_a_missing_path_under_a_repository_is_inside_it(tmp_path):
    root = git_init(tmp_path / "app")
    target = scratch.check_target(str(root / "a" / "b"))
    assert (target.state, target.root) == ("inside_repo", os.path.realpath(root))


def test_a_link_to_an_empty_folder(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    assert scratch.check_target(str(tmp_path / "link")).state == "empty"


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any folder")
def test_a_folder_lado_may_not_read(tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0)
    try:
        with pytest.raises(scratch.ScratchError) as refused:
            scratch.check_target(str(locked))
    finally:
        locked.chmod(0o700)
    assert refused.value.kind == "no_access"
    assert str(refused.value).startswith(f"cannot look at {locked}: ")


def test_the_default_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert scratch.default_folder("sait-kofeini") == tmp_path / "lado" / "sait-kofeini"


def test_the_default_folder_in_the_container(tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "projects"))
    name = scratch.names("Сайт кофейни").name
    folder = scratch.default_folder(name)
    assert folder == tmp_path / "projects" / "sait-kofeini"
    assert scratch.check_target(str(folder)).state == "new"
