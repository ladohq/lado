# Small fixes of the session's screen (LAD-198)

Change: `openspec/changes/session-screen-polish/` (proposal with AC-1..AC-16, new capabilities
`artifacts-list`, `flows-overview`, `notices`, deltas of `artifact-panel`, `session-forget`,
`launch-notes`, `session-layout`, `design.md` with D1-D18). This document is the human's view. Source
of the look: LAD-189 spec §7, group 7 of `lad-189-mockup.html`, run artifact
`mockup-session-tweaks.html`.

## What a user gets

    Find an artifact        [All scopes ▾]
    ▾ task/lad-198                               14
      [doc] design · The change as approved
            Document · analyst · 4 min ago · 18.2 KB
    ▾ Session                                     9
    ▸ task/lad-196                               31

A session of 115 artifacts fits on a screen: open work in sight, finished runs folded. The panel says
a title once. Empty tabs say where their content comes from. A run says what it is about.

## Sizes

| Part | Size |
|---|---|
| List row | 48 px; tile as today; line 1 13/18, the name mono 600; line 2 12/16 `--muted` |
| List, table limit | the tab's width: list under 720 px, table from 720 px |
| Group heading | `.group-head`, neutral; a run's name mono, no capitals, count at the right |
| Groups from | 100 artifacts of the session |
| Run's task line | 13 px `--muted`, one line, "…" |
| "Step took" | 13 px `--muted`, no frame |
| Stop's line | 13 px `--muted`, below the buttons |
| Notice | padding 8 12 (tight rows 4 8), radius 6, icon 16 px, no border |

## Words

| Where | Text |
|---|---|
| Row's type | Document, Code or text, Image, HTML, File |
| Group | Session, or the run's name |
| Pill | session, step <name> |
| Panel link | Open in Artifacts tab; on the Artifacts tab, Full page |
| Phone's button | More actions (its accessible name), shown as ⋯ |
| Artifacts, empty | No artifacts yet / Agents save plans, reviews, images and mockups here (write_artifact). |
| Flows, empty | No flow runs yet / Runs appear when the supervisor starts a flow of the session's kits: sdlc: task, epic. |
| Flows, no flows | No flow runs yet / This session's kits have no flows, so no runs will appear here. |
| Flows, kits unknown | No flow runs yet / Runs appear when the supervisor starts a flow of the session's kits. |
| Event | Step took 12 min |
| Stop | It has open runs, so it can be forgotten only from the Stopped list after stopping. |

## Width by width

| Window | Artifacts | Panel |
|---|---|---|
| 1440, terminals folded | table, groups from 100 | labelled buttons |
| 1440, terminals open | list | labelled buttons |
| 1024 | list or table by the column | labelled buttons, icons under 560 px |
| 768 | list or table by the column | icons under 560 px |
| 390 | list | Download, Copy link, ⋯, × |

## Where this departs from the spec, and why

- List under 720 px, not 600: the table does not fit between them (answer 1).
- Groups at any width, not only narrow: the list keeps its shape when the terminals open (answer 2).
- The group's heading is the session list's band, not the mini block's quiet line: the spec's text.
- Full page keeps the document icon, not ⤢: ⤢ is Expand in the same bar.
- Copy link stands for "Share": the system's share sheet needs https (answer 5).
- "⋯" only on a phone: the mini block shows it, the spec's text and the block's note say phone.
