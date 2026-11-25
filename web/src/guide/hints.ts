// The first-run guide's hints (docs/design/ui.md, First-run guide): every hint of the guide is
// data here, the one list, with all of its texts; only the engine's own controls (Not now,
// Got it, Don't show tips like this) and its screen reader lines are Guide.tsx's. In the main bundle (a few
// kB): the shell reads the ids to decide whether the lazy engine (Guide.tsx) is needed at all.
//
// A hint points at a `data-guide` marker on an existing element (`target`; `anchor`: what its
// card lines up with, inside the target) and shows while all of its `when` conditions hold
// (conditions.ts; a name starting with "!" is its negation). Guiding hints are tried in this
// file's order and the first that holds shows, so a more specific step stands before a more
// general one; one whose part is done in the system is skipped. A phone-only hint with
// `precede` shows instead of the step it names in `for` while its own `when` holds (the menu
// still closed, a Settings section open instead of the list). Tips are shown in their order,
// one at a time, each once. A hint whose texts change enough to be shown again gets a new id.
// `hints.test.ts` checks every marker, condition and text against the UI's code.

export type Side = "right" | "below" | "above" | "left";

// A condition: its name, then its arguments.
export type Cond = [name: string, ...args: string[]];

export type Part = "model" | "author" | "start";

export type Texts = {
  title?: string;
  body: string[]; // paragraphs; **a control's visible name**, `code`
  waiting?: string; // the footer's waiting line
  done?: string; // the done line, when the part before was done in this run of the guide
  link?: string; // a link of the card (`action`)
  buttons?: string[]; // a centred card's buttons, the first primary
  note?: string; // a centred card's muted note
  links?: { label: string; href: string }[]; // links opening a new tab
  help?: string; // a muted line under the links
};

export type Hint = {
  id: string;
  kind: "guiding" | "tip";
  centred?: boolean; // a guiding card in the middle, pointing at nothing
  part?: Part;
  target?: string;
  anchor?: string;
  when: Cond[];
  prefer?: Side[];
  precede?: { for: string[] }; // phone only: shown before a step aimed at one of these markers
  cli?: string; // a provider's row step: the provider the guide has texts for
  action?: "pass-row" | "none-of-these"; // what the card's link does
  keep?: string[]; // markers of what the card must not cover where it can stand elsewhere
  texts: Texts;
  variants?: Record<string, Texts>; // texts by the target's data-guide-refusal
};

// The parts of the main guide, in order; a part is done when its fact holds (conditions.ts).
export const PARTS: { part: Part; name: string }[] = [
  { part: "model", name: "Connect a model" },
  { part: "author", name: "Sign your work" },
  { part: "start", name: "Start working" },
];

const MODEL_DONE = "✓ Model connected";
const AUTHOR_DONE = "✓ Your work will be signed";
const SETTINGS_LIST = ["agent-clis-link", "model-servers-link", "git-servers-link"];
const AGENT_CLIS = "/settings/agent-clis";
const MODEL_SERVERS = "/settings/model-servers";
const GIT_SERVERS = "/settings/git-servers";

export const HINTS: Hint[] = [
  // The main path.
  {
    id: "welcome",
    kind: "guiding",
    centred: true,
    when: [["telemetryAnswered"], ["!windowOpen"]],
    texts: {
      title: "Welcome to LADO",
      body: [
        "LADO runs a team of AI agents for you: you describe a task, they plan it, do the work, and ask you when a decision is yours.",
        "The agents need access to an AI model: a subscription or a key you already have. This guide shows where to connect it.",
      ],
      buttons: ["Show me", "Not now"],
      note: "You can open the guide again from Help.",
    },
  },
  {
    id: "none-of-these",
    kind: "guiding",
    centred: true,
    part: "model",
    when: [["noneOfThese"]],
    texts: {
      title: "Don't have any of these yet?",
      body: [
        "The simplest way is a monthly plan: Claude Pro, or a paid ChatGPT plan such as Plus. With an API key from Anthropic, OpenAI, OpenRouter or Qwen (Alibaba Cloud) you pay for what the agents use instead.",
        "A plan, or an Anthropic or OpenAI key, goes in **Agent CLIs** (Log in…); an OpenRouter or Qwen key goes in **Model servers**. Get one, come back, and the guide goes on from here.",
      ],
      links: [
        { label: "Claude plans ↗", href: "https://claude.com/pricing" },
        { label: "ChatGPT plans ↗", href: "https://chatgpt.com/pricing" },
        { label: "OpenRouter keys ↗", href: "https://openrouter.ai/keys" },
        {
          label: "Qwen (Alibaba Cloud) keys ↗",
          href: "https://www.alibabacloud.com/help/en/model-studio/get-api-key",
        },
      ],
      help: "Not sure what any of this means? Ask your company's IT team, or someone who knows.",
      buttons: ["Back", "Not now"],
    },
  },
  {
    id: "open-menu",
    kind: "guiding",
    part: "model",
    target: "rail-menu",
    precede: { for: ["rail-settings"] },
    when: [["phone"], ["!drawerOpen"]],
    texts: {
      title: "Open the menu",
      body: ["**Settings**, where models are connected, is in the menu."],
      waiting: "Waiting for you to open the menu",
    },
  },
  {
    id: "open-settings",
    kind: "guiding",
    part: "model",
    target: "rail-settings",
    when: [["!route", "/settings"]],
    texts: {
      title: "Open Settings",
      body: ["AI models are connected in Settings."],
      waiting: "Waiting for you to open Settings",
    },
  },
  {
    id: "settings-back-model",
    kind: "guiding",
    part: "model",
    target: "settings-back",
    precede: { for: SETTINGS_LIST },
    when: [["phone"], ["settingsSection"], ["!nextVisible"]],
    texts: {
      title: "Back to Settings",
      body: ["**Model servers** is on the Settings list."],
      waiting: "Waiting for you to go back",
    },
  },
  {
    id: "login-refused",
    kind: "guiding",
    part: "model",
    target: "login-sheet",
    anchor: "login-refusal",
    when: [["loginRefused"]],
    texts: {
      title: "That didn't work yet",
      body: [
        "The red line says what is wrong and which choice to use. Copy the whole value again, with nothing before or after it, and press **Save**.",
      ],
      waiting: "Waiting for a value that works",
    },
  },
  {
    id: "login-claude-choice",
    kind: "guiding",
    part: "model",
    target: "login-sheet",
    anchor: "login-choices",
    when: [["loginWindow", "claude"], ["!loginPicked", "claude"]],
    texts: {
      title: "Which one do you have?",
      body: [
        "**Subscription** if you pay for Claude Pro or Max. **Pay per use** if you have an API key from console.anthropic.com. Choose yours here.",
      ],
      waiting: "Waiting for your choice",
    },
  },
  {
    id: "login-claude-token",
    kind: "guiding",
    part: "model",
    target: "login-sheet",
    anchor: "login-secret",
    keep: ["login-choices"],
    when: [["loginWindow", "claude"], ["loginChoice", "claude", "subscription"]],
    texts: {
      title: "Make a token with Claude Code",
      body: [
        "On a computer with Claude Code installed, open a terminal, type `claude setup-token` and sign in. Paste the token it prints (sk-ant-oat01-…) here and press **Save**.",
        "No such computer? Close this window: the next row signs in without a terminal.",
      ],
      waiting: "Waiting for the token",
    },
  },
  {
    id: "login-claude-key",
    kind: "guiding",
    part: "model",
    target: "login-sheet",
    anchor: "login-secret",
    keep: ["login-choices"],
    when: [["loginWindow", "claude"], ["loginChoice", "claude", "usage"]],
    texts: {
      title: "Paste your API key",
      body: [
        "Make one at console.anthropic.com, under API keys. It starts with sk-ant-api03-. Paste it here and press **Save**.",
      ],
      waiting: "Waiting for the key",
    },
  },
  {
    id: "login-codex-code",
    kind: "guiding",
    part: "model",
    target: "login-sheet",
    anchor: "login-action",
    keep: ["login-choices"], // the other choices' names and what they are
    when: [["loginWindow", "codex"], ["loginChoice", "codex", "chatgpt"]],
    texts: {
      title: "Sign in with a one-time code",
      body: [
        "Press **Get a sign-in code**, open the link it shows on any device, sign in to ChatGPT and type the code.",
        "An OpenAI API key instead? Choose **Pay per use**.",
      ],
      waiting: "Waiting for the sign-in",
    },
  },
  {
    // Any login window's choice that is a field to paste into and has no step of its own
    // (Codex's Pay per use and access token, a later CLI's): the steps above go first.
    id: "login-paste",
    kind: "guiding",
    part: "model",
    target: "login-sheet",
    anchor: "login-secret",
    keep: ["login-choices"],
    when: [["marker", "login-secret"]],
    texts: {
      title: "Paste it and press Save",
      body: [
        "The line above the field says where this comes from. Copy the whole value, paste it here and press **Save**.",
      ],
      waiting: "Waiting for the value",
    },
  },
  {
    id: "cli-login-claude",
    kind: "guiding",
    part: "model",
    cli: "claude",
    target: "cli-row-claude",
    action: "pass-row",
    when: [["route", AGENT_CLIS], ["cliToLogIn", "claude"]],
    texts: {
      title: "Claude Pro or Max, or an Anthropic API key?",
      body: [
        "If you have either, press **Log in…** on this row. The window that opens asks which one you have and what to paste.",
      ],
      link: "I have neither",
      waiting: "Waiting for the login",
    },
  },
  {
    id: "cli-login-codex",
    kind: "guiding",
    part: "model",
    cli: "codex",
    target: "cli-row-codex",
    action: "pass-row",
    when: [["route", AGENT_CLIS], ["cliToLogIn", "codex"]],
    texts: {
      title: "A ChatGPT plan, or an OpenAI API key?",
      body: [
        "A paid ChatGPT plan (Plus, Pro, Business or Enterprise) or a key from platform.openai.com: if you have one, press **Log in…** on this row. With a plan you sign in by a one-time code, no terminal needed.",
      ],
      link: "I have neither",
      waiting: "Waiting for the login",
    },
  },
  {
    id: "model-server-error",
    kind: "guiding",
    part: "model",
    target: "model-server-form",
    anchor: "model-server-error",
    when: [["marker", "model-server-error"]],
    texts: {
      title: "The key wasn't accepted",
      body: [
        "The service refused this key. Copy it again from the service's site, the whole key with no spaces, and paste it over this one. **Check key** comes back once the key changes: press it, or **Add server**.",
      ],
      waiting: "Waiting for a key that works",
    },
    variants: {
      unreachable: {
        title: "LADO can't reach this address",
        body: [
          "Check the address against the service's instructions. For a model on your own computer, make sure its app is running.",
        ],
        waiting: "Waiting for an address that answers",
      },
    },
  },
  {
    id: "model-server-form",
    kind: "guiding",
    part: "model",
    target: "model-server-form",
    when: [["marker", "model-server-form"]],
    texts: {
      title: "Name, address and key",
      body: [
        "Give it any name, paste the address and the key from the service's site, then press **Add server**. A model on your own computer usually needs no key.",
      ],
      waiting: "Waiting for the server to be added",
    },
  },
  // A server saved is no model yet: an agent CLI works on a model of it once it is ticked.
  {
    id: "model-clis",
    kind: "guiding",
    part: "model",
    target: "model-clis",
    when: [["marker", "model-clis"]],
    texts: {
      title: "Tick the agent CLIs that run it",
      body: [
        "Tick at least one. The agents of that CLI then work on this model; untick it to stop that.",
      ],
      waiting: "Waiting for a tick",
    },
  },
  {
    id: "model-pick",
    kind: "guiding",
    part: "model",
    target: "model-list",
    when: [["marker", "model-list"]],
    texts: {
      title: "Choose a model",
      body: [
        "These are the models your server offers. Press the one the agents should work on; you can add more later.",
      ],
      waiting: "Waiting for you to choose a model",
    },
  },
  {
    id: "model-id",
    kind: "guiding",
    part: "model",
    target: "model-id",
    when: [["marker", "model-id"]],
    texts: {
      title: "Type the model's id",
      body: [
        "This server doesn't list its models. Copy a model's id from the service's site, choose the agent CLI that runs it and press **Add**.",
      ],
      waiting: "Waiting for the model to be added",
    },
  },
  {
    // No installed CLI speaks the server's API: no model of it can be ticked here.
    id: "model-no-cli",
    kind: "guiding",
    part: "model",
    target: "model-no-cli",
    when: [["marker", "model-no-cli"]],
    texts: {
      title: "No agent CLI here can use this server",
      body: [
        "None of the agent CLIs installed on this computer works with this server. Install one that does: **Agent CLIs** lists the others and how to install each. Or add a server of another kind.",
      ],
      waiting: "Waiting for an agent CLI that can use it",
    },
  },
  {
    id: "model-server-row",
    kind: "guiding",
    part: "model",
    target: "model-server-row",
    when: [["route", MODEL_SERVERS], ["marker", "model-server-row"]],
    texts: {
      title: "Open your server",
      body: ["The server is saved; the agents still need a model of it. Press the server's row to see its models."],
      waiting: "Waiting for you to open the server",
    },
  },
  {
    id: "model-server-add",
    kind: "guiding",
    part: "model",
    target: "model-server-add",
    keep: ["model-servers-lead"], // which servers fit
    when: [["route", MODEL_SERVERS]],
    texts: {
      title: "Add your server",
      body: [
        "Press **Add server**. You give it a name, its address and your key, and LADO checks that its models answer.",
      ],
      waiting: "Waiting for you to press Add server",
    },
  },
  {
    id: "open-agent-clis",
    kind: "guiding",
    part: "model",
    target: "agent-clis-link",
    when: [["route", "/settings"], ["!route", AGENT_CLIS], ["!route", MODEL_SERVERS], ["cliToLogIn", "*"]],
    texts: {
      title: "Open Agent CLIs",
      body: [
        "Here LADO's agents log in with a subscription you may already have, such as Claude or ChatGPT.",
      ],
      waiting: "Waiting for you to open Agent CLIs",
    },
  },
  {
    id: "model-server-open",
    kind: "guiding",
    part: "model",
    target: "model-servers-link",
    action: "none-of-these",
    when: [["route", "/settings"], ["!route", MODEL_SERVERS], ["!cliToLogIn", "*"]],
    texts: {
      title: "An OpenRouter key, or a model on your computer?",
      body: [
        "With a key from OpenRouter, Qwen (Alibaba Cloud) or another OpenAI-compatible service, or a model running on your computer (Ollama, LM Studio), open **Model servers**.",
      ],
      link: "I have none of these — what should I choose?",
      waiting: "Waiting for you to open Model servers",
    },
  },
  {
    id: "open-menu-author",
    kind: "guiding",
    part: "author",
    target: "rail-menu",
    precede: { for: ["rail-settings"] },
    when: [["phone"], ["!drawerOpen"]],
    texts: {
      done: MODEL_DONE,
      title: "Open the menu",
      body: ["**Settings** is in the menu."],
      waiting: "Waiting for you to open the menu",
    },
  },
  {
    id: "open-settings-author",
    kind: "guiding",
    part: "author",
    target: "rail-settings",
    when: [["!route", "/settings"]],
    texts: {
      done: MODEL_DONE,
      title: "Open Settings",
      body: ["Who signs the agents' work is set in Settings, in **Git servers**."],
      waiting: "Waiting for you to open Settings",
    },
  },
  {
    id: "settings-back",
    kind: "guiding",
    part: "author",
    target: "settings-back",
    precede: { for: SETTINGS_LIST },
    when: [["phone"], ["settingsSection"], ["!nextVisible"]],
    texts: {
      done: MODEL_DONE,
      title: "Back to Settings",
      body: ["One more setting, in **Git servers**."],
      waiting: "Waiting for you to go back",
    },
  },
  {
    id: "author-form",
    kind: "guiding",
    part: "author",
    target: "author-form",
    when: [["marker", "author-form"]],
    texts: {
      title: "Your name and email",
      body: [
        "They are written into the history of each project the agents change. A work email is fine. Then press **Save author**.",
      ],
      waiting: "Waiting for the author to be saved",
    },
  },
  {
    id: "author-set",
    kind: "guiding",
    part: "author",
    target: "author-row",
    when: [["route", GIT_SERVERS]],
    texts: {
      title: "Who signs the work?",
      body: [
        "Nobody is set yet, so the agents can't save their work. Press **Set author** and enter your name and email.",
      ],
      waiting: "Waiting for you to press Set author",
    },
  },
  {
    id: "open-git-servers",
    kind: "guiding",
    part: "author",
    target: "git-servers-link",
    when: [["route", "/settings"]],
    texts: {
      done: MODEL_DONE,
      title: "Sign the agents' work",
      body: [
        "Agents save each step of their work under a name and email, so a project's history shows who did what. Open **Git servers** to set yours.",
      ],
      waiting: "Waiting for you to open Git servers",
    },
  },
  {
    id: "open-menu-new",
    kind: "guiding",
    part: "start",
    target: "rail-menu",
    precede: { for: ["rail-new-session"] },
    when: [["phone"], ["!drawerOpen"]],
    texts: {
      done: AUTHOR_DONE,
      title: "Open the menu",
      body: ["**New session** is in the menu."],
      waiting: "Waiting for you to open the menu",
    },
  },
  {
    id: "new-session",
    kind: "guiding",
    part: "start",
    target: "rail-new-session",
    keep: ["author-row"], // the author just saved
    when: [],
    texts: {
      done: AUTHOR_DONE,
      title: "Start your first session",
      body: [
        "Press **New session** and describe a task in your own words. The team takes it from there, and short tips explain what you see.",
      ],
      waiting: "Waiting for you to open New session",
    },
  },

  // Tips, each once, in this order.
  {
    id: "tip-launch",
    kind: "tip",
    target: "launch-task",
    when: [["marker", "launch-task"]],
    texts: {
      body: [
        "Describe the task here in your own words. Above, choose where the team works; below, which team and model take it. The small i beside a field explains it.",
      ],
    },
  },
  {
    id: "tip-session",
    kind: "tip",
    target: "session-tabs",
    prefer: ["below", "right"],
    keep: ["session-first"], // the task, the first message
    when: [["marker", "session-tabs"]],
    texts: {
      body: [
        "This is your session. **Activity** shows what the team does, and you write to its lead in the field at the bottom; the other tabs show the agents, the steps and the documents.",
      ],
    },
  },
  {
    id: "tip-gate",
    kind: "tip",
    target: "gate-card",
    prefer: ["above", "left", "right", "below"],
    when: [["marker", "gate-card"]],
    texts: {
      body: [
        "The team waits for your decision. Read the note and its documents, then press a button; a comment for the next step is optional.",
      ],
    },
  },
  {
    id: "tip-question",
    kind: "tip",
    target: "question-card",
    prefer: ["above", "left", "right", "below"],
    when: [["marker", "question-card"]],
    texts: {
      body: ["An agent asks you something. Press one of its answers, or write your own in your words."],
    },
  },
  {
    id: "tip-terminal",
    kind: "tip",
    // At the terminal's bar: on the terminal itself it would cover its newest lines.
    target: "terminal-tools",
    prefer: ["below", "left", "right", "above"],
    when: [["marker", "terminal-tools"]],
    texts: {
      body: ["This is the agent's own window. You can watch it work; you don't have to type anything here."],
    },
  },
];

export const TIP_IDS = HINTS.filter((hint) => hint.kind === "tip").map((hint) => hint.id);

// The providers whose rows and login windows the guide has texts for.
export const GUIDED_CLIS = HINTS.flatMap((hint) => (hint.cli ? [hint.cli] : []));

// Whether a page load needs the guide's engine: the main guide is not completed, or a tip
// is left to show with tips on.
export function leftToShow(info: { completed: boolean; tips_off: boolean; shown: string[] }): boolean {
  return !info.completed || (!info.tips_off && TIP_IDS.some((id) => !info.shown.includes(id)));
}
