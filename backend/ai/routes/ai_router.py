from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ai.schemas.ai_response import AIResponse
from ai.services.ai_service import AiService
from auth.depedencies import get_current_user
from core.database import get_db
from core.setup_logging import setup_logger
from orchestration.services.deployment_service import DeploymentService
from user.models.user import User
from user.schemas.user_request import UserRequest
from workflow.services.workflow_service import WorkflowService

logger = setup_logger("AI Router")

ai_router = APIRouter(prefix="/ai", tags=["AI"])


@ai_router.post("/interpret", response_model=AIResponse)
async def interpret_command(
    user_request: UserRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Main endpoint. Receives user's text, sends it to the AI,
    and returns a structured workflow definition or an error.
    """
    try:
        workflow_definition = AiService.create_workflow(user_request.text)

        ai_generated_definition_dict = {
            "trigger": workflow_definition.trigger.model_dump(),
            "actions": [action.model_dump() for action in workflow_definition.actions],
        }

        deployment_id = await DeploymentService.create_deployment_for_workflow(
            user.id, workflow_definition.name, ai_generated_definition_dict
        )

        WorkflowService.create(
            db,
            deployment_id,
            user.id,
            workflow_definition.name,
            workflow_definition.description,
            ai_generated_definition_dict,
        )

        return AIResponse(success=True, data=workflow_definition)
    except ValueError as e:
        logger.debug(f"Ai router, interpret_command value error: \n{e}")
        return AIResponse(success=False, error=str(e))
    except HTTPException as e:
        logger.debug(f"Ai router, interpret_command HTTP exception: \n{e}")
        return AIResponse(success=False, error=f"An HTTP error occurred: {str(e)}")
    except Exception as e:
        logger.debug(f"Ai router, interpret_command exception: \n{e}")
        return AIResponse(
            success=False, error=f"An unexpected error occurred: {str(e)}"
        )


@ai_router.get("/health")
async def health():
    """Health check endpoint to verify Azure connection"""
    try:
        return AiService.health_check()
    except Exception as e:
        logger.error(f"Ai model connection failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Azure connection failed: {str(e)}"
        )
