import shutil

import pytest
import yaml
from agent_helpers import init_repo, publish

from lado import kits, sources


def make_kit(base, name, agents=None, skills=(), **meta):
    """Write a kit into base/name. `agents`: name -> (frontmatter extras, body)."""
    path = base / name
    (path / "agents").mkdir(parents=True)
    (path / "kit.yaml").write_text(yaml.safe_dump({"name": name, "version": "1.0.0", **meta}))
    for agent, (extra, body) in (agents or {}).items():
        front = yaml.safe_dump({"name": agent, "description": f"the {agent}", **extra})
        (path / "agents" / f"{agent}.md").write_text(f"---\n{front}---\n{body}\n")
    for skill in skills:
        (path / "skills" / skill).mkdir(parents=True)
        front = f"name: {skill}\ndescription: use {skill}\nlicense: MIT\n"
        (path / "skills" / skill / "SKILL.md").write_text(f"---\n{front}---\nDo {skill}.\n")
    return path


@pytest.fixture
def project(repo):
    """The repo's project kits folder."""
    return repo / ".lado" / "kits"


def test_builtin_default_kit():
    env = kits.resolve(None, ["default"])
    assert list(env.agents) == ["supervisor", "worker"]
    assert env.supervisor().name == "supervisor"
    assert [a.name for a in env.roles()] == ["worker"]
    assert env.worker_role(None).name == "worker"
    gate = " ".join(env.supervisor().body.split())
    assert "Wait for the human's explicit OK before you merge it and call finish_worker" in gate
    assert "Without that OK, do not merge or finish the worker." in gate
    assert env.kits[0].where == "built-in"


def test_load_reads_agents_and_skills(project):
    path = make_kit(
        project,
        "k",
        agents={"rev": ({"skills": ["a"]}, "Review. Tools in ${KIT_DIR}/bin; keep ${HOME}.")},
        skills=["a", "b"],
        version="1.2.0",
    )
    kit = kits.load(path)
    assert (kit.name, kit.version, kit.path) == ("k", "1.2.0", path.resolve())
    assert list(kit.skills) == ["a", "b"]
    assert kit.skills["a"].path == (path / "skills" / "a").resolve()
    rev = kit.agents["rev"]
    assert rev.body == f"Review. Tools in {path.resolve()}/bin; keep ${{HOME}}."
    assert (rev.skills, rev.supervisor, rev.kit) == (["a"], False, "k")


@pytest.mark.parametrize(
    ("change", "error"),
    [
        (lambda p: (p / "kit.yaml").write_text("name: k\nflows: []\n"), "unknown keys flows"),
        (lambda p: (p / "kit.yaml").write_text("name: k\nversion: 1.2\n"), "must be X.Y.Z"),
        (lambda p: (p / "kit.yaml").write_text("name: k\nversion: v1.2.0\n"), "must be X.Y.Z"),
        (lambda p: (p / "kit.yaml").write_text("name: [k\n"), "invalid YAML"),
        (lambda p: (p / "kit.yaml").write_text("name: other\n"), 'differs from the folder "k"'),
        (lambda p: (p / "kit.yaml").write_text("name: k\ninclude: x\n"), "include must be"),
        (
            lambda p: (p / "agents" / "w.md").write_text(
                "---\nname: w\ndescription: d\nmodel: x\n---\n"
            ),
            "unknown keys model",
        ),
        (lambda p: (p / "agents" / "w.md").write_text("no frontmatter"), "YAML frontmatter"),
        (
            lambda p: (p / "agents" / "w.md").write_text("---\nname: v\ndescription: d\n---\n"),
            'differs from the file name "w"',
        ),
        (
            lambda p: (p / "agents" / "w.md").write_text("---\nname: w\n---\n"),
            "description is missing",
        ),
        (
            lambda p: (p / "agents" / "w.md").write_text(
                "---\nname: w\ndescription: d\nsupervisor: yes please\n---\n"
            ),
            "supervisor must be true or false",
        ),
        (
            lambda p: (p / "agents" / "w.md").write_text(
                "---\nname: w\ndescription: d\n---\n${SKILL_DIR}"
            ),
            "SKILL_DIR",
        ),
        (lambda p: (p / "skills" / "s" / "SKILL.md").unlink(), "no SKILL.md"),
        (
            lambda p: (p / "skills" / "s" / "SKILL.md").write_text(
                "---\nname: t\ndescription: d\n---\n"
            ),
            'name "t" differs from the folder "s"',
        ),
        (lambda p: (p / "agents" / "notes.txt").write_text(""), "holds <name>.md files"),
    ],
)
def test_load_errors(project, change, error):
    path = make_kit(project, "k", agents={"w": ({}, "")}, skills=["s"])
    change(path)
    with pytest.raises(kits.KitError, match=error):
        kits.load(path)


def test_load_reports_every_problem(project):
    path = make_kit(project, "k", skills=["s"])
    (path / "kit.yaml").write_text("name: k\nbogus: 1\n")
    (path / "skills" / "s" / "SKILL.md").write_text("---\nname: t\ndescription: d\n---\n")
    with pytest.raises(kits.KitError) as exc:
        kits.load(path)
    assert "unknown keys bogus" in str(exc.value) and 'name "t"' in str(exc.value)


@pytest.mark.parametrize(
    ("mcp", "error"),
    [
        ({"x": {"url": "http://x"}}, r"unknown keys url \(only stdio servers"),
        ({"x": {"command": "srv"}}, "non-empty list of strings"),
        ({"x": {"command": ["srv"], "env": {"A": 1}}}, "env must map names to strings"),
        ({"lado": {"command": ["srv"]}}, "invalid name"),
        ({"x": {"command": ["${HOME}/srv"]}}, r"unknown variable \$\{HOME\}"),
        ([], "mcp must map server names"),
    ],
)
def test_mcp_errors(project, mcp, error):
    path = make_kit(project, "k", agents={"w": ({"mcp": mcp}, "")})
    with pytest.raises(kits.KitError, match=error):
        kits.load(path)


def test_mcp_variables(project, monkeypatch):
    mcp = {"db": {"command": ["${KIT_DIR}/srv", "--x"], "env": {"T": "${TOKEN}-${KIT_DIR}"}}}
    path = make_kit(project, "k", agents={"w": ({"mcp": mcp}, "")})
    env = kits.resolve(None, [kits.load(path)])
    servers = env.resolve("w").mcp_servers({"TOKEN": "secret"})
    kit_dir = path.resolve()
    assert servers["db"].command == [f"{kit_dir}/srv", "--x"]
    assert servers["db"].env == {"T": f"secret-{kit_dir}"}
    monkeypatch.delenv("TOKEN", raising=False)
    with pytest.raises(kits.KitError, match="environment variable TOKEN is not set"):
        env.resolve("w").mcp_servers()


def test_lookup_order(repo, project, lado_home):
    user = lado_home / "kits"
    make_kit(user, "default", agents={"boss": ({"supervisor": True}, "user boss")})
    found = kits.find("default", repo)
    assert (found.where, found.path) == ("user", user / "default")
    make_kit(project, "default", agents={"boss": ({"supervisor": True}, "project boss")})
    found = kits.find("default", repo)
    assert (found.where, found.path) == ("project", project / "default")
    assert kits.resolve(repo, ["default"]).supervisor().body == "project boss"
    assert kits.find("default", None).where == "user"
    found = [(f.name, f.where, by) for f, by in kits.available(repo)]
    assert found == [
        ("default", "project", None),
        ("default", "user", "project"),
        ("default", "built-in", "project"),
    ]
    with pytest.raises(kits.KitError, match=f'kit "nope" not found; looked in {project}'):
        kits.find("nope", repo)


def test_include_combines_kits(repo, project):
    make_kit(project, "base", agents={"w": ({}, "")}, skills=["s1"])
    make_kit(project, "extra", skills=["s2"], include=["base"])
    make_kit(project, "top", agents={"rev": ({}, "")}, include=["extra", "base", "default"])
    env = kits.resolve(repo, ["top"])
    assert [k.name for k in env.kits] == ["base", "extra", "default", "top"]
    assert list(env.agents) == ["w", "supervisor", "worker", "rev"]
    assert list(env.skills) == ["s1", "s2"]
    # The same kit given twice is one kit.
    assert len(kits.resolve(repo, ["top", "base"]).kits) == 4


def test_include_cycle(repo, project):
    make_kit(project, "a", include=["b"])
    make_kit(project, "b", include=["c"])
    make_kit(project, "c", include=["a"])
    with pytest.raises(kits.KitError, match="kits include each other: a -> b -> c -> a"):
        kits.resolve(repo, ["a"])


def test_name_clash_names_both_kits(repo, project):
    make_kit(project, "a", skills=["s"])
    make_kit(project, "b", skills=["s"])
    with pytest.raises(kits.KitError, match='skill "s" is defined by two kits: a .* and b'):
        kits.resolve(repo, ["a", "b"])
    make_kit(project, "c", agents={"worker": ({}, "")})
    with pytest.raises(kits.KitError, match='agent "worker" is defined by two kits: default'):
        kits.resolve(repo, ["default", "c"])


def test_two_supervisors_need_one_switched_off(repo, project):
    make_kit(project, "mine", agents={"lead": ({"supervisor": True}, "")})
    env = kits.resolve(repo, ["default", "mine"])
    with pytest.raises(kits.KitError, match="more than one agent with `supervisor: true`"):
        env.supervisor()
    env = kits.resolve(repo, ["default", "mine"], ["agent:supervisor"])
    assert env.supervisor().name == "lead"
    with pytest.raises(kits.KitError, match="no agent with `supervisor: true`"):
        kits.resolve(repo, ["mine"], ["agent:lead"]).supervisor()


def test_without(repo, project):
    mcp = {"db": {"command": ["db"]}, "web": {"command": ["web"]}}
    make_kit(
        project,
        "k",
        agents={"w": ({"mcp": mcp}, ""), "rev": ({"skills": ["s1", "s2"]}, "")},
        skills=["s1", "s2", "s3"],
    )
    env = kits.resolve(repo, ["k"], ["skill:s2", "mcp:web"])
    assert list(env.skills) == ["s1", "s3"]
    w = env.resolve("w")
    assert (list(w.skills), list(w.mcp)) == (["s1", "s3"], ["db"])
    assert list(env.resolve("rev").skills) == ["s1"]
    # For one agent, on top of the session's.
    w = env.resolve("w", ["skill:s1", "mcp:db"])
    assert (list(w.skills), list(w.mcp)) == (["s3"], [])
    with pytest.raises(kits.KitError, match="cannot be switched off for one agent"):
        env.resolve("w", ["agent:rev"])
    with pytest.raises(kits.KitError, match="no worker role"):
        kits.resolve(repo, ["k"], ["agent:w"]).worker_role("w")


@pytest.mark.parametrize(
    ("item", "error"),
    [
        ("skill:nope", "cannot switch off skill:nope: no such skill; there are: s"),
        ("mcp:nope", "no such mcp; there are: none"),
        ("agent:nope", "no such agent; there are: supervisor, worker"),
        ("tool:x", "expected agent:<name>, skill:<name> or mcp:<name>"),
        ("skill", "expected agent:<name>"),
    ],
)
def test_without_errors(repo, project, item, error):
    make_kit(project, "k", skills=["s"], include=["default"])
    with pytest.raises(kits.KitError, match=error):
        kits.resolve(repo, ["k"], [item])


def test_agent_skills(repo, project):
    make_kit(project, "k", agents={"a": ({"skills": []}, ""), "b": ({}, "")}, skills=["s"])
    env = kits.resolve(repo, ["k"])
    assert env.resolve("a").skills == {}
    assert list(env.resolve("b").skills) == ["s"]
    make_kit(project, "bad", agents={"a": ({"skills": ["missing"]}, "")})
    with pytest.raises(kits.KitError, match='skill "missing" is not in the kits'):
        kits.resolve(repo, ["bad"])


def test_default_agent(repo, project):
    make_kit(project, "k", agents={"rev": ({}, "")}, include=["default"], default_agent="rev")
    env = kits.resolve(repo, ["k"])
    assert env.worker_role(None).name == "rev"
    assert env.worker_role("worker").name == "worker"
    with pytest.raises(
        kits.KitError, match='no worker role "supervisor" in this session; roles: worker, rev'
    ):
        env.worker_role("supervisor")
    make_kit(project, "j", agents={"x": ({}, "")}, default_agent="x")
    with pytest.raises(kits.KitError, match="kits set different default agents"):
        kits.resolve(repo, ["k", "j"])
    make_kit(project, "bad", default_agent="ghost")
    with pytest.raises(kits.KitError, match='default_agent "ghost" is not an agent'):
        kits.resolve(repo, ["bad"])


def test_lint_finds_hardcoded_paths(project):
    mcp = {"x": {"command": ["/usr/local/bin/srv"], "env": {"D": "~/data"}}}
    body = "Read ${KIT_DIR}/docs, src/lado/ and https://x.org/a/b; not /Users/me/notes.md."
    path = make_kit(project, "k", agents={"w": ({"mcp": mcp}, body)}, skills=["s"])
    (path / "skills" / "s" / "SKILL.md").write_text(
        "---\nname: s\ndescription: d\n---\nRun `~/bin/tool`.\n"
    )
    problems = kits.lint(kits.load(path))
    assert len(problems) == 4
    assert '"/Users/me/notes.md."' in problems[0]
    assert 'command: hardcoded path "/usr/local/bin/srv"' in problems[1]
    assert '"~/data"' in problems[2]
    assert '"~/bin/tool"' in problems[3]
    assert all("use ${KIT_DIR}" in p for p in problems)


def test_builtin_kits_are_clean():
    for found, _ in kits.available(None):
        assert kits.lint(found.load()) == []


SKILL_MD = "---\nname: tdd\ndescription: test first\n---\n"


def make_pack(base, skills):
    """A skill pack: SKILL.md folders under skills/, e.g. "eng/tdd"; no kit.yaml."""
    for skill in skills:
        name = skill.rsplit("/", 1)[-1]
        (base / "skills" / skill).mkdir(parents=True)
        (base / "skills" / skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: use {name}\n---\n"
        )
    return base


def test_source_with_kits_folder_and_root_kit(tmp_path):
    folder = tmp_path / "many"
    make_kit(folder / "kits", "a")
    make_kit(folder / "kits", "b")
    found = kits.in_source(sources.add(str(folder)))
    assert [(f.name, f.where, f.pack) for f in found] == [
        ("a", "source many", False),
        ("b", "source many", False),
    ]
    assert found[0].load().origin.name == "many"

    # One kit at the root: its name comes from kit.yaml, not from the folder.
    root = make_kit(tmp_path, "checkout", skills=["s"])
    (root / "kit.yaml").write_text("name: solo\nversion: 2.0.0\n")
    (found,) = kits.in_source(sources.add(str(root)))
    kit = found.load()
    assert (kit.name, kit.version, list(kit.skills), kit.where) == (
        "solo",
        "2.0.0",
        ["s"],
        "source checkout",
    )


def test_skill_pack_finds_nested_skills(tmp_path):
    pack = make_pack(tmp_path / "Team Pack", ["eng/tdd", "eng/review", "writing"])
    # Folders inside a skill belong to it.
    make_pack(pack / "skills" / "writing", ["examples"])
    (found,) = kits.in_source(sources.add(str(pack)))
    kit = found.load()
    assert (kit.name, kit.pack, kit.agents, kit.version) == ("team-pack", True, {}, "")
    assert list(kit.skills) == ["review", "tdd", "writing"]
    assert kit.skills["tdd"].path == (pack / "skills" / "eng" / "tdd").resolve()
    assert kit.description == "skill pack, 3 skills"
    assert kits.lint(kit) == []

    make_pack(pack / "skills" / "other", ["tdd"])
    with pytest.raises(kits.KitError, match='skill "tdd" is also in'):
        found.load()


@pytest.mark.parametrize(
    ("layout", "error"),
    [
        (lambda p: make_kit(p / "deep" / "er", "k"), "a source keeps kits in kits/<name>/"),
        (
            lambda p: (make_kit(p / "kits", "k"), make_pack(p, ["s"])),
            "skills of a source with kits belong in a kit",
        ),
        (
            lambda p: (make_kit(p / "kits", "solo"), (p / "kit.yaml").write_text("name: solo\n")),
            'has two kits named "solo"',
        ),
    ],
)
def test_source_layout_errors(tmp_path, layout, error):
    folder = tmp_path / "src"
    folder.mkdir()
    layout(folder)
    source = sources.add(str(folder))
    with pytest.raises(kits.KitError, match=error):
        kits.in_source(source)


def test_missing_source_folder_is_an_error(tmp_path, repo):
    folder = make_pack(tmp_path / "gone", ["s"])
    sources.add(str(folder))
    shutil.rmtree(folder)
    with pytest.raises(kits.KitError, match='source "gone": .* does not exist; run `lado sources'):
        kits.find("default", repo)


def test_lookup_order_with_sources(tmp_path, repo, project, lado_home):
    one, two = tmp_path / "one", tmp_path / "two"
    for folder in (one, two):
        make_kit(folder / "kits", "shared", description=folder.name)
        make_kit(folder / "kits", "default", agents={"boss": ({"supervisor": True}, "")})
    make_kit(lado_home / "kits", "default")
    sources.add(str(one))
    sources.add(str(two))
    assert kits.find("shared", repo).path == one / "kits" / "shared"
    assert kits.find("default", repo).where == "user"
    found = [(f.name, f.where, by) for f, by in kits.available(repo)]
    assert found == [
        ("default", "user", None),
        ("default", "source one", "user"),
        ("shared", "source one", None),
        ("default", "source two", "user"),
        ("shared", "source two", "source one"),
        ("default", "built-in", "user"),
    ]
    with pytest.raises(kits.KitError, match=f"looked in {project}, {lado_home / 'kits'}, {one}"):
        kits.find("nope", repo)


def test_include_across_sources(tmp_path, repo):
    url = publish(init_repo(tmp_path / "pack"), {"skills/eng/tdd/SKILL.md": SKILL_MD})
    pack = sources.add(url)
    make_kit(tmp_path / "dev" / "kits", "team", agents={"w": ({}, "")}, include=["pack"])
    sources.add(str(tmp_path / "dev"))
    env = kits.resolve(repo, ["team"])
    assert [(k.name, k.where) for k in env.kits] == [
        ("pack", "source pack"),
        ("team", "source dev"),
    ]
    assert env.skills["tdd"].path == (pack.path() / "skills" / "eng" / "tdd").resolve()
    assert env.resolve("w").skills == {"tdd": env.skills["tdd"]}
    assert env.kits[0].source == f"source pack @ {pack.revision()}: {pack.path().resolve()}"


def test_version_must_be_semver_and_match_the_tag(tmp_path, repo):
    work = init_repo(tmp_path / "team")
    url = publish(work, {"kit.yaml": "name: team\nversion: 1.0.0\n"}, tag="v1.0.0")
    source = sources.add(url)
    kit = kits.find("team", repo).load()
    assert kits.warnings(kit) == []
    publish(work, {"kit.yaml": "name: team\nversion: 1.0.0\ndescription: d\n"}, tag="v1.1.0")
    source.update()
    assert kits.warnings(kits.find("team", repo).load()) == [
        f"team: version 1.0.0 in kit.yaml, but team is at v1.1.0 ({source.describe()})"
    ]
    # Without a version tag on the commit there is nothing to compare.
    publish(work, {"kit.yaml": "name: team\n"})
    source.update()
    kit = kits.find("team", repo).load()
    assert kits.warnings(kit) == []
    assert kits.lint(kit) == [f"{kit.path / 'kit.yaml'}: version is missing; use X.Y.Z"]


def test_skill_pack_with_skills_folders(tmp_path):
    pack = make_pack(tmp_path / "pack", ["engineering/tdd", "productivity/grill", "misc/tdd"])
    (found,) = kits.in_source(sources.add(str(pack), "whole"))
    with pytest.raises(kits.KitError) as exc:
        found.load()
    message = str(exc.value)
    assert f'{pack / "skills" / "misc" / "tdd"}: skill "tdd" is also in' in message
    assert str((pack / "skills" / "engineering" / "tdd").resolve()) in message
    assert "lado sources add --skills" in message

    source = sources.add(str(pack), "picked", ["skills/engineering", "skills/productivity/"])
    assert source.skills == ("skills/engineering", "skills/productivity")
    assert sources.get("picked") == source  # kept in sources.yaml
    (found,) = kits.in_source(source)
    assert list(found.load().skills) == ["tdd", "grill"]

    missing = sources.add(str(pack), "missing", ["skills/nope"])
    with pytest.raises(kits.KitError, match="skills folder .*skills/nope does not exist"):
        kits.in_source(missing)
    with_kits = make_kit(tmp_path / "with-kits" / "kits", "k").parent.parent
    filtered = sources.add(str(with_kits), skills=["kits"])
    with pytest.raises(kits.KitError, match="only choose the skills of a skill pack"):
        kits.in_source(filtered)
