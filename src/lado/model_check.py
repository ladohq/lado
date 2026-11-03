"""The check of a model chosen for a session against its CLI (`lado start --model`, the
launch window): an alias of the CLI or a name of its own list starts; a name the list lacks
is refused; a CLI that gives no list starts with a warning. The one rule; the CLI, the API
and the UI show its text."""

from collections.abc import Mapping
from dataclasses import dataclass

from lado import providers
from lado.providers import base

DEFAULT, OK, WARN, REFUSED = "default", "ok", "warn", "refused"


@dataclass(frozen=True)
class Verdict:
    kind: str  # DEFAULT (no model), OK, WARN or REFUSED
    text: str  # for the human, one line
    page: str = ""  # a refusal's line naming no command, for Settings → Models ("": text)


def check(provider: providers.Provider, model: str, env: Mapping[str, str]) -> Verdict:
    """The verdict on `model` for `provider`'s CLI, whose list is read with the agents'
    environment `env`; "" is the CLI's default and reads no list."""
    if not model:
        return verdict(provider, model, base.ModelList())
    return verdict(provider, model, provider.model_list(env))


def verdict(
    provider: providers.Provider, model: str, listed: base.ModelList, whose: str | None = None
) -> Verdict:
    """The verdict on `model` against `listed`, the CLI's aliases and list, or another's
    list named `whose` (a model server's, lado.model_settings)."""
    title = provider.title
    whose = whose or title
    if not model:
        return Verdict(DEFAULT, f"empty: {title}'s default model; type or pick one of its models")
    if model in listed.aliases:
        return Verdict(OK, f"an alias of {title}")
    if listed.models is None:
        return Verdict(
            WARN,
            f"{listed.why}: LADO cannot check {model}; a wrong name stops its agents at their "
            "first turn",
        )
    if model in listed.models:
        return Verdict(OK, f"in {whose}'s list of models")
    return Verdict(
        REFUSED,
        f"{model} is not in {whose}'s list of models; {listed.command} prints the list",
        f"{model} is not in {whose}'s list of models",
    )
