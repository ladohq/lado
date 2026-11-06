# A stopped session's page Implementation Plan

**Goal:** A stopped session shows a bar with Resume session, a feed text of its own, Resume in the
head on tabs without the bar, folded terminals and "Agent not running".

**Architecture:** `session.status` drives everything, and one `useResume` serves both buttons. The
composer stays mounted and hidden. The fold is a view of the stored choice in `columns.ts`, and a
stopped terminal makes no socket. The web UI alone: no API, schema, MCP or CLI change.

**Tech Stack:** React, TypeScript, CSS, vitest, pytest with Playwright.

**Spec:** `openspec/changes/stopped-session-bar/` (AC-1..AC-10, D1-D10),
`docs/superpowers/specs/2026-11-06-stopped-session-bar-design.md`, run artifact
`mockup-stopped-session.html`.

## Global Constraints

- Colours by tokens only; no new token. UI texts word for word from the design doc.
- Do not touch `tmux_gone`, the running session's empty text, or the sections "Что работает" of the
  critiques. Keep edits of `Sessions.tsx` narrow: LAD-218 may run beside this.
- CHANGELOG.md: one item under `## 0.45.0 (unreleased)`, by docs/release.md's rules.
- UI tests with `-m ui`; suites with `-n auto`. Edit with edit tools, no sub-agents.

## Review Focus

- A session that stops while the human types: the draft and its files show again after Resume.
- A session that stops with the panel open and a terminal in control: control ends, the panel folds,
  nothing writes to `lado.terminals`.
- A reload or a move to another session and back: a stopped session's terminals are folded again.
- Files dropped on a stopped chat: the browser does not open them.
- An open gate in a stopped session: the card with its note stands above the bar, and neither hides
  the other at 390.

## Tests per requirement

No requirement crosses processes beyond what exists: the API does not change, so the integration
layer has nothing to add. Rules go to vitest. What needs real layout or a real resume goes to UI e2e,
in a new `tests/ui/test_stopped_session.py`, with the fake agent.

| Requirement | vitest (`make web`) | UI e2e (`tests/ui/`) |
|---|---|---|
| the bar in the composer's place | `Chat.test.tsx`: bar, no form shown, role on the text; stops live | `test_stopped_session.py`: 1440, 768, 390, empty and not; height at least 52 px above a phone |
| the bar fits a phone | | upright and 844×390: positions of the text and the button |
| Resume session is the head's Resume | `connection.test.tsx`: disabled when lost; `Chat.test.tsx`: draft kept | `test_launch.py`: bar, window, composer back; `test_connection.py`: Resume by the bar |
| the empty feed | `Chat.test.tsx`: both filters, running unchanged, entries unchanged | one shot per filter |
| the head by tab | `Launch.test.tsx`: table by status and tab | `test_session_head.py`: whole actions on Flows at 1440, 768, 390, 320 with a long title; no sideways scroll |
| no team | `Layout.test.tsx`: phone without Team, toggle's words and `aria-pressed` | 390 |
| terminals fold, store nothing | `columns.test.ts`: `stoppedPanel`; `Layout.test.tsx`: storage untouched | stored open, resume returns; opened by hand, reload |
| the terminal's text | `Terminals.test.tsx`: text, no socket, no Reconnect, no Take control; socket on resume; running keeps Reconnect | `test_terminal_panel.py`: rewrite the stopped test |
| the toggle's words | `Layout.test.tsx`: running keeps the icon alone | |

Regression: the tests that press `Resume…` in the head on Activity move to the bar's
`Resume session`, or open Flows first: `tests/ui/test_launch.py:480-511,587,638`,
`test_connection.py:396`, `test_session_head.py:298`, `web/src/Launch.test.tsx`,
`connection.test.tsx:659`. The status table at `Launch.test.tsx:1091` gains the tab.

### Task 1: The fold of the terminals

**Files:** Modify `web/src/columns.ts`, `web/src/Sessions.tsx`. Test `web/src/columns.test.ts`,
`web/src/Layout.test.tsx`.

**Interfaces:** Produces `stoppedPanel(panel, opened)`; `useSessionColumns(room, stopped: string | null)`.

- [ ] **Step 1: Write the failing tests** of the table's row, then run `make web`: they fail.
- [ ] **Step 2: Implement.**

```ts
// A stopped session's terminals: folded, whatever is stored, unless opened there (D7). The
// choice stays stored and comes back when the session runs.
export const stoppedPanel = (panel: ColumnsInput["panel"], opened: boolean): ColumnsInput["panel"] => ({
  ...panel,
  collapsed: !opened,
  chosen: opened,
});
```

```ts
// In Sessions(): the name of the session shown, when it is stopped.
const shownSession = loaded && "sessions" in loaded ? loaded.sessions.find((one) => one.name === current) : undefined;
const columns = useSessionColumns(room, shownSession?.status === "stopped" ? shownSession.name : null);

// In useSessionColumns(room, stopped):
const [openedIn, setOpenedIn] = useState<string | null>(null);
const isStopped = stopped !== null;
useEffect(() => {
  if (!isStopped) setLast(storedLastColumn()); // what a stopped session set in memory goes
}, [isStopped]);
const shownPanel = isStopped ? stoppedPanel(panel, openedIn === stopped) : panel;
const input = { room: room ?? Infinity, list: { ...list, width }, panel: shownPanel, last, control };

// panelColumn:
open: () => {
  if (narrow) return setOver("terminals");
  if (isStopped) {
    setLast("panel");
    return setOpenedIn(stopped);
  }
  openedLast("panel");
  keepPanel({ collapsed: false });
},
fold: () => {
  if (narrow) setOver(null);
  else if (isStopped) setOpenedIn(null);
  else keepPanel({ collapsed: true });
},
```

Add `isStopped`, `stopped` to the `useMemo` dependencies.

- [ ] **Step 3: Run** `make web`: PASS. **Commit** `A stopped session's terminals start folded and store nothing (LAD-196)`.

### Task 2: The terminal

**Files:** Modify `web/src/Terminals.tsx`, `web/src/Sessions.tsx`, `web/src/styles.css`. Test
`web/src/Terminals.test.tsx`, `tests/ui/test_terminal_panel.py`.

**Interfaces:** Produces `TerminalPanel`'s prop `stopped: boolean`.

- [ ] **Step 1: Write the failing tests;** rewrite `test_terminal_panel.py:195-205` to expect the text and no Reconnect. Keep the `closed:` tests of `Terminals.test.tsx` for a running session.
- [ ] **Step 2: Implement.**

```tsx
// In TerminalPanel: a stop ends control and Expand, as a fold does.
useEffect(() => {
  if (!stopped) return;
  releaseAll();
  setExpanded(false);
}, [stopped, releaseAll]);

// In a tab's panel, in place of AgentTerminal when `stopped`:
function StoppedTerminal() {
  return (
    <div className="term" data-link="stopped">
      <div className="term-tools">
        <span className="term-mode term-view">
          <ViewIcon />
          Viewing
        </span>
      </div>
      <div className="term-screen term-stopped">
        <p>Agent not running — resume the session to start it</p>
      </div>
    </div>
  );
}
```

```css
.term-stopped {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: var(--term-ground);
  color: var(--term-ink);
  font: 13px var(--mono);
  text-align: center;
}
```

In `SessionTab`: `<TerminalPanel key={name} session={name} column={panel} stopped={session.status === "stopped"}>`.

- [ ] **Step 3: Run** `make web` and `uv run pytest -m ui tests/ui/test_terminal_panel.py`: PASS. **Commit** `A stopped session's terminal says the agent is not running (LAD-196)`.

### Task 3: Resume in the head

**Files:** Modify `web/src/SessionControl.tsx`, `web/src/Sessions.tsx`, `web/src/styles.css`. Test
`web/src/Launch.test.tsx`, `web/src/connection.test.tsx`, `tests/ui/test_session_head.py`.

**Interfaces:** Produces `useResume(session: SessionInfo): { resume: () => void; lost: boolean }`;
`SessionActions({ session, onActivity })`, `onActivity: boolean` set by `HeadLine` and `PhoneHead`
(a boolean keeps `Sessions.tsx`'s `Tab` out of `SessionControl.tsx`).

- [ ] **Step 1: Write the failing tests;** move the regression list above.
- [ ] **Step 2: Implement.**

```tsx
function actionsOf(session: SessionInfo, onActivity: boolean): Action[] {
  switch (session.status) {
    case "running":
    case "loop_down":
      return ["stop"];
    case "stopped":
      return onActivity ? ["forget"] : ["resume", "forget"]; // on Activity the bar has Resume
    case "tmux_gone":
      return ["resume", "stop"];
  }
}

export function useResume(session: SessionInfo) {
  const launch = useLaunch();
  const { lost } = useLive();
  return { resume: () => launch({ kind: "resume", session }), lost };
}
```

The button shows `<span className="session-resume-word">Resume</span>` when `action === "resume"`
and `session.status === "stopped"`. Pass `onActivity={tab === "activity"}` through `SessionHead`,
`HeadLine` and `PhoneHead`.

```css
.session-head-actions .icon-button:has(.session-resume-word) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: auto;
  padding-inline: 10px;
}

.session-resume-word {
  font-size: 14px;
  font-weight: 500;
}

:root[data-phone] .session-head-actions .icon-button:has(.session-resume-word) {
  width: auto;
  padding-inline: 10px;
}
```

The last rule must come after the phone rule at `styles.css:10475`.

- [ ] **Step 3: Run** `make web` and `uv run pytest -m ui tests/ui/test_session_head.py`: PASS. **Commit** `A stopped session's head has Resume with its word off Activity (LAD-196)`.

### Task 4: The bar and the feed

**Files:** Modify `web/src/SessionControl.tsx`, `web/src/Chat.tsx`, `web/src/Composer.tsx`,
`web/src/Agents.tsx`, `web/src/Sessions.tsx`, `web/src/styles.css`. Test `web/src/Chat.test.tsx`,
`tests/ui/test_stopped_session.py`, `tests/ui/test_launch.py`, `tests/ui/test_connection.py`.

**Interfaces:** Consumes `useResume`. Produces `StoppedBar({ session })`; `Chat`'s prop `stoppedBar: ReactNode`; `Activity`'s prop `info: SessionInfo`.

- [ ] **Step 1: Write the failing tests;** change `Chat.test.tsx:512` (the placeholder is gone).
- [ ] **Step 2: Implement.**

```tsx
// SessionControl.tsx
export function StoppedBar({ session }: { session: SessionInfo }) {
  const { resume, lost } = useResume(session);
  return (
    <div className="stopped-bar">
      <div role="status" className="stopped-bar-text">
        <strong>This session is stopped</strong>
        <span>Its branches, runs and history are kept</span>
      </div>
      <Waits>
        <button type="button" className="primary" disabled={lost} onClick={resume}>
          <ResumeIcon />
          Resume session
        </button>
      </Waits>
    </div>
  );
}
```

```tsx
// Chat.tsx
const emptyText = (stopped: boolean, all: boolean) =>
  !stopped
    ? "No messages yet. Write to the supervisor below."
    : all
      ? "Nothing was said in this session."
      : "No messages with you. Messages between agents are hidden.";

{ready && shown.length === 0 && <p className={stopped ? "empty stopped-empty" : "empty"}>{emptyText(stopped, agentMessages)}</p>}
// the section: onDragOver/onDrop use `fold || stopped`
{stoppedBar}
<Composer session={session} folded={fold !== null || stopped} inputRef={composerField} />
```

In `Composer.tsx` drop the prop `stopped` and every use: the placeholder is
`` `Write to ${to ?? "the supervisor"}…` ``, `off: folded`, and `ActionProblem` has no `off`. In
`Agents.tsx:269` drop `stopped={false}`.

```css
.stopped-bar {
  display: flex;
  flex: none;
  gap: 12px;
  align-items: center;
  box-sizing: border-box;
  width: 100%;
  max-width: 860px;
  min-height: 52px;
  padding: 8px 8px 8px 16px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
}

.stopped-bar-text {
  flex: 1;
  min-width: 0;
}

.stopped-bar-text strong,
.stopped-bar-text span {
  display: block;
}

.stopped-bar-text strong {
  font-size: 14px;
  font-weight: 600;
}

.stopped-bar-text span {
  color: var(--muted);
  font-size: 13px;
}

.stopped-bar .primary {
  display: inline-flex;
  flex: none;
  gap: 8px;
  align-items: center;
  white-space: nowrap;
}

.chat-feed > .stopped-empty {
  margin-block: auto;
}

:root[data-phone] .stopped-bar .primary {
  height: 44px;
}

:root[data-phone="tall"] .stopped-bar {
  flex-wrap: wrap;
  gap: 10px;
  padding: 10px 12px;
}

:root[data-phone="tall"] .stopped-bar-text {
  flex-basis: 100%;
}

:root[data-phone="tall"] .stopped-bar .primary {
  flex: 1;
  justify-content: center;
}
```

Add `.chat > .stopped-bar` to the rule at `styles.css:3972`, which centres the composer. Check that
`Waits` does not narrow the button on a phone.

- [ ] **Step 3: Run** `make web` and `uv run pytest -m ui tests/ui/test_stopped_session.py tests/ui/test_launch.py tests/ui/test_connection.py`: PASS. **Commit** `A stopped session gets a bar with Resume session in the composer's place (LAD-196)`.

### Task 5: The team on a phone

**Files:** Modify `web/src/Sessions.tsx`, `web/src/styles.css`. Test `web/src/Layout.test.tsx`,
`tests/ui/test_stopped_session.py`.

- [ ] **Step 1: Write the failing tests** of the table's rows.
- [ ] **Step 2: Implement.** `Activity` takes `info: SessionInfo`; `stopped` follows from it.

```tsx
<div className="team-row">
  {!stopped && <Team session={session} />}
  <Tooltip tip={tip}>
    <button
      type="button"
      className={stopped ? "icon-button between-toggle with-words" : "icon-button between-toggle"}
      aria-label="Messages between agents"
      aria-pressed={agentMessages}
      onClick={() => storeAgentMessages(!agentMessages)}
    >
      <BetweenIcon />
      {stopped && <span>Messages between agents</span>}
    </button>
  </Tooltip>
</div>
```

```css
:root[data-phone] .icon-button.between-toggle.with-words {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  width: auto;
  height: 44px;
  padding-inline: 10px;
  border-color: var(--line);
  font-size: 13px;
}
```

Keep the `aria-pressed="true"` look of `.between-toggle`. Pass `stoppedBar={stopped ? <StoppedBar session={info} /> : null}` to `Chat`.

- [ ] **Step 3: Run** `make web`: PASS. **Commit** `A phone shows no team in a stopped session, and the toggle its words (LAD-196)`.

### Task 6: Documents and regression

**Files:** Modify `docs/design/ui.md`, `CHANGELOG.md`; comments of `Terminals.tsx:20`,
`SessionControl.tsx:1-8`, `Sessions.tsx:498`.

- [ ] **Step 1:** `docs/design/ui.md`: Session head (actions by tab), Terminal (`Reconnect`, a stopped session's terminal), Structure (the fold stored nowhere), Phone layout (the bar, the toggle), the chat's empty feed and the composer's stopped placeholder at line 805.
- [ ] **Step 2:** CHANGELOG.md, under `### Improved`:

```markdown
- **A stopped session says so and offers Resume.** A bar with Resume session stands in the
  composer's place, the empty feed tells what it shows, and terminals stay folded, saying the agent
  is not running. Your terminals' layout comes back after Resume.
```

- [ ] **Step 3:** Run `make web`, `make test`, `make lint`, `uv run pytest -m ui <changed files>`, `openspec validate stopped-session-bar --strict`, the trial archive of `.lado/sdlc.md`. Each log outside the tree, exit status read first.
- [ ] **Step 4:** Attach screenshots at 1440, 768, 390 and the dark theme to `build-report`, with a running URL of a stopped session for the second ui-review. **Commit** `The documents follow the stopped session's page (LAD-196)`.
