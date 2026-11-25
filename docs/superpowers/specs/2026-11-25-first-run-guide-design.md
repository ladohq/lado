# First-run guide, stage 1: design

Task: LAD-311. Change: `openspec/changes/first-run-guide/`. Decisions D1–D14 are in its
`design.md`; this document is the guide's behaviour, look and texts, so that the developer
builds it without the design flow's artifacts. It follows the design flow `ui-design/lad-311-guide`
(spec, mockup, design system, critique round 2: done) with the human's decisions of 25.11.2026,
which override it where they differ (the Help line, the "none of these" card, Codex's paste
step). The changed screens: run artifact `mockup-guide-stage1.html`; every other screen:
`ui-design/lad-311-guide/mockup.html`.

## 1. What the person sees

A guide drawn over LADO's unchanged screens. Two kinds of hints:

- **Guiding step**: the page dimmed, one existing element cut out of the dim and ringed, a
  card beside it. The card says what to press; the guide waits for the real action (the page
  opened, the person logged in, the author saved) and moves on by itself. No Next button,
  except on the two centred cards, which point at nothing.
- **Tip**: a small card with an arrow at an element, no dim, takes no focus, blocks nothing.
  **Got it** closes it; **Don't show tips like this** turns every tip off. Each tip is shown
  once in LADO's lifetime (on the server, so in every browser).

Stage 1 has the main path (guiding) and five tips: the New session window, the session page,
the first gate, the first agent question, the first terminal. Stage 2 (projects chain, more
models, git access chain, Kits) is a later task: its hints are not in the guide file of
this change.

The only new element on any screen is the Help menu's line **Getting started**.

## 2. When it shows

1. Nothing starts by itself while the server runs with `LADO_GUIDE=0` (for recording videos
   on a live LADO; set for every test but the guide's own UI e2e test): no welcome, no tip,
   no engine loaded. Help → Getting started still starts the guide for that page load.
2. **The main guide** runs while it is not completed and the person has not pressed Not now
   or Esc in this page load. It **starts only while no model is connected**: when the server
   first creates the guide's record and a model is connected already (an existing LADO
   updated to this version, or one set up by hand), the record is created completed and
   nothing shows; such a person meets the guide only through Help → Getting started. A
   person who has not answered the statistics question yet ("Help improve LADO?") sees the
   welcome only after answering it.
3. It starts at `welcome`. Then it shows the first step whose condition holds and whose part
   is not done in the system (§5). After Not now or Esc it comes back at the next page load,
   until completed. Opening the New session window completes it.
4. **Tips** show only while no guiding step shows, tips are not off, the tip's id is not
   among the shown ones, and its condition holds. One at a time; when two apply on one
   screen they follow the file's order (session → gate → question → terminal), and the next
   appears after Got it or after the person leaves the screen.
5. A hint is marked shown **as soon as it appears**, whatever the person then does.
6. **A marker missing** (the condition holds but no visible element carries the hint's
   `data-guide` marker for 2 s): the hint is skipped for this page load and the server writes
   it to LADO's error journal (`errors.jsonl`) with the hint's id and the marker.
7. **Help → Getting started**: tips back on, the main guide not completed, and it starts at
   `welcome` at once, even with a model connected. Steps done in the system are skipped as
   always. Tips already shown stay shown: the line turns tips on, it does not repeat them.
8. **New ids reach existing users once.** A hint changed enough to be shown again gets a new
   id; a new hint with a new id appears to people who saw all the others.

## 3. The layer

- **Guiding with a target**: a fixed layer over the window. The **hole** is the target's box
  plus 4 px, radius 8 px; around it the page is covered by `--guide-dim`. A 2 px
  `--guide-ring` outline is drawn inside the hole's edge (offset −2 px). Clicks and taps
  inside the hole reach the page; outside it they are blocked, and a press on the dim does
  nothing (it does not close the guide). The hole holds every control the card asks the
  person to press; when the card lines up with something smaller (an error line, a field),
  that is the step's `anchor`.
- **Guiding, centred** (`welcome`, `none-of-these`): the whole window dimmed, the card in the
  middle, nothing passes through.
- **Target inside an open modal `<dialog>`** (New session window): the layer is a
  `popover="manual"` element, so it sits above the dialog in the top layer; it draws no dim
  of its own (the dialog's backdrop is the dim), only the ring.
- **A CLI's login window** (`LoginSheet`, opened by Log in… / Change login…): the guide stays;
  its steps continue inside it (`login-*`). The hole is the window's box (`login-sheet`), so
  its Close stays usable; the card lines up with the anchor (the choices, the chosen box's
  field and Save, the action button, the refusal line). The sheet's own backdrop is the dim.
- **Another window opens over a guiding step** (the login terminal or sign-in code window,
  a confirmation): the guide hides until it closes; those windows carry their own steps.
- **Tip**: no dim, no hole, an arrow to its target. When it cannot stand next to its target,
  it rings the target instead: the **pointing ring**, 2 px **dashed** `--guide-ring`, 3 px
  outside the target, so it never reads as the focus ring.

## 4. Placement of the card

Margins: 16 px from the window's edges, 12 px between card and hole.

1. A target not fully in view is scrolled into view first (`block: center`; `start` when it
   is taller than half the window), then measured.
2. **Phone** (`<html data-phone>`): below, then above. The card is the window's width − 32 px.
3. **Wider**: the hint's `prefer` list, else right → below → above → left. Inside a window
   (a `<dialog>`, the login sheet) narrower than the screen, the card first tries right and
   left of the *window's* box at the anchor's height, pointing at it; a tip also tries below
   and above the window, where it does not point and its target gets the pointing ring.
4. The first place where the card fits whole in the window, covers no part of the hole or
   target and, for a tip, covers no focusable element outside its target, wins. The card's
   cross-axis position centres on the anchor, clamped to the window.
5. **A tip with no such place**: the nearest free place in the window (nothing focusable
   under it, not over its target), without an arrow, with the pointing ring. Failing that, a
   target taller than half the window (a terminal) carries the tip on its own lower part when
   no control is there. Failing that, beside its target after all, covering controls until
   Got it.
6. **A guiding card with no place** cuts out the anchor instead of the target and tries again.
   If still nothing fits: the window's bottom edge, over the target's lower part, no arrow.
7. **A target that fills the phone** (taller than 70 % of the window: the login sheet): no
   dim; the anchor is ringed, the whole window stays usable, and the card sits at the
   window's bottom edge.
8. Recompute on window resize, on scroll of any ancestor (a capture listener), on the
   target's `ResizeObserver` and when fonts load. Nothing runs while no hint shows.
9. The arrow: a 12 px square turned 45°, centred on the anchor, kept 12 px from the card's
   corners.

Placement is one pure function of rectangles (D10), unit-tested.

## 5. Parts, conditions and completion

Parts of the main guide, each done when its fact holds, a done part skipped and the
counter ("Step N of M") recounted:

| Part | Done when |
|---|---|
| Connect a model | `modelConnected`: any agent CLI is logged in, or a model server is saved |
| Sign your work | `authorInEffect`: LADO's commit author or git's own (outside any repository) signs commits: the source of Git servers' `⚠ Nobody: agents cannot commit` |
| Start working | the New session window opened (completes the guide) |

Named conditions the engine knows (the guide file names them; an unknown name fails the
unit test):

| Name | Reads | True when |
|---|---|---|
| `telemetryAnswered` | the guide's record (`telemetry_asked` false) | the statistics question needs no answer |
| `modelConnected` | facts (D4) | as above |
| `cliInstalled(cli)`, `cliLoggedIn(cli)` | facts of Agent CLIs (D4) | per provider |
| `authorInEffect` | facts (D4) | as above |
| `route(path)` | the router | the page is open |
| `marker(name)` | the DOM | a visible element carries `data-guide="name"`; this is how the open state of a form or window is read (`model-server-form`, `author-form`, `login-sheet`, `launch-task`, `gate-card`, …) |
| `loginWindow(cli)` | the DOM | the login sheet's marker carries `data-guide-cli="<cli>"` |
| `loginChoice(cli, id)` | the DOM | its chosen box carries `data-guide-choice="<id>"`; none clicked yet: no box chosen |
| `loginRefused` | the DOM | `login-refusal` is visible |
| `modelServerRefused` | the DOM | `model-server-error` is visible |
| `passedRow(cli)` | the guide's own page-load state | the person pressed "I have neither" on the row, or closed its login window without a login |

A provider whose name has no texts in the guide file gets no row step and no login steps
(neutral core); the path goes on to Model servers. Stage 1 has texts for `claude` and
`codex`.

## 6. The hints of stage 1

`eyebrow` of the model part: “Connect a model · Step 1 of 3” (the counter recounts when a part
is done). Every guiding card with a target has **Not now** and a waiting line.

### Main path (guiding)

**`welcome`** · centred
- When: not completed; `telemetryAnswered`; no window open.
- Done: Show me → the next step not done. Not now / Esc → closed until the next page load.
- Title “Welcome to LADO”. Text “LADO runs a team of AI agents for you: you describe a task,
  they plan it, do the work, and ask you when a decision is yours. ¶ The agents need access
  to an AI model: a subscription or a key you already have. This guide shows where to connect
  it.” Buttons “Show me”, “Not now”. Note “You can open the guide again from Help.”

**`open-menu`** · phone only · target `rail-menu`
- When: the next step's target is in the closed drawer. Done: the drawer is open.
- Title “Open the menu”. Text “**Settings**, where models are connected, is in the menu.”
  Waiting “Waiting for you to open the menu”.

**`open-settings`** · target `rail-settings`
- When: no model connected; no Settings page open. Done: a Settings page is open.
- Title “Open Settings”. Text “AI models are connected in Settings.” Waiting “Waiting for you
  to open Settings”.

**`open-agent-clis`** · target `agent-clis-link`
- When: no model connected; a Settings page other than Agent CLIs and Model servers is open
  (Settings opens on General; on a phone on its list), and a provider with texts is installed.
- Done: Agent CLIs is open.
- Title “Open Agent CLIs”. Text “Here LADO's agents log in with a subscription you may already
  have, such as Claude or ChatGPT.” Waiting “Waiting for you to open Agent CLIs”.

**`cli-login-claude`** · target `cli-row-claude`
- When: Agent CLIs open; Claude Code installed, not logged in, not passed.
- Done: Claude Code logged in (the part is done). The link → the next row.
- Title “Claude Pro or Max, or an Anthropic API key?”. Text “If you have either, press
  **Log in…** on this row. The window that opens asks which one you have and what to paste.”
  Link “I have neither”. Waiting “Waiting for the login”.

**`cli-login-codex`** · target `cli-row-codex`
- When: Agent CLIs open; Codex CLI installed, not logged in, not passed; Claude Code passed or
  not installed.
- Done: Codex CLI logged in. The link → the Model servers step.
- Title “A ChatGPT plan, or an OpenAI API key?”. Text “A paid ChatGPT plan (Plus, Pro,
  Business or Enterprise) or a key from platform.openai.com: if you have one, press
  **Log in…** on this row. With a plan you sign in by a one-time code, no terminal needed.”
  Link “I have neither”. Waiting “Waiting for the login”.

**`login-claude-choice`** · target `login-sheet`, anchor `login-choices`
- When: Claude Code's login window open; no choice clicked yet.
- Done: a choice is clicked, or its field gets the focus.
- Title “Which one do you have?”. Text “**Subscription** if you pay for Claude Pro or Max.
  **Pay per use** if you have an API key from console.anthropic.com. Choose yours here.”
  Waiting “Waiting for your choice”.

**`login-claude-token`** · target `login-sheet`, anchor `login-secret`
- When: Claude Code's window, Subscription chosen.
- Done: Claude Code logged in. Closing the window without it → the Codex row.
- Title “Make a token with Claude Code”. Text “On a computer with Claude Code installed, open
  a terminal, type `claude setup-token` and sign in. Paste the token it prints
  (sk-ant-oat01-…) here and press **Save**. ¶ No such computer? Close this window: the next
  row signs in without a terminal.” Waiting “Waiting for the token”.

**`login-claude-key`** · target `login-sheet`, anchor `login-secret`
- When: Claude Code's window, Pay per use chosen. Done: Claude Code logged in.
- Title “Paste your API key”. Text “Make one at console.anthropic.com, under API keys. It
  starts with sk-ant-api03-. Paste it here and press **Save**.” Waiting “Waiting for the key”.

**`login-paste`** · target `login-sheet`, anchor `login-secret` (critique F12)
- When: any CLI's login window with a chosen choice that is a field to paste into
  (`login-secret` visible) and no step of its own (Codex's Pay per use and access token
  today, any later CLI's). Done: that CLI logged in.
- Title “Paste it and press Save”. Text “The line above the field says where this comes from.
  Copy the whole value, paste it here and press **Save**.” Waiting “Waiting for the value”.

**`login-refused`** · target `login-sheet`, anchor `login-refusal`
- When: a CLI's login window shows a refusal of the value.
- Done: the refusal is gone (a new Save, another choice) → the chosen box's step.
- Title “That didn't work yet”. Text “The red line says what is wrong and which choice to use.
  Copy the whole value again, with nothing before or after it, and press **Save**.” Waiting
  “Waiting for a value that works”.

**`login-codex-code`** · target `login-sheet`, anchor `login-action`
- When: Codex CLI's window, the ChatGPT plan chosen.
- Done: Codex CLI logged in (the window closes by itself). While the code window shows, the
  guide waits behind it. After its Back, this step shows again.
- Title “Sign in with a one-time code”. Text “Press **Get a sign-in code**, open the link it
  shows on any device, sign in to ChatGPT and type the code. ¶ An OpenAI API key instead?
  Choose **Pay per use**.” Waiting “Waiting for the sign-in”.

**`model-server-open`** · target `model-servers-link` (the first visible: the Settings list's
item, or the sentence on Agent CLIs)
- When: no model connected; every CLI row with texts passed, or none installed.
- Done: Model servers is open.
- Title “An OpenRouter key, or a model on your computer?”. Text “With a key from OpenRouter,
  Qwen (Alibaba Cloud) or another OpenAI-compatible service, or a model running on your
  computer (Ollama, LM Studio), open **Model servers**.” Link “I have none of these — what
  should I choose?”. Waiting “Waiting for you to open Model servers”.

**`none-of-these`** · centred
- When: the person pressed “I have none of these”.
- Done: Back → the step it came from. Not now → closed until the next page load.
- Title “Don't have any of these yet?”. Text “The simplest way is a monthly plan: Claude Pro,
  or a paid ChatGPT plan such as Plus. With an API key from Anthropic, OpenAI, OpenRouter or
  Qwen (Alibaba Cloud) you pay for what the agents use instead. ¶ A plan, or an Anthropic or
  OpenAI key, goes in **Agent CLIs** (Log in…); an OpenRouter or Qwen key goes in **Model
  servers**. Get one, come back, and the guide goes on from here.”
- Links, each opening a new tab: “Claude plans ↗” `https://claude.com/pricing`, “ChatGPT
  plans ↗” `https://chatgpt.com/pricing`, “OpenRouter keys ↗” `https://openrouter.ai/keys`,
  “Qwen (Alibaba Cloud) keys ↗”
  `https://www.alibabacloud.com/help/en/model-studio/get-api-key`.
- A muted line under the links: “Not sure what any of this means? Ask your company's IT team,
  or someone who knows.”
- Buttons “Back”, “Not now”.

**`model-server-add`** · target `model-server-add`
- When: Model servers open, no server, the add form closed. Done: the add form is open.
- Title “Add your server”. Text “Press **Add server**. You give it a name, its address and your
  key, and LADO checks that its models answer.” Waiting “Waiting for you to press Add server”.

**`model-server-form`** · target `model-server-form`
- When: the add form is open, no refusal shown. Done: a model server is saved.
- Title “Name, address and key”. Text “Give it any name, paste the address and the key from the
  service's site, then press **Add server**. A model on your own computer usually needs no
  key.” Waiting “Waiting for the server to be added”.

**`model-server-error`** · target `model-server-form`, anchor `model-server-error`
- When: the form shows the server's refusal of the key (401/403).
- Done: the refusal gone → the form step, or on.
- Title “The key wasn't accepted”. Text “The service refused this key. Copy it again from the
  service's site, the whole key with no spaces, paste it and press **Check key**.” Waiting
  “Waiting for a key that works”.
- Variant for an unreachable address (same id's texts keyed by the refusal): title “LADO
  can't reach this address”; text “Check the address against the service's instructions. For
  a model on your own computer, make sure its app is running.”

**`settings-back`** · phone only · target `settings-back`
- When: the next step's target is on the Settings list and a section page is open.
- Done line “✓ Model connected”. Eyebrow “Sign your work · Step 2 of 3”. Title “Back to
  Settings”. Text “One more setting, in **Git servers**.” Waiting “Waiting for you to go back”.

**`open-git-servers`** · target `git-servers-link`
- When: a model connected; nobody signs commits; Git servers not open.
- Done line “✓ Model connected”. Eyebrow “Sign your work · Step 2 of 3”. Title “Sign the
  agents' work”. Text “Agents save each step of their work under a name and email, so a
  project's history shows who did what. Open **Git servers** to set yours.” Waiting “Waiting
  for you to open Git servers”.

**`author-set`** · target `author-row`
- When: Git servers open; nobody signs commits; the author form closed.
- Title “Who signs the work?”. Text “Nobody is set yet, so the agents can't save their work.
  Press **Set author** and enter your name and email.” Waiting “Waiting for you to press Set
  author”.

**`author-form`** · target `author-form`
- When: the author form is open. Done: an author is in effect.
- Title “Your name and email”. Text “They are written into the history of each project the
  agents change. A work email is fine. Then press **Save author**.” Waiting “Waiting for the
  author to be saved”.

**`open-menu-new`** · phone only · target `rail-menu`
- When: the step before New session, the drawer closed.
- Done line “✓ Your work will be signed”. Eyebrow “Start working · Step 3 of 3”. Title “Open
  the menu”. Text “**New session** is in the menu.” Waiting “Waiting for you to open the menu”.

**`new-session`** · target `rail-new-session`
- When: a model connected and an author in effect.
- Done: the New session window opens → the guide is completed.
- Done line “✓ Your work will be signed”. Eyebrow “Start working · Step 3 of 3”. Title “Start
  your first session”. Text “Press **New session** and describe a task in your own words.
  The team takes it from there, and short tips explain what you see.” Waiting “Waiting for
  you to open New session”.

The done line shows only when the part before was done during this run of the guide; the
step counter always counts the three parts.

### Tips

| id | Target | When (first time) | Prefer | Text |
|---|---|---|---|---|
| `tip-launch` | `launch-task` | the New session window is open | | “Describe the task here in your own words. Above, choose where the team works; below, which team and model take it. The small i beside a field explains it.” |
| `tip-session` | `session-tabs` | a session's page is open | below, right | “This is your session. **Activity** shows what the team does, and you write to its lead in the field at the bottom; the other tabs show the agents, the steps and the documents.” |
| `tip-gate` | `gate-card` | a gate is on screen in the waiting card | above, left, right, below | “The team waits for your decision. Read the note and its documents, then press a button; a comment for the next step is optional.” |
| `tip-question` | `question-card` | an agent's question is on screen in the waiting card | above, left, right, below | “An agent asks you something. Press one of its answers, or write your own in your words.” |
| `tip-terminal` | `terminal-panel` | an agent's terminal is on screen | | “This is the agent's own window. You can watch it work; you don't have to type anything here.” |

Each tip has “Got it” and “Don't show tips like this”.

## 7. Markers

`data-guide="<name>"` on existing elements; the same name on two elements means the first
visible one.

| Marker | Element |
|---|---|
| `rail-menu` | the phone top bar's Menu (☰) button |
| `rail-settings`, `rail-new-session` | the rail's / drawer's Settings and New session |
| `help-getting-started` | the Help menu's Getting started line |
| `agent-clis-link`, `git-servers-link` | the Settings list's Agent CLIs and Git servers items (wide and phone list) |
| `model-servers-link` | the Settings list's Model servers item **and** the sentence linking Model servers on Agent CLIs |
| `settings-back` | the phone's `‹ Settings` link |
| `cli-row-<cli>` | each row of Agent CLIs (`li.srow`), one per provider |
| `login-sheet` | the login window's box (`.login-window`), with `data-guide-cli="<provider>"` |
| `login-choices` | its list of choices (`.login-help`) |
| (attribute) `data-guide-choice="<id>"` | the chosen choice's box (`.login-chosen`) |
| `login-secret` | the chosen box's field and Save (`.login-send`) |
| `login-action` | the chosen box's action button (Codex: Get a sign-in code) |
| `login-refusal` | the refusal line under the choices |
| `model-server-add` | Model servers' Add server button |
| `model-server-form` | its add form |
| `model-server-error` | the form's refusal line, with `data-guide-refusal="key"` or `"unreachable"` |
| `author-row` | LADO's author row on Git servers |
| `author-form` | the author form |
| `launch-task` | the New session window's Task field |
| `session-tabs` | the session page's tabs |
| `gate-card`, `question-card` | the waiting card with that tab current |
| `terminal-panel` | the terminals panel; on a phone the full-screen terminal |

Stage 2's markers are added with stage 2.

## 8. Look

Tokens (in `tokens.css`, both added): `--guide-dim: light-dark(#16181d99, #000000b3)`,
`--guide-ring: var(--action)`. No orange (`--human` stays the team's request).

- **Card (guiding)**: `--panel`, 1 px `--line`, radius 8 px, shadow `0 12px 32px var(--shadow)`,
  padding 14/16/12 px, width 320 px (centred 400 px, padding 20/22/16 px), `--sans` 14/1.45.
  Content in order, each optional: done line (13 px/600 `--done`), eyebrow (12 px/600,
  uppercase, 0.04 em, `--muted`), title (an `h2`, 15 px/600; centred 18 px), body (one or two
  paragraphs; `<b>` names a control by its exact visible name; `code` in `--mono` on
  `--raised`), links (buttons styled as links, `--action`, underlined, at least 28 px high),
  a muted help line (none-of-these only, 13 px `--muted`), footer.
- **Footer**: the waiting line (12.5 px `--muted`, an 8 px `--action` dot that pulses three
  times, 1.6 s each, then stays solid; no pulse under reduced motion), then **Not now** on the
  right (a quiet text button, `--muted`, `--ink` and underline on hover). Centred cards:
  buttons, the first primary (`--action`/`--on-action`, 32 px, 600), the others secondary
  (`--panel`, 1 px `--line`; hover `--raised`).
- States: hover as above; focus-visible a 2 px `--action` outline 2 px out on every control;
  no disabled state.
- **Tip**: the same card, 296 px, padding 12/14/10 px, body 13.5 px, no title, no eyebrow;
  footer **Got it** (primary, 28 px, 13 px) and **Don't show tips like this** (quiet).
- Motion: a 120 ms opacity fade of the card; the hole does not glide; none under reduced
  motion.
- Layer `position: fixed; z-index: 1000`; inside a modal dialog `popover="manual"`.
- **Help → Getting started**: an item of the Help menu above Report a bug, in Report a bug's
  group (after the divider), a compass icon in the menu's 16 px stroke style. It closes the
  menu (and the phone drawer) and runs §2.7.
- The guide's CSS is a "Guide" section of `styles.css`, in its naming.

## 9. Phone and touch

- Card and tip buttons 44 px high, links at least 44 px of hit height; footer buttons share
  the width; the waiting line on its own line.
- Rail targets are preceded by `open-menu` (☰); the drawer opens over its own dim and the
  guide's hole is cut in it.
- A Settings section page is preceded by `settings-back` when the next target is on the
  Settings list.
- The full-screen terminal: the tip goes on its lower part and leaves its bar with Close
  visible.
- The login sheet fills the phone: placement rule 7.

## 10. Accessibility

- **Guiding card**: `role="dialog"`, `aria-labelledby` its title, `aria-describedby` its body.
  Centred cards `aria-modal="true"`, focus kept inside. Cards with a target
  `aria-modal="false"`; Tab cycles through the card's controls and the target's focusable
  elements only. A visually hidden line in the description names the spotlighted element:
  “Highlighted: <the target's accessible name>”.
- **The dimmed page is inert**: while a guiding step with a dim shows, every sibling along the
  path from `<body>` to the hole's element gets `inert`, except the guide's layer; a centred
  card makes everything but the layer inert. A step whose window draws the dim relies on that
  window's modality. Tips and phone steps without a dim make nothing inert. The guide removes
  every `inert` it set when the step ends or hides.
- **Focus**: a guiding card takes the focus when it appears (centred: its first button;
  others: the card, `tabindex=-1`). When the guide closes, the focus returns to where it was,
  else to the target, else to the page's `h2`. A step completed by the person's action leaves
  the focus where the action left it; the next card does not take it while a window the
  person opened is open.
- **Esc**: in the card = Not now. In an app window, the window's Esc runs first.
- **Waiting line**: `role="status"`.
- **Tips** take no focus; each is announced once through a polite live region (“Tip: …”),
  `role="region"`, `aria-label="Tip"`; Tab on the target goes to Got it, Shift+Tab back; Esc
  in the tip or on the target = Got it.
- Contrast: existing token pairs only (body 17.8:1 / 14.3:1, muted 6.1:1 / 6.6:1, links
  5.7:1 / 6.7:1, done 5.3:1 / 8.4:1, primary label 5.7:1 / 7.2:1, ring inside the hole 5.7:1 /
  6.7:1).

## 11. Server and data

- The guide's record: `LADO_HOME/guide.json`, `{"completed": bool, "shown": [ids],
  "tips_off": bool}` (D1).
- `GET /api/guide` → `GuideInfo` (D2): `auto` (false under `LADO_GUIDE=0`), `completed`, `shown`, `tips_off`,
  `telemetry_asked`, and while not completed `facts`: `{model: bool | null, author: bool}`
  (`model` null when the first login check has not ended within 20 s). With no record, the
  server creates it once `model` is known (D3).
- `POST /api/guide` with `{action, ids?, marker?}` → `GuideInfo`; actions `shown` (ids added),
  `complete`, `tips_off`, `restart` (completed false, tips on), `missing` (id and marker to
  the error journal).
- Live facts on the Settings pages come from those pages' own loads (D4).

## 12. Docs

- `docs/design/ui.md`: a section "First-run guide (decided 2026-11-25, LAD-311)": the two
  kinds, when they show, the layer and placement rules in short, the record and endpoints, the
  test switch, and **a pointer to `web/src/guide/hints.ts` instead of a list of hints**; the
  Help section gets Getting started; the review rule (a moved marker) points to `.lado/sdlc.md`.
- `docs/design/modules.md`: `guide.py`; `server/app.py`'s two routes.
- `docs/install.md`: `LADO_GUIDE=0`, beside `LADO_NO_UPDATE_CHECK=1`.
- `docs/testing.md`: `LADO_GUIDE=0` in every test, the guide's own UI e2e test.
- `AGENTS.md` Layout: one line for `guide.py`.
- `CHANGELOG.md` under `## 0.49.0 (unreleased)`, New: a getting-started guide line.

## 13. The manual check

On a fresh `LADO_HOME` with no login, no model server and no commit author
(`GIT_CONFIG_GLOBAL=/dev/null`), `uv run lado ui`: answer the statistics question, follow the
guide to the New session window without reading docs, light and dark, at 390, 768 and 1440 px.
Then restart with a model connected and a new `LADO_HOME`: no welcome.
