"""`lado stats`: how LADO was used on this machine in a period, from the usage table
(lado.state, USAGE) and LADO's error journal (lado.telemetry). Reads only, sends nothing."""

import datetime
from collections import Counter

from lado import state, telemetry

DEFAULT_DAYS = 30
WIDTH = 80  # a breakdown longer than the line wraps under itself
LABEL = 28  # the labels' column
BREAKDOWN = 2 + LABEL + 3 + 2  # where a breakdown starts: after the label and the count
UNKNOWN = "?"  # a provider or key a row does not name
NO_KIT = "@" + UNKNOWN
NO_KIT_NOTE = "(@?: kit not recorded, before 0.38.0)"
ERRORS_NOTE = "(errors.jsonl keeps only its latest part)"


def lines(days: int | None, now: datetime.datetime | None = None) -> list[str]:
    """What `lado stats` prints for the last `days` days to `now` (UTC), None: for
    everything kept."""
    now = now or telemetry.now()
    start = None if days is None else now - datetime.timedelta(days=days)
    since = "0000-01-01 00:00:00" if start is None else start.strftime("%Y-%m-%d %H:%M:%S")
    usage = state.usage_summary(since)
    # Every journal line's time is a text from 0000 on: "" takes them all.
    errors = telemetry.lado_errors("" if start is None else telemetry.format_time(start))
    earliest = state.usage_start()
    to = f"{now:%Y-%m-%d}"
    if start is None:
        head = [f"Usage of everything kept, to {to} (UTC) on this machine; nothing is sent."]
    else:
        span = f"{days} day" + ("" if days == 1 else "s")
        head = [
            f"Usage from {start:%Y-%m-%d} to {to} (UTC, {span}) on this machine; nothing is sent."
        ]
    if earliest is None:
        head.append("Earliest record: none yet.")
    elif start is None or earliest > since:
        head.append(f"Earliest record: {earliest[:10]}.")
    return [*head, "", *_groups(usage, errors)]


def _groups(usage: state.Usage, errors: int) -> list[str]:
    keys, providers = usage.keys, usage.providers
    roles = _parts(keys[state.USAGE_AGENT])
    agrees = usage.agrees[state.USAGE_GATE_CLOSE]
    advised = sum(agrees.values())
    advice = (
        _line("answered as the lead advised", agrees[1], f"of {advised} with a recommended choice")
        if advised
        else _line("answered as the lead advised", None, "no recommended choice")
    )
    return [
        "Sessions",
        _line("started", usage.count(state.USAGE_SESSION)),
        _line("resumed", usage.count(state.USAGE_RESUME)),
        "Agents",
        _line("started", usage.count(state.USAGE_AGENT), _parts(providers[state.USAGE_AGENT])),
        *_wrapped(_line("by role", None, roles), roles),
        *([" " * BREAKDOWN + NO_KIT_NOTE] if any(NO_KIT in p for p in roles) else []),
        _line(
            "ended by themselves",
            usage.count(state.USAGE_AGENT_ENDED),
            _parts(providers[state.USAGE_AGENT_ENDED]),
        ),
        *_turn_errors(usage),
        "Flow runs",
        *_counted(usage, "started", state.USAGE_RUN_START),
        _line("ended", usage.count(state.USAGE_RUN_END)),
        _line("cancelled", usage.count(state.USAGE_RUN_CANCEL)),
        "Gates and questions",
        *_counted(usage, "gates opened", state.USAGE_GATE_OPEN),
        *_counted(usage, "gates closed", state.USAGE_GATE_CLOSE),
        advice,
        _line("questions to you", usage.count(state.USAGE_QUESTION)),
        "Messages",
        _line("failed to deliver", usage.count(state.USAGE_MESSAGE_FAILED)),
        _line("dropped", usage.count(state.USAGE_MESSAGE_DROPPED)),
        "LADO",
        _line("own errors", errors, ERRORS_NOTE),
    ]


def _turn_errors(usage: state.Usage) -> list[str]:
    """Per provider, then per error kind: `claude 3 (overloaded 2, rate_limit 1)`."""
    kinds: dict[str | None, Counter] = {}
    for (provider, kind), n in usage.provider_keys[state.USAGE_TURN_ERROR].items():
        kinds.setdefault(provider, Counter())[kind] += n
    parts = [
        f"{_name(provider)} {n} ({', '.join(_parts(kinds[provider]))})"
        for provider, n in _ordered(usage.providers[state.USAGE_TURN_ERROR])
    ]
    return _counted_parts("turns ended on an error", usage.count(state.USAGE_TURN_ERROR), parts)


def _counted(usage: state.Usage, label: str, kind: str) -> list[str]:
    """A count of `kind` with its keys."""
    return _counted_parts(label, usage.count(kind), _parts(usage.keys[kind]))


def _counted_parts(label: str, count: int, parts: list[str]) -> list[str]:
    return _wrapped(_line(label, count, ", ".join(parts)), parts)


def _ordered(counts: Counter) -> list[tuple]:
    """The items of `counts` by count, the larger first, then by name."""
    return sorted(counts.items(), key=lambda item: (-item[1], _name(item[0])))


def _parts(counts: Counter) -> list[str]:
    """Each item of `counts` as shown, `<name> <n>`, in _ordered's order."""
    return [f"{_name(name)} {n}" for name, n in _ordered(counts)]


def _name(name: str | None) -> str:
    return UNKNOWN if name is None else name


def _line(label: str, count: int | None, breakdown: str | list[str] = "") -> str:
    shown = "" if count is None else str(count)
    text = breakdown if isinstance(breakdown, str) else ", ".join(breakdown)
    line = f"  {label:<{LABEL}}{shown:>3}"
    return f"{line}  {text}" if text else line


def _wrapped(line: str, parts: list[str]) -> list[str]:
    """`line` as is when it fits WIDTH, else its breakdown `parts` wrapped under itself,
    never within a part."""
    if len(line) <= WIDTH or not parts:
        return [line]
    head = line[:BREAKDOWN]
    out, current = [], ""
    for i, part in enumerate(parts):
        piece = part + ("," if i < len(parts) - 1 else "")
        if current and BREAKDOWN + len(current) + 1 + len(piece) > WIDTH:
            out.append(current)
            current = piece
        else:
            current = f"{current} {piece}" if current else piece
    out.append(current)
    return [head + out[0], *(" " * BREAKDOWN + rest for rest in out[1:])]
