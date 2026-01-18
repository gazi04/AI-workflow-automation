from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.depedencies import get_current_user
from core.database import get_db
from core.setup_logging import setup_logger
from orchestration.services import DeploymentService
from user.models.user import User
from workflow.schemas.delete_workflow_request import DeleteWorkflowRequest
from workflow.schemas.run_workflow_request import RunWorkflowRequest
from workflow.services import WorkflowService
from workflow.schemas import UpdateWorkflowRequest, ToggleWorkflowRequest


logger = setup_logger("Workflow Router")

workflow_router = APIRouter(prefix="/workflow", tags=["Workflow"])


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
        logger.error(
            f"Unexpected error occurred in the get_workflows endpoint with message: \n{e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )


@workflow_router.post("/run")
async def run_workflow(request: RunWorkflowRequest):
    try:
        # todo: validated the request
        return await DeploymentService.run(request.deployment_id)
    except Exception as e:
        raise e


@workflow_router.patch("/toggle")
async def toggle_workflow(
    request: ToggleWorkflowRequest, db: Session = Depends(get_db)
):
    """
    Pause or Resume a Prefect deployment and updates the status of the workflow in the database.
    """
    try:
        WorkflowService.update_is_active(
            db, request.deployment_id, request.status
        )

        result = await DeploymentService.toggle_workflow(
            deployment_id=request.deployment_id, active=request.status
        )

        db.commit()  # we commit the database changes here because of sequential dependencies between service and manager
        return result
    except Exception as e:
        logger.error(f"Error toggling workflow {request.deployment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
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
        WorkflowService.update_config(db, user.id, request.config)

        result = await DeploymentService.update_workflow_config(
            deployment_id=request.deployment_id, new_params=request.config
        )

        db.commit()  # we commit the config update here because of sequential dependencies between service and manager
        return result
    except Exception as e:
        logger.error(f"Error updating config for {request.deployment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )


@workflow_router.delete("/delete")
async def delete_workflow(
    request: DeleteWorkflowRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Deletes a workflow from the database and deletes it's deployment from Prefect
    """
    try:
        WorkflowService.delete_by_id(db, request.deployment_id)
        await DeploymentService.delete(request.deployment_id)
        db.commit()  # to actually commit the changes to the database
    except Exception as e:
        logger.error(f"Error deleting workflow {request.deployment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )
