## 1. The predicate and the refusal

- [x] 1.1 Unit tests first (layer 1), red before the code: `tests/test_update.py`:
  `in_container` for unset, empty, `0`, `1`, `yes`; `available_line` in and out of a
  container. `tests/test_self_update.py`: `refusal` gives `CONTAINER` with its `why` in a
  container, `AGENT` first inside an agent in a container, `CONTAINER` before `RUNNING`
  (lock held) and before `NO_INSTALLER`. The CLI (`cli.main(["update", ...])`, where
  `tests/test_self_update.py` tests `lado update` now): `lado update --yes`, `lado update
  0.36.0` and `lado update --yes --id <id>` in a container with an installer
  (`LADO_UPDATE_INSTALLER`) exit 1 with the one line, no request to the index
  (`LADO_UPDATE_INDEX` pointing at a missing file still gives the container line), no
  `update.lock` pid, `update.json` or `update.log` written, the result file as it was
  without `--id`, and nothing stopped (`runtime.stop_session` and the server's stop
  replaced by recorders that must stay uncalled).
- [x] 1.2 `update.py`: `in_container()`, `CONTAINER_UPDATE`; `available_line` names the
  command in a container (D1, D4). `self_update.py`: kind `CONTAINER` in `refusal` (D2).
  `cli._update`: raise for it before `_unfinished_update` (D2). `make lint`, `make test`.

## 2. Doctor and the report

- [x] 2.1 Unit tests first, `tests/test_doctor.py`: `check_lado` in a container, latest
  (`[ok  ] LADO: 0.38.0, the latest version, in a container`) and with an update out
  (`warn`, detail `0.38.0, in a container`, the hint with the command); outside a container
  unchanged; `report` with `System(container=True)` reads `(uv tool, in a container)` and
  `(no uv tool or pipx install, in a container)`; `system_info` sets `container`.
- [x] 2.2 `doctor.py`: `System.container`, `check_lado`, `report` (D4). `make test`.

## 3. The API and the System panel

- [x] 3.1 Unit tests first, `tests/test_server_system.py`: `GET /api/update` in a
  container: `can_update` false, `why_not` the reason, `by_hand` `[the command]`,
  `container` true; outside one `container` false; `POST /api/update` 409 with the reason
  and `self_update.start_detached` not called.
- [x] 3.2 `server/models.py`: `UpdateInfo.container`; `server/app.py`: `update_state` (D3).
  `make web-types`, commit `web/openapi.json` and `web/src/api.gen.ts`.
- [x] 3.3 vitest first, `web/src/SystemPanel.test.tsx`: with `container` true the head
  has a `container` pill with its tooltip; with an update out, no Update… button, the
  reason, `On the host:` and the command with Copy; with `container` false neither the
  pill nor the label. Then `SystemPanel.tsx` to the mockup
  (`task/lad-59/mockup-container.html`, option A). `make web`.
- [ ] 3.4 UI e2e (`tests/ui/test_system_panel.py`, `uv run pytest -m ui
  tests/ui/test_system_panel.py`): a `lado server` started with `LADO_CONTAINER=1` and a
  local index (`LADO_UPDATE_INDEX`) that has a newer version: the panel shows the pill, the
  block without Update… and the command; a screenshot of it (`shot`) as a run artifact.

## 4. Docs

- [ ] 4.1 AGENTS.md, Layout: `update.py` names `in_container` and `CONTAINER_UPDATE`,
  `self_update.py`'s `refusal` names the container. docs/design/ui.md: `UpdateInfo`'s
  `container` and `by_hand` in a container (A newer LADO), the head's `container` pill
  (P1) and the container case of the Update block (P3). CHANGELOG.md under
  `## 0.39.0 (unreleased)`: in a container (`LADO_CONTAINER`), `lado update` and the UI's
  update refuse and name `docker compose pull && docker compose up -d`; `lado doctor` and
  the System panel say LADO runs in a container.
- [ ] 4.2 By hand, in the LAD-52 prototype (`docs/research/docker-install/`), the image
  built with this branch's LADO and `LADO_CONTAINER=1`: `docker exec lado lado update
  --yes` exits 1 with the line, `docker ps` still shows the container up, `lado doctor`
  shows `in a container`, the System panel shows the pill. Record the output in the build
  report. `openspec validate update-in-container --strict`.
