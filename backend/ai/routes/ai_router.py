from fastapi import APIRouter, Depends, HTTPException

from ai.schemas.ai_response import AIResponse
from ai.services.ai_service import AiService
from auth.depedencies import get_current_user
from core.setup_logging import setup_logger
from user.models.user import User
from user.schemas.user_request import UserRequest

logger = setup_logger("AI Router")

ai_router = APIRouter(prefix="/ai", tags=["AI"])


@ai_router.post("/interpret", response_model=AIResponse)
async def interpret_command(
    user_request: UserRequest,
    user: User = Depends(get_current_user),
):
    """
    Main endpoint. Receives user's text, sends it to the AI,
    and returns a structured workflow definition or an error.
    """
    try:
        workflow_definition = AiService.generate_workflow(user_request.text, user_request.current_workflow)
        return AIResponse(success=True, data=workflow_definition)
    except ValueError as e:
        logger.error(f"AI Router: Interpret command value error: {e}")
        return AIResponse(
            success=False,
            error="I couldn't understand that command. Please try rephrasing it.",
        )
    except HTTPException as e:
        logger.error(f"AI Router: HTTP exception: {e}")
        return AIResponse(
            success=False,
            error="There was a problem connecting to the AI service. Please try again later.",
        )
    except Exception as e:
        logger.error(f"AI Router: Unexpected exception: {e}")
        return AIResponse(
            success=False,
            error="An unexpected error occurred while processing your request.",
        )


@ai_router.get("/health")
async def health():
    """Health check endpoint to verify Azure connection"""
    try:
        return AiService.health_check()
    except Exception as e:
        logger.error(f"Ai model connection failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="The AI service is currently unavailable. Please try again later.",
        )
