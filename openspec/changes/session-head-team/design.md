## Context

Spec: the design of run `ui-design/lad-197-team-head` (artifacts `spec`, `design-system`, `brief`,
`critique`), which replaces LAD-189 spec §6 and frames g6-*; the human's decisions of 2026-11-06
(answer #3978) and answer #3988; run artifact `mockup-team-head.html`, the designer's mockup with
the title's limit in its trial. Root cause and options: proposal, Why. Details of each size, state
and word: `docs/superpowers/specs/2026-11-06-session-head-team-design.md`.

Against AGENTS.md: the change lies in the web UI and names no CLI, so it works with every provider
(neutral core). The order of agents stays `teamGroups`, the choice of messages stays
`storedAgentMessages`, and marks come from one function used by the head and the strip (one source
of truth). An agent that does not fit is counted on the button and listed, and a team that fails
to load says so (no silent drops). No field, option or API is added (only what is used). ROADMAP.md's
coming stages touch nothing here: the desktop app and ACP keep the same head.

## Decisions

**D1. Pure rules in one new file.** `web/src/teamFit.ts` holds `fitLabel(name, k, names)`,
`agentMarks(names)` and `chooseLevel(steps, fits)`. The last walks the candidates (level 0, level 1
with `k` from the longest stem to 4, level 2, level 3 with `v` from N−1 to 0) and returns the first
that fits, or the last. So the order, the limit's place and the last step are tested without a
browser. Rejected: the loop inside the component, as `SessionTabs` has it; its steps are few, here
they depend on the team.

**D2. The trial.** `Team` for the head tries candidates in a `useLayoutEffect`, writing `data-fit`
and rendering each before the paint, like `SessionTabs`. A candidate fits when the right edge of the
team's last element lies within the team's box and, at levels 0 and 1, the title keeps its limit. It
runs again on a ResizeObserver on the top bar, not on the team (whose box the trial changes), on a
change of the agents' names or the title, and on `document.fonts.ready`. Status changes do not run
it: level 3's trial counts the button with its diamond.

**D3. The title's limit is measured by the text.** A `Range` over the first 24 characters of
`.session-title-text` gives the width they need; the limit holds when the span is at least that wide.
A shorter title needs itself. Why not `24ch`: `ch` is the digit's width, 12 px in this font, so 24ch
is 288 px, about 31 letters, not the 24 the human named. The measure works for any script. While
the title's field is open there is no text to measure, and the limit does not count.

**D4. Who gives way.** `flex-shrink` weights: title 1e18, project 1e12, run time 1e6, team 1000,
status words 1; Stop and the link do not shrink. The weights stand far apart for the reason
`styles.css` gives. Level 1 on, `.topbar:has(...)` hides the branch and the run time; Details has
both.

**D5. Numbers measured with the limit** (critique F13). 12 agents, 3 runs, a title of 47 characters:
1920 level 1, `k = 4`, title 256 px; 1440 and 1280 level 2, title 438 and 414 px; 1024 level 2, title
192 px; 768 level 3 with 8 avatars; 601 level 3 with 4. Title `lad-197 fix`: 1920 level 1, `k = 5`,
the rest as above. 4 agents, a run, a title of 20 characters: 1920 to 1280 level 0; 1024 level 1, whole
names; 768 and 601 level 2. The designer's spec and its critique say otherwise for 1920, 1024 and 768:
they had no limit. Tests take numbers from here.

**D6. The choice of messages is one small store.** `Yours | All` lives in the tab bar, so the state
leaves `Activity`. `SessionView` stays mounted across tabs, so a `useState` there would miss the store
that `Agents`' **All in Activity** writes. `prefs.ts` gets `useAgentMessages()` over
`useSyncExternalStore`; `storeAgentMessages` notifies. `SessionTabs` gets the radios as `children`,
next to `Find`; `Activity` keeps the icon for a phone only.

**D7. The word `Messages`.** `SessionTabs` adds one step before its levels: when level 0 does not
fit, `data-short` hides the word and the levels run as before. So the word depends on the bar's
content too: `Flows 1` is 23 px wider than `Flows`, and the first run can take the word away at
1440 with terminals (critique F10). Accepted: the words `Yours` and `All` stay, and design QA checks
they read.

**D8. The composer's line.** A wrapper `.composer-frame` holds `.composer-box` and the line, which
lies above a phone in the page's bottom padding (`position: absolute`, 14 px), so the page's height
does not count it. The hint turns visible by `.composer:has(textarea:focus:placeholder-shown)`, with
no React state. On an agent's page, which scrolls, the line stays in the flow and only the hint's
`visibility` changes. A `.field-problem` gets `margin-top: 10px` to stay clear of it.

**D9. `Team` has two views.** The phone keeps the row, `role="group"`, unchanged, rendered by
`Activity` under `usePhone`. `HeadLine` renders the head's view, `role="toolbar"`, with a roving
`tabindex`. Chips stay `AgentChip`; an avatar is `AgentAvatar`, sharing the strip's `strip-agent` class.

**D10. The focus ring over neighbours** (critique F12). The ring of a focused avatar stands 5 px off,
and neighbours are 4 px away, so it crosses them. `.head-team .strip-agent .dot { z-index: 2 }`
keeps their status marks above it; the ring may still cross their edges while the focus stands.

**D11. The list is Details' pattern.** `useDismiss`, `useBelow` and Details' focus rules, with the
frame of `.team-popover`. No new dismissal logic.

**D12. CSS comes from the design.** The artifact `design-system` of the run above is the new CSS, word
for word, but for the additions of D10. `.team-row` and `.between-toggle` stay for a phone only.

## Risks

- `Sessions.tsx` and `Composer.tsx` change in parallel in LAD-195: keep edits narrow; second to merge
  takes main.
- Not in the mockup, for design QA: the title's field beside the team, the Agents tab, branch at
  1600 px. `ui-review` checks them.
- The trial renders up to N + 10 candidates on a resize; each is a small render before the paint. If
  a resize drags, the trial may start from the current level.
