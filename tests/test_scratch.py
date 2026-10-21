"""lado.scratch: a session from scratch in a new or empty folder (openspec change
start-from-scratch)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from lado import runtime, scratch, state

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


def test_the_default_folder(home_workspace, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LADO_REPOS", raising=False)
    assert scratch.default_folder("sait-kofeini") == tmp_path / "workspace" / "sait-kofeini"
    assert not (tmp_path / "workspace").exists()  # Create and start makes it


def test_the_default_folder_in_the_container(tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "projects"))
    name = scratch.names("Сайт кофейни").name
    folder = scratch.default_folder(name)
    assert folder == tmp_path / "projects" / "sait-kofeini"
    assert scratch.check_target(str(folder)).state == "new"


NO_AUTHOR = "git doesn't know who signs the agents' commits: it has no user.name or user.email"


def test_a_developers_machine(git_config, tmp_path):
    assert scratch.author_problem(str(tmp_path / "shop")) is None


def test_a_git_without_the_email(git_config, tmp_path):
    git_config.write_text("[user]\n\tname = Ann\n")
    problem = scratch.author_problem(str(tmp_path / "shop"))
    assert (problem.kind, str(problem)) == ("no_author", NO_AUTHOR)
    assert problem.hint == runtime.Hint(
        "Tell git who you are, once for this computer:",
        'git config --global user.name "Your Name" && git config --global user.email '
        "you@example.com",
    )


def test_an_empty_name_is_no_author(git_config, tmp_path):
    git_config.write_text("[user]\n\tname =\n\temail = ann@example.com\n")
    assert scratch.author_problem(str(tmp_path)).kind == "no_author"


def test_the_container_without_the_variables(git_config, tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    git_config.write_text("")
    problem = scratch.author_problem(str(tmp_path))
    assert str(problem) == NO_AUTHOR
    assert problem.hint == runtime.Hint(
        "Set LADO_GIT_NAME and LADO_GIT_EMAIL in the .env file next to compose.yaml, then "
        "restart LADO there:",
        "docker compose up -d",
    )


def test_a_container_switched_off_is_outside(git_config, tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "0")
    git_config.write_text("")
    assert scratch.author_problem(str(tmp_path)).hint.command.startswith("git config --global")


def test_no_git_is_lad_5s_problem_not_an_author_one(git_config, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    with pytest.raises(runtime.FolderProblem) as refused:
        scratch.author_problem(str(tmp_path))
    assert refused.value.kind == "no_git"


def git_out(path, *args) -> str:
    result = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_a_new_folder(git_config, tmp_path):
    path = tmp_path / "a" / "sait-kofeini"
    root = scratch.make(str(path), "sait-kofeini")
    assert os.path.realpath(root) == os.path.realpath(path)
    assert os.listdir(path) == [".git"]
    assert git_out(path, "log", "--format=%s %an") == "Start from scratch LADO test"
    assert git_out(path, "symbolic-ref", "--short", "HEAD") == "main"
    assert git_out(path, "status", "--porcelain") == ""
    assert git_out(path, "ls-tree", "-r", "HEAD") == ""


def test_an_empty_folder_keeps_finders_file_out_of_the_commit(git_config, tmp_path):
    path = tmp_path / "coffee-site"
    path.mkdir()
    (path / ".DS_Store").write_bytes(b"\0")
    scratch.make(str(path), "coffee-site")
    assert git_out(path, "ls-tree", "-r", "HEAD") == ""
    assert git_out(path, "status", "--porcelain") == "?? .DS_Store"


def test_the_branch_is_gits_default_one(git_config, tmp_path):
    git_config.write_text(git_config.read_text() + "[init]\n\tdefaultBranch = trunk\n")
    scratch.make(str(tmp_path / "shop"), "shop")
    assert git_out(tmp_path / "shop", "symbolic-ref", "--short", "HEAD") == "trunk"


def test_no_signing_and_no_hooks(git_config, tmp_path):
    """A global config that signs every commit with a program that fails, and a template
    whose hooks fail or write a file, make the first commit all the same, without them."""
    hooks = tmp_path / "template" / "hooks"
    hooks.mkdir(parents=True)
    for hook in ("pre-commit", "commit-msg", "post-commit"):
        (hooks / hook).write_text(f"#!/bin/sh\ntouch {tmp_path}/{hook}-ran\nexit 1\n")
        (hooks / hook).chmod(0o755)
    git_config.write_text(
        git_config.read_text()
        + "[commit]\n\tgpgsign = true\n[gpg]\n\tprogram = false\n"
        + f"[init]\n\ttemplateDir = {tmp_path / 'template'}\n"
    )
    scratch.make(str(tmp_path / "shop"), "shop")
    assert git_out(tmp_path / "shop", "log", "--format=%s") == "Start from scratch"
    assert not list(tmp_path.glob("*-ran"))


def failing_commit(tmp_path, monkeypatch):
    """A git on PATH whose commit fails, as a broken git or a full disk would."""
    real = shutil.which("git")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "git").write_text(
        "#!/bin/sh\n"
        'for arg in "$@"; do\n'
        '  if [ "$arg" = commit ]; then echo "fatal: no commit today" >&2; exit 128; fi\n'
        "done\n"
        f'exec {real} "$@"\n'
    )
    (bin_dir / "git").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def test_a_failed_commit(git_config, tmp_path, monkeypatch):
    failing_commit(tmp_path, monkeypatch)
    path = tmp_path / "made" / "shop"
    with pytest.raises(scratch.ScratchError) as refused:
        scratch.make(str(path), "shop")
    assert (refused.value.kind, str(refused.value)) == (
        "git_failed",
        f"git could not make {path} a repository: fatal: no commit today",
    )
    assert not (tmp_path / "made").exists()


def test_a_failed_commit_in_an_empty_folder_leaves_it_as_it_was(git_config, tmp_path, monkeypatch):
    failing_commit(tmp_path, monkeypatch)
    path = tmp_path / "coffee-site"
    path.mkdir()
    (path / ".DS_Store").write_bytes(b"\0")
    with pytest.raises(scratch.ScratchError):
        scratch.make(str(path), "coffee-site")
    assert os.listdir(path) == [".DS_Store"]


def test_a_name_a_session_of_another_folder_has_is_refused_first(git_config, tmp_path):
    state.add_session(state.Session("shop", str(tmp_path / "elsewhere"), None, "claude"))
    with pytest.raises(runtime.LadoError, match='session "shop" was started in'):
        scratch.make(str(tmp_path / "shop"), "shop")
    assert not (tmp_path / "shop").exists()


def test_a_folder_with_files_is_refused_with_lad_5s_hint(git_config, tmp_path):
    (tmp_path / "notes.txt").write_text("x")
    with pytest.raises(scratch.ScratchError) as refused:
        scratch.make(str(tmp_path), "notes")
    assert (refused.value.kind, str(refused.value)) == (
        "not_empty",
        f"{tmp_path} is not empty: choose a new or empty folder",
    )
    assert refused.value.hint == runtime.NOT_REPO_HINT
    assert not (tmp_path / ".git").exists()


def test_a_folder_inside_a_repository_is_refused_with_its_start(git_config, tmp_path):
    root = git_init(tmp_path / "my app")
    with pytest.raises(scratch.ScratchError) as refused:
        scratch.make(str(root / "site"), "site")
    real = os.path.realpath(root)
    assert refused.value.kind == "inside_repo"
    assert refused.value.hint == runtime.Hint(
        "Start a session in that repository:", f"lado start '{real}'"
    )
    assert not (root / "site").exists()


def test_a_file_is_refused(git_config, tmp_path):
    (tmp_path / "notes.txt").write_text("x")
    with pytest.raises(scratch.ScratchError) as refused:
        scratch.make(str(tmp_path / "notes.txt"), "notes")
    assert (refused.value.kind, refused.value.hint) == ("not_folder", None)


def test_no_author_is_refused_before_anything(git_config, tmp_path):
    git_config.write_text("")
    with pytest.raises(scratch.ScratchError) as refused:
        scratch.make(str(tmp_path / "shop"), "shop")
    assert refused.value.kind == "no_author"
    assert not (tmp_path / "shop").exists()
