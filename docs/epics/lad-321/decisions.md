# Decisions: Session isolation, M1 — Agent API groundwork (LAD-321)

| Date | Where (step, gate) | Question | Options | Recommended (by whom) | Decided (by whom) | Taken? |
|---|---|---|---|---|---|---|
| 2026-11-28 | intake, #8901 q1 | The epic's key and tracker task | lad-321, LAD-321 is the epic; step tasks created one at a time on the human's "yes, create" | lad-321 (lead) | lad-321 (human) | yes |
| 2026-11-28 | intake, #8901 q2 | Branch strategy | each step into main; an epic branch | into main, every step releasable (lead) | into main (human) | yes |
| 2026-11-28 | intake, #8901 q3 | Steps in parallel | two at once (M1-1 and M1-4), then M1-10; one after another | two at once (lead) | the human asks whether parallel is worth it, is fine with one after another; settled in round 2 | open |
| 2026-11-28 | intake, #8901 q4 | Live tests with real models | by hand on live.yml before the merge of M1-2 and M1-3 only | M1-2 and M1-3 only (lead) | live tests are a must and as often as possible; the Claude Code subscription may be used; other CLIs or models through OpenRouter, kept cheap; the smoke tests must be reviewed and improved so they really work and help (human) | no |
| 2026-11-28 | intake, #8901 q5 | Where the prototype M1-6 runs (needs Docker; LADO's container has none) | the human's Mac runs the worker's script; CI; Docker in LADO's container | the human's Mac (lead) | a separate Mac of the human; Linux and Windows can be found if needed (human) | yes |
| 2026-11-28 | intake, #8901 q6 | The prototype's draft PR in the public repository | draft PR "prototype, do not merge" on ladohq/lado, closed after its findings are in the spec | as in the plan (lead) | as recommended (human) | yes |
| 2026-11-28 | intake, #8901 (human's own) | Manual checks | — | — | a mandatory manual check as often as possible, done by the human on another machine with another agent; the lead prepares a detailed checklist for it each time one is needed (human) | n/a (the human's own) |
