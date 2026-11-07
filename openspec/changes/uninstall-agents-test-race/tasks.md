## 1. The test

- [ ] 1.1 `tests/test_uninstall.py`, `test_the_agents_processes_are_taken_before_the_stop_and_waited_for`
  (unit): `hangup` keeps `time.sleep(1)` and `agent.terminate()`, and loses `agent.wait()` and
  `ended.set()`; `ended = threading.Event()` goes; the `_repos` hook records
  `agent.poll() is not None`; the comment on `seen` stays true, and a comment says that a
  `wait` in the thread would hold `Popen`'s lock and make `poll` answer `None`. The assertions
  stay as they are. The fixture `agent` needs no change. Check: AC-1.
- [ ] 1.2 The node id passes 20 times in a row with `-n0`; say so in `build-report`. Check: AC-2.
- [ ] 1.3 The node id passes 40 times on one CPU shared with busy loops, the load that failed
  the old test (`taskset -c <cpu>` around both the loops and pytest); say so in
  `build-report`. Check: AC-2.
- [ ] 1.4 With `_wait_for_agents(agents)` in `uninstall.py` turned off for one run and restored
  uncommitted, the test fails at `assert seen == [True]`; say so in `build-report`. Check: AC-3.
- [ ] 1.5 `make lint` and `make test` green; report the tests as numbers. Check: AC-4.
