# lead-recommendation Specification

## Purpose
The lead's own recommendation on each question to the human: LADO asks the session's lead
for its view whenever a flow gate opens or another agent asks the human, the lead gives it
with the MCP tool `recommend`, and it is stored with the gate or question and shown as part
of its card in the UI and in `lado answer`, never as a separate message.

## Requirements

### Requirement: LADO asks the lead for a recommendation on each question to the human

When a flow gate opens (an approval gate, a choice gate or a loop limit) or an agent other
than the session's lead asks the human with `ask_human`, LADO SHALL ask the lead for its
recommendation, if the lead runs: one message from `lado` to the lead, or, when the lead's
own `flow_advance` opened the gate, one notice in that tool's result. The gate's or
question's recommendation SHALL then be `asked`. The lead's own questions SHALL get
no request.

#### Scenario: The lead's own step leads to a gate
- **WHEN** the lead's `flow_advance` moves its run into a gate
- **THEN** the tool's result has the request in its `notices`, and no message about it is
  queued

#### Scenario: The lead asks the human
- **WHEN** the lead calls `ask_human`
- **THEN** no request is queued and the question has no recommendation

#### Scenario: The lead does not run
- **WHEN** a gate opens while the session's lead is not running
- **THEN** the gate opens as before and has no recommendation

### Requirement: The request names the gate or question with what the lead needs

The request for a recommendation SHALL
name the gate or question by its id, give its question, its options or choices, the note
that led to the gate (or the question's details) and the artifacts the gate reads, carry
the note's or the question's attachments, and say that only the human answers. The lead
SHALL NOT get the line "waiting for the human at <state> (gate #N)" any more.

#### Scenario: A worker's step leads to a gate
- **WHEN** the reviewer reports `approved` and the run enters the approval gate #7
- **THEN** the lead gets one message from `lado` whose summary names gate #7, the run and
  the state, whose body holds the question, the options and the reviewer's note, and which
  carries the note's artifacts; gate #7's recommendation is `asked`

#### Scenario: A worker asks the human
- **WHEN** the developer calls `ask_human` and it becomes question #12
- **THEN** the lead gets one request for question #12, with its details, its choices and
  its attachments

### Requirement: The lead gives its recommendation with the tool recommend

The lead SHALL have an MCP tool `recommend(text, gate, question, choice, disagrees)` that
stores its recommendation on an open gate or an open question of its session, given by
exactly one of `gate` and `question`.

#### Scenario: A recommendation on a question
- **WHEN** the lead calls `recommend(question=12, text="Later")` while question #12 is open
- **THEN** question #12's recommendation is `given` with that text and no choice

### Requirement: A recommendation holds its text, its option, its disagreement and its time

The recommendation `recommend` stores SHALL hold the text (Markdown, not empty, at most a message's
limit), the option it recommends if any (one of the gate's options, in any case an
approval gate's outcomes too, or one of the question's choices), whether it disagrees with
the agent whose report led to the gate or who asks, and the time.

#### Scenario: The lead recommends
- **WHEN** the lead calls `recommend(gate=7, text="Reject: no test of the turn end",
  choice="reject", disagrees=true)`
- **THEN** gate #7's recommendation is `given` with that text, the choice `reject`,
  disagrees set and the time

### Requirement: Only the lead recommends, and its later call replaces the earlier

A later call of `recommend` SHALL
replace the earlier recommendation. Only the lead SHALL
have the tool; a read-only lead has it too.

#### Scenario: The lead changes its mind
- **WHEN** the lead calls `recommend(gate=7, text="Approve", choice="approve")` while gate
  #7 is still open
- **THEN** gate #7's recommendation is that text and choice, with disagrees not set

#### Scenario: A worker has no such tool
- **WHEN** a worker lists its MCP tools
- **THEN** `recommend` is not among them

### Requirement: recommend refuses what it cannot store

The tool `recommend` SHALL refuse, with nothing changed, a gate or
question that is closed (naming how it was closed), unknown or of another session, a
choice that is no option, a choice for a question without choices, both or neither of
`gate` and `question`, an empty text, and the lead's own question.

#### Scenario: Too late
- **WHEN** the human answered gate #7 and the lead then calls `recommend(gate=7, ...)`
- **THEN** the call is refused with "gate #7 is closed already: approve by human" and
  nothing changes

#### Scenario: Not an option
- **WHEN** the lead calls `recommend(question=12, text="…", choice="maybe")` and question
  #12's choices are "yes" and "later"
- **THEN** the call is refused and names the choices

### Requirement: A request that is not needed any more is dropped

When a gate or question closes (answered, dismissed, overridden by `lado flow-set`, its
run cancelled, closed by its agent's end) while its request is still pending in the
lead's queue, the request SHALL be dropped in the same transaction, so the lead never gets
it.

#### Scenario: The human answers first
- **WHEN** the lead is busy, gate #7's request waits in its queue, and the human answers
  gate #7
- **THEN** the request is `dropped` and the lead's next hand-over does not hold it

### Requirement: A recommendation not given is said so

When the lead's turn ends, every open gate or question of its session whose
recommendation is `asked` and whose request the lead got (handed over and confirmed, or in
a tool's result of that turn) SHALL become `missing`, unless LADO plans to resume the lead
after a temporary error.

#### Scenario: The lead's turn ends without it
- **WHEN** the lead read gate #7's request and its turn ends without `recommend`
- **THEN** gate #7's recommendation is `missing`

#### Scenario: A request not handed over yet
- **WHEN** the lead's turn ends while gate #8's request is still pending in its queue
- **THEN** gate #8's recommendation stays `asked`

#### Scenario: A temporary error
- **WHEN** the lead's turn ends on a temporary API error and LADO plans its resume
- **THEN** gate #7's recommendation stays `asked`

### Requirement: A missing recommendation can still come, and a resume asks again

When the lead ends, or the session is stopped, every `asked`
recommendation of the session SHALL become `missing`. A `recommend` call SHALL still
replace a `missing` recommendation while its gate or question is open. On a resume, the new
lead SHALL get a request for each open gate whose recommendation is not `given`.

#### Scenario: A resume asks again
- **WHEN** a session with open gates #7 (`given`) and #8 (`missing`) is stopped and
  resumed
- **THEN** the new lead gets a request for gate #8 only, and gate #8's recommendation is
  `asked`

### Requirement: The card shows the recommendation as part of the gate or question

The web UI SHALL show an open gate's or question's recommendation inside its card (in the
chat's waiting card, on Needs you and on a run's page in Flows), between the question's
text and the answer: under the supervisor's small avatar and "Supervisor's
recommendation", with its time, and "disagrees with <agent>" in orange when the lead
disagrees, the whole text as Markdown. The human SHALL be able to
answer in every state.

#### Scenario: A recommendation that disagrees
- **WHEN** gate #7's note says "ready to merge" and the lead recommends `reject` with
  disagrees set
- **THEN** the card shows the block with "disagrees with reviewer" in orange and the text,
  and Reject is the primary button, Approve quiet

### Requirement: On a gate the recommended option is the primary button

On a gate, when the recommendation names an option, that option's
button SHALL be the only primary one and the others quiet, with no other label; otherwise
the first option is primary as before.

#### Scenario: The primary button moves to the recommended option
- **WHEN** approval gate #9 shows Approve as its primary button while its recommendation
  is `asked`, and the lead then recommends `reject`, agreeing or disagreeing alike
- **THEN** Reject becomes the primary button and Approve a quiet one

### Requirement: On a question the recommended choice is picked ahead

On a question, in its tab of the waiting card,
whose choices are picks and whose primary button is Send, the recommended choice SHALL be
picked ahead when it is one of the question's choices, and SHALL count and be sent as any
pick; the human's own pick, also unpicking it, SHALL win, and a recommendation given later
SHALL pick its choice only in a question the human has not touched.

#### Scenario: A question's recommended choice is picked ahead
- **WHEN** w1 asks question #12 with the choices "yes" and "later", and the lead recommends
  "later"
- **THEN** w1's tab shows the block under the question and "later" picked, and Send sends
  "later" unless the human picks otherwise

#### Scenario: The human unpicks the recommended choice
- **WHEN** the human clicks the picked "later" of question #12
- **THEN** no choice of #12 is picked, and Send waits for the human's own answer

#### Scenario: A recommendation without a choice
- **WHEN** the lead recommends on question #13 with text only, or with a choice the
  question does not have
- **THEN** the tab shows the block and picks nothing

### Requirement: The card says when a recommendation is being prepared or missing

While the recommendation is `asked`
the card SHALL say "Supervisor is preparing a recommendation…", when `missing` "The
supervisor gave no recommendation", and with none nothing.

#### Scenario: Still preparing
- **WHEN** gate #8's recommendation is `asked`
- **THEN** the card says "Supervisor is preparing a recommendation…" and its buttons work

### Requirement: A closed card shows the recommendation in one line

A closed question's card SHALL show the recommendation as one quiet line,
"Supervisor recommended: <option>" or "Supervisor's recommendation" without an option,
whose text opens on a click; a closed gate's card SHALL show it as its folded line
"Supervisor", "recommended <option>" and whether the human's answer agreed, whose text
opens on a click (capability closed-gate-card).

#### Scenario: Closed
- **WHEN** the human answered question #12, for which the lead recommended "later"
- **THEN** the closed card shows "Supervisor recommended: later", and a click shows the
  text

#### Scenario: A closed gate
- **WHEN** the human rejected gate #7, for which the lead recommended `reject`, and opens
  its card
- **THEN** the card shows the folded line "Supervisor" with "recommended Reject · you
  agreed", and a click on it shows the text

### Requirement: The API and the change feed carry the recommendation

The API SHALL give the recommendation as
`recommendation` of `GateInfo` and of a question's `MessageInfo` (state, text, choice,
disagrees, time; none when not asked), and the change feed SHALL bring each change of it.

#### Scenario: A recommendation given while the page is open
- **WHEN** the lead recommends `reject` on gate #7 while the session's page is open
- **THEN** gate #7's `recommendation` in `GET …/gates` has state `given`, the text, the
  choice `reject`, disagrees and the time, and the open card shows it without a reload

### Requirement: lado answer shows the recommendation

`lado answer` and the tmux popup SHALL print, after the gate's note, "Supervisor
recommends: <option>" (or "Supervisor's recommendation:" without an option) with
"(disagrees with <agent>)" when set, the text's first line and how many lines more `v`
shows; mark the recommended option in the list of options with "← supervisor recommends";
and give the whole text under `v`. The recommendation SHALL be read at each show of the
gate.

#### Scenario: A gate with a recommendation
- **WHEN** the human runs `lado answer s 7` and gate #7's recommendation is `reject`
- **THEN** the output has "Supervisor recommends: reject", the text's first line, and
  "2) reject   ← supervisor recommends"

### Requirement: lado answer says when a recommendation is being prepared or missing

`lado answer` and the tmux popup SHALL print "Supervisor is preparing a recommendation… (v
shows it once it is given)" while the recommendation is `asked` and "The supervisor gave
no recommendation." when `missing`.

#### Scenario: A recommendation still prepared
- **WHEN** the human runs `lado answer s 8` and gate #8's recommendation is `asked`
- **THEN** the output has "Supervisor is preparing a recommendation… (v shows it once it
  is given)"
