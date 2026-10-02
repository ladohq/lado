"""The UI server: one per LADO_HOME, the API under /api and the web UI's bundle (`lado ui`,
`lado server`). `auth` checks who may call it, `app` is the FastAPI app, `run` finds, starts
and stops the server process."""
