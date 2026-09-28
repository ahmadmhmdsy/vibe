from fastapi import FastAPI
from vibe.config import Settings

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="vibe")
    app.state.settings = settings

    @app.get("/health")
    def health():
        return {"status": "ok"}

    from vibe.api.routes import sessions, chat, catalog
    app.include_router(sessions.router)
    app.include_router(chat.router)
    app.include_router(catalog.router)

    return app
