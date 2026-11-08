# LAD-241 server-model-cli-reasons: review report

Pull request #259 `fix/lad-241-server-cli-reasons` → `main`. Scale: tweak, precision review. Head
reviewed: `1f9770df`. Under a server's model on Settings → Model servers, every agent CLI is listed
in LADO's order; one that cannot use the server has its tick off and disabled with
`cannot use this server: <why>` (the core's `Probe.cannot()`, the API's `ProbeInfo.cannot`) or
`not installed`. Delta: `model-settings-page` (one requirement added, one modified).

## Rounds

1. Local, precision, `origin/main...729f036a`: found F1.
2. Local, precision, `729f036a..b3e3c51d`: F1 closed, found F2 (in the code F1's fix changed).
3. Local, precision, `b3e3c51d..1f9770df`: F2 closed, no new finding.
4. External 1, Claude Code GitHub Action: no blocker; N1, N2, N4 minor (declined), N3 refuted. It
   read every risky file of the diff (`model_servers.py`, `server/models.py`, `model_entries.py`,
   `ModelSources.tsx`, `styles.css`, `modelFakes.ts`), not the tests, docs or openspec.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Source | Finding | Level | Fate |
|---|---|---|---|---|
| F1 | local | A disabled tick of a CLI with a model of it already saved showed as unticked, against ui.md's "A tick is on exactly when a configured model…" | important | fixed in `b3e3c51d`, vitest |
| F2 | local | The reason under such a tick fell into the 16px tick column and wrapped into a narrow strip | important | fixed in `1f9770df` (`.mx-sub-item .mx-as { grid-column: 2 }`), UI e2e |
| N1 | external | Two `place` helpers in `ModelSources.tsx` | minor | declined: they cannot diverge, merging them is a refactor |
| N2 | external | `.mx-cant > span:first-of-type` relies on span order | minor | declined: true for the one markup it applies to |
| N3 | external | `opacity: .45` of a disabled tick and contrast | — | refuted: WCAG does not cover disabled controls; the reason is readable text |
| N4 | external | `suiting(...)[1]` indexed instead of unpacked | minor | declined: style only |

## Checks

- The reviewer ran: `make lint` green; pytest over the touched modules, 496 passed; vitest
  `ModelSources` and `ModelSettings`, 61 passed; `tsc` clean; the two new UI tests, both passed;
  `openspec validate` of the change, valid.
- From the developer's report: the full `make test`, `make web` and the trial archive.
- CI on `1f9770df`: 23 of 23 green, `ci-ok` included.
- Not run: smoke and live. `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py`
  and `tests/live/` did not change, so no live run is needed before the merge.
- A local flake the developer met: `test_a_request_lado_s_server_did_not_answer_promises_nothing`
  (a screenshot timeout in a parallel run, passes alone with `-n0`); unrelated, green in CI.
- The external reviewer is the same model family; its "nothing found" weighs accordingly.

## Found on the way

None.
