"""Command-line entry point for LADO."""

import argparse
import datetime
import os
import select
import shlex
import shutil
import subprocess
import sys
import termios
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from lado import (
    __version__,
    doctor,
    flows,
    kits,
    log,
    loop,
    marketplaces,
    providers,
    runs,
    runtime,
    state,
    tmux,
    update,
)

PAGER = ["less", "-R"]  # for a gate's full note
POLL = 1.0  # seconds between two checks that a gate the human is asked about is open


def cmd_start(args: argparse.Namespace) -> int:
    try:
        started = runtime.start_session(
            args.path, args.name, args.permission_mode, args.provider, args.kit, args.without
        )
    except Exception as exc:
        _sources_warning(unless_in=str(exc))  # a kit not found says it already
        raise
    _sources_warning()
    sess = started.session
    if started.resumed:
        count = len(state.list_runs(sess.name, open_only=True))
        runs_told = f"{count} open run{'' if count == 1 else 's'}, the supervisor is told"
        print(f'Resumed session "{sess.name}" in {sess.repo}: {runs_told}.')
        for change in started.changes:
            print(f"  changed {change}")
        for problem in started.problems:
            print(f"lado: {problem}", file=sys.stderr)
    else:
        print(f'Started session "{sess.name}" in {sess.repo}')
    if started.chosen:
        print(f"provider: {started.chosen.line()}")
    print(started.lead)
    for warning in started.warnings:
        print(f"lado: {warning}", file=sys.stderr)
    if args.no_attach or not sys.stdout.isatty():
        print(f"Attach with: lado attach {sess.name}")
        return 0
    return _attach(sess.name)


def cmd_kits(args: argparse.Namespace) -> int:
    _sources_warning()
    legacy = kits.legacy_hint()
    if legacy:
        print(f"lado: {legacy}", file=sys.stderr)
    repo = _repo_or_none(args.repo)
    found = kits.available(repo)
    markets = {m.name for m in marketplaces.list_()}
    for kit, shadowed_by in found:
        note = f"  (shadowed by {shadowed_by})" if shadowed_by else ""
        try:
            about = _about(kit.load())
        except kits.KitError as exc:
            about = (
                f"invalid: {exc}"
                if kit.installed and not kit.path.exists()
                else "invalid; see: lado kits check " + str(kit.path)
            )
        row = kit.installed
        origin = f"  from {kit.link()}" if row and row.address else ""
        if row and row.marketplace:
            removed = "" if row.marketplace in markets else ", removed"
            origin += f" (marketplace {row.marketplace}{removed})"
        print(f"{kit.name:<16} {kit.where:<9} {kit.path}{origin}{note}\n  {about}")
    if not found:
        print("No kits found.")
    return 0


def _about(kit: kits.Kit) -> str:
    count = len(kit.unfetched())
    unfetched = f"; {count} pack{'' if count == 1 else 's'} not fetched yet" if count else ""
    return f"{kit.version or '-':<8} {kit.description}{unfetched}"


def cmd_kits_add(args: argparse.Namespace) -> int:
    plan = kits.plan_add(args.spec, args.marketplace, args.pre)
    _warn(plan.warnings)
    _print_plan(plan)
    if plan.needs_confirmation and not args.yes:
        if not sys.stdin.isatty():
            print("lado: not installed: confirm with --yes", file=sys.stderr)
            return 1
        if (_input("Install? [y/N] ") or "").lower() not in ("y", "yes"):
            print("Not installed.")
            return 1
    kit = kits.install(plan)
    source = "" if plan.source == "git" else f" ({plan.source})"
    print(f'Added kit "{kit.name}" {kit.version}{source}: installed, in {kit.path}')
    return 0


def _print_plan(plan: kits.Install) -> None:
    print(f"Kit {plan.name} {plan.kit.version} from {plan.source}: {plan.address}")
    if plan.tag:
        print(f"  version {plan.tag}, commit {plan.commit}")
    servers = ", ".join(kits.mcp_line(mcp) for mcp in plan.mcp.values()) or "none"
    print(f"  MCP servers it starts: {servers}")


def _warn(warnings) -> None:
    for warning in warnings:
        if warning:
            print(f"lado: WARNING: {warning}", file=sys.stderr)


def cmd_kits_update(args: argparse.Namespace) -> int:
    plan = kits.plan_update(args.name, args.tag, args.pre)
    _warn(plan.warnings)
    if plan.current:
        print(kits.current_line(plan))
        return 0
    _print_plan(plan)
    _warn(kits.new_mcp_warnings(plan))
    kit = kits.install(plan)
    print(f'Updated kit "{kit.name}" from {plan.installed} to {plan.tag}: installed, in {kit.path}')
    print(kits.update_line(plan, runtime.kit_users(plan.name).running))
    return 0


def cmd_kits_outdated(args: argparse.Namespace) -> int:
    for row in kits.outdated():
        _warn(row.warnings)
        if row.note:
            about = row.note
        else:
            pre = f"  pre: {row.pre}" if row.pre else ""
            about = f"latest {row.latest or '-'}{pre}"
        print(f"{row.name:<16} {row.installed or '-':<10} {about}")
    return 0


def cmd_marketplaces(args: argparse.Namespace) -> int:
    for market in marketplaces.list_():
        enabled = "enabled" if market.enabled else "disabled"
        updated = market.updated_at or "never"
        print(f"{market.name:<9} {enabled:<9} {marketplaces.url(market)}  updated {updated}")
    return 0


def _kits_count(name: str) -> str:
    count = len(marketplaces.kits(name))
    return f"{count} kit{'' if count == 1 else 's'}"


def cmd_marketplaces_add(args: argparse.Namespace) -> int:
    market = marketplaces.add(args.name, args.url)
    print(f'Added marketplace "{market.name}": {market.url} ({_kits_count(market.name)})')
    return 0


def cmd_marketplaces_remove(args: argparse.Namespace) -> int:
    stay = marketplaces.kits_from(args.name)
    marketplaces.remove(args.name)
    if not stay:
        print(f'Removed marketplace "{args.name}"; kits installed from it stay')
    elif len(stay) == 1:
        print(f'Removed marketplace "{args.name}"; 1 kit installed from it stays: {stay[0]}')
    else:
        print(
            f'Removed marketplace "{args.name}"; {len(stay)} kits installed from it stay: '
            f"{', '.join(stay)}"
        )
    return 0


def cmd_marketplaces_enable(args: argparse.Namespace) -> int:
    market = marketplaces.set_enabled(args.name, args.enable)
    print(f'Marketplace "{market.name}" {"enabled" if market.enabled else "disabled"}')
    return 0


def cmd_marketplaces_update(args: argparse.Namespace) -> int:
    failed = False
    for name, done in marketplaces.update_each([args.name] if args.name else None):
        if isinstance(done, str):
            print(f"lado: {name}: {done}", file=sys.stderr)
            failed = True
            continue
        print(f'Updated marketplace "{name}" ({_kits_count(name)})')
    return 1 if failed else 0


def cmd_kits_remove(args: argparse.Namespace) -> int:
    users = runtime.kit_users(args.name)
    folder = kits.remove(args.name)
    _warn([users.running_line(args.name), users.stopped_line(args.name)])
    if folder.is_dir():
        print(f'Removed kit "{args.name}" (was in {folder}); the folder stays')
    else:
        print(f'Removed kit "{args.name}" (was in {folder}, a folder no longer there)')
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    """`lado sources` is gone: say what to do instead."""
    print(
        "lado: "
        + (
            kits.migration_hint()
            or "lado sources is gone: install kits with `lado kits add <git-url>[@vX.Y.Z]` "
            "or `lado kits add <folder>`; list skill packs under dependencies.skills of a kit"
        ),
        file=sys.stderr,
    )
    return 1


def _sources_warning(unless_in: str = "") -> None:
    hint = kits.migration_hint()
    if hint and hint not in unless_in:
        print(f"lado: {hint}", file=sys.stderr)


def cmd_kits_show(args: argparse.Namespace) -> int:
    repo = _repo_or_none(args.repo)
    env = kits.resolve(repo, args.names, args.without)
    print(env.lead_line())
    for warning in env.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print("Kits:")
    labels = {}  # (kit, pack) -> the pack's name@ref
    for kit in env.kits:
        print(f"  {kit.name} {kit.version}  ({kit.source})")
        for pack in kit.packs.values():
            labels[kit.name, pack.name] = pack.label
            print(f"    pack {pack.name}: {pack.spec}  {pack.path}")
        if kit.packs and not kit.agents:
            print("    shares its packs with the session (no agents)")

    def origin(skill: kits.Skill) -> str:
        return f"{labels[skill.kit, skill.pack]} ({skill.kit})" if skill.pack else skill.kit

    print("Agents:")
    for agent in [env.lead, *env.agents.values()]:
        resolved = env.resolve(agent.name)
        flag = "  [lead]" if agent is env.lead else ""
        print(f"  {agent.name}{flag}  from {agent.kit}: {agent.path}")
        skills = ", ".join(f"{s.name} ({origin(s)})" for s in resolved.skills.values()) or "none"
        print(f"    skills{' (all)' if agent.skills is None else ''}: {skills}")
        for mcp in resolved.mcp.values():
            print(f"    mcp {mcp.name}: {' '.join(mcp.command)}")
    if env.lead_skills():
        print("Lead skills of LADO's built-in supervisor:")
    for lead_skill in env.lead_skills():
        source = env.kit_supervisors[lead_skill.kit]
        print(f"  {lead_skill.name}  from {lead_skill.kit}: {source.path}")
        named = ", ".join(f"{s.name} ({origin(s)})" for s in lead_skill.skills.values())
        print(f"    skills: {named or 'none'}")
        if lead_skill.missing_mcp:
            print(f"    mcp not available: {', '.join(lead_skill.missing_mcp)}")
    print("Skills:")
    where = {kit.name: kit.where for kit in env.kits}
    for skill in env.all_skills():
        print(f"  {skill.name}  from {origin(skill)} ({where[skill.kit]}): {skill.path}")
    if env.flows:
        print("Flows:")
    for flow in env.flows.values():
        print(f"  {flow.name}  from {flow.kit} ({where[flow.kit]}): {flow.path}")
        print(f"    {flow.description}")
        for step in flow.states.values():
            if step.kind != flows.WORK:
                continue
            if step.agent == kits.LEAD:
                who = f"the lead ({env.lead.name} of kit {env.lead.kit})"
            elif step.agent in env.agents:
                who = f"{step.agent} ({env.agents[step.agent].kit})"
            else:
                who = f"{step.agent} (no such role in this session)"
            print(f"    {step.name}: {who}")
    if env.without:
        print(f"Switched off: {', '.join(env.without)}")
    return 0


def cmd_kits_check(args: argparse.Namespace) -> int:
    target = Path(args.kit)
    repo = _repo_or_none(str(target) if target.is_dir() else args.repo)
    try:
        # A folder may be any kit, e.g. a kit at the root of its repository; with --tag,
        # what `lado kits add <address>@<tag>` would say of it.
        if target.is_dir():
            spec = f"{args.kit}@{args.tag}" if args.tag is not None else args.kit
            kit = kits.load_release(target, spec, args.tag)
        else:
            kit = kits.find(args.kit, repo).release(args.tag)
        env = kits.resolve(repo, [kit])
        problems = kits.lint(kit)
        doubts = kits.warnings(kit)
    except kits.KitError as exc:
        print(exc, file=sys.stderr)
        return 1
    for doubt in doubts:
        print(f"warning: {doubt}", file=sys.stderr)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    skills = len(env.all_skills())
    counts = f"{len(env.agents)} agents, {skills} skills, {len(kit.packs)} packs"
    print(f"{kit.name}: OK ({counts} and {len(env.flows)} flows)")
    return 0


def _repo_or_none(path: str) -> str | None:
    try:
        return runtime.repo_root(path)
    except runtime.LadoError:
        return None


def cmd_ls(args: argparse.Namespace) -> int:
    _unfinished_update()
    sessions = state.list_sessions()
    if not sessions:
        print("No sessions. Start one with: lado start <repo>")
    for sess in sessions:
        alive = {
            runtime.SessionStatus.RUNNING: "",
            runtime.SessionStatus.STOPPED: "  (stopped)",
            runtime.SessionStatus.TMUX_GONE: "  (tmux session is gone)",
            runtime.SessionStatus.LOOP_DOWN: (
                "  (session loop not running: unconfirmed messages are not retried; "
                f"run `lado attach {sess.name}` to restart it; "
                f"see {state.home() / 'loop.log'})"
            ),
        }[runtime.session_status(sess)]
        print(f"{sess.name}  {sess.repo}{alive}")
        since = state.status_since(sess.name)
        now = datetime.datetime.now(datetime.timezone.utc)
        reasons = runtime.waiting_reasons(sess.name)
        for agent in state.list_agents(sess.name):
            when = since.get(agent.name)
            took = format_duration((now - when).total_seconds()) if when else "-"
            line = f"  {agent.name:<12} {agent.role:<10} {agent.provider:<8} {agent.status:<9}"
            print(f"{line} {took:<6}  {agent.branch or ''}".rstrip())
            if agent.name in reasons:
                print(f"    waiting: {reasons[agent.name]}")
        run_since = state.run_since(sess.name)
        for run in state.list_runs(sess.name, open_only=True):
            when = run_since.get(run.name)
            took = format_duration((now - when).total_seconds()) if when else "-"
            print(f"  run {run.name}  {run.state}  {runs.now(run)}  {took}")
            gate = state.open_gate(sess.name, run.name)
            if gate:
                print(f"    gate #{gate.id} waiting: {gate.question}")
    available = update.available_line(update.check())  # a failed check: in `lado doctor`
    if available:
        print(available)
    return 0


DEFAULT_HOST = "127.0.0.1"  # `lado server --host`'s default


@dataclass
class Restarts:
    """What `lado update` stops and resumes: the sessions `runtime.session_status` says run
    (also those whose loop is down), and the UI server's server.json, if one runs."""

    sessions: list[state.Session]
    gone: list[state.Session]  # not stopped, but their tmux is gone: not restarted
    server: dict | None


def cmd_update(args: argparse.Namespace) -> int:
    # Everything the update needs from LADO is imported before the installer replaces it.
    from lado.server import run as server_run

    _human_only("update")
    _unfinished_update()
    try:
        index = update.fetch_index()
    except (OSError, ValueError) as exc:
        raise runtime.LadoError(f"cannot look up LADO's versions on PyPI: {exc}") from exc
    if args.version:
        to = update.release(index, args.version)
        if to is None:
            raise runtime.LadoError(f"PyPI has no LADO {args.version}; nothing was stopped")
    else:
        to = update.latest(index)
        if to is None or not update.newer(to.version, __version__):
            print(f"LADO {__version__} is the latest version.")
            return 0
    if update.same(to.version, __version__):
        print(f"LADO {__version__} is installed already.")
        return 0
    installer = update.installer()
    restarts = _restarts(server_run.running())
    _print_update_plan(to, installer, restarts)
    if installer is None:
        _print_update_by_hand(to.version, restarts)
        return 1
    if not args.yes:
        if not sys.stdin.isatty():
            print("lado: not updated: confirm with --yes", file=sys.stderr)
            return 1
        if (_input("Update? [y/N] ") or "").lower() not in ("y", "yes"):
            print("Not updated.")
            return 1
    return _update(to.version, installer, restarts, server_run.stop)


def _restarts(server: dict | None) -> Restarts:
    restarts = Restarts([], [], server)
    for sess in state.list_sessions():
        status = runtime.session_status(sess)
        if status in (runtime.SessionStatus.RUNNING, runtime.SessionStatus.LOOP_DOWN):
            restarts.sessions.append(sess)
        elif status == runtime.SessionStatus.TMUX_GONE:
            restarts.gone.append(sess)
    return restarts


def _print_update_plan(
    to: update.Release, installer: update.Installer | None, restarts: Restarts
) -> None:
    print(f"LADO {__version__} -> {to.version} (PyPI, released {to.date})")
    if installer:
        command = shlex.join(installer.command(to.version))
        print(f"Installed with {installer.kind}: {command}")
        if installer.lost:
            _warn([f"{command} does not keep {', '.join(installer.lost)} of this install"])
    if update.newer(__version__, to.version):
        _warn(
            [
                f"an older LADO may refuse lado.db (schema {state.SCHEMA_VERSION}); "
                "it says so when it starts"
            ]
        )
    if restarts.sessions or restarts.server:
        print("Restarts:")
    for sess in restarts.sessions:
        agents = ", ".join(f"{a.name} {a.status}" for a in state.list_agents(sess.name))
        count = len(state.list_runs(sess.name, open_only=True))
        open_runs = f"{count} open run{'' if count == 1 else 's'}" if count else "no open runs"
        print(f"  session {sess.name}  ({sess.repo})  {agents or 'no agents'}; {open_runs}")
    if restarts.server:
        print(f"  UI server  {restarts.server['url']}")
    if restarts.sessions:
        print(
            "Busy agents lose their current turn. Runs, gates, branches and worktrees stay;\n"
            "each supervisor starts a new conversation and gets what its open runs wait for."
        )
    for sess in restarts.gone:
        print(
            f"Not running, its tmux session is gone: {sess.name}; resume it with "
            f"lado start {sess.repo} --name {sess.name}"
        )
    print(f'Only sessions on tmux socket "{tmux.socket()}" are seen.')


def _print_update_by_hand(version: str, restarts: Restarts) -> None:
    prefix = update.prefix()
    print(
        f"LADO runs from {prefix}, not a uv tool or pipx install of lado from PyPI; "
        "lado update does not "
        "upgrade it. By hand:"
    )
    for sess in restarts.sessions:
        print(f"  lado stop {sess.name}")
    if restarts.server:
        print("  lado server stop")
    print(f"  {prefix / 'bin' / 'pip'} install lado=={version}")
    for sess in restarts.sessions:
        print(f"  lado start {sess.repo} --name {sess.name}")
    if restarts.server:
        print("  lado ui")


def _update(
    version: str,
    installer: update.Installer,
    restarts: Restarts,
    stop_server: Callable[[], object],
) -> int:
    """Stop, install, check the version, resume. After the installer this process starts
    nothing of its own (`providers.lado_command`): the installed `lado` resumes, through its
    public commands, whichever version it is."""
    server = restarts.server
    address = (server["host"], server["port"]) if server else None
    update.write_pending(update.Pending({s.name: s.repo for s in restarts.sessions}, address))
    binary = installer.binary
    stopped: list[state.Session] = []
    server_stopped = False
    try:
        for sess in restarts.sessions:
            print(f"Stopping session {sess.name}...", end=" ", flush=True)
            dropped = runtime.stop_session(sess.name).dropped
            stopped.append(sess)
            if not loop.wait_stopped(sess.name):
                print()
                raise runtime.LadoError(
                    f"the session loop of {sess.name} did not end; see {state.home() / 'loop.log'}"
                )
            not_read = f" ({dropped} messages not read are dropped)" if dropped else ""
            print(f"stopped{not_read}")
        if server:
            print("Stopping the UI server...", end=" ", flush=True)
            stop_server()
            server_stopped = True
            print("stopped")
    except (runtime.LadoError, tmux.TmuxError, OSError) as exc:
        print(f"lado: {exc}; nothing was upgraded. Resuming the sessions:", file=sys.stderr)
        _resume(binary, stopped, address if server_stopped else None)
        return 1
    command = installer.command(version)
    print(f"Upgrading: {shlex.join(command)}", flush=True)
    try:
        installed = subprocess.run(command, check=False).returncode == 0
    except OSError as exc:
        print(f"lado: {exc}", file=sys.stderr)
        installed = False
    if not installed:
        print(f"The upgrade failed; LADO {__version__} is unchanged. Resuming the sessions on it:")
        _resume(binary, stopped, address)
        return 1
    now = update.installed_version(binary)
    right = now is not None and update.same(now, version)
    if right:
        print(f"Resuming on LADO {version}:", flush=True)
    else:
        print(
            f"The installer finished, but LADO is {now or 'unknown'}, not {version}. "
            f"Resuming the sessions on {now or 'it'}:",
            flush=True,
        )
    resumed = _resume(binary, stopped, address)
    if not (right and resumed):
        return 1
    update.clear_pending()
    print(f"LADO {version} is ready." + (" Reload open UI tabs." if server else ""))
    return 0


def _resume(binary: Path, sessions: list[state.Session], server: tuple[str, int] | None) -> bool:
    """Resume the sessions, then the UI server, with `binary`'s public commands; whether
    each did."""
    resumed = True
    for sess in sessions:
        code = _run(binary, "start", sess.repo, "--name", sess.name, "--no-attach")
        if code:
            print(
                f"lado: session {sess.name} did not resume (exit code {code}); "
                f"resume it with lado start {sess.repo} --name {sess.name}",
                file=sys.stderr,
            )
            resumed = False
    if server:
        host, port = server
        # --host only when needed: a LADO before 0.20 has none.
        hosting = [] if host == DEFAULT_HOST else ["--host", host]
        code = _run(binary, "ui", "--no-open", *hosting, "--port", str(port))
        if code:
            print(
                f"lado: the UI server did not start (exit code {code}); start it with lado ui",
                file=sys.stderr,
            )
            resumed = False
    return resumed


def _run(binary: Path, *args: str) -> int:
    """`binary` with `args`, its output on this terminal: its exit code."""
    try:
        return subprocess.run([str(binary), *args], check=False).returncode
    except OSError as exc:
        print(f"lado: {exc}", file=sys.stderr)
        return 127


def _unfinished_update() -> None:
    """Say which sessions an update that did not finish left stopped, and how to resume
    them."""
    pending = update.read_pending()
    if pending is None:
        return
    left = []
    for name, repo in pending.sessions.items():
        sess = state.get_session(name)
        if sess and sess.stopped_at:
            left.append((name, repo))
    if not left:
        return
    names = ", ".join(name for name, _ in left)
    commands = "; ".join(f"lado start {repo} --name {name}" for name, repo in left)
    print(
        f"lado: an update did not finish: sessions {names} may be stopped; "
        f"resume them with {commands}",
        file=sys.stderr,
    )


def _human_only(command: str) -> None:
    """Agents have LADO_AGENT set: they must not answer for the human."""
    agent = os.environ.get("LADO_AGENT")
    if agent:
        raise runtime.LadoError(f'lado {command} is for the human; agent "{agent}" cannot use it')


def cmd_flow_set(args: argparse.Namespace) -> int:
    _human_only("flow-set")
    before = state.get_run(args.session, args.run)
    run = runs.force(args.session, args.run, args.state, args.reason)
    print(f"{run.name}: {before.state} -> {run.state} ({runs.now(run)})")
    return 0


def cmd_answer(args: argparse.Namespace) -> int:
    _human_only("answer")
    named = state.get_session(args.session) if args.session else None
    if named and named.stopped_at:
        runtime.running_session(named.name)  # says it is stopped and how to resume it
    if args.option:
        _answer(args.session, args.gate, args.option, args.comment)
        return 0
    if args.gate:
        try:
            first = runs.find_gate(args.session, args.gate)
        except runtime.LadoError as exc:
            # E.g. a popup for a gate answered meanwhile: on with the session's gates.
            print(f"lado: {exc}")
            first = None
    else:
        first = None
    session, answered, failed = args.session, False, 0
    # A stopped session's gates wait for its resume: its runs have no agents to go on with.
    stopped = {s.name for s in state.list_sessions() if s.stopped_at}
    while True:
        gates = [first] if first else state.open_gates(session)
        gates = [g for g in gates if g.session not in stopped]
        first = None
        if not gates:
            print("No more open gates." if answered else "No open gates.")
            return failed
        gate = gates[0] if len(gates) == 1 else _pick(gates)
        if gate is None:
            return failed
        # -m is for the first gate only, also when that one is answered elsewhere.
        comment, args.comment = args.comment, None
        try:
            option = _choose(gate)
            if option is not None and comment is None:
                comment = _input("Comment for the next step (Enter for none): ", gate)
            if option is None or comment is None:
                print(f"Gate #{gate.id} stays open.")
                return failed
            _answer(gate.session, str(gate.id), option, comment)
            answered = True
        except NotWanted:
            closed = state.get_gate(gate.id)
            print(
                f"Gate #{gate.id} was answered elsewhere: {closed.answer} by {closed.answered_by}"
            )
            answered = True
        except runtime.LadoError as exc:
            print(f"lado: {exc}")
            failed = 1
            first = gate if state.get_gate(gate.id).answer is None else None
        # Then the session's other open gates: a popup asks about them all.
        session = gate.session


def _answer(session: str, ref: str, option: str, comment: str | None) -> None:
    print(runs.answer_text(session, ref, option, comment))


class NotWanted(Exception):
    """What the human was asked for is no longer wanted: e.g. the gate was answered in the
    UI or in another `lado answer`."""


def _input(prompt: str, gate: state.Gate | None = None) -> str | None:
    """A line the human typed; None when they end the input or press Ctrl-C. While asked
    about `gate` on a terminal, NotWanted when the gate is answered elsewhere."""
    try:
        if gate is None or not sys.stdin.isatty():
            return input(prompt).strip()
        print(prompt, end="", flush=True)
        return read_line_while(sys.stdin, lambda: state.get_gate(gate.id).answer is None)
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def read_line_while(stdin: TextIO, wanted: Callable[[], bool]) -> str:
    """A line typed on the terminal `stdin`, checking every POLL seconds that it is still
    wanted. When it is not, what was typed so far is dropped, so it does not go to the next
    prompt, and NotWanted is raised."""
    while True:
        ready, _, _ = select.select([stdin], [], [], POLL)
        if ready:
            line = stdin.readline()
            if not line:
                raise EOFError
            return line.strip()
        if not wanted():
            termios.tcflush(stdin, termios.TCIFLUSH)
            print()
            raise NotWanted


def _pick(gates: list[state.Gate]) -> state.Gate | None:
    print("Open gates:")
    for n, gate in enumerate(gates, 1):
        print(f"  {n}) #{gate.id} {gate.session} {gate.run} at {gate.state}: {gate.question}")
    while True:
        picked = _input("Which one? (number, Enter to quit): ")
        if not picked:
            return None
        if picked.isdigit() and 1 <= int(picked) <= len(gates):
            return gates[int(picked) - 1]


def _choose(gate: state.Gate) -> str | None:
    """The option the human picks for the gate, by number or name; None to leave it. The
    note and the notes the gate needs show as their summaries; when there is more, "v"
    shows all of it in a pager."""
    needed = runs.gate_notes(gate)
    full_note = gate.note_body.strip() != "" or bool(needed)
    v = ", v for the full note" if full_note else ""
    _show_gate(gate, needed)
    while True:
        chosen = _input(f"Answer (number or name{v}, Enter to leave it open): ", gate)
        if not chosen:
            return None
        if full_note and chosen.lower() == "v":
            parts = [f"Note from {name}: {_note_text(note)}\n" for name, note in needed]
            parts.append(f"Note: {gate.note}\n\n{gate.note_body.strip()}\n")
            _page("\n".join(parts))
            _show_gate(gate, needed)
            continue
        if chosen.isdigit() and 1 <= int(chosen) <= len(gate.options):
            return gate.options[int(chosen) - 1]
        try:
            return runs.canonical_option(gate, chosen)
        except runtime.LadoError as exc:
            print(f"lado: {exc}")


def _note_text(note: state.Note | None) -> str:
    return f"{note.summary}\n{note.body.strip()}".rstrip() if note else "no note yet"


def _show_gate(gate: state.Gate, needed: list[tuple[str, state.Note | None]]) -> None:
    print(f"\nGate #{gate.id}, session {gate.session}, run {gate.run} at {gate.state}:")
    print(gate.question)
    lines = len(gate.note_body.strip().splitlines())
    if lines:
        print(f"Note: {gate.note} (v: the full note, {lines} more line{'' if lines == 1 else 's'})")
    elif gate.note:
        print(f"Note: {gate.note}")
    for name, note in needed:
        print(f"Note from {name}: {note.summary if note else 'no note yet'}")
    print("Options:")
    for n, option in enumerate(gate.options, 1):
        print(f"  {n}) {option}")


def _page(text: str) -> None:
    """Show `text` in the pager, or print it when there is none."""
    pager = shutil.which(PAGER[0])
    if pager is None:
        print(text, end="")
        return
    subprocess.run([pager, *PAGER[1:]], input=text, text=True, check=False)


def format_duration(seconds: float) -> str:
    """A short duration: 45s, 12m, 3h05m, 2d4h (rounded down, never negative)."""
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h{s % 3600 // 60:02d}m"
    return f"{s // 86400}d{s % 86400 // 3600}h"


def cmd_log(args: argparse.Namespace) -> int:
    log.show(args.session, args.agent, args.n, args.follow)
    return 0


def cmd_attach(args: argparse.Namespace) -> int:
    name = args.name
    if name is None:
        sessions = [s for s in state.list_sessions() if not s.stopped_at]
        if len(sessions) != 1:
            print("Name the session: lado attach <name> (see lado ls)", file=sys.stderr)
            return 1
        name = sessions[0].name
    sess = state.get_session(name)
    if sess and not sess.stopped_at and tmux.has_session(name):
        loop.ensure(name)
    return _attach(name)


def cmd_stop(args: argparse.Namespace) -> int:
    stopped = runtime.stop_session(args.name)
    n = stopped.dropped
    dropped = f"; {n} undelivered message{'' if n == 1 else 's'} dropped" if n else ""
    print(f'Stopped session "{args.name}"{dropped}.')
    _kept(runtime.session_worktrees(state.get_session(args.name).repo, args.name), "kept")
    print(
        "History, open runs and gates are kept: lado start resumes the session, "
        f"lado forget {args.name} drops them."
    )
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    forgotten = runtime.forget_session(args.session, args.force)
    dropped = f"; dropped open runs: {', '.join(forgotten.runs)}" if forgotten.runs else ""
    print(f'Forgot session "{args.session}" and its history{dropped}.')
    _kept(forgotten.worktrees, "left on disk:")
    return 0


def _kept(worktrees: dict[str, str], what: str) -> None:
    for tree, branch in worktrees.items():
        print(f"  {what} worktree {tree} (branch {branch})")
    if worktrees:
        print("Remove a worktree with: git worktree remove <path>")


def cmd_finish(args: argparse.Namespace) -> int:
    print(runtime.finish_worker(args.session, args.agent, args.discard).text())
    return 0


def cmd_server(args: argparse.Namespace) -> int:
    from lado.server import run as server_run  # FastAPI loads only for the server

    if args.action == "stop":
        info = server_run.stop()
        print(
            f"Stopped the LADO server at {info['url']}."
            if info
            else "The LADO server is not running."
        )
        return 0
    return server_run.serve(args.host, args.port, args.new_token)


def cmd_ui(args: argparse.Namespace) -> int:
    import webbrowser

    from lado.server import app, auth
    from lado.server import run as server_run

    info = server_run.running()
    if info and args.host is not None and server_run.address(args.host) != info["host"]:
        raise runtime.LadoError(
            f"the LADO server already runs at {info['url']}, listening on {info['host']}, "
            f"not on {args.host}; stop it with `lado server stop` to start it on another host"
        )
    if info and args.port and info["port"] != args.port:
        raise runtime.LadoError(
            f"the LADO server already runs at {info['url']}, not on port {args.port}; "
            "stop it with `lado server stop` to start it on another port"
        )
    if info is None:
        info = server_run.wait_ready(server_run.start_background(args.host, args.port))
    elif info["version"] != __version__:
        # An old server would serve this LADO's bundle from disk against its own, older API.
        try:
            server_run.stop()
        except (OSError, runtime.LadoError) as error:
            raise runtime.LadoError(
                f"the running LADO server is version {info['version']}, this LADO is "
                f"{__version__}, and stopping it failed: {error}; "
                "stop it with `lado server stop`, then run `lado ui` again"
            ) from error
        old = info["version"]
        started = server_run.start_background(info["host"], info["port"])
        info = server_run.wait_ready(started)
        print(f"lado: restarted the LADO server: {old} -> {info['version']}", file=sys.stderr)
    if app.bundle_missing(app.STATIC):
        print(f"lado: warning: the web UI's bundle is missing: {app.BUILD_HINT}", file=sys.stderr)
    listening = server_run.Listening.of(info["host"], info["port"])
    if listening.warning:
        print(f"lado: warning: {listening.warning}", file=sys.stderr)
    token = auth.token()
    url = f"{info['url']}/?token={token}"
    if args.no_open:
        print(url)
    else:
        print(f"Opening {url}")
        webbrowser.open(url)
    if listening.remote:
        print(f"From another machine: {listening.remote}/?token={token} (or this host's address)")
    return 0


def _port(value: str) -> int:
    n = int(value)
    if not 0 <= n <= 65535:
        raise argparse.ArgumentTypeError("a port is 0 to 65535")
    return n


def _attach(name: str) -> int:
    if not tmux.has_session(name):
        print(f'No running session "{name}" (see lado ls)', file=sys.stderr)
        return 1
    env = {k: v for k, v in os.environ.items() if k != "TMUX"}  # allow attaching from tmux
    argv = tmux.attach_argv(name)
    os.execvpe(argv[0], argv, env)


def _count(value: str) -> int:
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError("N must be 0 or more")
    return n


def _without_arg(parser: argparse.ArgumentParser, default: list[str] | None = None) -> None:
    parser.add_argument(
        "--without",
        action="append",
        default=default,
        metavar="KIND:NAME[@KIT]",
        help=(
            "switch off agent:<name>, skill:<name>, mcp:<name> or flow:<name> in the session, "
            "or with @<kit> in that kit only, before the kits are combined; repeatable"
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lado",
        description="Layered Agent Delegation & Orchestration.",
    )
    parser.add_argument("--version", action="version", version=f"lado {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="<command>")

    commands.add_parser("doctor", help="check that tmux and the agent CLIs are installed")

    start = commands.add_parser("start", help="start a supervisor agent for a git repository")
    start.add_argument("path", nargs="?", default=".", help="repository (default: current dir)")
    start.add_argument("--name", help="session name (default: repository folder name)")
    start.add_argument(
        "--provider",
        help=f"agent CLI for the session's agents: {', '.join(providers.names())}; without "
        "it, a new session takes its folder's last session's provider if installed, else the "
        "only one installed (a resume keeps its own)",
    )
    start.add_argument(
        "--permission-mode",
        help="permission mode for all agents, one their provider supports: "
        + "; ".join(
            f"{name}: {', '.join(providers.get(name).permission_modes)}"
            for name in providers.names()
        ),
    )
    start.add_argument(
        "--kit",
        action="append",
        help=f"kit to take agents, skills and MCP servers from; repeat to combine kits "
        f"(default: {kits.DEFAULT_KIT}; a resumed session keeps its kits)",
    )
    _without_arg(start)  # a resumed session keeps its own unless given
    start.add_argument("--no-attach", action="store_true", help="do not attach to the session")
    start.set_defaults(func=cmd_start)

    kits_cmd = commands.add_parser(
        "kits", help="list, show and check kits; add, update and remove installed ones"
    )
    kits_cmd.add_argument("--repo", default=".", help="repository for project kits")
    kits_cmd.set_defaults(func=cmd_kits)
    kits_sub = kits_cmd.add_subparsers(metavar="<command>")
    show = kits_sub.add_parser("show", help="what kits combine into: agents, skills, MCP")
    show.add_argument("names", nargs="+", metavar="name")
    _without_arg(show, [])
    show.set_defaults(func=cmd_kits_show)
    check = kits_sub.add_parser("check", help="validate a kit and fetch its skill packs")
    check.add_argument("kit", help="kit folder or name")
    check.add_argument(
        "--tag",
        metavar="vX.Y.Z",
        help="check it as `lado kits add <address>@<tag>` would: the version tag, kit.yaml at "
        "the root saying that version (for a kit's CI)",
    )
    check.set_defaults(func=cmd_kits_check)
    add = kits_sub.add_parser("add", help="install a kit from git, a marketplace or a folder")
    add.add_argument(
        "spec",
        metavar="<git-url[@vX.Y.Z]|folder|kit[@vX.Y.Z]>",
        help="a git URL (cloned into the cache at the version tag, by default the latest "
        "release), a folder (linked, read in place), or with -m a kit's name in a marketplace; "
        "the kit's kit.yaml at the root",
    )
    add.add_argument("-m", "--marketplace", help="the marketplace that lists the kit")
    add.add_argument("--pre", action="store_true", help="the latest version may be a pre-release")
    add.add_argument(
        "--yes", action="store_true", help="install without asking (not from official)"
    )
    add.set_defaults(func=cmd_kits_add)
    update = kits_sub.add_parser(
        "update", help="move a kit installed from git to its latest or another version"
    )
    update.add_argument("name")
    update.add_argument("tag", nargs="?", metavar="vX.Y.Z", help="default: the latest release")
    update.add_argument(
        "--pre", action="store_true", help="the latest version may be a pre-release"
    )
    update.set_defaults(func=cmd_kits_update)
    outdated = kits_sub.add_parser(
        "outdated", help="installed kits against the versions their repositories have now"
    )
    outdated.set_defaults(func=cmd_kits_outdated)
    remove = kits_sub.add_parser("remove", help="remove an installed kit (its folder stays)")
    remove.add_argument("name")
    remove.set_defaults(func=cmd_kits_remove)

    markets = commands.add_parser(
        "marketplaces", help="list, add, remove, enable, disable and update kit marketplaces"
    )
    markets.set_defaults(func=cmd_marketplaces)
    markets_sub = markets.add_subparsers(metavar="<command>")
    markets_sub.add_parser("list", help="the marketplaces").set_defaults(func=cmd_marketplaces)
    market_add = markets_sub.add_parser("add", help="add a marketplace: a git repository")
    market_add.add_argument("name")
    market_add.add_argument("url", metavar="git-url")
    market_add.set_defaults(func=cmd_marketplaces_add)
    market_remove = markets_sub.add_parser("remove", help="remove a marketplace (not official)")
    market_remove.add_argument("name")
    market_remove.set_defaults(func=cmd_marketplaces_remove)
    for verb, enable in (("enable", True), ("disable", False)):
        toggle = markets_sub.add_parser(verb, help=f"{verb} a marketplace")
        toggle.add_argument("name")
        toggle.set_defaults(func=cmd_marketplaces_enable, enable=enable)
    market_update = markets_sub.add_parser(
        "update", help="fetch the latest list of a marketplace, or of each enabled one"
    )
    market_update.add_argument("name", nargs="?")
    market_update.set_defaults(func=cmd_marketplaces_update)
    # Gone: says how to move to `lado kits add`.
    sources_cmd = commands.add_parser("sources", help="gone: see lado kits add")
    sources_cmd.add_argument("rest", nargs=argparse.REMAINDER)
    sources_cmd.set_defaults(func=cmd_sources)

    commands.add_parser("ls", help="list sessions and agents").set_defaults(func=cmd_ls)

    log_cmd = commands.add_parser("log", help="show a session's messages and agent events")
    log_cmd.add_argument("session")
    log_cmd.add_argument("--agent", help="only lines where this agent sends, gets or acts")
    log_cmd.add_argument("-n", type=_count, metavar="N", help="show only the last N entries")
    log_cmd.add_argument(
        "-f", "--follow", action="store_true", help="keep printing new entries until Ctrl-C"
    )
    log_cmd.set_defaults(func=cmd_log)

    attach = commands.add_parser("attach", help="attach to a session's tmux windows")
    attach.add_argument("name", nargs="?")
    attach.set_defaults(func=cmd_attach)

    stop = commands.add_parser(
        "stop", help="stop a session and all its agents; lado start resumes it"
    )
    stop.add_argument("name")
    stop.set_defaults(func=cmd_stop)

    forget = commands.add_parser(
        "forget", help="delete a stopped session with its history, runs and gates"
    )
    forget.add_argument("session")
    forget.add_argument("--force", action="store_true", help="also if it has open runs")
    forget.set_defaults(func=cmd_forget)

    finish = commands.add_parser(
        "finish", help="end a worker whose branch is merged: its window, worktree and branch"
    )
    finish.add_argument("session")
    finish.add_argument("agent")
    finish.add_argument(
        "--discard",
        action="store_true",
        help="also end it if its work is not merged or not committed, and throw that work away",
    )
    finish.set_defaults(func=cmd_finish)

    flow_set = commands.add_parser(
        "flow-set", help="put a flow run into a state, e.g. past a gate or a loop limit"
    )
    flow_set.add_argument("session")
    flow_set.add_argument("run", help="the run's name, <flow>/<name> (see lado ls)")
    flow_set.add_argument("state", help="a state of the run's flow")
    flow_set.add_argument("--reason", required=True, help="why; the next step is told")
    flow_set.set_defaults(func=cmd_flow_set)

    answer = commands.add_parser(
        "answer",
        help="answer a flow run that waits for the human; asks when options are left out",
    )
    answer.add_argument("session", nargs="?", help="default: open gates of all sessions")
    answer.add_argument("gate", nargs="?", help="the gate's number, or its run's name")
    answer.add_argument("option", nargs="?", help="e.g. approve, reject, continue, cancel")
    answer.add_argument("-m", dest="comment", metavar="COMMENT", help="for the next step")
    answer.set_defaults(func=cmd_answer)

    port_help = "exactly this port; 0 for any free one (default: 8000 or the next free to 8020)"
    server = commands.add_parser(
        "server", help="run the UI server of this LADO_HOME in the foreground; stop: end it"
    )
    server.add_argument("action", nargs="?", choices=["stop"], help="stop the running server")
    server.add_argument("--port", type=_port, help=port_help)
    host_help = (
        "address to listen on (default 127.0.0.1); 0.0.0.0 or another non-loopback address "
        "opens the UI to other machines, unencrypted"
    )
    server.add_argument("--host", default="127.0.0.1", help=host_help)
    server.add_argument(
        "--new-token", action="store_true", help="make a new token; links with the old one stop"
    )
    server.set_defaults(func=cmd_server)

    ui = commands.add_parser(
        "ui", help="open the web UI; starts the UI server in the background if none runs"
    )
    ui.add_argument("--no-open", action="store_true", help="only print the link")
    ui.add_argument("--port", type=_port, help=f"for a server it starts: {port_help}")
    ui.add_argument("--host", help=f"for a server it starts: {host_help}")
    ui.set_defaults(func=cmd_ui)

    update_cmd = commands.add_parser(
        "update",
        help="upgrade LADO (uv tool or pipx) and restart the running sessions and UI server",
    )
    update_cmd.add_argument(
        "version", nargs="?", metavar="X.Y.Z", help="this version (default: the latest)"
    )
    update_cmd.add_argument("--yes", action="store_true", help="update without asking")
    update_cmd.set_defaults(func=cmd_update)

    # Internal: started by the agent CLIs of LADO agents.
    commands.add_parser("mcp")
    hook = commands.add_parser("hook")
    hook.add_argument("event")
    hook.add_argument("--session", required=True)
    hook.add_argument("--agent", required=True)
    hook.add_argument("--instance", required=True)
    # Internal: started by `lado start`, one per session (lado.loop).
    loop_cmd = commands.add_parser("loop")
    loop_cmd.add_argument("session")

    args = parser.parse_args(argv)
    if args.command == "doctor":
        _sources_warning()
        return doctor.main()
    if args.command == "mcp":
        from lado import mcp_server

        return mcp_server.main()
    if args.command == "hook":
        from lado import hooks

        return hooks.main(args.event, args.session, args.agent, args.instance)
    if args.command == "loop":
        # No check_migration: the loop checks the schema itself and ends on another one.
        return loop.run(args.session)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        # `lado stop` is what the refusal asks for; it ends the session it migrates under.
        if args.command != "stop":
            runtime.check_migration()
        return args.func(args)
    except (
        runtime.LadoError,
        tmux.TmuxError,
        kits.KitError,
        marketplaces.MarketplaceError,
    ) as exc:
        # The notes: what undoing a failed start could not do (runtime._undo).
        for line in [str(exc), *getattr(exc, "__notes__", [])]:
            print(f"lado: {line}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
