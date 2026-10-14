Task: LAD-59

## Why

In a Docker container LADO's UI server is the container's main process. `lado update`
stops that server before it runs the installer, so Docker kills every process of the
container, the update too, in the middle of its installer; the restart policy brings LADO
back on the old version, and `update-result.json` says `running` for good
(docs/research/docker-install.md, H7 and 5.7). An update inside a container would be lost
anyway when the container is made again from its image. Yet in the image LADO is a
`uv tool` install, so `self_update.refusal` finds an installer, `lado update` goes ahead
and the System panel offers **Update…**. LADO does not know it runs in a container: the
first step of the Docker install plan (docs/research/docker-install-plan.md, T1).

## What Changes

- LADO runs in a container when `LADO_CONTAINER` is set to a value other than empty or
  `0`; the image will set it (a later task of the plan).
- In a container, `lado update` (with or without a version, with `--yes` too) refuses at
  once, exit 1, stopping nothing and without looking at PyPI:
  `lado: LADO runs in a container: a new image updates it, not lado update; on the host:
  docker compose pull && docker compose up -d`.
- The UI's update refuses the same way: `UpdateInfo.can_update` is false with that reason
  in `why_not`, `by_hand` holds `docker compose pull && docker compose up -d`, the new
  `UpdateInfo.container` is true, and `POST /api/update` answers 409. The System panel's
  Update block has no **Update…** button, says why, and shows the command under
  `On the host:` with Copy; its head shows a grey `container` pill beside `LADO <version>`
  (option A of the mockup), with a tooltip.
- `lado doctor`'s LADO line ends with `, in a container`; the line that a newer LADO is
  out (`lado ls`, `lado doctor`) names `docker compose pull && docker compose up -d`
  instead of `lado update`. The system report for an issue (System panel's copy,
  `lado bug-report`) says `(<installer>, in a container)` after the version.
- The Docker install plan moves into the repository, in English:
  docs/research/docker-install-plan.md.

## Scope

`src/lado/update.py` (the one predicate and the command), `src/lado/self_update.py` (the
refusal), `src/lado/cli.py` (`lado update` refuses first), `src/lado/doctor.py` (the LADO
line, `System.container`, the report), `src/lado/server/app.py` and `models.py`
(`UpdateInfo.container`, `by_hand`), `web/src/SystemPanel.tsx` (pill, Update block),
`web/openapi.json` and `web/src/api.gen.ts`, tests at the layers tasks.md names,
AGENTS.md (Layout: `update.py`, `self_update.py`), docs/design/ui.md (API's `UpdateInfo`,
System panel P1 and P3), CHANGELOG.md, docs/research/docker-install-plan.md. A new
capability `container`. Minor version: a CLI and API behaviour change. No schema change.

## Out of scope

- The UI server's links and its "open to other machines" warning in a container, and the
  folder picker's start folder: task T2 of the plan.
- `lado uninstall` in a container: it would remove the program from the container's
  writable layer only, harmless and undone by the next container; it belongs with the
  image (T3 and later).
- Detecting a container by itself (`/.dockerenv`, cgroups): it would also refuse in a dev
  container where LADO is a `uv tool` install whose server is not the container's main
  process and `lado update` works; only the image knows that its server is the main
  process.
- A process supervisor in the image that keeps the container up while the server
  restarts: the update would still be lost when the container is made again.
- Switching off the daily update check in a container: it still tells the human that a
  newer LADO, so a newer image, is out.

## Impact

- CLI: `lado update` in a container exits 1 at once; `lado ls` and `lado doctor` lines.
- API: `UpdateInfo.container` (new field), `can_update`, `why_not`, `by_hand` in a
  container; `POST /api/update` 409.
- UI: System panel head pill and Update block.
- Spec: new capability `container`.
