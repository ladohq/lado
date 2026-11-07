# LAD-177 model-server-probe: review report

Pull request #203 `feature/lad-177-model-server-probe` → `epic/lad-154-models`. Scale: full,
review depth: breadth, then precision. Head reviewed: `01dd3103` (= the remote head). The
new command `lado model-server probe <address>` tells what a model server in the human's
network is: its type, its models and the agent CLIs that can use it (an OpenAI-compatible
server: OpenCode and Kilo; a Responses API: Codex; an Anthropic Messages API: Claude
Code), by requests that generate nothing. A key is given by the name of a LADO or project
secret and never shows in output, logs or `lado.db`. A control POST to a path no API has
tells a gateway that answers 400 to everything from a real API. In a container, a silent
`localhost` gets a loud hint about `host.docker.internal`; the address is never rewritten.
`providers/` changed (one attribute, `server_api`).

## Rounds

- **Round 1** (`8cb02a9d..d4fedb73`, the whole pull request): a local breadth pass; F1–F4.
- **Round 2** (`d4fedb73..4e41d4fe`): local precision pass and external 1 of 2 (Claude
  Code GitHub Action); E1–E4.
- **Round 3** (`4e41d4fe..f455481c`): local precision pass and external 2 of 2; E5–E7.
  The external round cap was reached; the human chose one more build visit without a
  third external round.
- **Round 4** (`f455481c..01dd3103`): local precision pass with a run; no new findings.

External rounds used: 2 of 2. The external reviewer is of the same model family, so its
"no findings" weighs less. Two findings (E2, E5) were in code rewritten for an earlier
finding (F1).

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | A key starting with `-` (`--key -s3cr3t`) was printed by argparse's error | fixed (`33da1794`, `5c09f71b`, `a4d675ee`) |
| E2 | important | external: `--k -abc`, `--ke -abc`, `--key a b` printed the key | fixed (`5c09f71b`) |
| E5 | important | external: `--help=…`, `--he=…`, `--key --he=…`, on 3.10 `--key -hX` put the key in "ignored explicit argument" | fixed (`a4d675ee`): the probe's own parser error prints the usage and a fixed text |
| E1 | important | external: `urlsplit`'s error printed `user:pw` of the address | fixed (`5c09f71b`) |
| F2 | minor | Model ids and `Location` were printed unsanitised (forged lines, ESC) | fixed (`33da1794`): one line of visible text |
| F4 | minor | The PR's manual check switched the human's checkout | fixed: `git worktree add` |
| E6 | minor | external: the spec did not describe the widened refusal and an address urllib refuses | fixed (`01dd3103`) |
| E7 | minor | external: a long line in `docs/cli.md` | fixed (`01dd3103`) |
| F3 | minor | A key over 64 KiB from stdin is cut | declined: no such keys; the server refuses a cut key |
| E3 | minor | external: a key in clear text over `http://` | declined: the human chose the address and scheme; a warning is new behaviour outside the spec |
| E4 | — | external: TLS and OS texts not passed through `one_line` | refuted: they come from `ssl`/`OSError`, not from the server |

On the way the developer also fixed a false "does not answer" for an unparsable
`Location` (`5c09f71b`).

Found on the way: `lado project set … --secret` prints a value starting with `-` through
argparse's errors (BACKLOG.md); the same class as F1/E2/E5, outside the task.

## Checks

`make lint` clean; the four unit files of the change 378 passed;
`tests/integration/test_model_server_probe.py` 4 passed (all at `01dd3103`); the
developer's `make test` 4942 passed, 7 skipped; `openspec validate --specs --strict` after
the archive 58 passed; CI on `01dd3103` 23 of 23, `ci-ok` green.

## Not checked

- Real servers (Ollama, LM Studio, vLLM, LiteLLM) were not probed: that they answer 400/422
  with JSON to `{}` and otherwise on the control path is a design assumption, left to the
  PR's manual check.
- A gateway answering 403 on Ollama's or LM Studio's native paths with a right key is
  reported as "refused the key", as the spec requires.
- Behind `HTTP(S)_PROXY`, "does not answer" may be the proxy's.
- Live tests were not run, though `providers/` changed (agent behaviour untouched; smoke
  in CI green).
- The class "argparse prints argv" is closed for `probe` only; other commands print as
  before.
