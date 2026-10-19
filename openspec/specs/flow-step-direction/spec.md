# flow-step-direction Specification

## Purpose
How the web UI shows a flow step's direction: forward or back by the order the run's flow
declares its states, the same in a session's chat and in the Flows tab, with a return
icon on a step back and a tooltip that says where the step goes (docs/design/ui.md, Flow
events, Flows).

## Requirements

### Requirement: A flow step's direction follows the order its flow declares

The web UI SHALL show a flow step (a move of a run from one state to another, with its
outcome) as going back when the state it leads to is declared in the run's flow no later
than the state it left, a step that stays in its state included, and as going forward
otherwise. The session's chat and the Flows tab SHALL decide it by this one rule, from the
run's flow (`RunInfo.states`) alone, never from which other steps are loaded.

#### Scenario: Ready again after changes
- **WHEN** a run of a flow declaring `design, design_ok, build, review, merge_ok, merge,
  done` moves `build → review` (`ready`), `review → build` (`changes`) and `build →
  review` (`ready`)
- **THEN** in the chat and in the Flows tab both `ready` are forward and `changes` is back

#### Scenario: Earlier pages load
- **WHEN** the chat shows a run's `build → review` step and loads an earlier page holding
  that run's earlier steps
- **THEN** the step's direction stays what it was

#### Scenario: A step stays in its state
- **WHEN** a run moves `review → review`
- **THEN** the step is back

### Requirement: A step of a run whose flow is not known has no direction

When the
run's flow is not known (the run is not loaded, its flow cannot be read, or a state is not
in it), the chat SHALL show the step's outcome as neither forward nor back.

#### Scenario: The flow cannot be read
- **WHEN** a run's flow snapshot cannot be read and the chat shows one of its steps
- **THEN** the step's outcome is neither forward nor back: no colour of either, no icon
  and no tooltip

### Requirement: A step back is orange with a return icon

The web UI SHALL show a forward step's outcome green with no icon and a step back's
outcome orange with a return icon before it, in the session's chat and in the Flows tab
alike, and SHALL say the direction to assistive technology with the outcome (`<outcome>,
a step back` / `<outcome>, a step forward`).

#### Scenario: Changes sends the work back
- **WHEN** a reviewer's step `review → build` with outcome `changes` is shown in the chat
  and in the Flows tab
- **THEN** both show `changes` orange with the return icon, and a screen reader reads it
  as `changes, a step back`

### Requirement: A step's outcome explains its direction in the UI's tooltip

Hovering a forward or back step's outcome, in the chat and in the Flows tab, SHALL show
the UI's own tooltip (not the browser's `title`). For a forward step it SHALL say
`Forward in the flow, to <to>`. It SHALL NOT show the whole flow.

#### Scenario: Forward to review
- **WHEN** the human hovers the outcome of `build → review` (`ready`)
- **THEN** the tooltip says `Forward in the flow, to review` and nothing more

### Requirement: A step back's tooltip names the states that run again

For a step back the tooltip SHALL say `Back: the work returns to
<to>` and, when the flow has a way from `<to>` to the state the step left, a second line
`Runs again: <state> › … › <state>`: the shortest way through the flow's outcomes from
`<to>` to the state left, both included, ties broken by the flow's declared order.

#### Scenario: Back from review
- **WHEN** the human hovers the outcome of `review → build` (`changes`) in the sdlc task
  flow
- **THEN** the tooltip says `Back: the work returns to build` and `Runs again: build ›
  review`

#### Scenario: A branched flow
- **WHEN** a flow declares `triage, design, design_ok, build, fix, review, done`, where
  `triage` leads to `design` or `fix`, `build` and `fix` lead to `review`, and `review`
  leads back to `build` or `fix`, and the human hovers `review → fix`
- **THEN** the tooltip's second line is `Runs again: fix › review`, one line

#### Scenario: No way back to the state left
- **WHEN** a step goes back to a state from which no way through the flow leads to the
  state it left
- **THEN** the tooltip has only its first line
