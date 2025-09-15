from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
from dotenv import load_dotenv
from typing import Optional

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

from schemas import WorkflowDefinition
from prompts import SYSTEM_PROMPT

load_dotenv()

app = FastAPI(title="AI Workflow Orchestrator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Vue dev server default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT", "https://models.github.ai/inference")
AZURE_MODEL = os.getenv("AZURE_MODEL", "deepseek/DeepSeek-R1-0528")
AZURE_API_KEY = os.getenv("AZURE_API_KEY")


def get_azure_client():
    """Initialize and return the Azure ChatCompletionsClient"""
    if not AZURE_API_KEY:
        raise HTTPException(status_code=500, detail="Azure API key not configured")

    return ChatCompletionsClient(
        endpoint=AZURE_ENDPOINT,
        credential=AzureKeyCredential(AZURE_API_KEY),
    )


# Pydantic model for the API request
class UserRequest(BaseModel):
    text: str


# Pydantic model for the API response (can be a success or an error)
class AIResponse(BaseModel):
    success: bool
    data: Optional[WorkflowDefinition] = None
    error: Optional[str] = None


def get_ai_response(user_input: str) -> str:
    """Sends the prompt to Azure AI and returns the raw response."""
    try:
        client = get_azure_client()

        response = client.complete(
            messages=[
                SystemMessage(SYSTEM_PROMPT),
                UserMessage(user_input),
            ],
            model=AZURE_MODEL,
            max_tokens=1000,
            temperature=0.7,
        )

        return response.choices[0].message.content

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI API call failed: {str(e)}")


def parse_ai_response(raw_response: str) -> WorkflowDefinition:
    """Tries to extract and parse JSON from the AI's response."""
    try:
        # Find the first JSON block in the response
        start = raw_response.find("{")
        end = raw_response.rfind("}") + 1

        if start == -1 or end == 0:
            raise ValueError("No JSON object found in the response")

        json_str = raw_response[start:end]
        data = json.loads(json_str)

        # Validate and create the Pydantic model
        return WorkflowDefinition(**data)

    except (json.JSONDecodeError, ValueError) as e:
        # Check if the AI itself responded with an error
        if "error" in raw_response.lower():
            raise ValueError(raw_response)
        else:
            raise ValueError(
                f"Failed to parse AI response as JSON: {e}\nResponse was: {raw_response}"
            )


@app.post("/interpret", response_model=AIResponse)
async def interpret_command(user_request: UserRequest):
    """
    Main endpoint. Receives user's text, sends it to the AI,
    and returns a structured workflow definition or an error.
    """
    print(f"📨 Received request: {user_request.text}")

    try:
        # 1. Get the raw response from Azure AI
        raw_ai_response = get_ai_response(user_request.text)
        print(f"🤖 Raw AI response: {raw_ai_response}")

        # 2. Parse the response into our structured schema
        workflow_definition = parse_ai_response(raw_ai_response)

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


@app.get("/health")
async def health_check():
    """Health check endpoint to verify Azure connection"""
    try:
        client = get_azure_client()
        # Try a simple test call
        response = client.complete(
            messages=[UserMessage("Hello")],
            model=AZURE_MODEL,
            max_tokens=10,
        )
        return {"status": "healthy", "azure_connected": True}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Azure connection failed: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    # Run the server on http://localhost:8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
