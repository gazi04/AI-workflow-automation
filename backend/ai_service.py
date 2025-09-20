import json
import os

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from fastapi import HTTPException

from prompts import SYSTEM_PROMPT
from schemas import WorkflowDefinition


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


def health_check() -> dict:
    client = get_azure_client()
    # Try a simple test call
    client.complete(
        messages=[UserMessage("Hello")],
        model=AZURE_MODEL,
        max_tokens=10,
    )
    return {"status": "healthy", "azure_connected": True}
