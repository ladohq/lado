## ADDED Requirements

### Requirement: The live flow test crosses a human gate

The live tests SHALL, with every provider of `live.yml`'s matrix, take a flow run through a
human's answer at an approval gate between two steps of the same worker: the test MUST answer
the gate as the human with a comment, and MUST check that the real agent then got the next
step as a message from LADO, did it and reported its outcome, using a word that only the
human's comment names.

#### Scenario: The human approves with a comment

- **WHEN** the run's worker has reported its first step and the human approves the gate with
  a comment naming a word
- **THEN** the worker gets the next step as a message from LADO, writes that word into a file
  on the run's branch and reports, and the run ends

#### Scenario: The step after the gate never reaches the agent

- **WHEN** a provider's agent does not take the message that carries the step after the gate
- **THEN** that provider's live cell fails waiting for the run to end
