from typing import Any, Dict, Optional
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from fastapi import HTTPException

from core.config_loader import settings
from core.setup_logging import setup_logger
from workflow.schemas import WorkflowSchema

import json

logger = setup_logger("AI Service")


class AiService:
    @staticmethod
    def __get_azure_client():
        """Initialize and return the Azure ChatCompletionsClient"""
        if not settings.azure_api_key:
            raise HTTPException(status_code=500, detail="Azure API key not configured")

        return ChatCompletionsClient(
            endpoint=settings.azure_endpoint,
            credential=AzureKeyCredential(settings.azure_api_key),
        )

    @staticmethod
    def __make_ai_request(input: str, prompt: str = settings.system_prompt) -> str:
        """Sends the prompt to Azure AI and returns the raw response."""
        try:
            client = AiService.__get_azure_client()

            response = client.complete(
                messages=[
                    SystemMessage(prompt),
                    UserMessage(input),
                ],
                model=settings.azure_model,
                max_tokens=2000,
                temperature=0.1,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Unhandled error: {e}")
            raise HTTPException(status_code=500, detail=f"AI API call failed: {str(e)}")

    @staticmethod
    def __clean_json_response(raw_response: str) -> str:
        clean_text = raw_response.replace("```json", "").replace("```", "").strip()

        start = clean_text.find("{")
        end = clean_text.rfind("}")

        if start == -1 or end == -1:
            raise ValueError(
                "No valid JSON object (enclosed in {}) found in the response"
            )

        return clean_text[
            start : end + 1
        ]  # the +1 will enclude the '}' character in the return

    @staticmethod
    def generate_workflow(
        user_input: str, current_workflow: Optional[Dict[str, Any]] = None
    ) -> WorkflowSchema:
        """
        Makes a request to create or modify a workflow.
        """
        workflow_schema = json.dumps(WorkflowSchema.model_json_schema(), indent=2)

        base_prompt = f"{settings.system_prompt}"

        context_modifier = ""
        if current_workflow:
            context_modifier = f"""
            IMPORTANT CONTEXT:
            The user is modifying an EXISTING workflow. Here is the current JSON structure:
            {json.dumps(current_workflow, indent=2)}

            INSTRUCTIONS FOR MODIFICATION:
            1. Keep existing node IDs and edge IDs intact if they are being used in the logic.
            2. If the current workflow has a default 'manual' trigger and the user's request implies a different trigger (like an email or schedule), REMOVE the default manual trigger and replace it.
            3. Ensure EVERY trigger node in the 'nodes' dictionary has at least one outgoing edge. Do not leave "floating" or isolated triggers.
            4. Splice new nodes into the existing `nodes` dictionary.
            5. Update the `edges` list to wire the new nodes logically into the flow.
            """

        strict_system_prompt = f"""
        {base_prompt}
        
        {context_modifier}

        CRITICAL OUTPUT INSTRUCTIONS:
        1. You must output ONLY a valid JSON object.
        2. Do not include markdown formatting, code blocks, or explanations.
        3. Your JSON must strictly adhere to the following schema:
        {workflow_schema}
        """

        response = AiService.__make_ai_request(user_input, strict_system_prompt)
        json_content = AiService.__clean_json_response(response)
        return WorkflowSchema.model_validate_json(json_content)

    @staticmethod
    def ask_ai(user_input: str, prompt: str) -> str:
        """Make generall questions to AI and get it's response"""
        return AiService.__make_ai_request(user_input, prompt)

    @staticmethod
    def health_check() -> dict:
        client = AiService.__get_azure_client()
        client.complete(
            messages=[UserMessage("Hello")],
            model=settings.azure_model,
            max_tokens=10,
        )
        return {"status": "healthy", "azure_connected": True}
