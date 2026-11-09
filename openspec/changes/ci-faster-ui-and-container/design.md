## Context

`ci.yml` runs every heavy job at once; the run lasts as long as its longest job plus the
queue. Today that is `ui (1)`: `make dist` (92 s), the browser setup (20 s median, 171-438 s
p90, once six hours) and `pytest -m ui -n 2 --shard 1/2` (492 s median). Then
`container (amd64)`: `make docker` (76 s) and 64 container tests in one process (390 s).
The free plan runs 20 jobs of the account at once; a run has 23.

`--with-deps` on the runner image installs only nine font packages (every other library is
already there) after an `apt-get update`, both from `azure.archive.ubuntu.com`; Chromium,
its headless shell and FFmpeg come from Playwright's CDN in about 8 s.

## Decisions

- D1. Time limits at about twice the job's p90 with room for the suite's growth: `unit` 15,
  `integration` 15, `ui` 25, `web` 15, `changes` 5, `ci-ok` 5; `smoke` 20 and `container`
  30 unchanged. The browser step also gets its own `timeout-minutes: 10`, so a hung mirror
  ends that step, not the whole budget. A unit test requires a limit on every job (the
  rule, not the values).
- D2. UI shards 2 → 4, `-n 2` kept (four workers on the 4-vCPU runner starve LADO's test
  timers, LAD-41). Each UI job builds only the bundle (`cd web && npm ci --no-audit
  --no-fund && npm run build`, today's shard-2 step). Four shards halve each job's tests;
  more would spend more on the per-job setup (~1 min) and slots of the 20.
- D3. A job `web` takes `make dist` and the Node tests; the job `js` goes. The UI tests
  need the bundle, not tsc or vitest, so `make dist` leaves their critical path, and a
  vitest flake no longer reruns a ten-minute browser job. Folding `js` (12 s, node only)
  into `web`, which sets up Node anyway, keeps the run at 27 jobs instead of 28 on the free
  plan's 20.
- D4. The browser cache with `actions/cache/restore` and `actions/cache/save` (the actions
  the workflow's owners already trust), no third-party action:
  - paths `~/.cache/ms-playwright` and `~/.cache/lado-apt` (the `.deb` files);
  - key `ui-browser-${ImageOS}-${ImageVersion}-playwright-<version>`, the version read with
    `uv run python -c` from `importlib.metadata` after `uv sync`; the image version in the
    key makes a new runner image take a fresh `--with-deps` instead of debs that may no
    longer fit it;
  - hit: `sudo dpkg -i ~/.cache/lado-apt/*.deb` (when the folder holds any) and
    `uv run playwright install chromium`, which finds the browser in its cache;
  - miss: a file in `/etc/apt/apt.conf.d/` with `Acquire::Retries "3"`,
    `Acquire::http::Timeout "30"` and `APT::Keep-Downloaded-Packages "true"` (and its
    `Binary::apt::` form), then `uv run playwright install --with-deps chromium` as
    today, then the `.deb` files of `/var/cache/apt/archives/` copied to `~/.cache/lado-apt`
    (the folder may be empty when the image already has every package);
  - save only when `github.event_name != 'pull_request'` and the restore missed: a pull
    request's cache is visible to that pull request alone and would spend the 10 GB that
    LAD-249's Docker cache also needs.
  The packages are those `--with-deps` chose on that very image: no list of packages kept
  by hand, so nothing drifts when Playwright changes its dependencies. A cached package that
  no longer installs fails `dpkg` loudly, never silently.
- D5. Container shards: matrix `include` of (arch, runner) × `shard: [1, 2]`, name
  `container (${{ matrix.arch }}, ${{ matrix.shard }})`, `fail-fast: false`. Each cell builds
  its own image (LAD-249's cache will make that cheap) and runs
  `scripts/smoke_ci.py container "$RUNNER_TEMP/container" ${{ matrix.shard }}/2`; the
  script's `container <out> [K/N]` adds `--shard K/N` to pytest and keeps the pass rule, so
  an empty shard is red. The artifact becomes `container-<arch>-<shard>`. The tests'
  session fixtures (the image check, Go's archive) run once per cell; the time spreads
  evenly over the files (21-65 s each), so a hash split is close to half.
- D6. `ci-ok` and `scripts/ci_ok.py` stay as they are: the script judges whatever `needs`
  holds, and the unit test already demands that `needs` lists every other job.
- D7. The browser cache is checked before merge by two `workflow_dispatch` runs of CI on
  the pull request's branch (a dispatch is not a pull request, so it saves; the second
  run reads the first's entry in the branch's scope).

## Risks / Trade-offs

- 27 jobs instead of 23 on the free plan's 20: two pull requests at once queue more. The
  shorter jobs free their slots sooner; the Team plan is the human's later choice.
- About 1 job-minute more per run for the extra setup of six cells.
- LAD-249 edits the same job `container`: a textual conflict for whichever merges second,
  resolved by keeping both (its build step, this matrix).
