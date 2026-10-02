"""The UI server's FastAPI app: the API under /api, the web UI's bundle on /.

Its OpenAPI schema is the one contract with the UI (web/openapi.json, from which the UI's
TypeScript types are made). Data comes only through lado.state and lado.runtime; the server
never migrates the database: another schema version answers 503.
"""

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
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

    if (static / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def page(path: str, request: Request):
        """A file of the bundle, or for any other path the UI's page, whose router shows it.
        A path under /api or one that names a file (has an extension) is never the page: an
        open tab asking for a file an upgrade removed gets 404, not HTML."""
        if path == "api" or path.startswith("api/") or path.startswith("assets/"):
            raise HTTPException(404)
        if "token" in request.query_params:
            return guard.login(request)
        file = bundle_file(static, path)
        if file is not None:
            return FileResponse(file)
        if "." in path.rsplit("/", 1)[-1]:
            raise HTTPException(404)
        if bundle_missing(static):
            return PlainTextResponse(f"The web UI's bundle is missing: {BUILD_HINT}.", 503)
        return FileResponse(static / "index.html")

    return app


def bundle_file(static: Path, path: str) -> Path | None:
    """The file `path` names in the bundle's top folder (favicon and the like), if any."""
    if not path or "/" in path:
        return None
    file = (static / path).resolve()
    if file.parent != static.resolve() or not file.is_file():
        return None
    return file


if __name__ == "__main__":  # `make web-types`
    import json

    print(json.dumps(contract(), indent=2))
