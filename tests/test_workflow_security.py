"""The public repository's own guards (openspec change public-repo-hardening): every action
pinned to a commit, Claude only for the repository's people, Dependabot."""

import re
import shlex
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
WORKFLOWS = sorted(
    p for p in (ROOT / ".github" / "workflows").iterdir() if p.suffix in (".yml", ".yaml")
)
PINNED = re.compile(r"[\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+")
PEOPLE = (
    """contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'), """
    "github.event.{}.author_association)"
)
# The object of each event whose author the guard checks.
AUTHOR = {
    "issue_comment": "comment",
    "pull_request_review_comment": "comment",
    "pull_request_review": "review",
    "issues": "issue",
}


def unpinned(text: str) -> list[str]:
    """Each `uses:` line not pinned to a commit with its release, as `<line>: <text>`."""
    bad = []
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"\s*(?:- )?uses:\s*(.*)", line)
        if match and not PINNED.fullmatch(match.group(1).rstrip()):
            bad.append(f"{number}: {line.strip()}")
    return bad


def test_the_workflows_are_there():
    names = {p.name for p in WORKFLOWS}
    assert names >= {"ci.yml", "claude.yml", "release.yml", "windows-shell.yml"}


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflows_pin_every_action_to_a_commit(path):
    text = path.read_text()
    assert "uses:" in text
    assert unpinned(text) == [], path.name


@pytest.mark.parametrize(
    "line",
    [
        "      - uses: actions/checkout@v7",
        "      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7",
        "        uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10",
        "        uses: anthropics/claude-code-action@v1 # v1.0.0",
    ],
)
def test_an_unpinned_action_is_named_with_its_line(line):
    text = f"steps:\n{line}\n"
    assert unpinned(text) == [f"2: {line.strip()}"]


@pytest.fixture(scope="module")
def claude() -> dict:
    return yaml.safe_load((ROOT / ".github" / "workflows" / "claude.yml").read_text())


def test_claude_runs_only_for_the_repositorys_people(claude):
    # One branch per line, joined by `||`.
    lines = claude["jobs"]["claude"]["if"].splitlines()
    branches = [b.strip().removesuffix("||").strip() for b in lines if b.strip()]
    events = []
    for branch in branches:
        (event,) = re.findall(r"github\.event_name == '(\w+)'", branch)
        events.append(event)
        assert PEOPLE.format(AUTHOR[event]) in branch, branch
        checked = set(re.findall(r"github\.event\.(\w+)\.author_association", branch))
        assert checked == {AUTHOR[event]}, branch
    # PyYAML reads the key `on` as True.
    assert sorted(events) == sorted(claude[True]) == sorted(AUTHOR)


def test_the_people_guard_is_the_jobs_own_condition(claude):
    """In the job's `if`, so the job, its checkout and the secret never start for others."""
    (job,) = claude["jobs"].values()
    assert "author_association" in job["if"]
    assert all("author_association" not in str(step.get("if", "")) for step in job["steps"])


READING = {"Bash(git diff:*)", "Bash(git log:*)", "Bash(gh pr diff:*)"}


def claude_step(claude: dict, name: str) -> dict:
    (step,) = [s for s in claude["jobs"]["claude"]["steps"] if s.get("name") == name]
    return step


def claude_flags(claude: dict) -> dict[str, list[str]]:
    """Each flag of the Action's `claude_args` with the values it was given, in order."""
    args = shlex.split(claude_step(claude, "Run Claude Code")["with"]["claude_args"])
    flags: dict[str, list[str]] = {}
    for arg in args:
        if arg.startswith("--"):
            flag = arg
            flags.setdefault(flag, [])
        else:
            flags[flag].append(arg)
    return flags


def test_claude_checks_out_the_full_history(claude):
    """`git diff origin/main...HEAD` needs the merge base, which a shallow checkout lacks."""
    assert claude_step(claude, "Checkout repository")["with"]["fetch-depth"] == 0


def test_claude_is_allowed_only_the_three_reading_commands(claude):
    flags = claude_flags(claude)
    assert sorted(flags) == ["--allowedTools", "--append-system-prompt"]
    tools = {t.strip() for value in flags["--allowedTools"] for t in value.split(",")}
    assert tools - READING == set(), "extra tools"
    assert tools == READING


def test_claude_has_no_prompt_input(claude):
    """A `prompt` switches the pinned Action to its automation mode: no "Claude finished"."""
    assert "prompt" not in claude_step(claude, "Run Claude Code")["with"]


def test_claude_job_permissions_stay_at_reading(claude):
    assert claude["jobs"]["claude"]["permissions"] == {
        "contents": "read",
        "pull-requests": "read",
        "issues": "read",
        "id-token": "write",
        "actions": "read",
    }


def test_claude_review_instruction_names_the_diff_and_the_lists(claude):
    (instruction,) = claude_flags(claude)["--append-system-prompt"]
    for needed in (
        "origin/main...HEAD",
        "Files read",
        "Files not read",
        "Risky code not fully read",
        "security and secrets",
        "deleting data",
        "agents' environment",
        "the server's API",
    ):
        assert needed in instruction, needed


def test_dependabot_keeps_actions_and_dependencies_current():
    config = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text())
    assert config["version"] == 2
    updates = config["updates"]
    assert sorted((u["package-ecosystem"], u["directory"]) for u in updates) == [
        ("docker", "/docker"),
        ("github-actions", "/"),
        ("npm", "/web"),
        ("uv", "/"),
    ]
    for update in updates:
        assert update["schedule"]["interval"] == "weekly", update
        assert update["cooldown"] == {"default-days": 7}, update
        (group,) = update["groups"].values()
        assert sorted(group["update-types"]) == ["minor", "patch"], update
        assert group["patterns"] == ["*"], update
