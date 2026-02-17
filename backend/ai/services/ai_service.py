from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from fastapi import HTTPException

from core.config_loader import settings
from core.setup_logging import setup_logger
from workflow.schemas.workflow_definition import WorkflowDefinition

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
            raise ValueError("No valid JSON object (enclosed in {}) found in the response")
            
        return clean_text[start:end+1] # the +1 will enclude the '}' character in the return

    @staticmethod
    def create_workflow(user_input: str) -> WorkflowDefinition:
        """
        Make a request to create a workflow, parses the response
        Returns the parsed workflow definition
        """
        workflow_schema = json.dumps(WorkflowDefinition.model_json_schema(), indent=2)

        strict_system_prompt = f"""
        {settings.system_prompt}

        CRITICAL OUTPUT INSTRUCTIONS:
        1. You must output ONLY a valid JSON object.
        2. Do not include markdown formatting, code blocks, or explanations.
        3. Your JSON must strictly adhere to the following schema:
        
        {workflow_schema}
        """

        response = AiService.__make_ai_request(user_input, strict_system_prompt)
        json_content = AiService.__clean_json_response(response)
        return WorkflowDefinition.model_validate_json(json_content)

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
