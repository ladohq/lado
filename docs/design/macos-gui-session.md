# macOS: агенты LADO в графической сессии, также при запуске по ssh

Версия: фикс, 0.32.1. Статус: требования согласованы с человеком, код не начат.

## Проблема

После `lado update`, запущенного в терминале по ssh, ни один агент Claude Code не
работает: `authentication_failed`, в окне агента `Not logged in · Please run /login` и
`Run in another terminal: security unlock-keychain`. `claude`, запущенный в Terminal.app
(локально или через Screen Sharing), работает.

### Причина (проверено на хосте 10.73.10.235, macOS, tmux 3.7c, Claude Code 2.1.296)

- Claude Code на macOS хранит OAuth-токен в login keychain (`Claude Code-credentials`).
- macOS выдаёт доступ к login keychain только процессам графической security session
  (audit session) пользователя. Процесс из ssh живёт в своей audit session, и keychain
  там закрыт: `security find-generic-password -s "Claude Code-credentials" -w` из ssh
  выходит с кодом 36 (`errSecInteractionNotAllowed`), запись при этом находится (без `-w` код 0).
- Audit session наследуется от родителя, не от переменных окружения. Окно tmux порождает
  tmux-сервер, а не клиент, поэтому агент получает сессию **tmux-сервера LADO**.
  `agent_env` (`$SHELL -ilc`) здесь ничего не меняет: окружение то же, сессия другая.
- `lado update` останавливает все сессии; tmux-сервер `lado` при этом выходит (последняя
  сессия ушла, `exit-empty` по умолчанию on). Затем LADO возобновляет сессии и UI-сервер
  из вызвавшего процесса, то есть из ssh: новый tmux-сервер оказывается в SSH-сессии, и
  все агенты теряют доступ к keychain. Молча.
- Тот же эффект от `lado stop --all` + `lado start` по ssh вручную или первого `lado start`
  по ssh после перезагрузки. Апдейт делает это неявно, поэтому ловушка в первую очередь его.
- Факты с хоста: у нового tmux-сервера (`tmux -L lado`) и `lado server` в окружении
  `SSH_CONNECTION=10.73.112.3 …`; у работающего `claude` в Terminal.app
  `SECURITYSESSIONID=186bb`, `TERM_PROGRAM=Apple_Terminal`.

## Эксперименты (все из ssh-сессии на хосте)

| Как запущен процесс | keychain (`-w`) | флаги audit session |
|---|---|---|
| напрямую из ssh | код 36 | `0x5020` |
| задание launchd: `launchctl bootstrap gui/<uid> <plist>` | код 0 | `0x6030` |
| `launchctl submit` (устаревшее, по умолчанию KeepAlive) | код 0 | — |
| `launchctl asuser <uid> …` без root | `Operation not permitted` | — |
| нынешний tmux-сервер LADO на хосте (через `tmux run-shell`) | — | `0x5020` |

Флаги (`ai_flags` из `getaudit_addr`, `<bsm/audit.h>`):
`0x0010 HAS_GRAPHIC_ACCESS`, `0x0020 HAS_TTY`, `0x1000 IS_REMOTE`,
`0x2000 HAS_CONSOLE_ACCESS`, `0x4000 HAS_AUTHENTICATED`. SSH: `0x5020`. GUI: `0x6030`.

Цепочка, которая решает задачу (проверена):

1. Из ssh: `launchctl bootstrap gui/<uid>` задания с
   `ProgramArguments = [<абсолютный путь tmux>, -L, <socket>, start-server, ;, set-option, -g, exit-empty, off]`,
   `RunAtLoad = true`, `AbandonProcessGroup = true`.
2. Дождаться сервера: `tmux -L <socket> list-sessions` сначала даёт `error connecting to …`,
   через ~0.1 с работает (с `exit-empty off` пустой сервер живёт).
3. `launchctl bootout gui/<uid>/<label>`: сервер остаётся жить.
4. Из ssh `tmux -L <socket> new-session …` и `new-window …`: процессы в окнах получают
   доступ к keychain (код 0), хотя клиент был в ssh.
5. `tmux -L s set -g exit-empty on \; new-session …` с ошибкой в new-session: сервер
   выходит сам. Значит, после первой сессии `exit-empty` возвращаем в on, и сервер
   ведёт себя как сейчас (выходит без сессий), пустых серверов не остаётся.

Ещё факты:

- `launchctl print gui/<uid>`: код 0, когда пользователь вошёл в графическую сессию
  (локально или Screen Sharing), код 112, когда GUI-домена нет.
- `tmux -L <socket> run-shell "<cmd>"` печатает вывод команды клиенту. Так читаются флаги
  audit session уже работающего tmux-сервера: команду запускает сервер.
- `getaudit_addr` доступен через `ctypes.CDLL(None)`; структура 48 байт:
  `auid u32; mask {u32, u32}; termid {int32 port, u32 type, u32 addr[4]}; asid int32; flags u64`.
- Окружение tmux-сервера из launchd минимальное: `PATH=/usr/bin:/bin:/usr/sbin:/sbin`,
  `HOME`, `USER`, `LOGNAME`, `SHELL`, `TMPDIR`, `SSH_AUTH_SOCK` (launchd), **`LANG` пуст,
  локаль C**. Нужно передать в plist (`EnvironmentVariables`) хотя бы `LANG`, `LC_ALL`,
  `LC_CTYPE` и `TMUX_TMPDIR` (иначе клиент и сервер могут разойтись в пути сокета) из
  окружения вызывающего, если они заданы.

## Варианты окружения

Определяются по флагам audit session текущего процесса и наличию GUI-домена,
**не** по переменным (`SSH_CONNECTION`, `SECURITYSESSIONID`, `TERM_PROGRAM`): в задании
launchd их нет, а в tmux они бывают унаследованы.

| Место | Как узнать | Что делает LADO при запуске tmux-сервера |
|---|---|---|
| не macOS (Linux и др.) | `sys.platform != "darwin"` | как сейчас, ничего нового |
| macOS, GUI (Terminal.app локально или через Screen Sharing; они неотличимы и не нужно) | `HAS_GRAPHIC_ACCESS` | как сейчас (`new-session` поднимает сервер) |
| macOS, не GUI (ssh, cron и т. п.), GUI-домен есть | нет флага, `launchctl print gui/<uid>` = 0 | сервер через launchd в `gui/<uid>` |
| macOS, не GUI, GUI-домена нет (никто не вошёл после перезагрузки) | нет флага, код ≠ 0 | как сейчас + громкое предупреждение (ниже) |
| флаги прочитать не удалось | ошибка ctypes/вызова | как сейчас, `doctor` пишет `not checked` |

## Требования

### R1. Модуль места процесса (новый, напр. `src/lado/gui_session.py`)

- `place()` → одно из `OTHER`, `GUI`, `REMOTE` (не GUI, домен есть), `NO_GUI`, `UNKNOWN`
  для текущего процесса; только стандартная библиотека (`ctypes`, `subprocess`).
- `server_place(socket)` → место уже работающего tmux-сервера LADO: `tmux run-shell`
  с LADO-шным Python `-I -c <проба флагов>`; `None`, когда сервера нет.
- Переменная только для тестов, как `LADO_UPDATE_*`: `LADO_MACOS_PLACE=gui|remote|no-gui`
  подменяет флаги и домен текущего процесса.

### R2. Запуск tmux-сервера (`tmux.py`, место запуска: `tmux.new_session`, его зовёт `runtime.start_session`)

- Перед `new-session`: если сервера на сокете нет и `place() == REMOTE`, поднять его через
  launchd (цепочка выше): plist через `plistlib` во временный файл под `LADO_HOME`, label
  уникальный (сокет + pid), абсолютный путь tmux по PATH из `clean_env()`, переменные
  из R-фактов выше, ожидание сокета с таймаутом, `bootout`, удаление plist всегда
  (также при ошибке).
- `new_session` в цепочке ставит `set-option -g exit-empty on` перед `new-session`, чтобы
  поднятый через launchd сервер дальше жил как обычный (уходит с последней сессией;
  если `new-session` упал, сервер уходит сразу).
- Гонка двух стартов (два `lado start` / UI): второй `bootstrap` с другим label поднимает
  `start-server` на уже живом сокете, это безвредно; ошибка bootstrap не ошибка, если
  сервер после неё есть.
- Если launchd не удался (код ≠ 0, таймаут): старт продолжается как сейчас, с
  предупреждением (R4) и строкой в `loop.log`.
- В остальных местах ничего не менять: просмотрщики UI (`new_viewer`) и окна воркеров
  создаются на уже живом сервере.

### R3. `lado update` и UI-обновление

- Специальной логики не нужно: после остановки сессий сервер выходит, возобновление
  из ssh поднимает новый через R2. Проверить именно этот сценарий вручную на хосте.
- План обновления (`self_update.plan`, `print_plan`, API `UpdatePlan`) говорит, где
  возобновятся агенты, когда `place()` не `OTHER`/`GUI`: `REMOTE` → «tmux server will be
  started in the graphical session (launchd)», `NO_GUI` → предупреждение из R4.

### R4. Предупреждение о keychain (No silent drops)

- Провайдер говорит, нужен ли его агенту login keychain macOS: новый метод в
  `providers/base.py`, напр. `keychain_login(env) -> bool`, по умолчанию False.
  Claude Code: True на darwin, если в окружении агента нет `CLAUDE_CODE_OAUTH_TOKEN` и
  `ANTHROPIC_API_KEY`. Kilo, OpenCode: False (файлы). Codex: False, но с пометкой в
  BACKLOG.md (`cli_auth_credentials_store = "keyring"` не проверяется).
- При запуске агента (start, resume, spawn; рядом с `_first_hook_blocker` в `runtime.py`)
  на macOS, если провайдеру нужен keychain, а место сервера (`server_place`, или для
  ещё не поднятого — то, что сделает R2) не GUI: предупреждение в `Launch.warnings`
  (`lado start` на stderr, UI `Started.warnings`, `spawn_worker` warnings и `loop.log`).
  Тексты:
  - сервер уже работает вне GUI (поднят по ssh прежним LADO): «LADO's tmux server runs
    outside the graphical session, so Claude Code cannot read its login from the
    Keychain: run `lado stop --all`, then start the sessions again (from ssh too)».
  - `NO_GUI`: «nobody is logged in to the graphical session, so Claude Code cannot read
    its login from the Keychain: log in on the Mac (Screen Sharing works), or set
    `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token`) in your login shell».
- Агент при этом запускается (решение человека: предупредить, не отказывать).

### R5. `lado doctor` и панель System в UI

- Новая проверка только на macOS, напр. «Graphical session»: место текущего процесса,
  GUI-домен, место tmux-сервера LADO, если он работает.
  OK: сервер в GUI, или сервера нет и `place()` `GUI`/`REMOTE`. WARN: сервер вне GUI
  или `NO_GUI` (с текстами R4). INFO: `UNKNOWN`. На Linux проверки нет.
- `doctor.system_info` (панель System) получает то же место; в текст отчёта для issue —
  только вид места, без адресов.

### R6. Документация

- AGENTS.md: `tmux.py` и новый модуль в Layout; в How agents talk — пункт про audit
  session на macOS (сервер через launchd, когда процесс не в GUI; что наследует агент).
- README/docs: запуск по ssh на Mac работает, если пользователь вошёл в графическую
  сессию; иначе `CLAUDE_CODE_OAUTH_TOKEN`.
- CHANGELOG `## 0.32.1 (unreleased)`: «On macOS, agents started over ssh (also by
  `lado update`) run in the graphical session, so Claude Code reads its login from the
  Keychain; LADO warns when it cannot».
- BACKLOG.md: Codex с keyring; сессия на macOS без GUI-входа.

## Тесты

- Unit: `place()` на подменённых флагах и коде `launchctl`; разбор структуры
  `getaudit_addr`; argv `launchctl` и содержимое plist (recorder); цепочка `new_session`
  с `exit-empty on`; удаление plist при ошибке; `keychain_login` Claude Code по env;
  предупреждения R4 в `Started.warnings` и `spawn_worker`; doctor-проверка по каждому месту.
- Integration (только macOS, `skipif sys.platform != "darwin"`; в CI на Linux пропуск):
  `LADO_MACOS_PLACE=remote`, свой сокет: `lado start` с fake-агентом поднимает сервер
  через launchd; `server_place` сервера — GUI; после остановки последней сессии сервер
  выходит; label задания в `launchctl list` не остаётся.
- Вручную на хосте 10.73.10.235 по ssh: `lado update` (или `lado stop --all` +
  `lado start`) → агент Claude Code отвечает, не `Not logged in`; `lado doctor`
  показывает место; с `LADO_MACOS_PLACE=no-gui` — предупреждение.

## Состояние хоста (на 2026-10-10)

- Нынешний tmux-сервер `lado` и `lado server` (pid 73279, `--host 0.0.0.0 --port 8000`)
  подняты из ssh: агенты Claude Code там не залогинены. Обойти до фикса: в Terminal.app
  (Screen Sharing) `lado stop --all`, остановить UI-сервер, убедиться, что
  `tmux -L lado ls` пуст, затем `lado ui --host 0.0.0.0 --port 8000 --no-open`.
- Остаток live-теста со 2026-10-08: `tmux -L lado-test-ba75ff42` с opencode
  (pid 38283, 38335) и `/private/tmp/claude-501/rev-68699/srv.py` (pid 68719): можно убить.
