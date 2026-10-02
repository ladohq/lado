"""The UI server's FastAPI app: the API under /api, the web UI's bundle on /.

Its OpenAPI schema is the one contract with the UI (web/openapi.json, from which the UI's
TypeScript types are made). Data comes only through lado.state and lado.runtime; the server
never migrates the database: another schema version answers 503.
"""

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from lado import __version__, runtime, state
from lado.server.auth import Guard

STATIC = Path(__file__).parent / "static"  # the built bundle (make web); not in git
BUILD_HINT = "build it with `make web` in a LADO checkout"


class Health(BaseModel):
    ok: bool
    version: str


class SessionInfo(BaseModel):
    name: str
    repo: str
    status: runtime.SessionStatus
    agents: int  # agents the session has now


def database() -> bool:
    """A dependency of every endpoint that reads lado.db: whether there is one. Reads its
    schema version without opening it for writing, so the server never migrates it."""
    version = state.schema_version()
    if version is not None and version != state.SCHEMA_VERSION:
        raise HTTPException(
            503,
            f"{state.home() / 'lado.db'} has schema version {version}, this server knows "
            f"{state.SCHEMA_VERSION}: upgrade LADO or restart `lado server`",
        )
    return version is not None


def bundle_missing(static: Path) -> bool:
    return not (static / "index.html").is_file()


def contract() -> dict:
    """The API's OpenAPI schema as web/openapi.json keeps it (`make web-types`): without
    LADO's version, so a release does not change it."""
    schema = create_app("", 0).openapi()
    del schema["info"]["version"]
    return schema


def create_app(token: str, port: int, static: Path = STATIC) -> FastAPI:
    guard = Guard(token, port)
    app = FastAPI(title="LADO", version=__version__)

    @app.get("/api/health")
    def health() -> Health:
        return Health(ok=True, version=__version__)

    @app.get("/api/sessions", dependencies=[Depends(guard)])
    def sessions(has_db: bool = Depends(database)) -> list[SessionInfo]:
        if not has_db:
            return []
        return [
            SessionInfo(
                name=sess.name,
                repo=sess.repo,
                status=runtime.session_status(sess),
                agents=len(state.list_agents(sess.name)),
            )
            for sess in state.list_sessions()
        ]

    @app.get("/", include_in_schema=False)
    def page(token: str | None = None):
        if token is not None:
            return guard.login(token)
        if bundle_missing(static):
            return PlainTextResponse(f"The web UI's bundle is missing: {BUILD_HINT}.", 503)
        return FileResponse(static / "index.html")

    if not bundle_missing(static):
        app.mount("/", StaticFiles(directory=static), name="static")
    return app


if __name__ == "__main__":  # `make web-types`
    import json

    print(json.dumps(contract(), indent=2))
