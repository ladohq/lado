import shutil

import pytest
import yaml
from agent_helpers import init_repo, publish

from lado import gitcache, kits, sources


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
    assert "in your window" not in gate  # LADO's instructions say where the human talks
    assert "ask_human" in gate
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
        (lambda p: (p / "kit.yaml").write_text("name: k\ninclude: x\n"), "include is gone"),
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


def test_kits_combine_in_a_session(repo, project):
    make_kit(project, "base", agents={"w": ({}, "")}, skills=["s1"])
    make_kit(project, "extra", skills=["s2"])
    make_kit(project, "top", agents={"rev": ({}, "")})
    env = kits.resolve(repo, ["base", "extra", "default", "top"])
    assert [k.name for k in env.kits] == ["base", "extra", "default", "top"]
    assert list(env.agents) == ["w", "supervisor", "worker", "rev"]
    assert list(env.shared) == ["s1", "s2"]
    # The same kit given twice is one kit.
    assert len(kits.resolve(repo, ["top", "base", "top"]).kits) == 2


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
    assert list(env.shared) == ["s1", "s3"]
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
        ("tool:x", "expected agent:<name>, skill:<name>, mcp:<name> or flow:<name>"),
        ("skill", "expected agent:<name>"),
    ],
)
def test_without_errors(repo, project, item, error):
    make_kit(project, "k", skills=["s"])
    with pytest.raises(kits.KitError, match=error):
        kits.resolve(repo, ["default", "k"], [item])


def test_agent_skills(repo, project):
    make_kit(project, "k", agents={"a": ({"skills": []}, ""), "b": ({}, "")}, skills=["s"])
    env = kits.resolve(repo, ["k"])
    assert env.resolve("a").skills == {}
    assert list(env.resolve("b").skills) == ["s"]
    make_kit(project, "bad", agents={"a": ({"skills": ["missing"]}, "")})
    with pytest.raises(kits.KitError, match='skill "missing" is not visible to agent "a"'):
        kits.resolve(repo, ["bad"])


def test_default_agent(repo, project):
    make_kit(project, "k", agents={"rev": ({}, "")}, default_agent="rev")
    env = kits.resolve(repo, ["default", "k"])
    assert env.worker_role(None).name == "rev"
    assert env.worker_role("worker").name == "worker"
    with pytest.raises(
        kits.KitError, match='no worker role "supervisor" in this session; roles: worker, rev'
    ):
        env.worker_role("supervisor")
    make_kit(project, "j", agents={"x": ({}, "")}, default_agent="x")
    with pytest.raises(kits.KitError, match="kits set different default agents"):
        kits.resolve(repo, ["default", "k", "j"])
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


FLOW = """\
name: {name}
description: the {name} flow
start: build
states:
  build:
    agent: {role}
    do: Build it.
    outcomes: {{done: finish}}
  finish:
    end: true
"""


def make_flow(kit, name, role="worker"):
    (kit / "flows").mkdir(exist_ok=True)
    (kit / "flows" / f"{name}.yaml").write_text(FLOW.format(name=name, role=role))


def test_flows_are_found_in_the_flows_folder(project):
    kit = make_kit(project, "k")
    make_flow(kit, "ship")
    flow = kits.load(kit).flows["ship"]
    assert (flow.kit, flow.description, flow.path) == (
        "k",
        "the ship flow",
        str(kit.resolve() / "flows" / "ship.yaml"),
    )


@pytest.mark.parametrize(
    ("write", "error"),
    [
        (lambda f: (f / "ship.yaml").write_text("name: [x\n"), "ship.yaml: invalid YAML"),
        (lambda f: (f / "notes.txt").write_text(""), "flows/ holds <name>.yaml files"),
        (lambda f: (f / "ship.yaml").write_text("name: other\n"), "differs from the file name"),
    ],
)
def test_flow_load_errors(project, write, error):
    kit = make_kit(project, "k")
    (kit / "flows").mkdir()
    write(kit / "flows")
    with pytest.raises(kits.KitError, match=error):
        kits.load(kit)


def test_flows_of_the_kits_combine_and_can_be_switched_off(repo, project):
    make_flow(make_kit(project, "base"), "ship")
    make_flow(make_kit(project, "team"), "hotfix")
    env = kits.resolve(repo, ["default", "base", "team"])
    assert sorted(env.flows) == ["hotfix", "ship"]
    env = kits.resolve(repo, ["default", "base", "team"], ["flow:ship"])
    assert list(env.flows) == ["hotfix"]
    with pytest.raises(kits.KitError, match="cannot switch off flow:nope: no such flow"):
        kits.resolve(repo, ["default", "base", "team"], ["flow:nope"])
    with pytest.raises(kits.KitError, match="cannot be switched off for one agent"):
        env.resolve("worker", ["flow:hotfix"])


def test_same_flow_name_in_two_kits_names_both(repo, project):
    make_flow(make_kit(project, "a"), "ship")
    make_flow(make_kit(project, "b"), "ship")
    with pytest.raises(kits.KitError, match='flow "ship" is defined by two kits: a .* and b'):
        kits.resolve(repo, ["a", "b"])


def test_a_flow_role_must_exist_in_the_environment(repo, project):
    kit = make_kit(project, "k", agents={"rev": ({}, "")})
    make_flow(kit, "ship", role="rev")
    env = kits.resolve(repo, ["default", "k"])
    assert env.flow("ship").name == "ship"
    env = kits.resolve(repo, ["default", "k"], ["agent:rev"])
    with pytest.raises(kits.KitError, match='state "build": no role "rev" in this session'):
        env.flow("ship")
    with pytest.raises(kits.KitError, match='no flow "nope"; flows: ship'):
        env.flow("nope")


def pack_kit(project, name="k", packs=None, agents=None, skills=(), **meta):
    """A kit whose dependencies.skills are `packs`."""
    deps = {"skills": packs or {}}
    return make_kit(project, name, agents=agents, skills=skills, dependencies=deps, **meta)


def test_a_local_pack_is_read_in_place(project):
    pack = make_pack(project.parent / "packs" / "mine", ["eng/tdd", "plan"])
    kit = kits.load(pack_kit(project, packs={"mine": "../../packs/mine"}, skills=["own"]))
    (found,) = kit.packs.values()
    assert (found.name, found.address, found.ref, found.path) == (
        "mine",
        "../../packs/mine",
        None,
        pack.resolve(),
    )
    assert list(found.skills) == ["tdd", "plan"]
    tdd = found.skills["tdd"]
    assert (tdd.path, tdd.kit, tdd.pack) == (
        (pack / "skills" / "eng" / "tdd").resolve(),
        "k",
        "mine",
    )
    assert list(kit.skills) == ["own"] and kit.skills["own"].pack is None


def test_pack_folders_choose_the_skills(project):
    make_pack(project.parent / "p", ["engineering/tdd", "productivity/grill", "misc/tdd"])
    spec = {"from": "../../p", "folders": ["skills/engineering", "skills/productivity/"]}
    kit = kits.load(pack_kit(project, packs={"p": spec}))
    assert kit.packs["p"].folders == ("skills/engineering", "skills/productivity")
    assert list(kit.packs["p"].skills) == ["tdd", "grill"]


@pytest.mark.parametrize(
    ("packs", "error"),
    [
        (
            {"p": "https://github.com/o/r"},
            r"dependencies.skills.p: pin a version: https://github.com/o/r@<tag or commit>",
        ),
        ({"p": "/abs/pack"}, "dependencies.skills.p: a local pack is a path relative to the kit"),
        ({"p": "~/pack"}, "a local pack is a path relative to the kit"),
        ({"p": "../p@v1"}, "a local pack has no version; drop @v1"),
        ({"p": "../nope"}, r"dependencies.skills.p: .*nope does not exist"),
        ({"Bad Name": "../p"}, 'dependencies.skills: "Bad Name" is not a valid pack name'),
        ({"p": {"from": "../p", "skill": "x"}}, "dependencies.skills.p: unknown keys skill"),
        ({"p": {"folders": ["skills"]}}, "dependencies.skills.p: from is missing"),
        ({"p": 3}, r"dependencies.skills.p: expected <address>@<ref> or \{from, folders\}"),
        ({"p": {"from": "../p", "folders": ["../up"]}}, "folders are relative paths inside"),
        ({"p": {"from": "../p", "folders": ["nope"]}}, r"folder .*nope does not exist"),
    ],
)
def test_dependency_errors_name_the_file_and_the_entry(project, packs, error):
    make_pack(project / "p", ["s"])
    path = pack_kit(project, packs=packs)
    with pytest.raises(kits.KitError, match=error) as exc:
        kits.load(path)
    assert str(exc.value).startswith(str(path.resolve() / "kit.yaml"))


@pytest.mark.parametrize(
    ("deps", "error"),
    [
        ({"tools": ["x"]}, "dependencies: unknown keys tools; allowed: lado, skills"),
        ({"lado": "0.19"}, r'dependencies.lado must be ">=X.Y" or ">=X.Y.Z"'),
        ({"lado": ">=0.19, <1"}, r'dependencies.lado must be ">=X.Y" or ">=X.Y.Z"'),
        ({"lado": ">=99.0"}, r'kit "k" needs LADO >=99.0, this is \S+; upgrade LADO'),
        ({"skills": ["x"]}, "dependencies.skills must map pack names"),
        ([], "dependencies must be a mapping"),
    ],
)
def test_dependencies_errors(project, deps, error):
    path = make_kit(project, "k", dependencies=deps)
    with pytest.raises(kits.KitError, match=error):
        kits.load(path)


def test_a_kit_may_need_an_older_lado(project):
    kits.load(make_kit(project, "k", dependencies={"lado": ">=0.1"}))
    kits.load(make_kit(project, "j", dependencies={"lado": ">=0.1.5"}))


def test_include_is_gone(project):
    path = make_kit(project, "k", include=["default"])
    with pytest.raises(kits.KitError) as exc:
        kits.load(path)
    assert (
        "include is gone: a kit takes skill packs from dependencies.skills "
        "(<name>: <git-url>@<version>); a kit no longer includes another kit"
    ) in str(exc.value)


@pytest.mark.parametrize("where", [".", "kits/team", "deep/er"])
def test_a_pack_with_a_kit_yaml_is_a_kit(project, where):
    pack = make_pack(project.parent / "p", ["s"])
    (pack / where).mkdir(parents=True, exist_ok=True)
    (pack / where / "kit.yaml").write_text("name: team\n")
    with pytest.raises(kits.KitError, match=r"\.\./\.\./p is a kit, not a skill pack"):
        kits.load(pack_kit(project, packs={"p": "../../p"}))


def test_one_skill_name_twice_in_a_kit_names_both_folders(project):
    one = make_pack(project.parent / "one", ["tdd"])
    two = make_pack(project.parent / "two", ["eng/tdd"])
    with pytest.raises(kits.KitError) as exc:
        kits.load(pack_kit(project, "k", packs={"one": "../../one", "two": "../../two"}))
    message = str(exc.value)
    assert 'skill "tdd"' in message and "choose them with folders" in message
    assert str((one / "skills" / "tdd").resolve()) in message
    assert str((two / "skills" / "eng" / "tdd").resolve()) in message
    with pytest.raises(kits.KitError, match='skill "tdd"'):
        kits.load(pack_kit(project, "j", packs={"one": "../../one"}, skills=["tdd"]))
    # Within one pack too.
    make_pack(one / "skills" / "other", ["tdd"])
    with pytest.raises(kits.KitError, match='skill "tdd"'):
        kits.load(pack_kit(project, "i", packs={"one": "../../one"}))


def no_git(monkeypatch):
    def run(*args, **kwargs):
        raise AssertionError(f"git ran: {args}")

    monkeypatch.setattr(gitcache.subprocess, "run", run)


def test_load_does_not_fetch_and_fetch_does(tmp_path, project, monkeypatch, lado_home):
    url = publish(init_repo(tmp_path / "pack"), {"skills/eng/tdd/SKILL.md": SKILL_MD}, tag="v1")
    path = pack_kit(project, packs={"pack": f"{url}@v1"}, agents={"w": ({}, "")})
    with monkeypatch.context() as patch:
        no_git(patch)
        kit = kits.load(path)
    pack = kit.packs["pack"]
    assert (pack.address, pack.ref, pack.path, pack.skills) == (url, "v1", None, None)
    assert kit.unfetched() == ["pack"]
    assert not (lado_home / "cache").exists()

    fetched = kits.fetch(kit)
    pack = fetched.packs["pack"]
    assert pack.path == gitcache.clone_dir(url, "v1").resolve()
    assert list(pack.skills) == ["tdd"] and pack.skills["tdd"].pack == "pack"
    assert fetched.unfetched() == []
    # Once in the cache, load reads it without git.
    with monkeypatch.context() as patch:
        no_git(patch)
        assert kits.load(path).packs["pack"].skills == pack.skills
        assert kits.fetch(kits.load(path)).packs == fetched.packs


def test_fetch_errors_name_the_kit(tmp_path, project):
    work = init_repo(tmp_path / "pack")
    url = publish(work, {"skills/tdd/SKILL.md": SKILL_MD}, tag="v1")
    kit = kits.load(pack_kit(project, "k", packs={"pack": f"{url}@main"}))
    with pytest.raises(
        kits.KitError, match=r"kit.yaml: dependencies.skills.pack: .*main is a branch"
    ):
        kits.fetch(kit)
    publish(work, {"kit.yaml": "name: team\n"}, tag="v2")
    kit = kits.load(pack_kit(project, "j", packs={"pack": f"{url}@v2"}))
    with pytest.raises(kits.KitError, match=f"{url}@v2 is a kit, not a skill pack"):
        kits.fetch(kit)


def test_a_local_pack_of_a_kit_from_the_cache_stays_in_its_clone(tmp_path, project):
    files = {
        "kits/team/kit.yaml": "name: team\ndependencies:\n  skills:\n    p: ../../packs/p\n",
        "packs/p/skills/tdd/SKILL.md": SKILL_MD,
        "kits/out/kit.yaml": "name: out\ndependencies:\n  skills:\n    p: ../../../outside\n",
    }
    url = publish(init_repo(tmp_path / "kits"), files, tag="v1")
    make_pack(tmp_path / "outside", ["s"])
    clone = gitcache.fetch_pinned(url, "v1")
    assert list(kits.load(clone / "kits" / "team").packs["p"].skills) == ["tdd"]
    with pytest.raises(kits.KitError) as exc:
        kits.load(clone / "kits" / "out")
    assert (
        "dependencies.skills.p: local pack outside the kit's repository works only on this "
        f"machine; use <git-url>@<ref>"
    ) in str(exc.value)


@pytest.fixture
def three_kits(project):
    """Kits a and b with agents and a pack each, kit n without agents with a pack."""
    for name in ("pa", "pb", "pn"):
        make_pack(project.parent / name, [f"{name}-skill"])
    pack_kit(project, "a", packs={"pa": "../../pa"}, agents={"wa": ({}, "")}, skills=["own-a"])
    pack_kit(project, "b", packs={"pb": "../../pb"}, agents={"wb": ({}, "")})
    pack_kit(project, "n", packs={"pn": "../../pn"}, skills=["own-n"])


def test_an_agent_sees_its_kits_packs_and_the_sessions_shared_skills(repo, project, three_kits):
    env = kits.resolve(repo, ["a", "b", "n"])
    assert sorted(env.resolve("wa").skills) == ["own-a", "own-n", "pa-skill", "pn-skill"]
    assert sorted(env.resolve("wb").skills) == ["own-a", "own-n", "pb-skill", "pn-skill"]
    assert sorted(env.shared) == ["own-a", "own-n", "pn-skill"]
    assert {k: sorted(v) for k, v in env.private.items()} == {"a": ["pa-skill"], "b": ["pb-skill"]}
    pack_kit(project, "c", agents={"wc": ({"skills": ["own-a", "pa-skill"]}, "")})
    with pytest.raises(kits.KitError) as exc:
        kits.resolve(repo, ["a", "c"])
    assert (
        'skill "pa-skill" is not visible to agent "wc" (kit "c"): not a skill of the '
        "session's kits or of kit \"c\"'s dependencies"
    ) in str(exc.value)
    env = kits.resolve(repo, ["a", "c"], ["skill:pa-skill"])
    assert list(env.resolve("wc").skills) == ["own-a"]
    assert list(env.resolve("wa").skills) == ["own-a"]


def test_a_kit_without_agents_shares_its_packs(repo, project, three_kits):
    env = kits.resolve(repo, ["default", "n"])
    assert sorted(env.resolve("worker").skills) == ["own-n", "pn-skill"]
    # Without agents means by what the kit holds, not after --without.
    env = kits.resolve(repo, ["default", "a"], ["agent:wa"])
    assert sorted(env.resolve("worker").skills) == ["own-a"]


def test_one_skill_name_from_two_folders_for_an_agent_is_an_error(repo, project, three_kits):
    clash = make_pack(project.parent / "clash", ["own-a"])
    pack_kit(project, "d", packs={"clash": "../../clash"}, agents={"wd": ({}, "")})
    with pytest.raises(kits.KitError) as exc:
        kits.resolve(repo, ["a", "d"])
    message = str(exc.value)
    assert 'skill "own-a" comes from two folders for the agents of kit "d"' in message
    assert str((project / "a" / "skills" / "own-a").resolve()) in message
    assert str((clash / "skills" / "own-a").resolve()) in message
    # A kit without agents shares its packs: the same clash for every agent.
    pack_kit(project, "e", packs={"clash": "../../clash"})
    with pytest.raises(kits.KitError, match='skill "own-a" is defined by two kits'):
        kits.resolve(repo, ["a", "e"])
    # The same folder by two ways is one skill.
    pack_kit(project, "f", packs={"pa": "../../pa"})
    pack_kit(project, "g", packs={"pa": "../../pa"}, agents={"wg": ({}, "")})
    env = kits.resolve(repo, ["a", "f", "g"])
    assert sorted(env.resolve("wg").skills) == ["own-a", "pa-skill"]


def test_two_kits_take_two_versions_of_one_pack(tmp_path, repo, project):
    work = init_repo(tmp_path / "pack")
    url = publish(work, {"skills/tdd/SKILL.md": SKILL_MD}, tag="v1")
    publish(work, {"skills/tdd/SKILL.md": SKILL_MD + "Second version.\n"}, tag="v2")
    pack_kit(project, "one", packs={"pack": f"{url}@v1"}, agents={"w1": ({}, "")})
    pack_kit(project, "two", packs={"pack": f"{url}@v2"}, agents={"w2": ({}, "")})
    env = kits.resolve(repo, ["one", "two"])
    first, second = env.resolve("w1").skills["tdd"], env.resolve("w2").skills["tdd"]
    assert first.path == gitcache.clone_dir(url, "v1").resolve() / "skills" / "tdd"
    assert second.path == gitcache.clone_dir(url, "v2").resolve() / "skills" / "tdd"
    assert "Second version." in (second.path / "SKILL.md").read_text()
    assert "Second version." not in (first.path / "SKILL.md").read_text()


def test_no_environment_from_a_kit_with_a_pack_not_fetched(tmp_path, project):
    url = publish(init_repo(tmp_path / "pack"), {"skills/tdd/SKILL.md": SKILL_MD}, tag="v1")
    kit = kits.load(pack_kit(project, packs={"pack": f"{url}@v1"}, agents={"w": ({}, "")}))
    with pytest.raises(kits.KitError, match='kit "k": pack not fetched yet: pack'):
        kits.resolve(None, [kit])
    assert list(kits.resolve(None, [kits.fetch(kit)]).resolve("w").skills) == ["tdd"]
