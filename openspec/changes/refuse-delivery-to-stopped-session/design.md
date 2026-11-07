## Decisions

**D1. The refusal is made in `_deliver`.** The whole of `_sweep_sent` and `hand_over` there goes
in one `try`, since both type. `except tmux.TmuxError as error`: when the session ended, raise the
refusal `from error`, else `raise`. `hand_over` itself stays as it is: hooks and the sweep call it
and have their own handling. Hooks reach `_deliver` through `post`, where `_tell_lead` and
`_report_failure` already suppress `LadoError`.

**D2. "The session ended" is read from its row, then from tmux.** True when `state.get_session`
gives a session with `stopped_at`, or when `loop.tmux_gone(session, error)` says so. The database
goes first: it costs no tmux call and answers for every stop, as `_mark_stopped` marks before it
kills. `tmux_gone` covers a tmux killed by hand or a crash; it answers False for `TmuxMissing` and
for a tmux that cannot tell, so these stay errors. A session the database does not know did not
end for this purpose: the sentence promises a Resume it cannot have. `_to_running` keeps its `no
running agent` text there (an agent's `send_message` under a session LADO has no row for), and a
session forgotten during the typing is refused as `unknown session`, `running_session`'s words.
`loop.why_stop` is not used: it answers for an unknown session too.

**D3. One sentence, one source.** A helper or constant in `runtime.py`, formatted with the
recipient: `The session stopped before this message reached <recipient>, so it was not delivered.
Send it again after Resume.` It stays true after Resume, where the composer shows it again
(`stopped-session`, the composer stays mounted behind the bar). `_to_running` raises it instead of
its `no running agent` text when the session is stopped, so the end of `_deliver` and the two
places that store a message give the same refusal; a stopped agent of a running session keeps the
old text. A name that was never an agent of the stopped session gets the sentence too: a stop
forgets its agents (`state.stop_session`), so the two cannot be told apart, the sentence stays true
of the message, and the old text would only add an empty list. `running_session`'s refusal, for a session stopped before the request, stays: it is what a
request to a stopped session has always answered.

**D4. The status stays 400.** `core` maps `LadoError` to 400, and the composer shows any refusal's
`detail`. 409 would be more exact and buy the UI nothing.

**D5. The message is left as the stop left it.** Dropped by the stop, or `sent` when tmux went
without a stop, until the loop finds it gone and the stop drops it. No state change is added.

**D6. The supervisor's copy needs no handling of its own.** The second `_deliver` of
`write_as_human` refuses as the first when the session ends between them. The human then reads
"not delivered" for a message typed into a dying agent, which the stop dropped or would have
dropped unconfirmed, and keeps the draft: the safe side.

**D7. Exact targets.** `send_text` and `capture` use `f"={session}:={window}"`, `new_window`
`f"={session}:"`. Checked on tmux 3.3a: `new-window -d -t =<session>: -n <name>` adds a window as
before, next index included, `capture-pane` and `send-keys` work, and each fails with `can't find
session` for a session that is gone. `display-message` with a gone target still succeeds, printing
nothing, so `send_text` goes on to `paste-buffer`, which fails: nothing changes there.
