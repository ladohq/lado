## Context

`self_update.refusal` is the one answer to "can this LADO update itself now", for the CLI
(`cli._update`) and the UI server (`app.update_state`, `POST /api/update`). Its kinds are
`AGENT`, `RUNNING` and `NO_INSTALLER`; only `RUNNING` and `AGENT` stop `lado update`
before PyPI, `NO_INSTALLER` prints the plan and the commands by hand. `update.available_line`
is the one line that a newer LADO is out (`lado ls`, `lado doctor`), and `doctor.System`
holds what the System panel and the issue report show.

## Decisions

- **D1. One predicate, one command.** `update.in_container()` reads `LADO_CONTAINER`
  (set, not empty, not `0`) at each call, no cache; `update.CONTAINER_UPDATE` is the text
  `docker compose pull && docker compose up -d`. Every other module asks them, so the rule
  and the command are written once. In `update.py` because the update check, the refusal
  and the doctor all import it already, and it stays free of the server.
- **D2. A refusal kind `CONTAINER`.** `self_update.refusal` gains `CONTAINER`, checked
  after `AGENT` and before `RUNNING` and `NO_INSTALLER`; its `why` is `LADO runs in a
  container: a new image updates it, not lado update`. `cli._update` raises
  `runtime.LadoError(f"{why}; on the host: {CONTAINER_UPDATE}")` for it right after the
  refusal is computed, before `_unfinished_update` and `fetch_index`, as it does for
  `AGENT`. With `--id` (the UI's detached update, which the API never starts in a
  container) the existing `not_started` path writes its failed result as for any refusal.
- **D3. The UI reuses P3.** `app.update_state` sets `by_hand = [CONTAINER_UPDATE]` for
  `CONTAINER` (and keeps `plan().by_hand()` for `NO_INSTALLER`), so the System panel's
  existing "no button, reason, commands with Copy" block shows it; no new block.
  `UpdateInfo` gains `container: bool` (from `in_container()`), which the panel reads for
  the head's pill and for the label `On the host:` instead of `By hand:`. In `UpdateInfo`,
  not `SystemInfo`, beside `prerelease`, which drives the head's other pill: the head has
  `UpdateInfo` first (it comes with the feed), so the pill does not wait for the slower
  `/api/system`.
- **D4. The doctor's line, not a new check.** `doctor.check_lado` appends `, in a
  container` to its detail (after `, the latest version`, or after the version when an
  update is out); `doctor.System` gains `container: bool`, and `doctor.report` writes
  `(<installer or "no uv tool or pipx install">, in a container)`. `update.available_line`
  names `CONTAINER_UPDATE` instead of `lado update` in a container.
- **D5. The update check stays on.** In a container it still looks at PyPI once a day:
  a newer LADO means a newer image, which the human wants to hear about.

## Risks

- The image is not built yet (T3): the refusal is checked by unit tests and by hand in the
  LAD-52 prototype (`docs/research/docker-install/`) with `LADO_CONTAINER=1`, its
  `environment` in `compose.yaml` or `docker exec -e`.
- A LADO image published before this change has no refusal; the plan publishes images only
  after it (T7).
