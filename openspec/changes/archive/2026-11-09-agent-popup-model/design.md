## Context

`AgentPopup` (web/src/Team.tsx) is the tooltip of an agent's avatar in the session's head
(`AgentAvatar`) and on the terminals' strip (web/src/Terminals.tsx). It renders five
`.tooltip-line` divs; `.tooltip-line + .tooltip-line` makes every line after the first
muted, so they read as one block. `AgentTip`, the compact tooltip of a terminal's tab and a
phone's chip, already names the model as `info.model.configured ?? info.model.name`.
`AgentInfo.model` (`ModelInfo`) carries `name`, `configured` and the source's `words`; no
server change is needed. The approved mock-up is the run artifact
`mockup-agent-popup.html`, option A.

## Decisions

### D1. One rule for the model's name in a tooltip

A helper in Team.tsx, `modelName(model: ModelInfo): string | null`, returns
`model.configured ?? model.name`; `AgentTip` and `AgentPopup` both use it, so the two
tooltips cannot name one agent's model differently. The agent's page keeps its own
`ModelFact`, which says more (the id, the server, the source).

### D2. The popup's markup

```
<div class="tip-head">  <StatusDot/> <span class="tip-agent">name</span> </div>
<div class="tip-status[ waits]">status · since</div>
<dl class="tip-facts">  <dt>Role</dt><dd>…</dd> <dt>CLI</dt><dd>…</dd>
                        <dt>Model</dt><dd>…</dd> <dt>Flow</dt><dd>…</dd> </dl>
<div class="tip-hint">Click to open the terminal</div>
```

`Role` is left out when the role is the name, `Flow` when the agent has no run, and the
facts with them when `info` is null (an agent not listed: name and hint only, as now). A
model the CLI named is in `<code>` (mono, as on the agent's page); a configured model's
saved name is plain text; none is `CLI default` in `.muted`. The popup no longer uses
`.tooltip-line`, so the shared muted rule does not apply to it; its parts get their own
rules beside `.tooltip .tip-agent` in styles.css: the status indented under the name past
the dot, muted, `--human` when it waits; the facts a two-column grid (`auto 1fr`), labels
muted, values in `--ink`, a 1 px `--line` top border; the hint 11.5 px, muted, with its own
top border. The tooltip's `max-width: 320px` and `overflow-wrap: anywhere` keep a long
model id inside.

### D3. Tests read the popup by its parts

The vitest tests (Layout.test.tsx, Terminals.test.tsx) and the UI e2e test
(`tests/ui/test_layout.py`) that list `.tooltip-line` texts read the name, the status, the
facts as `label value` pairs and the hint instead. The fake agent's CLI names no model, so
the UI test expects `Model CLI default`; a model with a name is the unit tests' (Team.test.tsx),
the lowest layer that renders the popup.

### D4. A patch for 0.45.0rc2

No API, MCP, CLI or schema change; CHANGELOG's existing 0.45.0 item is reworded, no new
item: the popup now does what 0.45.0 already announces.
