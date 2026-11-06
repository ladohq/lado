# connection-loss Specification

## Purpose
How the UI behaves when it loses the server: the change feed's mark says so, the buttons that write
wait, and an action that got no answer is settled by what LADO reads once it can, so the human
always learns whether it arrived.

## Requirements

### Requirement: The change feed's mark says the connection is lost

Two seconds after the change feed is lost the mark in the top bar SHALL read "reconnecting…" on
the warning ground with a no-network icon; in the phone layout the icon alone, named by that word.
A drop shorter than that SHALL change nothing on the screen. When the feed is back the mark SHALL
be plain live again, with no state of its own for the return. No strip SHALL show on any page.

#### Scenario: The server stops
- **WHEN** the feed is lost and stays lost for 2 s
- **THEN** the mark reads "reconnecting…" on the warning ground

#### Scenario: A short drop
- **WHEN** the feed is lost and back within 1 s
- **THEN** the mark stays live and no button changes

#### Scenario: The server is back
- **WHEN** the feed opens again
- **THEN** the mark is live at once, as before the loss

#### Scenario: A refused token
- **WHEN** the stream is refused with a 401
- **THEN** the connection counts as refused, not lost: the page says how to get in

### Requirement: A screen reader hears the loss and the return

The top bar SHALL hold one `role="status"` region for as long as the shell stands, also while the
stream is refused, read out and not shown. Its text SHALL follow the mark: "reconnecting…" while
lost, "live" when back, and nothing while the stream is refused, as there is no mark then. The mark
itself SHALL carry no status role, so nothing is read twice.

#### Scenario: The loss
- **WHEN** the connection has been lost for 2 s
- **THEN** the region that stood there already changes its text to "reconnecting…", and it is read out

#### Scenario: The return
- **WHEN** the feed opens after a loss
- **THEN** the same region changes its text to "live"

#### Scenario: A short drop
- **WHEN** the feed is lost and back within 1 s
- **THEN** the region's text does not change

#### Scenario: Refused after a loss
- **WHEN** the stream is refused with a 401 after a loss
- **THEN** the region is empty, never "live", and the page's alert says why

### Requirement: While the connection is lost the buttons that write wait

While the mark says the connection is lost, a gate's buttons wherever the gate shows, Send
answer, Send, Stop, Stop and forget and Resume SHALL be disabled, and Enter in the composer SHALL
send nothing. Fields SHALL stay active and keep what is in them. "Waiting for connection"
SHALL stand beside a gate's buttons, and the others SHALL say it in a tooltip.

#### Scenario: A gate
- **WHEN** the connection is lost with a gate open in the chat, on Needs you or on its run's page
- **THEN** its buttons are disabled with "Waiting for connection" beside them, and its comment
  takes text

#### Scenario: The composer
- **WHEN** the connection is lost and the human presses Enter in the composer
- **THEN** nothing is sent and the text stays

#### Scenario: A tooltip on a disabled button
- **WHEN** the pointer rests on the disabled Send
- **THEN** the tooltip reads "Waiting for connection"

### Requirement: An action without an answer says LADO could not confirm it

A request of a gate's answer, an answer to questions, Send, Stop or Resume that ends with no
answer from the server SHALL show under its buttons "<What> not confirmed" with a Retry button, which SHALL be disabled until LADO
has looked at the outcome. The raw exception SHALL go to the browser's console only.

#### Scenario: Approve as the server goes away
- **WHEN** the request of Approve fails with no answer
- **THEN** the card reads "Approval not confirmed" and Retry is disabled

#### Scenario: A file not uploaded
- **WHEN** a file's upload fails with no answer before the answer was sent
- **THEN** nothing was sent, its chip is red and the line reads "<file> was not uploaded: no connection." as for any failed upload

### Requirement: An error names the action in the human's words

`<What>` SHALL be "Approval" for Approve, "Rejection" for Reject, "Answer" for a gate's other
buttons and for Send answer, "Message" for Send, "Stop" for Stop and Stop and forget, and "Resume"
for Resume. No other sentence SHALL stand with it.

#### Scenario: Cancel run
- **WHEN** the request of Cancel run fails with no answer
- **THEN** the card reads "Answer not confirmed"

#### Scenario: Stop
- **WHEN** the request of Stop fails with no answer
- **THEN** the popover reads "Stop not confirmed"

### Requirement: LADO settles an action without an answer by the state it reads

Once the server answers, LADO SHALL read the state of what the action acted on, also when the
feed never dropped, and again until it can. Reached: the error SHALL go. Not reached: "<What> not delivered" SHALL show,
with Retry and the action's buttons active.

#### Scenario: The gate is closed
- **WHEN** the connection is back and the gate has an answer, whoever gave it
- **THEN** the error goes, the card goes by the live lists, and the answer is in the feed

#### Scenario: The gate is open
- **WHEN** the connection is back and the gate is still open
- **THEN** the card reads "Approval not delivered" and Retry,
  Approve and Reject are active

#### Scenario: The questions
- **WHEN** the connection is back and none of the questions sent is open any more
- **THEN** the error goes

#### Scenario: One question still open
- **WHEN** the connection is back and one of the questions sent is still open
- **THEN** the card reads "Answer not delivered"

#### Scenario: Stop
- **WHEN** the connection is back and the session is stopped or gone
- **THEN** the error goes and the popover closes

#### Scenario: Resume
- **WHEN** the connection is back and the session runs
- **THEN** the error goes, the window closes and the session's page shows

#### Scenario: The feed never dropped
- **WHEN** one request fails with no answer while the stream stays open
- **THEN** LADO reads the state at once, and every 3 s until it can

### Requirement: The error of an action goes only when its outcome is known

The error SHALL go only when LADO found the action reached, after a Retry that succeeded, or
after another decision on the same item. The connection coming back SHALL NOT clear it. It SHALL
show the same wherever the item shows and survive a change of page.

#### Scenario: The connection comes back
- **WHEN** the feed opens and LADO has not read the state yet
- **THEN** the error stays and Retry stays disabled

#### Scenario: Another decision
- **WHEN** the card reads "Approval not delivered" and the human presses Reject
- **THEN** the error goes and the rejection is sent

#### Scenario: Another page
- **WHEN** the card shows the error and the human opens the gate's run in Flows
- **THEN** the run's page shows the same error with the same Retry

### Requirement: Send is settled by the feed

LADO SHALL look for a message from the human to the same agent, with the same text and files, after
the last message known at the click. Found: the error SHALL go, the files sent SHALL leave, and the
field SHALL be cleared if its text did not change. Not found: Retry. The server SHALL NOT change.

#### Scenario: The answer was lost
- **WHEN** the message reached the server and only its answer was lost
- **THEN** the error goes, the field is empty and no second message exists

#### Scenario: The human wrote on
- **WHEN** the message is found and the human changed the field meanwhile
- **THEN** the error goes and the field keeps the new text

#### Scenario: The same words earlier
- **WHEN** the human sent the same text before the click and this one did not reach the server
- **THEN** the earlier message does not count, and Retry is active

#### Scenario: A file alone
- **WHEN** a message of files only reached the server
- **THEN** it is found by its files

### Requirement: Retry repeats the action and takes a closed item as closed

Retry SHALL repeat what was pressed: the same option, comment, words and files. A Retry refused
because the item is closed already SHALL count as reached, with no error shown: `gate #N is closed
already`, `question #N is` answered, dismissed, closed, stopped or gone, `is stopped already` for
Stop, `is already running` for Resume.

#### Scenario: A gate someone closed
- **WHEN** Retry is refused with `gate #3 is closed already: approve by human`
- **THEN** no error shows and the card goes

#### Scenario: A stopped question
- **WHEN** Retry is refused with `question #12 is stopped`
- **THEN** no error shows and the card goes

#### Scenario: Any other refusal
- **WHEN** Retry is refused with another text
- **THEN** that text shows as a refusal does today

#### Scenario: Words changed after the failure
- **WHEN** the human changed the composer's text and presses Retry
- **THEN** the words of the click are sent and the field keeps the new text

### Requirement: Stop and forget never forgets by itself

When a Stop and forget ends with no answer to its stop, LADO SHALL settle the stop alone: reached,
the popover SHALL close with the session stopped; Retry SHALL repeat the stop alone. The forget
SHALL run only when the human asks for it again.

#### Scenario: The stop reached the server
- **WHEN** Stop and forget lost its answer and the session is found stopped
- **THEN** the popover closes, and the session stays stopped and not forgotten

### Requirement: No raw exception text shows in the UI

A request with no answer SHALL read "No connection" wherever the UI prints its reason, and
SHALL write the exception to the browser's console. A request the UI itself aborted SHALL stay
silent as before. A refusal the server answered SHALL show its text as before.

#### Scenario: A page that cannot load
- **WHEN** the human opens a tab while the server is away
- **THEN** it reads "No connection", and no `TypeError`

#### Scenario: The mark's tooltip
- **WHEN** the server cannot be reached
- **THEN** the mark has no reason; a reason the server answered (a 503) stands in its tooltip

### Requirement: Reads recover by themselves after a loss

A reload that fails SHALL keep what was loaded, and with it the open items and the fields of their
card. When the feed opens after a loss, every list that failed SHALL load again, also when the
stream resumes without a reset.

#### Scenario: A reload fails
- **WHEN** the feed resets and the load of the gates fails with a comment written on an open gate
- **THEN** the gate's card and its comment stay

#### Scenario: A tab opened while away
- **WHEN** a list failed to load while the server was away and the feed resumes
- **THEN** the list loads and its error goes
