import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.cookies import CSRF_COOKIE
from core.event_listener import listener
from core.setup_logging import setup_logger
from scripts.register_renewal import register_renewal_deployment
from auth.routes import auth_router, connection_router
from ai.routes.ai_router import ai_router
from gmail.routes.webhook_router import webhook_router
from workflow.routes.workflow_router import workflow_router

# The models are imported as a top level to resolve some issues
# first is the circular dependecies that the models import eachother
# and the other issue has to do with the SQLAchemy string resolution
# in the mapper of defining relantionships
import core.models  # noqa: F401

logger = setup_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the Postgres LISTEN thread so worker-emitted node events reach
    # connected WebSockets. Pass the running loop for run_coroutine_threadsafe.
    listener.start(asyncio.get_running_loop())

    # Register the daily Gmail-watch renewal deployment. Best-effort: a Prefect
    # outage must not block API boot — the manual script remains a fallback.
    try:
        await register_renewal_deployment()
    except Exception as e:
        logger.warning(
            f"Gmail watch-renewal deployment not registered at startup: {e}"
        )

    try:
        yield
    finally:
        listener.stop()


app = FastAPI(title="AI Workflow Orchestrator API", lifespan=lifespan)

app.include_router(auth_router, prefix="/api")
app.include_router(connection_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(webhook_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")

# Paths exempt from CSRF: Pub/Sub webhooks (no cookie, verified via OIDC) and
# the OAuth callback (cross-site redirect from Google).
_CSRF_EXEMPT_PREFIXES = ("/api/webhooks", "/api/auth/callback")
_CSRF_PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def csrf_protect(request: Request, call_next):
    """Double-submit CSRF check: X-CSRF-Token header must match the csrf cookie.

    Only cookie-authenticated (browser) requests are at risk, so requests carrying
    an Authorization header (bearer clients, tests) are exempt.
    """
    if (
        request.method in _CSRF_PROTECTED_METHODS
        and not request.url.path.startswith(_CSRF_EXEMPT_PREFIXES)
        and "authorization" not in request.headers
    ):
        cookie_token = request.cookies.get(CSRF_COOKIE)
        header_token = request.headers.get("X-CSRF-Token")
        if not cookie_token or not header_token or cookie_token != header_token:
            return JSONResponse(
                status_code=403, content={"detail": "CSRF check failed"}
            )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
