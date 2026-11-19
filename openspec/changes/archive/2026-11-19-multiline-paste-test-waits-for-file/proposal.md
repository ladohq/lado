Task: LAD-296

## Why

Symptom: `tests/test_tmux.py::test_send_text_pastes_multiline_text` failed in CI of PR #324
(run 44165723305, attempt 1, job unit, Python 3.10) with `FileNotFoundError:
…/test_send_text_pastes_multilin0/out.txt`; the other 5772 tests passed, and a rerun of the
failed jobs passed. The pull request touched neither `src/lado/tmux.py` nor `tests/test_tmux.py`.

Cause: a race in the test, not a defect of LADO. The test starts a tmux window running
`sh -c "cat > out.txt"`, and the file comes into being only when that shell opens it for
`cat`. Right after `send_text` the wait loop calls `out.read_text()`, which raises at once when
the file is not there yet: the loop has no way to wait for a file that does not exist, so on a
loaded runner, where the shell starts later than the test reaches the loop, the test fails
before its 5 s deadline even begins to count. The text itself is not lost: tmux writes the paste
into the pane's terminal, where it waits until `cat` reads it.

The two neighbours in the same file already avoid it: the fixture `neighbour` creates
`out.txt` before it starts the window, and the popup test waits with
`out.exists() and out.read_text()`.

Checked by the analyst with the probe of task 1.1 (`sleep 1; cat > out.txt`): the test fails
at once with the same `FileNotFoundError`, and with `out.touch()` added it passes (1.11 s).

The product is not at fault: `send_text` returns once tmux has the paste, and it promises
nothing about when the program in the window has written its output.

Options weighed:

- A (taken): create `out.txt` (`out.touch()`) before the window starts, as the fixture
  `neighbour` does. The loop then waits for the text as it was meant to; `cat >` truncates an
  empty file, so nothing else changes. A real failure (the text never arrives) still fails the
  assertion after 5 s, now with the lines it got instead of a missing file. Long-term cost: one
  line.
- B: make the loop tolerate a missing file, `not (out.exists() and "line two;" in
  out.read_text())`, as the popup test does. Equally correct, but a text that never arrives
  ends in `FileNotFoundError` on the assertion instead of a comparison of lines. Long-term cost:
  one line, a less telling failure.
- C: wait in the test for the shell to start (poll the pane's command) before sending. More
  code, and it states a precondition the test does not need, as tmux keeps the paste anyway.
  Long-term cost: a helper for one test.

## What Changes

- `tests/test_tmux.py`: `test_send_text_pastes_multiline_text` creates `out.txt` before it
  starts the window.
- Neither a minor nor a patch of its own: tests only, users see nothing, so no CHANGELOG.md
  line, and no API, schema, MCP, CLI or UI change.

## Scope

- `tests/test_tmux.py`. Nothing in `src/` or `web/`.

## Out of scope

- `src/lado/tmux.py` (`send_text`): the paste is not lost and the function behaves as its
  docstring says; nothing there to fix.
- Other tests of `tests/test_tmux.py`: the fixture `neighbour` and the popup test already wait
  safely, and no other test reads a file a window writes.
- A rerun plugin or a longer timeout: they hide the race rather than close it, and the task
  asks for no retries inside pytest.
- BACKLOG.md: it has no entry for this test, so nothing to remove.

## Acceptance criteria

- AC-1: `test_send_text_pastes_multiline_text` calls `out.touch()` before `tmux.new_session`;
  the rest of the test is unchanged.
- AC-2: The race is shown by hand once: with the window's command delayed (`sleep 1; cat >
  out.txt`, the probe of task 1.1), the old test fails with `FileNotFoundError` and the new one
  passes. The build report quotes both; the probe is not committed.
- AC-3: With the fix, the test passes 50 times in a row alone (`-n0`, in a shell loop) and `uv run pytest -n auto tests/test_tmux.py` 3 times in a row, each run's exit
  status read (not piped).
- AC-4: `make lint` passes and CI is green on the first attempt (no rerun of the unit jobs).

## Impact

- `tests/test_tmux.py` only.
- No delta (`skip_specs` in `.openspec.yaml`): no behaviour rule changes; archived with
  `--skip-specs`.

## Decisions for the record

- Scale tweak: a test-only change of known shape, as the earlier flake fix
  `unmerged-finish-test-waits-for-idle`; review by precision.
- Option A over B: the same one line, and a real failure reads as a comparison of lines.
- Test layer: unit (`tests/test_tmux.py`, real tmux on the test's own socket), the test
  itself; no new test.
- The probe delays the window's shell rather than loading the machine: it makes the race
  happen every time and touches no product code.
