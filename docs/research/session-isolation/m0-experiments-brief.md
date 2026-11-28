# M0 experiments: briefs for an agent on another machine

> The briefs of the M0 experiments as given to the agent that ran them (2026-11-27),
> archived as written; only this Russian preface for the human is translated, and the
> report's section names in 0.4 (in Russian, as the reports were) get an English gloss.
> The reports: [E14](m0-e14.md), [E9](m0-e9.md), [E3](m0-e3.md), [E15](m0-e15.md),
> [E10](m0-e10.md); the results in the
> [plan](../session-isolation-plan.md#5-the-m0-experiments).
>
> The preface, translated. These are tasks for an agent (Claude Code or another CLI) that
> works **on another machine, not inside LADO and not in LADO's Docker container**. One
> session, one experiment: give the agent "Part 0" and the section of the experiment
> needed, for example: "Read m0-experiments.md, do part 0 and experiment E9". Each
> experiment's report is a separate file, which you bring here.
>
> **The order** (by the effect on the plan): E14 → E9 → E3 → E15 → E10 → E8 → E7 → E5. The
> first four may change the plan at once, so they come first; after each I read the report
> and, if needed, revise the next tasks. E1 (speed), E2 (density), E4 (logins), E6 and E13
> (Windows) get separate briefs later, on your machines.
>
> **Where to run.** If the machine is Linux with root and Docker (an own server or one
> from the sysadmins), the agent works right on it: that is better, and speed is measured
> on it later. If the machine is a Mac or has no root, the agent runs the checks on GitHub
> Actions in the private `kao73/gvisor-spike`, as in round 2. The tasks are written in
> English so the agent is more precise; the report is in Russian.

---

## Part 0. Common to every experiment

### 0.1 Context

LADO runs teams of AI coding agents (Claude Code, Codex, OpenCode, Kilo) in tmux. We are
isolating each LADO session, as the first step to a cloud. The candidate layout: a `lado`
container (the control panel) and a `runner` container; inside `runner`, each session runs
in its own gVisor sandbox (`runsc run`) with its own netns whose iptables rules let it reach
only a proxy. Read, in the public repository `github.com/ladohq/lado` (`main`):

- `docs/research/session-isolation-plan.md`: the plan; section 5 holds every experiment's
  **threshold, approved by the human on 2026-11-27**;
- `docs/research/session-isolation.md`: the research of rounds 1–2, with its corrections;
- `docs/research/session-isolation/s3-linux.md` (round 2 on Linux; the closest to this work)
  and `gvisor-spike-2-brief.md` (round 2's method).

Round 2's scripts are in the private repository **`kao73/gvisor-spike`** (`docker/`,
`scripts/` incl. `netns.sh`, `seccomp/runner.json` and `runner-narrow.json`,
`apparmor/lado-runner-lite`, `probe/`, `ci/`, `.github/`). **Reuse them**; same scripts,
comparable results. Clone with LF line endings (`git clone -c core.autocrlf=false`).

Known facts — do not re-derive, build on them:
- Profile **R+net** works on Linux x86/arm64, WSL2 and Docker Desktop macOS: `init: true`,
  `cap_drop: [ALL]`, `cap_add: [SYS_ADMIN, NET_ADMIN, NET_RAW, SETUID, SETGID, SETFCAP]`,
  seccomp `runner.json` (Docker default + `pivot_root`, `chroot`) or `runner-narrow.json`,
  `no-new-privileges`, `sysctls: [net.ipv4.ip_forward=1]`. On Ubuntu 24.04 AppArmor
  `docker-default` refuses it; `lado-runner-lite` works.
- Rootless runsc with a shared uid is out: a process of the runner's uid can ptrace other
  sandboxes' sentries.
- runsc `release-20261123.0`; the release is a tarball and runsc looks for `gvisor-bin/`
  beside itself; a netns is single-use (recreate before each run); filter containers by
  label; without `init: true` the runner collects zombies.

### 0.2 Where to run

- **A Linux host with root and Docker:** run directly on it. Record the host (provider, CPU
  model, dedicated or shared vCPU, cores, RAM, disk type, kernel, distro, Docker version,
  cgroup version, AppArmor/SELinux state).
- **Otherwise:** GitHub Actions in `kao73/gvisor-spike` on a branch `m0-<experiment>`
  (`ubuntu-24.04`, and `ubuntu-24.04-arm` only where the answer may differ by architecture),
  `workflow_dispatch` only, logs kept as artifacts of the run.
- Speed from GitHub runners is a hint, never a decision (2 vCPU, up to 2× spread between
  VMs).

### 0.3 Rules

- No real secrets: no logins to agent CLIs, no API keys, no repository secrets added.
- Nothing is pushed to `ladohq/lado`. Commits go only to `kao73/gvisor-spike`.
- Raised privileges only for this experiment's containers. On a host: record every host
  change (packages, `daemon.json`, sysctls, AppArmor profiles) and undo it at the end.
- Label every container, network, volume and image `lado.m0=<experiment>`; clean up by that
  label. Snapshot `docker ps -a`, `images`, `volume ls`, `network ls` before; compare after.
- Work folder `~/lado-m0/<experiment>/`; scripts and raw logs there.
- When a step fails: the exact error, at most two or three variants, then move on and
  record it. **Never weaken a check to make it pass.**
- About 1–2 hours per experiment; stop and report if it grows much beyond.

### 0.4 Report

`~/lado-m0/<experiment>/REPORT.md`, **in Russian**, readable without the logs; pack the
folder into `<experiment>.tar.gz`. Sections:

1. **Итог** [Summary] (3–8 строк [lines]): результат и **на какую сторону порога он попал**, одной фразой —
   решение по порогу. Если на грани или не удалось проверить — так и написать.
   [The result and **which side of the threshold it fell on**, in one sentence: the
   decision by the threshold. If borderline or not checkable, say so.]
2. Окружение [Environment].
3. Что сделано [What was done]: шаги, команды, таблица результатов [steps, commands, a table of results].
4. Что это значит для плана [What it means for the plan] — предложением (план правит супервизор) [as a proposal; the supervisor edits the plan].
5. Проблемы и неожиданности; что не сделано и почему [Problems and surprises; what was not done and why].
6. Уборка [Cleanup]: снимки до и после совпадают; что изменено на хосте и откачено [the snapshots before and after match; what was changed on the host and undone].

---

## E14. runsc as Docker's runtime on the host

**Question.** On an own Linux server, can sessions run as ordinary containers with
`--runtime=runsc` (gVisor installed on the host), instead of the privileged nested runner?
That would remove the six capabilities, the custom seccomp profile and its upkeep.

**Do.**
1. Install runsc on the host (`runsc install`, `systemctl restart docker`); record every
   step an installer would have to do, and what it changes.
2. Two "session" containers with `--runtime=runsc`, each with its own network that reaches
   only a proxy container (Docker network plus iptables in `DOCKER-USER`, or a per-session
   internal network with the proxy as the only gateway; choose and justify).
3. The isolation table of round 2 between them and against the host: processes, files,
   TCP to the other session and to the host's services, `docker.sock`, `/proc`, metadata
   address `169.254.169.254`, IPv6. Root inside the container too.
4. The compatibility list as uid 1000 inside (git clone/status/worktree, tmux `-L lado`,
   `uv sync` + `lado --version` of ladohq/lado, `npm ci`, gcc, `codex sandbox -- true` if
   installable without login, bwrap, inotify).
5. Same workloads (W2 git, W7 exec of round 2) in the nested runner on the same host, three
   runs each; record, do not decide on speed if the host is a GitHub runner.
6. Who needs the Docker socket in this design (the component that starts session
   containers) and what it can do with it.

**Threshold.** Same isolation, the install fits in one installer step, speed no worse →
on an own server the runner uses the host's runtime; the nested variant is needed only
where nothing can be installed on the host (Docker Desktop). Note: the component holding
the Docker socket equals root on that host; record it as a trusted part of the host.

## E9. The runc step

*Updated after E14's report (2026-11-27).* E14 passed: on an own server sessions run as
containers with the host's runtime, in network scheme **B** (a bridge network per session,
the proxy in its own network, `DOCKER-USER` rules over the pool, plus `INPUT`/`ip6tables`
REJECT from the session bridges). **Reuse E14's scripts from branch `m0-e14` of
`kao73/gvisor-spike`** (`m0.yml`, `repo/m0/e14/`): E9 is largely E14's matrix with
`--runtime=runc`.

**Question.** Is a plain container per session (runc) with the same network setup already
a real isolation step, before gVisor?

**Do.** Two forms, the same isolation table for both, with runsc in the same run as the
baseline:

1. **On the host** (the own-server form): E14's scheme B with the hardening, sessions with
   `--runtime=runc` instead of `--runtime=runsc`.
2. **Nested** (the Docker Desktop form): round 2's runner and sandbox setup (R+net), the
   sandbox started with `runc` instead of `runsc`, same netns and iptables rules.

Users: uid 1000 and root with Docker's default capabilities (LADO never adds capabilities to
a session; `--cap-add ALL` is not a case for runc). Two sessions with separate rootfs and a
random marker. Rows, as in E14's table 3.3, plus what differs for a real kernel:

- processes, files and markers of the other session and of the host/runner; `docker.sock`;
  host paths in mountinfo;
- TCP to the other session; the host's (runner's) services over IPv4, with and without the
  `INPUT` hardening; IPv6 link-local and out; metadata `169.254.169.254`;
- direct internet; **DNS**: E14 found that runc in scheme B resolves external names
  through Docker's DNS (`127.0.0.11`), an exfiltration path that runsc does not have. Find
  the simplest setting that closes it (`--dns` to an unroutable address, a rule on
  `127.0.0.11`, an internal network for DNS) and check it does not break the session;
- the proxy reachable; root's attempts to route around it; rules unchanged after;
- **kernel-facing leaks**: `/proc` and `/sys` (kallsyms, `/proc/sys/kernel/*`, sysrq,
  `core_pattern`, `/sys/class/net`, DMI), raw and packet sockets, `dmesg`, `mount`,
  `unshare -U -r` and what it then allows, the seccomp and AppArmor actually applied
  (`/proc/self/status`), `keyctl`, `perf_event_open`, `bpf`;
- cgroup limits (`--memory`, `--cpus`) apply, as a side note (E8 is separate).

**Threshold.** All rows closed as under runsc → the runc step is accepted. Any row open → no
such step. **Also record for each open row whether one simple setting closes it** (the
human may soften the threshold to "closed by a simple setting"). Kernel exploits themselves
are out of scope: runc never closes them (threat T5), that is what gVisor is for.

## E3. The proxy and the Agent API gateway inside the runner

**Question.** Can the proxy (and later the Agent API gateway) live inside the runner, or
must it move into its own container?

*Known from E14:* a proxy without an allowlist reaches the host's services; in scheme A
(the proxy attached to every session network) it bridges sessions; Docker's DNS does not
work under runsc, so sessions reach the proxy by IP; `proxy.py` does not pass the
`Metadata` header, so metadata through the proxy was not really tested.
*Known from E9:* in R+net the sandbox reaches the runner's services over IPv6 link-local
(`[fe80::…%eth0]`) unless `ip6tables` INPUT/FORWARD REJECT from `veth+` is set; round 2's
rules were IPv4 only. Test E3 with that hardening in place, and once without it as a check.
Docker's default capabilities do include `NET_RAW` for runc (E14's report said otherwise).

**Do.** In R+net with the proxy inside the runner (round 2 ran it outside), and in E14's
scheme B with the proxy in its own network: from the sandbox, as uid 1000 and as root —
- IPv6: link-local to the runner, `ip6tables` state, any route out;
- DNS: can the sandbox resolve names directly; DNS as an exfiltration path; the proxy
  checks the host before resolving it (CONNECT to an allowed name that resolves to a
  private address; to an IP literal; to `localhost`, `169.254.169.254`, the runner's own
  addresses);
- the runner's other ports (anything listening on the veth or `0.0.0.0`);
- a malformed CONNECT, header smuggling, very long lines;
- metadata `169.254.169.254` **through the proxy**, with a proxy that passes headers (Azure
  needs `Metadata: true`, GCP `Metadata-Flavor: Google`);
- rules unchanged after the attempts.

**Threshold.** A hole in the proxy → the proxy goes into a separate container. The gateway
stays reachable from the sandbox anyway: record what it needs (its own port only, strict
parsing, its own check).

## E15. Rootless runsc with a uid per sandbox

*Known from E14, E9, E3:* use the hardened network rules (`INPUT` and `ip6tables`
INPUT/FORWARD REJECT from `veth+`; only the proxy's port and a gateway port open) and E3's
`strict_proxy.py` with the owner rules (branch `m0-e3`). Root in R+net has no `CAP_KILL`:
it cannot signal processes of another uid, so stop each uid's processes as that uid. In a
rootless variant check the same for one sandbox's uid against another's (signals, ptrace,
`/proc/<pid>/mem`, `/proc/<pid>/environ`).

**Question.** Can the runner drop root and most capabilities (Dangerzone-like), if each
sandbox runs under its own uid, so ptrace between sentries is closed?

**Do.** runsc `--rootless` (or the closest variant) in a runner with as few capabilities as
possible, each sandbox launched as a different uid (setuid helper, or `newuidmap` ranges).
Check: ptrace from one sandbox's sentry uid to another's; the per-sandbox netns and
proxy-only rules still work; the smoke check of round 2 (sandbox starts, git status, tmux,
curl through the proxy). Record the exact capabilities, seccomp and AppArmor it needs; on
Ubuntu 24.04 the `apparmor_restrict_unprivileged_userns` question.

**Threshold.** ptrace between sandboxes closed and the network works → a candidate profile
instead of R+net.

## E10. A separate uid for the agents in today's LADO image

*Known from E9, E15:* under runc and as root in a rootless sandbox, `codex sandbox` and
bwrap fail (user namespaces). As uid 1000 in E15's sandbox bwrap works, but `codex sandbox`
failed with `could not create PATH aliases: Permission denied` and `execvp
codex-linux-sandbox: No such file or directory` — likely codex's install (its helper in a
folder the second user cannot write), not isolation. **Settle this here:** make
`codex sandbox -- true` work for the second user (its own HOME, where codex puts its helper),
and record exactly what it needed.

**Question.** Inside today's LADO container (no gVisor), can the agents' process tree run as
a different uid from LADO itself, so agents cannot read LADO's database and secrets?

**Do.** Build LADO's image from `ladohq/lado` `main` (`make docker`, or
`docker build -f docker/Dockerfile`). Inside it, create a second user; run as that user:
tmux on its own socket, git in a bind-mounted repository owned by the host user, the four
CLIs' `--version` (installed in the image), `uv run` of a small Python script. Check what
it can reach of LADO's: `~/.lado/lado.db`, `~/.lado/secrets`, `~/.lado/server-token`,
`~/.lado/git-servers`, the `lado` tmux socket. Then the obstacles: file ownership in the
bind mount (both directions), git's `safe.directory` (note: the image sets `'*'` globally,
Dockerfile ~line 148), the CLIs' home folders, how LADO would start processes as that uid
(sudo, setpriv, a tiny helper).

**Threshold.** The bind-mounted repository and the CLIs work → the uid step goes into M3.
List each obstacle with its fix.

## E8. cgroups per sandbox under runsc

*Known from E14, E9:* with the host's runtime (`--runtime=runsc`, E14) and with runc on the
host (E9) Docker's `--memory` and `--cpus` work. In the nested runner, moving the runner's
processes into a leaf cgroup failed (`echo pid > init/cgroup.procs: Operation not
supported`), so controllers could not be enabled for children. Focus on the **nested**
runner, in both profiles: R+net and E15's rootless "R-uid" (`--rootless`, a uid per
sandbox, `--ignore-cgroups` today). If cgroups cannot be delegated there, say what the
runner container needs (`cgroupns: private`, a writable cgroup mount, systemd delegation)
or that limits must come from elsewhere.

**Question.** Can each gVisor sandbox get its own CPU and memory limits, so one session
cannot starve or kill the others? (Round 1 needed `--ignore-cgroups`.)

**Do.** In R+net, cgroup v2: start sandboxes with limits (OCI spec `linux.resources`, or a
child cgroup the runner creates and delegates). A memory hog and a CPU hog in one sandbox;
measure that the neighbour stays responsive and the runner survives; what happens at the
limit (OOM inside the sandbox, the sandbox killed, the runner killed). Record what the
runner container needs for it (cgroup namespace, `cgroupns: private`, a writable cgroup
mount).

**Threshold.** The limits do not work → limits at the level of a container per session.

## E7. Other Linux environments

*Known:* three runner variants now: R+net (round 2), E15's rootless "R-uid" (`SETUID SETGID
NET_ADMIN`, seccomp Docker default + 8 calls, AppArmor `lado-runner-lite`), and E14's host
runtime `--runtime=runsc`. Check all three where possible.

**Question.** Where does R+net (and E14's variant, if done) not work?

**Do.** Smoke check of round 2 under: Docker Engine 29 (newest); rootless Docker;
`userns-remap`; Fedora with SELinux enforcing (a Fedora VM via nested KVM on the x86 runner,
or on a host if available; otherwise say it needs a server). One table: environment × does
it start × smoke checks × the exact error.

**Threshold.** Does not work → `lado doctor` says so and runsc is not offered there.

## E5. tmux and PTYs under runsc

**Question.** Are gVisor's tmux and PTY problems (poll busy-loop, PTY errors) fixed in the
release we use?

**Do.** From gVisor's changelog and commits: are PR #12851 (poll) and the PTY fixes in
`release-20261123.0`? Then a short regression inside a sandbox: tmux idle CPU over 5 min
(it must be near zero), window resize, `stty -isig`, SIGHUP to the client, `capture-pane`
after 1000 lines.

**Threshold.** A regression → pin to a release with the fix.
