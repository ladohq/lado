## Purpose

The web UI's first-run guide: guiding steps that lead a person on a fresh LADO to connect a model,
set the commit author and open New session, one-time tips at first encounters, the marks the
server keeps, the restart from Help, and the rules that keep its hints in step with the UI.

## ADDED Requirements

### Requirement: The guide starts on a LADO with no model

The web UI SHALL show the guide's centred welcome on a page load while the guide is not completed, the statistics question needs no answer, no window is open and no model is connected (no agent CLI logged in, no model server saved). When the guide's record is first made and a model is connected, it SHALL be made completed and nothing SHALL show.

#### Scenario: A fresh LADO
- **WHEN** a person opens the UI of a LADO with no login and no model server and answers the statistics question
- **THEN** the welcome "Welcome to LADO" shows in the middle with Show me and Not now

#### Scenario: An updated LADO that is set up
- **WHEN** the UI of a LADO with a logged-in agent CLI is opened for the first time after the update
- **THEN** no welcome shows, and the guide's record says completed

#### Scenario: The statistics question first
- **WHEN** the statistics banner still asks
- **THEN** the welcome waits until it is answered

### Requirement: Guiding steps wait for the real action

A guiding step SHALL dim the page, cut out and ring its target, let presses inside the cut-out reach the page, block presses outside it without closing the guide, and SHALL move on only when the person's action makes its completion true. Besides the centred cards' buttons, only a step's link saying the person lacks what it asks for (I have neither, I have none of these) SHALL move the guide on.

#### Scenario: Open Settings
- **WHEN** the step "Open Settings" shows and the person presses the rail's Settings
- **THEN** Settings opens and the next step shows by itself

#### Scenario: A press on the dim
- **WHEN** the person presses the dimmed page outside the cut-out
- **THEN** nothing happens and the step stays

### Requirement: The main path connects a model, then an author, then New session

The main guide SHALL lead through three parts in order: connect a model (Agent CLIs' rows of the providers the guide has texts for, their login windows, then Model servers' Add server and its form), sign your work (Git servers' Set author and its form, only while nobody signs commits), start working (New session). A part done in the system SHALL be skipped and the step counter recounted.

#### Scenario: An author already in effect
- **WHEN** a model gets connected and git's own author is set
- **THEN** the next step is New session, counted "Step 2 of 2"

#### Scenario: A provider without texts
- **WHEN** only a CLI the guide has no texts for is installed
- **THEN** no row or login step shows for it, and the path goes to Model servers

### Requirement: Login window steps

While a CLI's login window is open on the main path, the guide SHALL stay and point inside it: at its choices until one is picked; at the chosen box's field and Save (Claude Code's token or key step, else the generic "Paste it and press Save"); at Codex CLI's Get a sign-in code; at a refusal line while it shows. The guide SHALL hide while a window opened from it is on top.

#### Scenario: Codex CLI's Pay per use
- **WHEN** the person chooses Pay per use in Codex CLI's login window
- **THEN** the step "Paste it and press Save" points at the field and Save

#### Scenario: A refused value
- **WHEN** the login window shows a refusal of the pasted value
- **THEN** the step "That didn't work yet" points at the refusal line

#### Scenario: Passing a row
- **WHEN** the person presses "I have neither" on Claude Code's row
- **THEN** Codex CLI's row is the next step, or Model servers when Codex CLI is not installed

### Requirement: A card for a person with no subscription and no key

Model servers' step SHALL offer "I have none of these — what should I choose?", which SHALL open a centred card that says where a plan or each kind of key goes, links Claude plans, ChatGPT plans, OpenRouter keys and Qwen (Alibaba Cloud) keys in a new tab, says to ask the company's IT team or someone who knows when unsure, and has Back and Not now.

#### Scenario: Back
- **WHEN** the person presses Back on the card
- **THEN** the Model servers step shows again

### Requirement: New session completes the guide

The main guide SHALL be marked completed when the New session window opens while it is not completed, whichever step shows.

#### Scenario: The last step
- **WHEN** the step "Start your first session" shows and the person presses New session
- **THEN** the guide is completed, and the New session window's tip shows

### Requirement: Not now closes the guide until the next page load

Not now, and Esc with the focus in a guiding card, SHALL close the main guide for the rest of the page load; on the next page load it SHALL start again, at the first step not done, until it is completed.

#### Scenario: Reload after Not now
- **WHEN** the person presses Not now and later reloads the page with no model connected
- **THEN** the welcome shows again

### Requirement: Tips show once and never over the guide

A tip SHALL show only while no guiding step shows, tips are on, its condition holds and it was never shown; at most one tip SHALL show at a time. A hint SHALL be marked shown as soon as it appears. Got it SHALL close the tip; Don't show tips like this SHALL close it and turn every tip off. Stage 1's tips SHALL be: the New session window, the session page, a gate, an agent's question, an agent's terminal.

#### Scenario: Once
- **WHEN** the session page's tip was shown and the person opens another session
- **THEN** no tip about the session page shows

#### Scenario: Tips off
- **WHEN** the person presses Don't show tips like this
- **THEN** no further tip shows in any browser until Help → Getting started

### Requirement: The guide's marks are kept by the server

LADO SHALL keep whether the guide is completed, the ids of the hints shown and whether tips are off in `LADO_HOME/guide.json`, read by `GET /api/guide` and changed by `POST /api/guide`, so that every browser of the LADO sees the same marks. Marks of two tabs SHALL both be kept.

#### Scenario: Another browser
- **WHEN** the person completed the guide in one browser and opens LADO in another
- **THEN** no guide shows there

### Requirement: Help restarts the guide

Help → Getting started SHALL turn tips back on, mark the guide not completed and start it at the welcome at once, even when a model is connected; steps done in the system SHALL be skipped and tips already shown SHALL stay shown.

#### Scenario: Restart on a set-up LADO
- **WHEN** the person with a model and an author chooses Help → Getting started
- **THEN** the welcome shows, and Show me leads straight to New session

### Requirement: The guide costs nothing once done

The web UI SHALL read the guide's record once per page load and SHALL load the guide's engine only while the guide is not completed or a tip is left to show with tips on. While the main guide is not completed, the record's answer SHALL carry whether a model is connected and an author is in effect; on Agent CLIs, Model servers and Git servers the guide SHALL use what those pages loaded, with no request of its own.

#### Scenario: Done
- **WHEN** the guide is completed and every tip was shown
- **THEN** a page load makes one request for the guide and loads none of its engine

### Requirement: Hints are data aimed at markers

Every hint SHALL be data in one file of the web UI (id, kind, target, condition, completion, texts) whose targets are `data-guide` markers on existing elements; a unit test SHALL fail when a target is not in the UI's code, a condition is unknown, an id repeats or a text is empty. A hint whose marker is not on screen within 2 s while its condition holds SHALL be skipped for the page load and written to LADO's error journal.

#### Scenario: A lost marker in the code
- **WHEN** a change removes the element marked `model-server-add`
- **THEN** the guide's unit test fails naming the hint and the marker

#### Scenario: A lost marker at run time
- **WHEN** a hint's condition holds and its marker is not visible for 2 s
- **THEN** the hint is skipped and `errors.jsonl` gets an entry with its id and marker

### Requirement: LADO_GUIDE=0 keeps the guide from starting by itself

With `LADO_GUIDE=0` in the environment of LADO's server, the guide SHALL neither start nor show a tip by itself and the UI SHALL load none of its engine; Help → Getting started SHALL still start it for that page load. It is for recording videos on a live LADO, and every test but the guide's own UI e2e test SHALL run with it.

#### Scenario: Recording a video
- **WHEN** LADO's server runs with `LADO_GUIDE=0` on a fresh LADO
- **THEN** no welcome and no tip shows, and Help still lists Getting started

#### Scenario: Getting started under the switch
- **WHEN** the person chooses Help → Getting started with `LADO_GUIDE=0`
- **THEN** the welcome shows; after a reload nothing starts by itself

#### Scenario: A UI e2e test
- **WHEN** any UI e2e test but the guide's opens the UI
- **THEN** no guide card or tip shows

### Requirement: A hint stands beside its target

A card SHALL stand beside its target (a phone: below or above), clear of target and anchor, where that fits; a tip first where it covers no control outside its target. Failing that, a tip SHALL take the nearest free place and ring its target dashed, else a tall target's lower part, else its side over controls; a guiding card SHALL cut out only its anchor, else take the bottom edge. A login window filling a phone SHALL get no dim, its anchor ringed, the card at the bottom.

#### Scenario: A phone
- **WHEN** the step "Open Settings" shows at 390 px wide
- **THEN** the step "Open the menu" rings ☰ first, and its card is below it

### Requirement: The guide works by keyboard and screen reader

A guiding card SHALL be a dialog named by its title that takes the focus, names the highlighted element, keeps Tab within itself and its target, and makes the dimmed page inert; Esc SHALL be Not now; the focus SHALL return where it was when the guide closes. A tip SHALL take no focus, be announced once, and be reachable by Tab from its target. Under reduced motion nothing SHALL move.

#### Scenario: Esc
- **WHEN** a guiding card has the focus and the person presses Esc
- **THEN** the guide closes and the focus returns to the element it was on
