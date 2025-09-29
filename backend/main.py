from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv


from schemas import UserRequest, AIResponse
load_dotenv() # Need to load the .env file before importing ai_service
from ai_service import get_ai_response, health_check, parse_ai_response
from routes.auth import router as auth_router


app = FastAPI(title="AI Workflow Orchestrator API")
app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Vue dev server default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
async def health():
    """Health check endpoint to verify Azure connection"""
    try:
        return health_check()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Azure connection failed: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    # Run the server on http://localhost:8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
