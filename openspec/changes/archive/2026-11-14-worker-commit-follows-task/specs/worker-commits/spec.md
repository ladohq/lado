## Purpose
That a worker commits its work on its branch by default and leaves it uncommitted when its task explicitly says so, whatever its kit or provider.

## ADDED Requirements

### Requirement: A worker's task can forbid the commit

The instructions LADO gives every worker, in its own worktree or in a flow run's, SHALL tell it to commit its work on its branch unless its task says otherwise, and SHALL say that an explicit instruction of the task (not to commit, to leave the branch as it is) wins over that default; the same text for every provider and kit.

#### Scenario: The task forbids the commit

- **WHEN** the supervisor spawns w1 with the task "Create a file hello.txt containing exactly OK. Do not commit. Then report to the supervisor with send_message."
- **THEN** w1's branch has no commit beyond its start, and hello.txt is in w1's worktree, uncommitted

#### Scenario: The task says nothing of commits

- **WHEN** the supervisor spawns w2 with the task "Create a file hello.txt containing exactly OK. Then report to the supervisor with send_message."
- **THEN** w2's branch has a new commit holding hello.txt

#### Scenario: A flow run's worker

- **WHEN** a worker is spawned for a flow run
- **THEN** its instructions hold the same rule on commits as a worker in its own worktree
