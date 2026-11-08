# LAD-239 new-session-window: review report

Pull request #257 `feature/lad-239-new-session-window` → `main`. Scale: full. Head reviewed:
`ce135dbc`. The New session window is rebuilt as place → task → team: one list of recent places
and other ways in, the task second, the team as one line, a footer that says what is missing, and
a Resume mode beside a stopped session; a plain folder outside git is set up (a preview of the
first commit and of what is left out, written to `.gitignore`) by the window's one button. Delta:
the new capabilities `folder-setup` and `new-session-window`, and changes to `launch-notes`,
`model-context`, `model-settings-page`, `phone-layout`, `projects`, `provider-logins`,
`repos-folder`, `session-clone`, `session-first-message`, `session-folder`, `session-model`,
`session-scratch`, `stopped-session`.

## Rounds

1. Local, breadth, `origin/main...e1b3d5c9`: lenses spec, tests, silent failures / general (web)
   and the architecture against AGENTS.md; core and server read by hand, screenshots held against
   the mockup. Found F1–F17; F18, F19 refuted.
2. Local, precision, `e1b3d5c9..190cb0a4`: no new finding. Then two external rounds:
   - external 1, Claude Code GitHub Action, read the server and core: F21–F23 minor, F20, F24
     refuted;
   - external 2 read the web window whole, `models.py` and the providers' diff: F25 important,
     F26–F29 minor, F30 refuted.
3. Local, precision, `190cb0a4..c05db3d2`, with CI's results: F31 (CI red on `ui (1)`).
4. Local, precision, `c05db3d2..ce135dbc`: the fix of F31 and the merge of main (LAD-238, the
   Settings pages); the conflicts resolved correctly (`agentClisPath(name)` carried onto the new
   window code, the phone-layout delta takes Help from main). No new finding.

External rounds used: 2 of 2. Stand-ins: 0.

Correction to rounds 1–2: "no red" was recorded while CI still ran; the runs on `e1b3d5c9` and
`190cb0a4` were red (F31), found and returned in round 3.

## The human's decisions

- **Gate `merge_ok`, approved** with no comment: F15, F16, F17, F21, F22, F23, F26, F27 and F28
  stay declined.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | blocker | A path typed with `~` failed the check: the server expands `~`, the window compared text | fixed in `88f3ed09`, test |
| F2 | important | A recheck of a folder outside git: endless "Counting files…" on an error, focus lost to body, "Checking…" unreachable | fixed in `88f3ed09`, two tests |
| F3 | important | The scenario "While counting" unreachable on the first check, no test | fixed in `d2c8368d`, `88f3ed09` |
| F4 | important | A secret with a newline in its name went into the commit | fixed in `88f3ed09` (`odd_name`), test |
| F5 | important | A non-UTF-8 name of a left-out file gave 500 | fixed in `88f3ed09`, two tests |
| F6 | important | The `.gitignore` escaping had no test: a mutation passed all 37 tests | fixed, test |
| F7 | important | folder-setup items without tests: refusal after set-up, a taken name, the signature, hooks, the branch | fixed, three tests |
| F8 | important | The TS window repeated the core's quoting and escaping (a second source of truth) | fixed in `88f3ed09` (`LeftOutInfo.line`, `SetupInfo.make`, `max_files`) |
| F9 | important | The footer was silent while agents load or when their load failed | fixed in `88f3ed09` / `190cb0a4`, tests |
| F10 | important | Enter started a new session where the blue button was Resume | fixed in `88f3ed09`, test |
| F11 | important | The draft did not keep the model | fixed in `88f3ed09`, test |
| F12 | important | The folder-setup spec lagged the code; the footer text for `unreadable` | fixed |
| F13 | minor | Stale ticks were sent | fixed, test |
| F14 | minor | The time in a Recent row differed from the spec | fixed (spec) |
| F15 | minor | The set-up preview also runs for subfolder suggestions | declined: bounded by the 20 000-file threshold and a 200 ms debounce |
| F16 | minor | `InfoTip` is not in the top layer and does not follow a scroll | declined: cosmetic, D10's behaviours work |
| F17 | minor | Small test gaps: symlinks, `recent_folders` branches, set-up of an empty folder through the API | declined: low risk |
| F18 | — | A taken name is not refused before the click | refuted: the requirement does not ask it; 409 sets `aria-invalid` |
| F19 | — | The signature of `free_name` (D3) | refuted: the same result |
| F20 | — | external: `setup.make` on a missing path falls past `SetupError` | refuted: `ScratchError` gives 400, checked by a run |
| F21 | minor | external: a `.gitignore` directory gives 500 | declined: does not occur in a real folder |
| F22 | minor | external: a file gone between the listing and `lstat` gives 500 | declined: a recheck passes |
| F23 | minor | external: a file appearing between the preview and `git add -A` | declined: a window of milliseconds |
| F24 | — | external: a tab in a name, `free_name`, the pass of `recent_folders` | refuted: no defect |
| F25 | important | external: Resume beside a stopped session silently changed its settings | fixed in `c05db3d2`: only the `touched` fields count; tests red before the fix |
| F26 | minor | external: a 409 on Resume reads as a name conflict | declined: a rare race |
| F27 | minor | external: on the first run focus goes to New empty folder | declined: first run only |
| F28 | minor | external: `InfoTip` in Safari, Esc closes the whole window | declined: the draft is not lost |
| F29 | minor | external: `key` through a spread in JSX | fixed in `c05db3d2` |
| F30 | — | external: `cli` on mount, `mode_words` | refuted: unreachable, both builders of `ProviderInfo` pass the field |
| F31 | important | CI red on `ui (1)`: the set-up's UI test put the `server` fixture before `git_config`, the server had no git author | fixed in `3013760a`; red with `GIT_CONFIG_GLOBAL=/dev/null` before the fix |

## Checks

| Check | Head | Result |
|---|---|---|
| CI of the pull request, required `ci-ok` | `ce135dbc` | green: 23 of 23, ui ×2, smoke of every provider on Linux and macOS, container |
| `make lint` | `ce135dbc` | clean |
| `openspec validate new-session-window --strict`; `--specs --strict`; trial archive | `ce135dbc` | valid; 80 passed; 82 passed |
| `openspec validate --specs --strict` after the archive | archive commit | 82 passed |

## Metrics

Rounds: 4 local (1 breadth, 3 precision), 2 external, 0 stand-in. Local: 18 confirmed (F1–F17,
F31), 2 refuted. External: 8 confirmed, 3 refuted. Findings in code changed by the developer's
cleanup (`f92b1b4f`, before round 1): not measured; F4, F5 and F8 lie in `setup.py` and
`LaunchSetup.tsx`, which it touched.

## What was not checked

- `providers/` (`base.py`, `claude.py`, `codex.py`, `opencode_family.py`: the permission modes'
  words) and `runtime.py` (`free_name`, the `last_any` step) changed; the live tests were not run.
  Smoke was green for all four providers.
- The fixes of F25 and F31 and the merge of main were read only by the local precision pass; the
  external reviewer's round cap was used up. It is the same model family.
- The developer reported one UI flake in Settings brought from main: it passes on a rerun alone;
  not in the pull request's CI, not reproduced by the reviewer.

## Found on the way

None.
