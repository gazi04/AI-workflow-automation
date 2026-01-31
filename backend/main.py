from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from actions.routes.webhook_router import webhook_router
from auth.routes.auth_router import auth_router
from ai.routes.ai_router import ai_router
from workflow.routes.workflow_router import workflow_router

# The models are imported as a top level to resolve some issues
# first is the circular dependecies that the models import eachother 
# and the other issue has to do with the SQLAchemy string resolution 
# in the mapper of defining relantionships
import auth.models # noqa: F401
import user.models # noqa: F401
import workflow.models # noqa: F401

app = FastAPI(title="AI Workflow Orchestrator API")

@app.get("/")
def read_root():
    """A simple root endpoint to confirm the server is reachable."""
    return {"message": "AI Workflow Orchestrator API is running."}

@app.get("/api/status")
def api_status():
    """Endpoint to check the general status of the API."""
    return {"status": "ok", "service": "backend"}

app.include_router(auth_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(webhook_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn
    # Run the server on http://localhost:8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
