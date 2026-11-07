## 1. The wait

- [x] 1.1 `tests/test_tmux.py`, `test_popup_opens_on_the_clients_attached_to_the_session` (unit
  layer, where the test lives; it uses a real tmux and no agent): the loop before
  `assert out.read_text() == "approve\n"` becomes
  `while time.time() < deadline and not (out.exists() and out.read_text()):`.
- [x] 1.2 Proof that it closes the race, in a throwaway copy of the test file, nothing of it
  committed: the popup's script becomes
  `echo "asks $LADO_X"; read a; exec 3> "{out}"; sleep 0.3; echo "$a" >&3`. Without 1.1 the
  copy fails with `assert '' == 'approve\n'`; with 1.1 it passes. Say so in `build-report`.
- [x] 1.3 Unslowed, the test passes 20 times in a row under `-n auto`, each run among
  `tests/test_tmux.py` as a whole; say so in `build-report`.
- [x] 1.4 `make lint` and `make test` green; report the tests as numbers.
