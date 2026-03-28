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
import asyncio

from auth.depedencies import get_current_user
from core.database import get_db
from core.setup_logging import setup_logger
from orchestration.services import DeploymentService
from user.models import User
from utils.catalog_introspector import build_catalog
from workflow.schemas.catalog import WorkflowCatalog
from workflow.schemas.workflow_run import WorkflowRun
from workflow.schemas import (
    RunWorkflowRequest,
    UpdateWorkflowRequest,
    ToggleWorkflowRequest,
    CreateWorkflowRequest,
)
from workflow.services import WorkflowService
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
        return WorkflowService.get_by_id(db, workflow_id)
    except Exception as e:
        logger.error(f"Error fetching workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not fetch the workflow {workflow_id}.",
        )


@workflow_router.post("/run")
async def run_workflow(request: RunWorkflowRequest):
    try:
        # todo: validated the request
        return await DeploymentService.run(request.deployment_id)
    except Exception as e:
        logger.error(f"Error running workflow {request.deployment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not run the workflow {request.deployment_id}",
        )


@workflow_router.patch("/toggle")
async def toggle_workflow(
    request: ToggleWorkflowRequest, db: Session = Depends(get_db)
):
    """
    Pause or Resume a Prefect deployment and updates the status of the workflow in the database.
    """
    try:
        WorkflowService.update_is_active(db, request.deployment_id, request.status)

        result = await DeploymentService.toggle_workflow(
            deployment_id=request.deployment_id, active=request.status
        )

        db.commit()  # we commit the database changes here because of sequential dependencies between service and manager
        return result
    except Exception as e:
        logger.error(f"Error toggling workflow {request.deployment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not toggle workflow {request.deployment_id}.",
        )


@workflow_router.post("/create")
async def create_workflow(
    request: CreateWorkflowRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Register a new workflow in Prefect and save it to the local database.
    """
    try:
        deployment_id = await DeploymentService.create_deployment_for_workflow(
            user.id, request.workflow_definition
        )

        new_workflow = WorkflowService.create(
            db=db,
            workflow_id=deployment_id,
            user_id=user.id,
            name=request.name,
            description=request.description,
            workflow_definition=request.workflow_definition.model_dump(),
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
        workflow_config_dict = request.config.model_dump(
            by_alias=True, exclude_none=True
        )
        WorkflowService.update_config(db, request.deployment_id, workflow_config_dict)

        result = await DeploymentService.update_workflow_config(
            deployment_id=request.deployment_id, new_params=workflow_config_dict
        )

        db.commit()  # we commit the config update here because of sequential dependencies between service and manager
        return result
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
        WorkflowService.delete_by_id(db, deployment_id)
        await DeploymentService.delete(deployment_id)
        db.commit()  # to actually commit the changes to the database
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
    deployement_id: UUID, user: User = Depends(get_current_user)
):
    """Fetches only the history for a specific deployment"""
    try:
        return await DeploymentService.get_workflow_history(deployement_id)
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
        # Note: In a production app, you might want to verify
        # that this run_id actually belongs to the current user.
        return await DeploymentService.get_run_logs(run_id)
    except Exception as e:
        logger.error(f"Error fetching logs for run {run_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve logs for this run.",
        )


@workflow_router.post("/test-notification/{user_id}")
async def test_notification(user_id: str, message: str = "Test notification"):
    """
    Push a test notification to a specific user via WebSocket.
    """
    await manager.broadcast_to_user(
        user_id, {"type": "notification", "message": message}
    )
    return {"status": "success", "message_sent": message}


@workflow_router.websocket("/ws/workflows/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            try:
                uid = UUID(user_id)
                latest_runs = await DeploymentService.get_latest_runs_status(uid)

                # Makes the websocket connection available for multiple tabs open at once
                await manager.broadcast_to_user(
                    user_id,
                    {
                        "type": "workflow_update",
                        "data": [run.model_dump(mode="json") for run in latest_runs],
                    },
                )
            except Exception as e:
                logger.error(f"Error in WebSocket loop for user {user_id}: {e}")
                break

            await asyncio.sleep(5)
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
        logger.info(f"WebSocket disconnected for user {user_id}")
    finally:
        manager.disconnect(user_id, websocket)
        logger.info(f"WebSocket fully cleaned up for user {user_id}")
