from typing import List
from uuid import UUID
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.orm import Session

from jwt import PyJWTError

from auth.depedencies import get_current_user
from core.database import get_db, db_session
from core.setup_logging import setup_logger
from utils.security import decode_access_token
from orchestration.services import DeploymentService
from user.models import User
from utils.catalog_introspector import build_catalog
from workflow.schemas.catalog import WorkflowCatalog
from workflow.schemas import WorkflowSchema
from workflow.schemas.workflow_run import WorkflowRun
from workflow.schemas import (
    RunWorkflowRequest,
    UpdateWorkflowRequest,
    ToggleWorkflowRequest,
)
from workflow.services import WorkflowService, WorkflowRunService
from core.websocket_manager import manager


logger = setup_logger("Workflow Router")

workflow_router = APIRouter(prefix="/workflow", tags=["Workflow"])


@workflow_router.get("/catalog", response_model=WorkflowCatalog)
def get_catalog():
    """
    Returns a structured manifest of all available trigger and action nodes,
    including their field definitions and UI metadata (category, icon).
    Designed for the frontend catalog-driven editor to consume.
    """
    try:
        return build_catalog()
    except Exception as e:
        logger.error(f"Failed to build workflow catalog: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate workflow catalog.",
        )


@workflow_router.get("/get_workflows")
async def get_workflows(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """
    Get a list of the all the workflows from the current user
    """
    try:
        return WorkflowService.get_by_user_id(db, user.id)
    except Exception as e:
        logger.error(f"Error fetching workflows: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch the workflow.",
        )


@workflow_router.get("/get_workflow/{workflow_id}")
async def get_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        workflow = WorkflowService.get_by_id_and_user(db, workflow_id, user.id)
        if workflow is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found.",
            )
        return workflow
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not fetch the workflow {workflow_id}.",
        )


@workflow_router.post("/run")
async def run_workflow(
    request: RunWorkflowRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        workflow = WorkflowService.get_by_id_and_user(
            db, request.deployment_id, user.id
        )
        if workflow is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found.",
            )
        return await DeploymentService.run(request.deployment_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running workflow {request.deployment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not run the workflow {request.deployment_id}",
        )


@workflow_router.patch("/toggle")
async def toggle_workflow(
    request: ToggleWorkflowRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Pause or Resume a Prefect deployment and updates the status of the workflow in the database.
    """
    try:
        if (
            WorkflowService.get_by_id_and_user(db, request.deployment_id, user.id)
            is None
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found.",
            )

        WorkflowService.update_is_active(db, request.deployment_id, request.status)

        result = await DeploymentService.toggle_workflow(
            deployment_id=request.deployment_id, active=request.status
        )

        db.commit()  # we commit the database changes here because of sequential dependencies between service and manager
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling workflow {request.deployment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not toggle workflow {request.deployment_id}.",
        )


@workflow_router.post("/create")
async def create_workflow(
    schema: WorkflowSchema,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Register a new workflow in Prefect and save it to the local database.
    """
    try:
        deployment_id = await DeploymentService.create_deployment_for_workflow(
            user.id, schema
        )

        new_workflow = WorkflowService.create(
            db=db, workflow_id=deployment_id, user_id=user.id, schema=schema
        )

        return new_workflow
    except Exception as e:
        logger.error(f"Error creating workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create the workflow.",
        )


@workflow_router.patch("/update-config")
async def update_workflow_config(
    request: UpdateWorkflowRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Update the parameters/config of a specific Prefect deployment and also it's workflow corresponding entity.
    """
    try:
        if (
            WorkflowService.get_by_id_and_user(db, request.deployment_id, user.id)
            is None
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found.",
            )

        workflow_config_dict = request.schema.execution_config.model_dump(
            by_alias=True, exclude_none=True
        )
        WorkflowService.update_config(db, request.deployment_id, request.schema)

        result = await DeploymentService.update_workflow_config(
            deployment_id=request.deployment_id, new_params=workflow_config_dict
        )

        db.commit()  # we commit the config update here because of sequential dependencies between service and manager
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating config for {request.deployment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not update the workflow {request.deployment_id}.",
        )


@workflow_router.delete("/delete")
async def delete_workflow(
    deployment_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Deletes a workflow from the database and deletes it's deployment from Prefect
    """
    try:
        if WorkflowService.get_by_id_and_user(db, deployment_id, user.id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found.",
            )

        WorkflowService.delete_by_id(db, deployment_id)
        await DeploymentService.delete(deployment_id)
        db.commit()  # to actually commit the changes to the database
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting workflow {deployment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete workflow.",
        )


@workflow_router.get("/histories", response_model=List[WorkflowRun])
async def get_workflow_histories(user: User = Depends(get_current_user)):
    """Fetches the history of all the deployments of the user"""
    try:
        return await DeploymentService.get_history(user.id)
    except Exception as e:
        logger.error(f"Error fetching deployment historeis for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch the workflow histories.",
        )


@workflow_router.get("/{deployement_id}/history", response_model=List[WorkflowRun])
async def get_workflow_history(
    deployement_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetches only the history for a specific deployment"""
    try:
        if WorkflowService.get_by_id_and_user(db, deployement_id, user.id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found.",
            )

        return await DeploymentService.get_workflow_history(deployement_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching history for deployment {deployement_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch the history of the workflow.",
        )


@workflow_router.get("/runs/latest", response_model=List[WorkflowRun])
async def get_latest_runs(user: User = Depends(get_current_user)):
    """
    Lightweight endpoint for frontend polling.
    Checks the most recent runs to trigger toast notifications.
    """
    try:
        return await DeploymentService.get_latest_runs_status(user.id)
    except Exception as e:
        logger.error(f"Error fetching latest runs for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch latest run status.",
        )


@workflow_router.get("/runs/{run_id}/logs")
async def get_run_logs(run_id: UUID, user: User = Depends(get_current_user)):
    """
    Fetches the full terminal logs for a specific execution.
    Used when a user clicks the 'Eye' icon or 'View Logs' button.
    """
    try:
        if not await DeploymentService.user_owns_run(run_id, user.id):
            # 404 (not 403) so we don't leak the existence of another user's run.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found.",
            )

        return await DeploymentService.get_run_logs(run_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching logs for run {run_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve logs for this run.",
        )


@workflow_router.websocket("/ws/workflows/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    # Authenticate from a ?token= query param (WebSockets can't use the bearer
    # Depends easily). The user_id is taken from the verified token, never the
    # path: reject if the token is missing/invalid or doesn't match the path.
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    try:
        payload = decode_access_token(token)
    except PyJWTError:
        await websocket.close(code=1008)
        return

    token_user_id = payload.get("sub")
    if token_user_id is None or token_user_id != user_id:
        await websocket.close(code=1008)
        return

    await manager.connect(user_id, websocket)
    uid = UUID(user_id)
    try:
        # Initial run snapshot so a (re)connecting client isn't blank.
        try:
            latest_runs = await DeploymentService.get_latest_runs_status(uid)
            await manager.broadcast_to_user(
                user_id,
                {
                    "type": "workflow_update",
                    "data": [run.model_dump(mode="json") for run in latest_runs],
                },
            )
        except Exception as e:
            logger.error(f"Initial run snapshot failed for user {user_id}: {e}")

        # Replay failures that occurred while this user had no socket connected.
        # Live per-node events now arrive via the Postgres LISTEN listener
        # (core/event_listener.py) — no per-connection poll loop.
        try:
            with db_session() as db:
                failed_runs = WorkflowRunService.get_undelivered_failures(db, uid)
                for record in failed_runs:
                    for node_id, result in (record.node_results or {}).items():
                        if result.get("status") != "failed":
                            continue
                        await manager.broadcast_to_user(
                            user_id,
                            {
                                "type": "node_failed",
                                "workflow_id": str(record.workflow_id),
                                "run_id": str(record.id),
                                "node_id": node_id,
                                "error": result.get("error"),
                            },
                        )
                if failed_runs:
                    WorkflowRunService.mark_notified(
                        db, [record.id for record in failed_runs]
                    )
        except Exception as e:
            logger.error(f"Failure replay failed for user {user_id}: {e}")

        # Keep the socket open; the global listener pushes live events. Reading
        # blocks until the client disconnects (and drains any pings/messages).
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.warning(f"WebSocket disconnected for user {user_id}")
    finally:
        manager.disconnect(user_id, websocket)
