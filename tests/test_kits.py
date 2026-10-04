import json
import re
import shutil
import subprocess

import pytest
import yaml
from agent_helpers import init_repo, publish

from lado import flows, gitcache, kits


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
    assert list(env.agents) == ["worker"]
    assert (env.lead.name, env.lead.kit) == ("supervisor", "default")
    assert env.lead_line() == "lead: supervisor of kit default"
    assert [a.name for a in env.roles()] == ["worker"]
    assert env.role(None).name == "worker"
    assert env.resolve("supervisor").agent is env.lead
    gate = " ".join(env.lead.body.split())
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
    assert (rev.skills, rev.kit) == (["a"], "k")
    assert kit.supervisor is None


def test_kit_names_its_supervisor(project):
    path = make_kit(project, "k", agents={"boss": ({}, ""), "w": ({}, "")}, supervisor="boss")
    assert kits.load(path).supervisor == "boss"


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
                "---\nname: w\ndescription: d\nsupervisor: true\n---\n"
            ),
            "unknown keys supervisor",
        ),
        (
            lambda p: (p / "kit.yaml").write_text("name: k\ndefault_agent: w\n"),
            "unknown keys default_agent",
        ),
        (
            lambda p: (p / "kit.yaml").write_text("name: k\nsupervisor: ghost\n"),
            'supervisor "ghost" is not an agent of kit "k"',
        ),
        (
            lambda p: (p / "agents" / "supervisor.md").write_text(
                "---\nname: supervisor\ndescription: d\n---\n"
            ),
            'agent name "supervisor" is reserved for the session\'s lead',
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
    make_kit(user, "default", agents={"boss": ({}, "user boss")}, supervisor="boss")
    found = kits.find("default", repo)
    assert (found.where, found.path) == ("user", user / "default")
    make_kit(project, "default", agents={"boss": ({}, "project boss")}, supervisor="boss")
    found = kits.find("default", repo)
    assert (found.where, found.path) == ("project", project / "default")
    assert kits.resolve(repo, ["default"]).lead.body == "project boss"
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
    assert list(env.agents) == ["w", "worker", "rev"]
    assert list(env.shared) == ["s1", "s2"]
    # The same kit given twice is one kit.
    assert len(kits.resolve(repo, ["top", "base", "top"]).kits) == 2


def test_name_clash_names_both_kits(repo, project):
    make_kit(project, "a", skills=["s"])
    make_kit(project, "b", skills=["s"])
    with pytest.raises(kits.KitError, match='skill "s" is defined by two kits: a .* and b'):
        kits.resolve(repo, ["a", "b"])
    make_kit(project, "c", agents={"worker": ({}, "")})
    with pytest.raises(kits.KitError, match='agent "worker" is defined by two kits: default') as e:
        kits.resolve(repo, ["default", "c"])
    assert "switch one off: --without agent:worker@default or --without agent:worker@c" in str(
        e.value
    )
    assert e.value.switch_off == ["agent:worker@default", "agent:worker@c"]


def test_one_kit_supervisor_leads(repo, project):
    make_kit(project, "mine", agents={"lead": ({}, "boss"), "w": ({}, "")}, supervisor="lead")
    make_kit(project, "extra", skills=["s"])  # a kit without agents changes nothing
    env = kits.resolve(repo, ["mine", "extra"])
    assert (env.lead.name, env.lead.kit, env.lead.body) == ("lead", "mine", "boss")
    assert list(env.agents) == ["w"] and [a.name for a in env.roles()] == ["w"]
    assert env.lead_line() == "lead: lead of kit mine" and env.warnings == []
    assert list(env.resolve("lead").skills) == ["s"]


def test_no_kit_supervisor_the_builtin_one_leads(repo, project):
    make_kit(project, "team", agents={"w": ({}, "")})
    env = kits.resolve(repo, ["team"])
    assert (env.lead.name, env.lead.kit) == ("supervisor", "default")
    assert env.lead.path == kits.BUILTIN / "default" / "agents" / "supervisor.md"
    assert list(env.agents) == ["w"]  # not the built-in worker
    assert env.lead_line() == "lead: LADO's built-in supervisor (no kit has a supervisor)"
    assert env.warnings == []
    env = kits.resolve(repo, ["team", "default"], ["agent:supervisor@default"])
    assert env.lead.path == kits.BUILTIN / "default" / "agents" / "supervisor.md"
    assert list(env.agents) == ["w", "worker"]


def test_several_kit_supervisors_the_builtin_one_leads(repo, project):
    make_kit(
        project, "a", agents={"supervisor": ({}, "a boss"), "x": ({}, "")}, supervisor=kits.LEAD
    )
    make_kit(
        project, "b", agents={"supervisor": ({}, "b boss"), "y": ({}, "")}, supervisor=kits.LEAD
    )
    env = kits.resolve(repo, ["a", "b"])
    assert env.lead.path == kits.BUILTIN / "default" / "agents" / "supervisor.md"
    assert list(env.agents) == ["x", "y"]
    assert env.lead_line() == (
        "lead: LADO's built-in supervisor (kits a and b each have a supervisor)"
    )
    assert env.warnings == [
        "kit a's supervisor is not used: LADO's built-in supervisor leads (several kits have "
        "a supervisor); to keep one, switch the others off: --without agent:supervisor@b",
        "kit b's supervisor is not used: LADO's built-in supervisor leads (several kits have "
        "a supervisor); to keep one, switch the others off: --without agent:supervisor@a",
    ]
    env = kits.resolve(repo, ["a", "b"], ["agent:supervisor@b"])
    assert (env.lead.kit, env.lead.body, env.warnings) == ("a", "a boss", [])


def test_a_kit_supervisor_is_switched_off_with_its_kit(repo, project):
    make_kit(project, "mine", agents={"lead": ({}, ""), "w": ({}, "")}, supervisor="lead")
    env = kits.resolve(repo, ["mine"], ["agent:lead@mine"])
    assert env.lead.kit == "default"
    # Without @kit, as sessions of older LADOs stored it: the supervisor of the one kit
    # that has it by that name.
    env = kits.resolve(repo, ["default", "mine"], ["agent:supervisor"])
    assert (env.lead.name, env.lead.kit, env.warnings) == ("lead", "mine", [])
    assert env.without == ["agent:supervisor"]
    assert kits.resolve(repo, ["mine"], ["agent:lead"]).lead.kit == "default"


def test_a_supervisor_name_of_several_kits_needs_its_kit(repo, project):
    make_kit(project, "a", agents={"supervisor": ({}, ""), "x": ({}, "")}, supervisor=kits.LEAD)
    make_kit(project, "b", agents={"supervisor": ({}, ""), "y": ({}, "")}, supervisor=kits.LEAD)
    with pytest.raises(
        kits.KitError,
        match="cannot switch off agent:supervisor: it is the supervisor of kits a and b; "
        "use --without agent:supervisor@a or --without agent:supervisor@b",
    ) as e:
        kits.resolve(repo, ["a", "b"], ["agent:supervisor"])
    assert e.value.switch_off == ["agent:supervisor@a", "agent:supervisor@b"]


def test_the_leads_mcp_server_is_switched_off_by_name(repo, project):
    mcp = {"db": {"command": ["db"]}}
    make_kit(project, "mine", agents={"lead": ({"mcp": mcp}, ""), "w": ({}, "")}, supervisor="lead")
    env = kits.resolve(repo, ["mine"], ["mcp:db"])
    assert env.resolve("lead").mcp == {}
    assert list(kits.resolve(repo, ["mine"]).resolve("lead", ["mcp:db@mine"]).mcp) == []


def test_a_lead_step_of_a_kit_flow_is_the_sessions_lead(repo, project):
    path = make_kit(project, "mine", agents={"lead": ({}, ""), "w": ({}, "")}, supervisor="lead")
    (path / "flows").mkdir()
    (path / "flows" / "f.yaml").write_text(LEAD_FLOW)
    flow = kits.resolve(repo, ["mine"]).flow("f")
    assert flow.states["plan"].agent == kits.LEAD
    assert flow.states["build"].agent == "w"
    assert flow.snapshot["states"]["plan"]["agent"] == kits.LEAD
    rebuilt = flows.from_snapshot(json.loads(json.dumps(flow.snapshot)), "mine")
    assert rebuilt.states["plan"].agent == kits.LEAD


LEAD_FLOW = """\
name: f
description: plan then build
start: plan
states:
  plan: {agent: lead, do: plan it, outcomes: {ok: build}}
  build: {agent: w, do: build it, outcomes: {ok: end}}
  end: {end: true}
"""


def test_role_is_required_when_the_session_has_several(repo, project):
    make_kit(project, "k", agents={"rev": ({}, ""), "dev": ({}, "")})
    env = kits.resolve(repo, ["k"])
    with pytest.raises(
        kits.KitError, match="role is required: this session has several worker roles: dev, rev"
    ):
        env.role(None)
    assert env.role("rev").name == "rev"
    with pytest.raises(kits.KitError, match='no worker role "supervisor" in this session'):
        env.role("supervisor")
    assert kits.resolve(repo, ["k"], ["agent:dev"]).role(None).name == "rev"


def test_the_same_name_in_two_kits_is_resolved_with_at_kit(repo, project):
    a = make_kit(project, "a", agents={"reviewer": ({}, "a rev")})
    b = make_kit(project, "b", agents={"reviewer": ({}, "b rev")})
    for kit, flow in ((a, "fa"), (b, "fb"), (b, "same")):
        (kit / "flows").mkdir(exist_ok=True)
        (kit / "flows" / f"{flow}.yaml").write_text(REVIEW_FLOW.format(name=flow))
    (a / "flows" / "same.yaml").write_text(REVIEW_FLOW.format(name="same"))
    with pytest.raises(kits.KitError, match='agent "reviewer" is defined by two kits'):
        kits.resolve(repo, ["a", "b"])
    with pytest.raises(kits.KitError, match='flow "same" is defined by two kits') as e:
        kits.resolve(repo, ["a", "b"], ["agent:reviewer@b"])
    assert e.value.switch_off == ["flow:same@a", "flow:same@b"]
    env = kits.resolve(repo, ["a", "b"], ["agent:reviewer@b", "flow:same@a"])
    assert env.agents["reviewer"].body == "a rev"
    assert env.flow("fb").kit == "b"  # kit b's flow calls kit a's reviewer
    assert env.flows["same"].kit == "b"
    assert env.without == ["agent:reviewer@b", "flow:same@a"]


REVIEW_FLOW = """\
name: {name}
description: review
start: review
states:
  review: {{agent: reviewer, do: review it, outcomes: {{ok: end}}}}
  end: {{end: true}}
"""


def test_skills_and_mcp_are_switched_off_in_one_kit(repo, project):
    mcp = {"db": {"command": ["db"]}}
    a = make_kit(project, "a", agents={"x": ({"mcp": mcp}, "")}, skills=["s"])
    make_pack(a / "pack", ["tdd"])
    (a / "kit.yaml").write_text(
        yaml.safe_dump({"name": "a", "dependencies": {"skills": {"p": "pack"}}})
    )
    make_kit(project, "b", agents={"y": ({"mcp": mcp}, "")}, skills=["t"])
    env = kits.resolve(repo, ["a", "b"], ["skill:s@a", "skill:tdd@a", "mcp:db@b"])
    assert list(env.resolve("x").skills) == ["t"]
    assert list(env.resolve("x").mcp) == ["db"]
    assert list(env.resolve("y").mcp) == []
    env = kits.resolve(repo, ["a", "b"])
    # For one agent: only the skill or server from that kit.
    assert list(env.resolve("y", ["skill:s@a"]).skills) == ["t"]
    assert list(env.resolve("x", ["skill:tdd@a", "skill:t@b"]).skills) == ["s"]
    assert list(env.resolve("x", ["mcp:db@a"]).mcp) == []
    assert list(env.resolve("y", ["mcp:db@a"]).mcp) == ["db"]
    with pytest.raises(kits.KitError, match="kit a has no skill t"):
        env.resolve("x", ["skill:t@a"])
    with pytest.raises(kits.KitError, match="cannot be switched off for one agent"):
        env.resolve("x", ["agent:y@b"])


def test_a_skill_an_agent_names_may_be_switched_off_in_its_kit(repo, project):
    """As with skill:style for the whole session: switched off is no error."""
    make_kit(project, "a", agents={"dev": ({"skills": ["style"]}, "")})
    make_kit(project, "b", skills=["style"])
    for item in ("skill:style", "skill:style@b"):
        assert kits.resolve(repo, ["a", "b"], [item]).resolve("dev").skills == {}


@pytest.mark.parametrize(
    ("item", "error"),
    [
        ("agent:nope@a", "cannot switch off agent:nope@a: kit a has no agent nope; it has: x"),
        ("skill:t@a", "cannot switch off skill:t@a: kit a has no skill t; it has: s"),
        ("mcp:db@b", "cannot switch off mcp:db@b: kit b has no mcp db; it has: none"),
        ("flow:f@a", "cannot switch off flow:f@a: kit a has no flow f; it has: none"),
        ("agent:x@zz", "cannot switch off agent:x@zz: no kit zz in this session; kits: a, b"),
        ("agent:x@", "expected agent:<name>"),
    ],
)
def test_without_at_kit_errors(repo, project, item, error):
    make_kit(project, "a", agents={"x": ({"mcp": {"db": {"command": ["db"]}}}, "")}, skills=["s"])
    make_kit(project, "b", agents={"y": ({}, "")}, skills=["t"])
    with pytest.raises(kits.KitError, match=re.escape(error)):
        kits.resolve(repo, ["a", "b"], [item])


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
        kits.resolve(repo, ["k"], ["agent:w"]).role("w")


@pytest.mark.parametrize(
    ("item", "error"),
    [
        ("skill:nope", "cannot switch off skill:nope: no such skill; there are: s"),
        ("mcp:nope", "no such mcp; there are: none"),
        ("agent:nope", "no such agent; there are: worker"),
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
        "machine; use <git-url>@<ref>"
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


TEAM = "name: team\nversion: 1.0.0\n"
AGENT = "---\nname: w\ndescription: works\n---\nWork.\n"


def links(lado_home):
    folder = lado_home / "kits"
    return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []


def test_add_a_kit_from_the_root_of_a_git_repository(tmp_path, repo, lado_home):
    work = init_repo(tmp_path / "team-kit")
    url = publish(work, {"kit.yaml": TEAM, "agents/w.md": AGENT}, tag="v1.0.0")
    (kit,) = kits.add(f"{url}@v1.0.0")
    link = lado_home / "kits" / "team"
    clone = gitcache.clone_dir(url, "v1.0.0").resolve()
    assert link.is_symlink() and link.resolve() == clone
    # The name is checked against the link's, not the clone's folder (v1.0.0).
    found = kits.find("team", repo)
    assert (found.where, found.path, found.link()) == ("user", link, f"{url}@v1.0.0")
    loaded = found.load()
    assert (loaded.name, loaded.path, list(loaded.agents)) == ("team", clone, ["w"])
    assert loaded.source == f"user {url}@v1.0.0: {clone}"
    assert kits.warnings(loaded) == []


def test_add_the_kits_of_a_repository_or_some_of_them(tmp_path, lado_home):
    files = {
        "kits/a/kit.yaml": "name: a\nversion: 1.0.0\n",
        "kits/b/kit.yaml": "name: b\nversion: 2.0.0\n",
    }
    url = publish(init_repo(tmp_path / "many"), files, tag="v3")
    assert [k.name for k in kits.add(f"{url}@v3", ["b"])] == ["b"]
    assert links(lado_home) == ["b"]
    # A kit that is not a kit's version warns.
    assert kits.warnings(kits.find("b", None).load()) == []
    with pytest.raises(kits.KitError, match=r'no kit "c" in .*; kits there: a, b'):
        kits.add(f"{url}@v3", ["c"])
    with pytest.raises(
        kits.KitError, match='kit "b" is installed already: .*; `lado kits remove b`'
    ):
        kits.add(f"{url}@v3")
    assert links(lado_home) == ["b"]  # nothing of a refused add stays
    kits.remove("b")
    assert [k.name for k in kits.add(f"{url}@v3")] == ["a", "b"]


def test_add_a_local_folder_links_it(tmp_path, repo, lado_home):
    folder = tmp_path / "dev"
    make_kit(folder / "kits", "team", agents={"w": ({}, "Work.")})
    (kit,) = kits.add(str(folder))
    link = lado_home / "kits" / "team"
    assert link.resolve() == (folder / "kits" / "team").resolve()
    assert kits.find("team", repo).link() == str((folder / "kits" / "team").resolve())
    # Read in place: a change in the folder is the kit's.
    (folder / "kits" / "team" / "agents" / "w.md").write_text(AGENT.replace("Work.", "Changed."))
    assert kits.find("team", repo).load().agents["w"].body == "Changed."
    assert kit.where == "user"


@pytest.mark.parametrize(
    ("spec", "error"),
    [
        ("{url}", "pin a version: {url}@<tag or commit>"),
        ("{url}@main", "main is a branch of {url}; pin a tag or a commit"),
        ("{pack}@v1", "{pack}@v1 is a skill pack, not a kit: list it under dependencies.skills"),
        ("{bad}@v1", 'agents/w.md: name "x" differs'),
        ("{tmp}/nowhere", "nowhere is not a folder"),
        ("{tmp}/empty", "no kit in .*empty: a kit has kit.yaml at the root or in kits/<name>/"),
    ],
)
def test_add_errors_leave_no_link(tmp_path, lado_home, spec, error):
    url = publish(init_repo(tmp_path / "team"), {"kit.yaml": TEAM}, tag="v1")
    pack = publish(init_repo(tmp_path / "pack"), {"skills/tdd/SKILL.md": SKILL_MD}, tag="v1")
    bad = publish(
        init_repo(tmp_path / "bad"), {"kit.yaml": TEAM, "agents/w.md": AGENT.replace("w", "x")}
    )
    subprocess.run(["git", "-C", str(tmp_path / "bad"), "tag", "v1"], check=True)
    subprocess.run(["git", "-C", str(tmp_path / "bad"), "push", "-q", bad, "v1"], check=True)
    (tmp_path / "empty").mkdir()
    values = {"url": url, "pack": pack, "bad": bad, "tmp": tmp_path}
    with pytest.raises(kits.KitError, match=error.format(**values)):
        kits.add(spec.format(**values))
    assert links(lado_home) == []


def test_add_refuses_a_name_taken_by_a_folder(tmp_path, lado_home):
    make_kit(lado_home / "kits", "team")
    make_kit(tmp_path / "dev", "team")
    with pytest.raises(kits.KitError, match='kit "team" is installed already'):
        kits.add(str(tmp_path / "dev" / "team"))


def test_update_moves_the_link_to_another_version(tmp_path, repo, lado_home):
    work = init_repo(tmp_path / "team")
    url = publish(work, {"kit.yaml": TEAM}, tag="v1.0.0")
    publish(work, {"kit.yaml": TEAM.replace("1.0.0", "1.1.0")}, tag="v1.1.0")
    kits.add(f"{url}@v1.0.0")
    kit = kits.update("team", "v1.1.0")
    assert (kit.version, kit.path) == ("1.1.0", gitcache.clone_dir(url, "v1.1.0").resolve())
    link = lado_home / "kits" / "team"
    assert link.resolve() == kit.path and links(lado_home) == ["team"]
    assert kits.find("team", repo).link() == f"{url}@v1.1.0"
    # The old version stays in the cache for the agents that run it.
    assert gitcache.clone_dir(url, "v1.0.0").is_dir()
    with pytest.raises(kits.KitError, match="main is a branch"):
        kits.update("team", "main")
    assert link.resolve() == kit.path


def test_update_and_remove_refuse_what_lado_did_not_install(tmp_path, lado_home):
    make_kit(lado_home / "kits", "mine")
    make_kit(tmp_path / "dev", "local")
    kits.add(str(tmp_path / "dev" / "local"))
    with pytest.raises(kits.KitError, match="mine is a folder LADO did not install; nothing to"):
        kits.update("mine", "v1")
    with pytest.raises(kits.KitError, match="local links to the folder .*dev/local: it is read in"):
        kits.update("local", "v1")
    with pytest.raises(kits.KitError, match="not installed by LADO; delete .*mine yourself"):
        kits.remove("mine")
    with pytest.raises(kits.KitError, match='no kit "nope" in '):
        kits.remove("nope")
    assert kits.remove("local") == (tmp_path / "dev" / "local").resolve()
    assert links(lado_home) == ["mine"] and (tmp_path / "dev" / "local").is_dir()


def test_a_broken_link_does_not_stop_other_kits(tmp_path, repo, lado_home):
    make_kit(tmp_path / "dev", "gone")
    kits.add(str(tmp_path / "dev" / "gone"))
    shutil.rmtree(tmp_path / "dev")
    (found,) = [f for f, _ in kits.available(repo) if f.name == "gone"]
    with pytest.raises(kits.KitError, match="gone: broken link → .*; run `lado kits remove gone`"):
        found.load()
    assert kits.resolve(repo, ["default"]).lead.name == "supervisor"
    kits.remove("gone")
    assert links(lado_home) == []


def test_kit_version_is_compared_with_the_tags_of_its_clone(tmp_path):
    work = init_repo(tmp_path / "team")
    url = publish(work, {"kit.yaml": TEAM}, tag="v1.1.0")
    (kit,) = kits.add(f"{url}@v1.1.0")
    assert kits.warnings(kit) == [f"team: version 1.0.0 in kit.yaml, but {url}@v1.1.0 is at v1.1.0"]
    assert kits.lint(kits.load(make_kit(tmp_path, "nov", version=None))) != []


SOURCES_YAML = """\
sources:
- {{name: dev, kind: path, location: {dev}}}
- {{name: team, kind: git, location: {url}, ref: v1}}
- {{name: pack, kind: git, location: https://example.com/pack.git, skills: [skills/eng]}}
- {{name: old, kind: path, location: /nowhere/old}}
- {{name: far, kind: git, location: https://example.com/far.git, ref: v2}}
"""


def test_find_says_how_to_move_from_sources_yaml(tmp_path, repo, lado_home):
    dev = tmp_path / "dev"
    make_kit(dev / "kits", "mine")
    clone = lado_home / "sources" / "team"
    clone.mkdir(parents=True)
    (clone / "kit.yaml").write_text(TEAM)
    make_pack(lado_home / "sources" / "pack", ["eng/tdd"])
    lado_home.mkdir(exist_ok=True)
    (lado_home / "sources.yaml").write_text(
        SOURCES_YAML.format(dev=dev, url="https://example.com/team.git")
    )
    hint = kits.migration_hint()
    assert f"{lado_home / 'sources.yaml'} is no longer read" in hint
    assert f"  lado kits add {dev}\n" in hint
    assert "  lado kits add https://example.com/team.git@v1\n" in hint
    assert (
        "  pack is a skill pack: list it under dependencies.skills of a kit "
        "(pack: {from: https://example.com/pack.git@<tag or commit>, folders: [skills/eng]})"
    ) in hint
    # What is not on disk is not guessed at.
    assert "  old: /nowhere/old is gone; nothing to move\n" in hint
    assert (
        f"  far: no clone in {lado_home / 'sources' / 'far'}; with kits: lado kits add "
        "https://example.com/far.git@v2; a skill pack: list it under dependencies.skills "
        "of a kit (far: https://example.com/far.git@v2)\n"
    ) in hint
    assert f"then delete {lado_home / 'sources.yaml'} and {lado_home / 'sources'}" in hint
    with pytest.raises(kits.KitError) as exc:
        kits.find("mine", repo)
    assert str(exc.value).startswith('kit "mine" not found; looked in ')
    assert hint in str(exc.value)
    (lado_home / "sources.yaml").unlink()
    assert kits.migration_hint() is None
    with pytest.raises(kits.KitError) as exc:
        kits.find("mine", repo)
    assert "sources.yaml" not in str(exc.value)


def test_a_damaged_clone_is_a_kit_error_not_a_crash(tmp_path, lado_home):
    url = publish(init_repo(tmp_path / "team"), {"kit.yaml": TEAM}, tag="v1.1.0")
    (kit,) = kits.add(f"{url}@v1.1.0")
    shutil.rmtree(kit.path / ".git")
    with pytest.raises(kits.KitError, match=f"cannot read the clone {kit.path}: "):
        kits.update("team", "v1.2.0")
    (warning,) = kits.warnings(kit)
    assert warning.startswith(f"team: cannot read the version tags of {kit.path}: ")
