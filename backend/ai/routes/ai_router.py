from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ai.schemas.ai_response import AIResponse
from ai.services.ai_service import AiService
from auth.depedencies import get_current_user
from core.database import get_db
from user.models.user import User
from user.schemas.user_request import UserRequest
from workflow.services.workflow_service import WorkflowService

ai_router = APIRouter(
    prefix="/ai",
    tags=["AI"]
)

@ai_router.post("/interpret", response_model=AIResponse)
async def interpret_command(user_request: UserRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Main endpoint. Receives user's text, sends it to the AI,
    and returns a structured workflow definition or an error.
    """
    try:
        # 1. Get the raw response from Azure AI
        raw_ai_response = AiService.get_ai_response(user_request.text)

        # 2. Parse the response into our structured schema
        workflow_definition = AiService.parse_ai_response(raw_ai_response)

        ai_generated_definition_dict = {
            "trigger": workflow_definition.trigger.model_dump(),
            "actions": [action.model_dump() for action in workflow_definition.actions]
        }

        await WorkflowService.create(
            db,
            user.id,
            workflow_definition.name,
            workflow_definition.description,
            ai_generated_definition_dict
        )

        # 3. Return the successful result
        return AIResponse(success=True, data=workflow_definition)

    except ValueError as e:
        # This handles parsing errors and AI-generated errors
        return AIResponse(success=False, error=str(e))
    except HTTPException as he:
        # Re-raise HTTP exceptions from get_ai_response
        raise he
    except Exception as e:
        # Catch any other unexpected errors
        return AIResponse(
            success=False, error=f"An unexpected error occurred: {str(e)}"
        )


@ai_router.get("/health")
async def health():
    """Health check endpoint to verify Azure connection"""
    try:
        return AiService.health_check()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Azure connection failed: {str(e)}"
        )

