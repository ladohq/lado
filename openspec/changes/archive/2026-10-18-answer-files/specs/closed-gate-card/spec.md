## ADDED Requirements

### Requirement: The answer's files show with its comment

The files the human attached to a gate's answer (`answer_attachments`) SHALL show under
the run's move that the answer made, after its comment, as the human's own message shows
its files: the images as previews (at most 240 × 180), then a chip per file. The opened
closed gate's card SHALL show them as chips only, in its answer block after the comment.
The closed gate's folded line SHALL NOT show them.

#### Scenario: Reject with a screenshot and a log
- **WHEN** the human rejected task/lad-86's design_ok gate with a comment, a screenshot
  and `server.log`
- **THEN** under the move "You … reject" stand the comment, the screenshot's preview and
  the chips of both files, and the opened gate's card shows the comment and the two chips
  without a preview

#### Scenario: Files without a comment
- **WHEN** the human approved a gate with one file and no comment
- **THEN** under the move stands that file's chip, with no comment
