import pytest
import yaml

from lado import kits


def make_kit(base, name, agents=None, skills=(), **meta):
    """Write a kit into base/name. `agents`: name -> (frontmatter extras, body)."""
    path = base / name
    (path / "agents").mkdir(parents=True)
    (path / "kit.yaml").write_text(yaml.safe_dump({"name": name, **meta}))
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
    assert "merge it into your branch" in env.supervisor().body
    assert env.kits[0].where == "built-in"


def test_load_reads_agents_and_skills(project):
    path = make_kit(
        project,
        "k",
        agents={"rev": ({"skills": ["a"]}, "Review. Tools in ${KIT_DIR}/bin; keep ${HOME}.")},
        skills=["a", "b"],
        version="1.2",
    )
    kit = kits.load(path)
    assert (kit.name, kit.version, kit.path) == ("k", "1.2", path.resolve())
    assert list(kit.skills) == ["a", "b"]
    assert kit.skills["a"].path == (path / "skills" / "a").resolve()
    rev = kit.agents["rev"]
    assert rev.body == f"Review. Tools in {path.resolve()}/bin; keep ${{HOME}}."
    assert (rev.skills, rev.supervisor, rev.kit) == (["a"], False, "k")


@pytest.mark.parametrize(
    ("change", "error"),
    [
        (lambda p: (p / "kit.yaml").write_text("name: k\nflows: []\n"), "unknown keys flows"),
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
    assert kits.find("default", repo) == ("user", user / "default")
    make_kit(project, "default", agents={"boss": ({"supervisor": True}, "project boss")})
    assert kits.find("default", repo) == ("project", project / "default")
    assert kits.resolve(repo, ["default"]).supervisor().body == "project boss"
    assert kits.find("default", None)[0] == "user"
    found = [(name, where, shadowed) for name, where, _, shadowed in kits.available(repo)]
    assert found == [
        ("default", "project", False),
        ("default", "user", True),
        ("default", "built-in", True),
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
    for _, _, path, _ in kits.available(None):
        assert kits.lint(kits.load(path)) == []
