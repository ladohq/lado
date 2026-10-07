"""LADO: Layered Agent Delegation & Orchestration."""


def __getattr__(name: str) -> str:
    # `__version__` is read from the package's metadata only when asked for: importing
    # importlib.metadata alone costs every LADO process (each hook) 15-20 ms. Read it as
    # `lado.__version__` where it is used, not `from lado import __version__` at the top.
    if name == "__version__":
        from importlib.metadata import version

        globals()["__version__"] = found = version("lado")
        return found
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
