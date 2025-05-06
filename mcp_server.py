from fastapi import FastAPI, HTTPException
import httpx
import json
from pydantic import BaseModel
from typing import Optional
from action_logger import ActionLogger

app = FastAPI(title="MCP Server")
logger = ActionLogger()

# Configuration
SANDBOX_URL = "http://localhost:8000"

class CommandRequest(BaseModel):
    command: str
    context: Optional[dict] = None

@app.get("/")
def root():
    return {"status": "MCP server ready"}

@app.post("/execute")
async def execute_command(request: CommandRequest):
    try:
        # Log the start of command execution from UI
        logger.log_action(
            action_type="ui_command_execution_start",
            command=request.command,
            reasoning="Command received from UI interface",
            context=request.context if request.context else {}
        )

        # Forward the command to the bash sandbox
        async with httpx.AsyncClient() as client:
            # Print request for debugging
            print(f"Sending request to sandbox: {{'command': '{request.command}'}}")
            
            response = await client.post(
                f"{SANDBOX_URL}/run",
                json={"command": request.command},
                headers={"Content-Type": "application/json"}
            )
            
            # Print response for debugging
            print(f"Sandbox response status: {response.status_code}")
            print(f"Sandbox response body: {response.text}")
            
            if response.status_code != 200:
                error_msg = f"Sandbox error: {response.text}"
                # Log the error
                logger.log_action(
                    action_type="ui_command_execution_error",
                    command=request.command,
                    status="error",
                    error=error_msg,
                    context=request.context if request.context else {}
                )
                raise HTTPException(status_code=response.status_code, detail=error_msg)
            
            result = response.json()
            
            # Add context to the response if provided
            if request.context:
                result["context"] = request.context

            # Log successful execution
            logger.log_action(
                action_type="ui_command_execution_success",
                command=request.command,
                status="success",
                output=result.get("output", ""),
                context=request.context if request.context else {}
            )
                
            return result
            
    except httpx.RequestError as e:
        error_msg = f"Failed to communicate with sandbox: {str(e)}"
        # Log the error
        logger.log_action(
            action_type="ui_command_execution_error",
            command=request.command,
            status="error",
            error=error_msg,
            context=request.context if request.context else {}
        )
        raise HTTPException(status_code=500, detail=error_msg)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002) 