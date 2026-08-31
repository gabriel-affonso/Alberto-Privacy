import hmac

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import alberto_bridge, accounts, cases, companies, discovery, health, portals, provenance, requests, responses
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    @app.middleware("http")
    async def configured_token_auth(request: Request, call_next):
        # Local-only deployments can leave the token empty. Any remotely exposed deployment must set it.
        if settings.privacy_api_token and request.url.path != "/health" and not request.url.path.startswith("/alberto/"):
            supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
            if not hmac.compare_digest(supplied, settings.privacy_api_token):
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)

    app.include_router(health.router)
    app.include_router(companies.router)
    app.include_router(accounts.router)
    app.include_router(discovery.router)
    app.include_router(requests.router)
    app.include_router(cases.router)
    app.include_router(responses.router)
    app.include_router(provenance.router)
    app.include_router(portals.router)
    app.include_router(alberto_bridge.router)

    return app


app = create_app()
