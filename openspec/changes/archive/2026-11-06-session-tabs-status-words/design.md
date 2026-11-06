## Context

Root cause and options: proposal, Why. Mockup: run artifact `mockup-tabs-status.html`; the human
took the recommendations by answer #4034. Against AGENTS.md: the change lies in the web UI and
names no CLI, so it works with every provider (neutral core); the word table stays one (one source
of truth); the fold loses no function, as the icon does what the radios do (no silent drops); the
one new level is what the finding needs (only what is used). ROADMAP.md's coming stages do not
touch the tab bar.

## Decisions

**D1. The fold is a level of the tabs, not a second mechanism.** `LAST_FIT` becomes 4: 0 as they
are, 1 no icons, 2 no counts, 3 a tool's short form, 4 the scroll with ‹ and ›. `choose` stays as
it is. On a bar with no short form level 3 changes nothing, so the loop passes on to 4 with no
special case: Find on Flows does not move. Counts stay hidden at 3 and 4 in the CSS.

**D2. One icon, two places.** The phone's button in `ActivityTab` becomes a component, with its
tip, used by the team's row and by `MessagesChoice`. `MessagesChoice` renders the radios and the
icon, and `.session-tabs[data-fit="3"|"4"]` shows the icon and hides `.between-wrap`, so React state
is not a part of the trial. Both read `useAgentMessages`, so the choice cannot differ. Hidden by
`display: none`, the unused form is out of the tab order and the accessibility tree.

**D3. The focus lives through the trial.** `choose` passes level 0 on every resize, which hides the
icon for a moment, as Team's trial does (`test_the_focus_lives_through_a_trial`). `choose` notes
the focused control of the bar's tool before the trial and, after it, puts the focus back on that
control or on its other form with `preventScroll`. The focus given back must show no tooltip the
human did not ask for.

**D4. One function keeps a tab in view.** A pure `tabScroll(view, tab, room)` gives the row's
`scrollLeft` that shows the tab clear of `room` px at each end that has more, and its result is
clamped by the row. Tab start wins when the tab is wider than the room left. The effect for the
tab shown and a new `onFocus` on the row use it, through the row's own scroll: `scrollIntoView`,
which the finding suggests, is what the code's comment rules out, as Chromium's Tab would start
from the tab scrolled to. `room` is the fade's 56 px, not the button's 26 px: text under the fade
is hard to read. A constant beside `LAST_FIT` with a comment, as `CHAT_MIN` names `--chat-min`.

**D5. The words stay in `Team.tsx`.** `STATUS_WORDS` is exported there, beside `StatusDot`, which
`Agents.tsx` already imports. `AgentChip`'s default name and the terminal tab's name take it too.
The update's list gets a status typed by the API: when it is a plain string, unknown values show
as they are. The agent's page drops `for`: `<words> · <time> · spawned <clock>`.

**D6. The tooltip is `Tooltip` around the list's button, with `name` as the tip.** One place covers
the chevron and `+N`. `Tooltip` keeps child handlers and the ref, and adds no element until shown,
so the toolbar and the trial see the same button. While the list is open it must not show:
`Tooltip` gets a way to stay silent (a `null` tip shows nothing), which also hides one that is up.

**D7. `moreName` agrees with its number.** `1 waits for you`, `2 wait for you`.

## Test layers

No behaviour crosses processes, so no integration test. Unit (vitest) by default; a UI test only
where real widths or real focus decide.

| Requirement | Layer | Test |
|---|---|---|
| A session's tabs give way in levels | UI | `test_narrow_layout.py`: 1100, 1120, 1140, 1160 px; panel opened by hand at 420 px; changes `test_at_a_chat_of_420_px_the_tabs_keep_their_counts` (level 3, the icon) |
| A focused tab stands clear of the bar's ends | vitest + UI | `tabScroll` cases; `test_narrow_layout.py`: bar narrowed by a style, Tab through the tabs |
| A narrow tab bar shows the icon instead of the radios | vitest + UI | `Sessions`/`Layout.test.tsx`: tips and choice; `test_team_head.py`: the icon chooses, the focus through a resize, Flows' Find |
| An agent's status reads the same | vitest | `Agents.test.tsx`, `SystemPanel` test, `Terminals.test.tsx`, `Team.test.tsx` |
| The team's list button says its name in a tooltip; The team is one stop of the keyboard | vitest | `Team.test.tsx`: `moreName`, tip on hover, none while open |

Regression: `make web`, `make test`, `make lint`, `uv run pytest -m ui` on `test_narrow_layout.py`,
`test_team_head.py`, `test_tabs.py`, `test_agents_tab.py`, `test_chat.py`, `test_terminal_panel.py`.
