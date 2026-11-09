## 1. The popup names the model (D1, D2)

- [ ] 1.1 web/src/Team.test.tsx (vitest): `AgentPopup` of an agent with role `analyst`, on
  `claude-opus-5-5`, run `task/lad-254`, renders the name, `idle · …`, the facts `Role
  analyst`, `CLI claude`, `Model claude-opus-5-5`, `Flow task/lad-254` and the hint; of
  `supervisor` (role `supervisor`, no run) the facts `CLI`, `Model` alone; a configured
  model reads its saved name; a model the CLI has not named reads `CLI default` (muted); a
  waiting agent's status has `waits`; `info` null renders the name and the hint only; no
  part names the effort or a source. Red before 1.2.
- [ ] 1.2 web/src/Team.tsx: `modelName` (D1), used by `AgentTip` and `AgentPopup`;
  `AgentPopup` by D2; its comment says the three parts. web/src/styles.css: the rules of
  D2 beside `.tooltip .tip-agent`. 1.1 and the existing `AgentTip` test pass.

## 2. The tests that read the popup (D3)

- [ ] 2.1 web/src/Layout.test.tsx and web/src/Terminals.test.tsx: read the head's and the
  strip's popup by its parts (D3), expecting the model fact. `make web` passes.
- [ ] 2.2 tests/ui/test_layout.py, `test_a_chips_tooltip_says_its_name_role_and_provider`:
  expect `w1`, `idle · …`, `CLI fake`, `Model CLI default` (and the role when it is not the
  name) and the hint; screenshot of the head's popup attached to the build report.
  `uv run pytest -m ui tests/ui/test_layout.py` passes.

## 3. Documents

- [ ] 3.1 CHANGELOG.md, 0.45.0's "See which model each agent runs on": "The agent's page
  shows its model and effort and where they came from; the Team tooltip and `lado ls` name
  the model." (at most three lines, the rest of the item as it is).
- [ ] 3.2 docs/design/ui.md, Session head's "An agent's popup" bullet: the three parts,
  the facts and the model's rule; the sentence about `AgentTip` kept.

## 4. Checks

- [ ] 4.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_layout.py`,
  `openspec validate agent-popup-model --strict`, and the trial archive of the settings'
  Checks pass.
