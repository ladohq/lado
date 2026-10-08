import json
import re
import shutil
import subprocess

import pytest
import yaml
from agent_helpers import init_repo, publish

import lado
from lado import flows, gitcache, kits, marketplaces, mcp_exec, state


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
    servers = env.resolve("w").mcp_servers({"TOKEN": "s3cr3t"})
    kit_dir = path.resolve()
    # The value stays in the agent's environment: the server is started by the wrapper.
    assert "s3cr3t" not in repr(servers)
    assert servers["db"].command == mcp_exec.wrap(
        "db", [f"{kit_dir}/srv", "--x"], {"T": f"${{TOKEN}}-{kit_dir}"}
    )
    assert servers["db"].env == {}
    monkeypatch.delenv("TOKEN", raising=False)
    with pytest.raises(kits.KitError, match="environment variable TOKEN is not set"):
        env.resolve("w").mcp_servers()


def test_mcp_without_references_is_not_wrapped(project):
    mcp = {"db": {"command": ["srv"], "env": {"MODE": "${KIT_DIR}/ro"}}}
    path = make_kit(project, "k", agents={"w": ({"mcp": mcp}, "")})
    servers = kits.resolve(None, [kits.load(path)]).resolve("w").mcp_servers({})
    assert servers["db"].command == ["srv"]
    assert servers["db"].env == {"MODE": f"{path.resolve()}/ro"}


def test_mcp_literals_stay_beside_the_templates(project):
    mcp = {"db": {"command": ["srv"], "env": {"MODE": "ro", "T": "${TOKEN}"}}}
    path = make_kit(project, "k", agents={"w": ({"mcp": mcp}, "")})
    servers = kits.resolve(None, [kits.load(path)]).resolve("w").mcp_servers({"TOKEN": "s"})
    assert servers["db"].env == {"MODE": "ro"}
    assert servers["db"].command == mcp_exec.wrap("db", ["srv"], {"T": "${TOKEN}"})


def test_lookup_order(tmp_path, repo, project, lado_home):
    user = make_kit(
        tmp_path / "dev", "default", agents={"boss": ({}, "user boss")}, supervisor="boss"
    )
    state.add_kit(state.InstalledKit("default", folder=str(user)))
    found = kits.find("default", repo)
    assert (found.where, found.path, found.installed) == ("user", user, state.get_kit("default"))
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
    with pytest.raises(kits.KitError) as exc:
        kits.find("nope", repo)
    assert str(exc.value) == (
        f'kit "nope" not found; looked in {project}, the installed kits in '
        f"{lado_home / 'lado.db'}, {kits.BUILTIN}"
    )
    # A kit in LADO_HOME/kits, the place of older LADOs, is not found.
    make_kit(lado_home / "kits", "old")
    with pytest.raises(kits.KitError, match='kit "old" not found'):
        kits.find("old", repo)


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
        "kit a's supervisor does not lead (several kits have a supervisor): its prompt is the "
        "built-in supervisor's skill lead-a; to make it the lead, switch the others off: "
        "--without agent:supervisor@b",
        "kit a's supervisor lists no skills: its lead skill carries none",
        "kit b's supervisor does not lead (several kits have a supervisor): its prompt is the "
        "built-in supervisor's skill lead-b; to make it the lead, switch the others off: "
        "--without agent:supervisor@a",
        "kit b's supervisor lists no skills: its lead skill carries none",
    ]
    env = kits.resolve(repo, ["a", "b"], ["agent:supervisor@b"])
    assert (env.lead.kit, env.lead.body, env.warnings) == ("a", "a boss", [])


def lead_kit(project, name, sup=None, pack=None, skills=(), body=None):
    """Kit `name` with a supervisor (frontmatter `sup`), a role and, with `pack`, a local
    pack of those skills whose SKILL.md says which kit it is."""
    packs = {}
    if pack:
        folder = make_pack(project.parent / f"pack-{name}", pack)
        for skill in pack:
            md = folder / "skills" / skill / "SKILL.md"
            md.write_text(md.read_text() + f"Version of {name}.\n")
        packs = {"p": f"../../pack-{name}"}
    agents = {"supervisor": (sup or {}, body or f"{name} boss"), f"w{name}": ({}, "")}
    return pack_kit(project, name, packs=packs, agents=agents, skills=skills, supervisor=kits.LEAD)


def test_no_lead_skills_when_a_kit_supervisor_leads(repo, project):
    lead_kit(project, "a", {"skills": ["tdd"]}, pack=["tdd"])
    env = kits.resolve(repo, ["a"])
    assert env.kit_supervisors == {} and env.lead_skills() == []


def test_each_kit_supervisor_that_does_not_lead_gives_a_lead_skill(repo, project):
    lead_kit(
        project, "a", {"skills": ["tdd", "own-a"], "description": "Leads a."}, ["tdd"], ["own-a"]
    )
    lead_kit(project, "b", {"skills": ["tdd"]}, pack=["tdd"])
    env = kits.resolve(repo, ["a", "b", "default"])
    assert list(env.kit_supervisors) == ["a", "b"]  # not the built-in default's
    a, b = env.lead_skills()
    assert (a.name, a.kit, a.body) == ("lead-a", "a", "a boss")
    assert a.description == (
        "How kit a wants its work led: read it before you take a task for its roles or "
        "flows. Leads a."
    )
    assert list(a.skills) == ["tdd", "own-a"] and list(b.skills) == ["tdd"]
    # Each kit's own version of one skill.
    assert "Version of a." in (a.skills["tdd"].path / "SKILL.md").read_text()
    assert "Version of b." in (b.skills["tdd"].path / "SKILL.md").read_text()
    assert a.skills["tdd"].path != b.skills["tdd"].path
    # Kit packs stay private: the lead does not get them.
    assert "tdd" not in env.resolve("supervisor").skills


def test_a_kit_supervisor_switched_off_gives_no_lead_skill(repo, project):
    lead_kit(project, "a")
    lead_kit(project, "b")
    lead_kit(project, "c")
    env = kits.resolve(repo, ["a", "b", "c"], ["agent:supervisor@b"])
    assert [s.name for s in env.lead_skills()] == ["lead-a", "lead-c"]


def test_a_lead_skill_without_the_skills_switched_off(repo, project):
    lead_kit(project, "a", {"skills": ["tdd", "plan"]}, pack=["tdd", "plan"])
    lead_kit(project, "b", {"skills": ["own-b"]}, skills=["own-b"])
    env = kits.resolve(repo, ["a", "b"], ["skill:tdd@a", "skill:own-b"])
    a, b = env.lead_skills()
    assert list(a.skills) == ["plan"] and b.skills == {}


def test_a_skill_a_kit_supervisor_cannot_see_is_an_error(repo, project):
    """As if it led: its skills are checked when it does not lead too."""
    lead_kit(project, "a", {"skills": ["nope"]})
    lead_kit(project, "b")
    with pytest.raises(kits.KitError, match='skill "nope" is not visible to agent "supervisor"'):
        kits.resolve(repo, ["a", "b"])


def test_the_mcp_servers_of_a_kit_supervisor_are_named(repo, project):
    mcp = {"db": {"command": ["db"]}, "web": {"command": ["web"]}}
    lead_kit(project, "a", {"mcp": mcp})
    lead_kit(project, "b")
    assert kits.resolve(repo, ["a", "b"]).lead_skills()[0].missing_mcp == ["db", "web"]
    for item in ("mcp:db@a", "mcp:db"):
        assert kits.resolve(repo, ["a", "b"], [item]).lead_skills()[0].missing_mcp == ["web"]


def test_warnings_say_how_kit_supervisors_are_used(repo, project):
    mcp = {"db": {"command": ["db"]}, "web": {"command": ["web"]}}
    lead_kit(project, "a", {"skills": [], "mcp": mcp})
    env = kits.resolve(repo, ["a", "default"])
    assert env.warnings == [
        "kit a's supervisor does not lead (several kits have a supervisor): its prompt is the "
        "built-in supervisor's skill lead-a; to make it the lead, switch the others off: "
        "--without agent:supervisor@default",
        "MCP servers of kit a's supervisor (db, web) are not available to the session's lead",
        # Switching kit a's supervisor off would not make another the lead: no way out here.
        "kit default's supervisor leads as LADO's built-in supervisor (several kits have a "
        "supervisor)",
    ]
    assert kits.resolve(repo, ["a", "default"], ["mcp:db", "mcp:web@a"]).warnings[1:] == [
        env.warnings[2]
    ]


def test_a_skill_named_like_a_lead_skill_is_an_error(repo, project):
    lead_kit(project, "x")
    lead_kit(project, "y", skills=["lead-x"])
    with pytest.raises(kits.KitError) as e:
        kits.resolve(repo, ["x", "y"])
    message = str(e.value)
    assert 'skill "lead-x" of kit y' in message
    assert str((project / "y" / "skills" / "lead-x").resolve()) in message
    assert "the lead skill of kit x's supervisor" in message
    assert e.value.switch_off == ["skill:lead-x", "agent:supervisor@x"]
    for way_out in e.value.switch_off:
        kits.resolve(repo, ["x", "y"], [way_out])


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
        yaml.safe_dump({"name": "a", "version": "1.0.0", "dependencies": {"skills": {"p": "pack"}}})
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


def test_lint_names_the_graph_problems_of_each_flow(project):
    kit = make_kit(project, "k", agents={"worker": ({}, "")})
    make_flow(kit, "ship")
    (kit / "flows" / "loop.yaml").write_text(
        FLOW.format(name="loop", role="worker").replace(
            "{done: finish}", "{done: finish, again: build}"
        )
    )
    loaded = kits.load(kit)  # the kit still loads
    path = loaded.flows["loop"].path
    assert kits.lint(loaded) == [
        f"{path}: cycle build -> build has no state with max_visits and no gate; "
        "agents could loop forever"
    ]


def test_warnings_name_a_role_that_acts_in_no_flow(project):
    agents = {"boss": ({}, ""), "worker": ({}, ""), "idle": ({}, "")}
    kit = make_kit(project, "k", agents=agents, supervisor="boss")
    assert kits.warnings(kits.load(kit)) == []  # no flows: roles are spawned without them
    make_flow(kit, "ship")
    loaded = kits.load(kit)
    assert kits.warnings(loaded) == [
        f'{loaded.agents["idle"].path}: role "idle" acts in no state of the kit\'s flows; '
        "it can still be spawned outside a flow"
    ]


def test_warnings_name_a_flow_role_that_is_not_in_the_kit(project):
    kit = make_kit(project, "k", agents={"worker": ({}, "")})
    make_flow(kit, "ship", role="worker")
    make_flow(kit, "other", role="reviewer")
    make_flow(kit, "lead", role=kits.LEAD)  # the session's lead's step
    loaded = kits.load(kit)
    assert kits.warnings(loaded) == [
        f'{loaded.flows["other"].path}: state "build": role "reviewer" is not in kit "k"; '
        "a session needs a kit that has it"
    ]


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
        "kits/team/kit.yaml": (
            "name: team\nversion: 1.0.0\ndependencies:\n  skills:\n    p: ../../packs/p\n"
        ),
        "packs/p/skills/tdd/SKILL.md": SKILL_MD,
        "kits/out/kit.yaml": (
            "name: out\nversion: 1.0.0\ndependencies:\n  skills:\n    p: ../../../outside\n"
        ),
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


def rows(lado_home):
    """The installed kits' names; LADO_HOME/kits is never made."""
    assert not (lado_home / "kits").exists()
    return [kit.name for kit in state.list_kits()]


def rev(work, ref) -> str:
    return subprocess.run(
        ["git", "-C", str(work), "rev-parse", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def kit_repo(tmp_path, *versions, name="team", files=None):
    """A kit's repository with a tag v<version> for each version, its kit.yaml saying it,
    published to a bare repo: (the work repo, the bare repo's URL)."""
    work = init_repo(tmp_path / f"{name}-kit")
    url = ""
    for version in versions:
        kit_yaml = f"name: {name}\nversion: {version}\n"
        url = publish(work, {"kit.yaml": kit_yaml, **(files or {})}, tag=f"v{version}")
    return work, url


def move_tag(work, url, tag):
    """Make a new commit and move `tag` to it, on the remote too (a force push)."""
    git = ["git", "-C", str(work)]
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "changed"], check=True)
    subprocess.run([*git, "tag", "-f", tag], check=True, capture_output=True)
    subprocess.run([*git, "push", "-q", "-f", url, tag], check=True, capture_output=True)


def test_add_takes_the_latest_release_and_the_plan_changes_nothing(
    tmp_path, repo, lado_home, capsys
):
    work, url = kit_repo(tmp_path, "1.0.0", "1.1.0", "1.2.0-rc.1", files={"agents/w.md": AGENT})
    plan = kits.plan_add(url)
    assert (plan.name, plan.address, plan.tag, plan.commit) == (
        "team",
        url,
        "v1.1.0",
        rev(work, "v1.1.0"),
    )
    assert (plan.source, plan.needs_confirmation, plan.installed, plan.warnings) == (
        "git",
        True,
        None,
        (),
    )
    assert plan.kit.version == "1.1.0"
    assert rows(lado_home) == [] and capsys.readouterr() == ("", "")
    kit = kits.install(plan)
    row = state.get_kit("team")
    assert (row.address, row.tag, row.commit, row.folder, row.marketplace) == (
        url,
        "v1.1.0",
        rev(work, "v1.1.0"),
        None,
        None,
    )
    assert row.installed_at and row.updated_at is None and rows(lado_home) == ["team"]
    clone = gitcache.clone_dir(url, "v1.1.0").resolve()
    assert kit.path == clone and kit.source == f"user {url}@v1.1.0: {clone}"
    found = kits.find("team", repo)
    assert (found.where, found.path.resolve(), found.link()) == ("user", clone, f"{url}@v1.1.0")
    # The clone's folder is named after its tag, not the kit: an installed kit loads anyway.
    loaded = found.load()
    assert (loaded.name, loaded.path, list(loaded.agents)) == ("team", clone, ["w"])
    assert loaded.source == f"user {url}@v1.1.0: {clone}"
    assert kits.warnings(loaded) == []
    assert found.release("v1.1.0").version == "1.1.0"
    with pytest.raises(kits.KitError) as exc:
        kits.plan_add(url)
    assert str(exc.value) == (
        f'kit "team" is installed already: {url}@v1.1.0; `lado kits update team` or '
        "`lado kits remove team` first"
    )


def test_add_takes_a_pre_release_when_asked(tmp_path, lado_home):
    _, url = kit_repo(tmp_path, "1.0.0", "1.1.0-rc.2", "1.1.0-rc.10")
    assert kits.plan_add(url, pre=True).tag == "v1.1.0-rc.10"
    assert kits.plan_add(f"{url}@v1.1.0-rc.2").tag == "v1.1.0-rc.2"
    assert kits.plan_add(f"{url}@v1.0.0").tag == "v1.0.0"


@pytest.mark.parametrize(
    ("ref", "error"),
    [
        ("{commit}", "{url}@{commit}: a kit is pinned by its version tag vX.Y.Z"),
        ("main", "{url}@main: a kit is pinned by its version tag vX.Y.Z; to try an unreleased "),
        ("1.0.0", "{url}@1.0.0: a kit is pinned by its version tag vX.Y.Z"),
        ("v9.9.9", "{url} has no tag v9.9.9; its versions: v1.0.0"),
    ],
)
def test_add_takes_only_a_version_tag_it_has(tmp_path, lado_home, ref, error):
    work, url = kit_repo(tmp_path, "1.0.0")
    values = {"url": url, "commit": rev(work, "HEAD")}
    with pytest.raises(kits.KitError, match=re.escape(error.format(**values))):
        kits.plan_add(f"{url}@{ref.format(**values)}")


def test_the_tag_and_kit_yaml_must_agree(tmp_path, lado_home):
    url = publish(init_repo(tmp_path / "team"), {"kit.yaml": TEAM}, tag="v1.2.0")
    with pytest.raises(
        kits.KitError,
        match=re.escape(
            f"{url}@v1.2.0: kit.yaml says version 1.0.0; the tag and kit.yaml must agree"
        ),
    ):
        kits.plan_add(url)


def test_a_repository_without_releases_is_refused(tmp_path, lado_home):
    work = init_repo(tmp_path / "team")
    url = publish(work, {"kit.yaml": TEAM})
    with pytest.raises(kits.KitError, match=re.escape(f"{url} has no version tags vX.Y.Z")):
        kits.plan_add(url)
    subprocess.run(["git", "-C", str(work), "tag", "v1.0.0-rc.1"], check=True)
    subprocess.run(["git", "-C", str(work), "push", "-q", url, "v1.0.0-rc.1"], check=True)
    with pytest.raises(
        kits.KitError,
        match=re.escape(f"{url} has pre-releases only (v1.0.0-rc.1): add --pre or @<tag>"),
    ):
        kits.plan_add(url)


def test_the_latest_version_that_needs_a_newer_lado_is_refused(tmp_path, lado_home):
    work, url = kit_repo(tmp_path, "1.3.0")
    kit_yaml = 'name: team\nversion: 1.4.0\ndependencies:\n  lado: ">=99.1"\n'
    publish(work, {"kit.yaml": kit_yaml}, tag="v1.4.0")
    with pytest.raises(kits.KitError) as exc:
        kits.plan_add(url)
    assert str(exc.value) == (
        f"team 1.4.0 needs LADO 99.1, this is {lado.__version__}; upgrade LADO, or add an "
        f"older version: lado kits add {url}@v1.3.0"
    )
    assert rows(lado_home) == []


def test_a_folder_released_at_a_tag_has_the_rules_of_add(tmp_path):
    """`lado kits check <folder> --tag` and `lado kits add <address>@<tag>` share them."""
    root = make_kit(tmp_path, "team", version="1.2.0")
    assert kits.load_release(root, f"{root}@v1.2.0", "v1.2.0").version == "1.2.0"
    cases = {
        "": f"{root}@: a kit is pinned by its version tag vX.Y.Z",
        "main": f"{root}@main: a kit is pinned by its version tag vX.Y.Z; to try an unreleased",
        "1.2.0": f"{root}@1.2.0: a kit is pinned by its version tag vX.Y.Z",
        "v1.3.0": f"{root}@v1.3.0: kit.yaml says version 1.2.0; the tag and kit.yaml must agree",
    }
    for tag, error in cases.items():
        with pytest.raises(kits.KitError, match=re.escape(error)):
            kits.load_release(root, f"{root}@{tag}", tag)
    old = make_kit(tmp_path / "old", "kits/team")
    with pytest.raises(kits.KitError) as exc:
        kits.load_release(old.parent.parent, "x@v1.0.0", "v1.0.0")
    assert str(exc.value) == (
        "x@v1.0.0: kits in kits/<name>/ are no longer supported: a kit is one repository "
        "with kit.yaml at its root"
    )


def test_a_folder_that_needs_a_newer_lado_has_the_text_of_add(tmp_path):
    root = make_kit(tmp_path, "team", version="1.4.0", dependencies={"lado": ">=99.1"})
    for tag in ("v1.4.0", None):
        with pytest.raises(kits.KitError) as exc:
            kits.load_release(root, str(root), tag)
        assert str(exc.value) == (
            f"team 1.4.0 needs LADO 99.1, this is {lado.__version__}; upgrade LADO"
        )


def test_a_bare_name_is_no_kit_of_a_marketplace_without_m(lado_home):
    with pytest.raises(kits.KitError) as exc:
        kits.plan_add("lado-dev")
    assert str(exc.value) == (
        '"lado-dev" is neither a git address nor a folder; for a kit of a marketplace add '
        "-m <marketplace> (lado marketplaces lists them)"
    )
    assert not (lado_home / "marketplaces").exists()


def marketplace(tmp_path, name="team-m", **listed):
    murl = publish(
        init_repo(tmp_path / f"{name}-market"),
        {"marketplace.yaml": "kits:\n" + "".join(f"  {k}: {u}\n" for k, u in listed.items())},
    )
    return marketplaces.add(name, murl)


def test_add_a_kit_of_a_marketplace(tmp_path, lado_home, monkeypatch):
    _, url = kit_repo(tmp_path, "1.0.0", "1.1.0")
    marketplace(tmp_path, team=url, other=url)
    plan = kits.plan_add("team", market="team-m")
    assert (plan.tag, plan.address, plan.source, plan.needs_confirmation, plan.marketplace) == (
        "v1.1.0",
        url,
        "marketplace team-m",
        True,
        "team-m",
    )
    old = kits.plan_add("team@v1.0.0", market="team-m")
    assert old.tag == "v1.0.0"
    # The row records the marketplace it was added from; an update keeps it, and its time.
    kits.install(old)
    added = state.get_kit("team")
    assert (added.marketplace, added.tag, added.updated_at) == ("team-m", "v1.0.0", None)
    update = kits.plan_update("team")
    assert (update.source, update.marketplace) == ("marketplace team-m", "team-m")
    kits.install(update)
    updated = state.get_kit("team")
    assert (updated.marketplace, updated.tag) == ("team-m", "v1.1.0")
    assert updated.installed_at == added.installed_at and updated.updated_at is not None
    kits.remove("team")
    with pytest.raises(
        kits.KitError,
        match=re.escape(f'marketplace "team-m" lists "other" at {url}, but its kit is "team"'),
    ):
        kits.plan_add("other", market="team-m")
    with pytest.raises(marketplaces.MarketplaceError, match='no kit "nope" in marketplace'):
        kits.plan_add("nope", market="team-m")
    official = publish(
        init_repo(tmp_path / "official"), {"marketplace.yaml": f"kits:\n  team: {url}\n"}
    )
    monkeypatch.setattr(marketplaces, "OFFICIAL_URL", official)
    plan = kits.plan_add("team", market="official")
    assert (plan.source, plan.needs_confirmation) == ("official", False)


def test_add_a_local_folder_installs_it_in_place(tmp_path, repo, lado_home):
    # The folder's name need not be the kit's.
    folder = make_kit(tmp_path / "dev", "team", agents={"w": ({}, "Work.")})
    folder = folder.rename(tmp_path / "dev" / "team-work")
    plan = kits.plan_add(str(folder))
    assert (plan.source, plan.tag, plan.needs_confirmation) == ("folder", None, False)
    kit = kits.install(plan)
    row = state.get_kit("team")
    assert (row.folder, row.address, row.tag, row.commit) == (
        str(folder.resolve()),
        None,
        None,
        None,
    )
    assert rows(lado_home) == ["team"]
    found = kits.find("team", repo)
    assert (found.path, found.link()) == (folder.resolve(), str(folder.resolve()))
    # Read in place: a change in the folder is the kit's.
    (folder / "agents" / "w.md").write_text(AGENT.replace("Work.", "Changed."))
    assert found.load().agents["w"].body == "Changed."
    assert found.load().source == f"user: {folder.resolve()}"
    assert kit.where == "user"
    # kit.yaml renamed after it was installed: the row's name is no longer the kit's.
    (folder / "kit.yaml").write_text("name: other\nversion: 1.0.0\n")
    for load in (found.load, lambda: found.release(None)):
        with pytest.raises(kits.KitError) as exc:
            load()
        assert str(exc.value) == (
            f'kit "team" is installed from {folder.resolve()}, but its kit.yaml names it '
            f'"other": `lado kits remove team`, then `lado kits add {folder.resolve()}`'
        )


@pytest.mark.parametrize(
    ("spec", "error"),
    [
        (
            "{many}",
            "{many}@v1.0.0: kits in kits/<name>/ are no longer supported: a kit is one "
            "repository with kit.yaml at its root",
        ),
        ("{pack}", "{pack}@v1.0.0 is a skill pack, not a kit: list it under dependencies.skills"),
        ("{bad}", 'agents/w.md: name "x" differs'),
        ("{tmp}/nowhere", "nowhere is not a folder"),
        ("{tmp}/empty@v1.0.0", "a local folder has no version; drop @v1.0.0"),
        ("{tmp}/empty", "no kit in .*empty: a kit has kit.yaml at its root"),
        ("{tmp}/dev", "dev: kits in kits/<name>/ are no longer supported"),
    ],
)
def test_add_errors_leave_no_link(tmp_path, lado_home, spec, error):
    many = publish(init_repo(tmp_path / "many"), {"kits/a/kit.yaml": TEAM}, tag="v1.0.0")
    pack = publish(init_repo(tmp_path / "pack"), {"skills/tdd/SKILL.md": SKILL_MD}, tag="v1.0.0")
    bad = publish(
        init_repo(tmp_path / "bad"),
        {"kit.yaml": TEAM, "agents/w.md": AGENT.replace("w", "x")},
        tag="v1.0.0",
    )
    (tmp_path / "empty").mkdir()
    make_kit(tmp_path / "dev" / "kits", "a")
    values = {"many": many, "pack": pack, "bad": bad, "tmp": tmp_path}
    with pytest.raises(kits.KitError, match=error.format(**values)):
        kits.install(kits.plan_add(spec.format(**values)))
    assert rows(lado_home) == []


def test_add_refuses_a_name_installed_already(tmp_path, lado_home):
    first = make_kit(tmp_path / "dev", "team")
    plan = kits.plan_add(str(first))
    kits.install(plan)
    make_kit(tmp_path / "other", "team")
    with pytest.raises(kits.KitError, match=f'kit "team" is installed already: {first.resolve()}'):
        kits.plan_add(str(tmp_path / "other" / "team"))
    # Two adds planned at once: the second install is refused.
    with pytest.raises(kits.KitError, match='kit "team" is installed already'):
        kits.install(plan)
    assert state.get_kit("team").folder == str(first.resolve())


def test_an_update_of_a_kit_removed_meanwhile_is_refused(tmp_path, lado_home):
    work, url = kit_repo(tmp_path, "1.0.0")
    kits.install(kits.plan_add(url))
    publish(work, {"kit.yaml": TEAM.replace("1.0.0", "1.1.0")}, "v1.1.0")
    plan = kits.plan_update("team")
    kits.remove("team")  # by another process, while the update was planned
    with pytest.raises(kits.KitError) as exc:
        kits.install(plan)
    assert str(exc.value) == 'kit "team" is no longer installed; `lado kits add` it again'
    assert rows(lado_home) == []


def test_update_goes_to_the_latest_and_names_new_mcp_servers(tmp_path, repo, lado_home):
    work, url = kit_repo(tmp_path, "1.0.0")
    kits.install(kits.plan_add(url))
    agent = "---\nname: w\ndescription: d\nmcp: {db: {command: [db]}, fs: {command: [fs]}}\n---\n"
    publish(work, {"kit.yaml": TEAM.replace("1.0.0", "1.1.0"), "agents/w.md": agent}, "v1.1.0")
    plan = kits.plan_update("team")
    assert (plan.tag, plan.installed, plan.new_mcp, plan.needs_confirmation) == (
        "v1.1.0",
        "v1.0.0",
        ("db", "fs"),
        False,
    )
    assert plan.source == "git" and sorted(plan.mcp) == ["db", "fs"]
    assert state.get_kit("team").tag == "v1.0.0"  # a plan only
    kit = kits.install(plan)
    assert (kit.version, kit.path) == ("1.1.0", gitcache.clone_dir(url, "v1.1.0").resolve())
    row = state.get_kit("team")
    assert (row.tag, row.commit) == ("v1.1.0", rev(work, "v1.1.0"))
    assert rows(lado_home) == ["team"]
    assert kits.find("team", repo).link() == f"{url}@v1.1.0"
    # The old version stays in the cache for the agents that run it.
    assert gitcache.clone_dir(url, "v1.0.0").is_dir()
    back = kits.plan_update("team", "v1.0.0")
    assert (back.tag, back.new_mcp) == ("v1.0.0", ())
    with pytest.raises(kits.KitError, match="a kit is pinned by its version tag"):
        kits.plan_update("team", "main")
    assert state.get_kit("team").tag == "v1.1.0"


def test_a_moved_tag_is_warned_about(tmp_path, lado_home):
    work, url = kit_repo(tmp_path, "1.0.0")
    installed = rev(work, "v1.0.0")
    kits.install(kits.plan_add(url))
    move_tag(work, url, "v1.0.0")
    moved = (
        f"tag v1.0.0 of {url} now points to {rev(work, 'v1.0.0')}, installed {installed}; "
        "the kit was changed under the same version"
    )
    assert kits.plan_update("team").warnings == (moved,)
    (row,) = kits.outdated()
    assert row.warnings == (moved,)
    kits.remove("team")
    # Added again with a clone in the cache already: the same check, with the same tag.
    plan = kits.plan_add(f"{url}@v1.0.0")
    assert plan.warnings == (moved,) and plan.commit == installed


def test_outdated_checks_each_kit_from_git_and_says_why_not_the_others(tmp_path, lado_home):
    work, url = kit_repo(tmp_path, "1.0.0")
    kits.install(kits.plan_add(url))
    publish(work, {"kit.yaml": TEAM.replace("1.0.0", "1.1.0")}, "v1.1.0")
    publish(work, {"kit.yaml": TEAM.replace("1.0.0", "1.2.0-rc.1")}, "v1.2.0-rc.1")
    _, solo = kit_repo(tmp_path, "2.0.0", name="solo")
    kits.install(kits.plan_add(solo))
    kits.install(kits.plan_add(str(make_kit(tmp_path / "dev", "local"))))
    kits.install(kits.plan_add(str(make_kit(tmp_path / "dev", "moved"))))
    shutil.rmtree(tmp_path / "dev" / "moved")
    _, cleaned = kit_repo(tmp_path, "1.0.0", name="cleaned")
    kits.install(kits.plan_add(cleaned))
    shutil.rmtree(gitcache.clone_dir(cleaned, "v1.0.0"))
    rows = {row.name: row for row in kits.outdated()}
    assert list(rows) == ["cleaned", "local", "moved", "solo", "team"]
    team = rows["team"]
    assert (team.installed, team.latest, team.pre, team.note) == (
        "v1.0.0",
        "v1.1.0",
        "v1.2.0-rc.1",
        "",
    )
    assert (rows["solo"].installed, rows["solo"].latest, rows["solo"].pre) == (
        "v2.0.0",
        "v2.0.0",
        None,
    )
    assert rows["local"].note == "local, not checked"
    assert rows["moved"].note == "folder missing; `lado kits remove moved`"
    assert (rows["cleaned"].installed, rows["cleaned"].note) == (
        "v1.0.0",
        "folder missing; `lado kits remove cleaned`",
    )


def test_update_and_remove_refuse_what_is_not_installed_from_git(tmp_path, lado_home):
    make_kit(tmp_path / "dev", "local")
    kits.install(kits.plan_add(str(tmp_path / "dev" / "local")))
    local = (tmp_path / "dev" / "local").resolve()
    with pytest.raises(kits.KitError) as exc:
        kits.plan_update("local")
    assert str(exc.value) == f"local is the folder {local}: it is read in place, nothing to update"
    for refused in (lambda: kits.plan_update("nope"), lambda: kits.remove("nope")):
        with pytest.raises(kits.KitError) as exc:
            refused()
        assert str(exc.value) == 'no kit "nope" is installed; `lado kits` lists the kits'
    with pytest.raises(kits.KitError, match='no kit "default" is installed'):
        kits.remove("default")  # a built-in kit
    assert kits.remove("local") == local
    assert rows(lado_home) == [] and local.is_dir()


def test_an_installed_kit_whose_folder_is_gone_does_not_stop_other_kits(
    tmp_path, repo, lado_home, monkeypatch
):
    make_kit(tmp_path / "dev", "gone")
    kits.install(kits.plan_add(str(tmp_path / "dev" / "gone")))
    _, url = kit_repo(tmp_path, "1.0.0")
    kits.install(kits.plan_add(url))
    clone = gitcache.clone_dir(url, "v1.0.0")
    shutil.rmtree(tmp_path / "dev")
    shutil.rmtree(clone)
    found = {f.name: f for f, _ in kits.available(repo)}
    no_git(monkeypatch)
    with pytest.raises(kits.KitError) as exc:
        found["gone"].load()
    gone = (tmp_path / "dev" / "gone").resolve()
    assert str(exc.value) == (
        f'kit "gone": its folder {gone} is missing; `lado kits remove gone`, then to have it '
        f"back `lado kits add {gone}`"
    )
    with pytest.raises(kits.KitError) as exc:
        found["team"].load()
    assert str(exc.value) == (
        f'kit "team": its folder {clone} is missing; `lado kits remove team`, then to have it '
        f"back `lado kits add {url}@v1.0.0`"
    )
    assert kits.resolve(repo, ["default"]).lead.name == "supervisor"
    # Removing it is no error: the row goes, and the folder that was there is named.
    assert kits.remove("gone") == gone
    assert kits.remove("team") == clone
    assert rows(lado_home) == []


def test_kit_version_is_compared_with_the_tags_of_its_clone(tmp_path, lado_home):
    """A kit pinned to a commit by an older LADO may disagree with its tag."""
    work = init_repo(tmp_path / "team")
    url = publish(work, {"kit.yaml": TEAM}, tag="v1.1.0")
    kit = kits.load(gitcache.fetch_pinned(url, rev(work, "HEAD")), named_folder=False)
    assert kits.warnings(kit) == [
        f"team: version 1.0.0 in kit.yaml, but {url}@{rev(work, 'HEAD')} is at v1.1.0"
    ]


def test_a_kit_without_a_version_does_not_load(tmp_path):
    path = make_kit(tmp_path, "nov", version=None)
    with pytest.raises(kits.KitError) as exc:
        kits.load(path)
    assert f"{path.resolve() / 'kit.yaml'}: version is missing; add `version: X.Y.Z`" in str(
        exc.value
    )


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


def test_kits_in_lado_home_kits_of_older_lados_are_named_with_how_to_add_them(
    tmp_path, repo, lado_home
):
    old = lado_home / "kits"
    old.mkdir(parents=True)
    _, url = kit_repo(tmp_path, "1.0.0")
    (old / "team").symlink_to(gitcache.fetch_pinned(url, "v1.0.0"))
    work, pinned = kit_repo(tmp_path, "1.0.0", name="pinned")
    commit = rev(work, "HEAD")
    (old / "pinned").symlink_to(gitcache.fetch_pinned(pinned, commit))
    many = publish(init_repo(tmp_path / "many"), {"kits/multi/kit.yaml": TEAM}, tag="v1.0.0")
    (old / "multi").symlink_to(gitcache.fetch_pinned(many, "v1.0.0") / "kits" / "multi")
    local = make_kit(tmp_path / "dev", "local")
    (old / "local").symlink_to(local)
    (old / "broken").symlink_to(tmp_path / "nowhere")
    make_kit(old, "mine")
    (old / ".team.new").symlink_to(local)  # a temporary link of an update of older LADOs
    before = sorted((p.name, p.is_symlink()) for p in old.iterdir())
    hint = kits.legacy_hint()
    assert hint == "\n".join(
        [
            f"{old} is no longer read: installed kits are kept in lado.db; add them again:",
            f"  broken: a broken link to {tmp_path / 'nowhere'}; nothing to add",
            f"  lado kits add {local.resolve()}",
            f"  mine: a folder in {old}: move it out, then `lado kits add <its new folder>`",
            "  multi: from a multi-kit repository, no longer supported: add the kit from its "
            "own repository",
            f"  lado kits add {pinned}  (pinned was at {commit}, no version tag: this adds the "
            "latest release)",
            f"  lado kits add {url}@v1.0.0",
            f"then delete {old}",
        ]
    )
    with pytest.raises(kits.KitError) as exc:
        kits.find("team", repo)
    assert str(exc.value).endswith("\n" + hint)
    # LADO leaves the folder as it is.
    assert sorted((p.name, p.is_symlink()) for p in old.iterdir()) == before
    shutil.rmtree(old)
    assert kits.legacy_hint() is None


def test_a_damaged_clone_is_a_kit_error_not_a_crash(tmp_path, lado_home):
    _, url = kit_repo(tmp_path, "1.1.0")
    kit = kits.install(kits.plan_add(url))
    shutil.rmtree(kit.path / ".git")
    with pytest.raises(kits.KitError, match=f"cannot read the clone {kit.path}: "):
        kits.plan_update("team")
    (warning,) = kits.warnings(kit)
    assert warning.startswith(f"team: cannot read the version tags of {kit.path}: ")


def sdlc_kit(project, name="sdlc", supervisor=False, **meta):
    """A process kit whose role analyst uses skill tracker, which it expects; with
    `supervisor`, its supervisor uses it too."""
    agents = {"analyst": ({"skills": ["tracker"]}, "")}
    if supervisor:
        agents["supervisor"] = ({"skills": ["tracker"]}, f"{name} boss")
        meta["supervisor"] = kits.LEAD
    return make_kit(project, name, agents=agents, expects={"skills": ["tracker"]}, **meta)


@pytest.mark.parametrize(
    "expects, error",
    [
        ("nope", "expects must be a mapping"),
        ({"skills": ["tracker"], "mcp": ["db"]}, "expects: unknown keys mcp; allowed: skills"),
        ({"skills": "tracker"}, "expects.skills must be a list of skill names"),
        ({"skills": ["Tracker"]}, 'expects.skills: "Tracker" must be lowercase letters'),
        ({"skills": ["tracker", "tracker"]}, 'expects.skills: "tracker" is listed twice'),
        (
            {"skills": ["own"]},
            'expects.skills: "own" is a skill of this kit (skills/own); a kit does not '
            "expect what it has",
        ),
        (
            {"skills": ["tdd"]},
            'expects.skills: "tdd" comes with its pack "p" (dependencies.skills); a kit does '
            "not expect what it has",
        ),
    ],
)
def test_expects_errors(project, expects, error):
    make_pack(project.parent / "p", ["tdd"])
    kit = pack_kit(project, packs={"p": "../../p"}, skills=["own"], expects=expects)
    with pytest.raises(kits.KitError) as exc:
        kits.load(kit)
    assert f"{(kit / 'kit.yaml').resolve()}: {error}" in str(exc.value)


def test_expects_is_read(project):
    assert kits.load(sdlc_kit(project)).expects == ("tracker",)
    assert kits.load(make_kit(project, "plain")).expects == ()


def test_expects_of_a_pack_fetched_later_is_an_error(tmp_path, project, lado_home):
    url = publish(
        init_repo(tmp_path / "pack"),
        {"skills/tracker/SKILL.md": SKILL_MD.replace("tdd", "tracker")},
        tag="v1",
    )
    kit = pack_kit(project, packs={"p": f"{url}@v1"}, expects={"skills": ["tracker"]})
    loaded = kits.load(kit)
    with pytest.raises(kits.KitError, match='"tracker" comes with its pack "p"'):
        kits.fetch(loaded)


def test_a_kit_alone_may_name_a_skill_it_expects_when_assumed(repo, project):
    sdlc_kit(project, supervisor=True)
    env = kits.resolve(repo, ["sdlc"], expected=kits.ASSUME)
    assert env.resolve("analyst").skills == {}
    make_kit(project, "loose", agents={"rev": ({"skills": ["tracker"]}, "")})
    with pytest.raises(kits.KitError) as exc:
        kits.resolve(repo, ["loose"], expected=kits.ASSUME)
    assert str(exc.value) == (
        f'{(project / "loose" / "agents" / "rev.md").resolve()}: skill "tracker" is not '
        'visible to agent "rev" (kit "loose"): not a skill of the session\'s kits or of kit '
        '"loose"\'s dependencies'
    )


def test_a_non_leading_kit_supervisor_may_name_a_skill_its_kit_expects_when_assumed(repo, project):
    sdlc_kit(project, supervisor=True)
    lead_kit(project, "b")
    env = kits.resolve(repo, ["sdlc", "b"], expected=kits.ASSUME)
    assert [s.name for s in env.lead_skills()] == ["lead-sdlc", "lead-b"]


def test_a_kit_that_provides_an_expected_skill_gives_it(repo, project):
    sdlc_kit(project)
    make_kit(project, "tracker-jira-server", skills=["tracker"])
    env = kits.resolve(repo, ["sdlc", "tracker-jira-server"])
    assert env.resolve("analyst").skills["tracker"].kit == "tracker-jira-server"
    # A pack of a kit without agents provides it as well.
    make_pack(project.parent / "tp", ["tracker"])
    pack_kit(project, "tracker-pack", packs={"tp": "../../tp"})
    env = kits.resolve(repo, ["sdlc", "tracker-pack"])
    assert env.resolve("analyst").skills["tracker"].pack == "tp"


def test_an_expected_skill_reaches_the_kits_supervisor_leading_or_not(repo, project):
    sdlc_kit(project, supervisor=True)
    make_kit(project, "tracker-jira-server", skills=["tracker"])
    env = kits.resolve(repo, ["sdlc", "tracker-jira-server"])
    assert list(env.resolve("supervisor").skills) == ["tracker"]
    lead_kit(project, "b")
    env = kits.resolve(repo, ["sdlc", "tracker-jira-server", "b"])
    sdlc = next(s for s in env.lead_skills() if s.kit == "sdlc")
    assert list(sdlc.skills) == ["tracker"]


NOT_PROVIDED = (
    'kit "sdlc" expects skill "tracker", which no kit of the session provides: add a kit that '
    "provides it with --kit <kit>"
)


def test_a_session_without_a_kit_that_provides_an_expected_skill_is_refused(repo, project):
    sdlc_kit(project)
    with pytest.raises(kits.KitError) as exc:
        kits.resolve(repo, ["sdlc"])
    assert str(exc.value) == NOT_PROVIDED  # not "is not visible to agent"
    assert "tracker-" not in str(exc.value) and "jira" not in str(exc.value)
    # Also when no role names it.
    make_kit(project, "quiet", expects={"skills": ["tracker"]})
    with pytest.raises(kits.KitError, match='kit "quiet" expects skill "tracker", which no kit'):
        kits.resolve(repo, ["default", "quiet"])


def test_an_expected_skill_only_in_a_private_pack_is_refused(repo, project):
    sdlc_kit(project)
    make_pack(project.parent / "tp", ["tracker"])
    pack_kit(project, "x", packs={"tp": "../../tp"}, agents={"wx": ({}, "")})
    with pytest.raises(kits.KitError) as exc:
        kits.resolve(repo, ["sdlc", "x"])
    assert str(exc.value) == (
        'kit "sdlc" expects skill "tracker", which kit "x" has only for its own agents (its '
        "dependencies.skills): add a kit that provides it with --kit <kit>"
    )


@pytest.mark.parametrize("item", ["skill:tracker", "skill:tracker@tracker-jira-server"])
def test_a_session_without_that_switches_off_an_expected_skill_is_refused(repo, project, item):
    sdlc_kit(project)
    make_kit(project, "tracker-jira-server", skills=["tracker"])
    with pytest.raises(kits.KitError) as exc:
        kits.resolve(repo, ["sdlc", "tracker-jira-server"], [item])
    assert str(exc.value) == (
        f'kit "sdlc" expects skill "tracker", which --without {item} switches off; the kit '
        "does not work without it: drop that --without item"
    )


def test_without_one_of_two_providers_keeps_the_other(repo, project):
    sdlc_kit(project)
    make_kit(project, "ta", skills=["tracker"])
    make_pack(project.parent / "tp", ["tracker"])
    pack_kit(project, "tb", packs={"tp": "../../tp"})
    # Two providers clash as any skill of two kits does; switching one off is the way out.
    with pytest.raises(kits.KitError, match='skill "tracker" is defined by two kits'):
        kits.resolve(repo, ["sdlc", "ta", "tb"])
    env = kits.resolve(repo, ["sdlc", "ta", "tb"], ["skill:tracker@ta"])
    assert env.resolve("analyst").skills["tracker"].kit == "tb"


def test_one_agents_without_may_not_switch_off_a_skill_its_kit_expects(repo, project):
    sdlc_kit(project)
    make_kit(project, "tracker-jira-server", skills=["tracker"])
    make_kit(project, "other", agents={"dev": ({}, "")})
    env = kits.resolve(repo, ["sdlc", "tracker-jira-server", "other"])
    for item in ("skill:tracker", "skill:tracker@tracker-jira-server"):
        with pytest.raises(kits.KitError) as exc:
            env.resolve("analyst", [item])
        assert str(exc.value) == (
            f'kit "sdlc" expects skill "tracker"; agent "analyst" cannot run without it: '
            f"drop {item} from without"
        )
    assert "tracker" not in env.resolve("dev", ["skill:tracker"]).skills


def test_warnings_name_expects_without_a_lado_dependency(project, monkeypatch):
    monkeypatch.setattr(lado, "__version__", "0.30.0")  # a kit may need up to this LADO
    message = (
        'kit.yaml: expects needs LADO 0.29 or newer; add dependencies.lado: ">=0.29" so an '
        "older LADO says to upgrade"
    )
    kit = sdlc_kit(project)
    assert any(message in w for w in kits.warnings(kits.load(kit)))
    (kit / "kit.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "sdlc",
                "version": "1.0.0",
                "expects": {"skills": ["tracker"]},
                "dependencies": {"lado": ">=0.28"},
            }
        )
    )
    assert any(message in w for w in kits.warnings(kits.load(kit)))
    for need in (">=0.29", ">=0.29.0", ">=0.30"):
        meta = yaml.safe_load((kit / "kit.yaml").read_text())
        meta["dependencies"]["lado"] = need
        (kit / "kit.yaml").write_text(yaml.safe_dump(meta))
        assert not any("expects" in w for w in kits.warnings(kits.load(kit)))
    assert not any("expects" in w for w in kits.warnings(kits.load(make_kit(project, "plain"))))
