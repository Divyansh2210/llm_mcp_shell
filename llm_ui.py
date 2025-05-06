from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
import json
from typing import Dict, Any
import asyncio
from pathlib import Path
import urllib.parse

app = FastAPI(title="LLM Command Interface")

# Create templates directory
templates_dir = Path("templates")
templates_dir.mkdir(exist_ok=True)

# Create static directory
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# MCP Client configuration
MCP_SERVER_URL = "http://localhost:8002"  # Updated to point to MCP server
LLM_API_URL = "http://localhost:11434/api/generate"  # Default Ollama API endpoint

class LLMClient:
    def __init__(self, api_url: str = LLM_API_URL):
        self.api_url = api_url
        
    async def generate_command(self, prompt: str) -> Dict[str, Any]:
        """Generate a command based on the user's prompt using the local LLM."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json={
                        "model": "qwen3:0.6b",
                        "prompt": f"""You are a command generator. Your task is to convert user requests into bash commands.

IMPORTANT: Respond with ONLY a JSON object. No other text, no thoughts, no explanations.
The response must be a valid JSON object with exactly these fields:
- command: the bash command to execute
- explanation: a brief explanation of what the command does

Example response:
{{"command": "ls -la", "explanation": "Lists all files including hidden ones with detailed information"}}

User request: {prompt}

Response:""",
                        "stream": False
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    return {
                        "error": f"LLM API error: {response.status_code}",
                        "details": response.text
                    }
                
                result = response.json()
                response_text = result.get("response", "").strip()
                
                # Debug logging
                print("\n=== LLM Response ===")
                print(f"Raw response: {response_text}")
                
                try:
                    # Try to parse the response as JSON
                    response_text = response_text.strip()
                    
                    # Extract JSON part from the response
                    # Look for the last occurrence of a JSON object in the text
                    json_start = response_text.rfind('{')
                    json_end = response_text.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        response_text = response_text[json_start:json_end]
                    else:
                        return {
                            "error": "No JSON object found in response",
                            "details": {"response": response_text}
                        }
                    
                    # Debug logging
                    print(f"\nExtracted JSON: {response_text}")
                    
                    command_data = json.loads(response_text)
                    
                    # Debug logging
                    print(f"\nParsed JSON: {command_data}")
                    
                    command = command_data.get("command", "").strip()
                    explanation = command_data.get("explanation", "").strip()
                    
                    # Debug logging
                    print(f"\nExtracted command: {command}")
                    print(f"Extracted explanation: {explanation}")
                    
                    if not command:
                        return {
                            "error": "No command found in response",
                            "details": {"response": response_text}
                        }
                    
                    return {
                        "command": command,
                        "explanation": explanation,
                        "raw_response": result
                    }
                except json.JSONDecodeError:
                    # If not JSON, try to extract just the command
                    # Look for lines that might contain the command
                    lines = response_text.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith(('{', '[', '<', 'think', 'Thought', 'Okay', 'Let', 'I', 'The')):
                            return {
                                "command": line,
                                "explanation": "Command extracted from response",
                                "raw_response": result
                            }
                    
                    return {
                        "error": "Could not extract command from response",
                        "details": {"response": response_text}
                    }
                
        except Exception as e:
            return {
                "error": f"Failed to generate command: {str(e)}",
                "details": {"prompt": prompt}
            }

class MCPClient:
    def __init__(self, server_url: str = MCP_SERVER_URL):
        self.server_url = server_url
        
    async def execute_command(self, command: str, purpose: str) -> Dict[str, Any]:
        """Execute a command through the MCP server."""
        try:
            # Print request for debugging
            print(f"Sending request to MCP: {{'command': '{command}', 'context': {{'purpose': '{purpose}'}}}}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.server_url}/execute",
                    json={
                        "command": command,
                        "context": {
                            "purpose": purpose
                        }
                    },
                    timeout=30.0
                )
                
                # Print response for debugging
                print(f"MCP response status: {response.status_code}")
                print(f"MCP response body: {response.text}")
                
                if response.status_code != 200:
                    return {
                        "error": f"Server error: {response.status_code}",
                        "details": response.text
                    }
                
                return response.json()
                
        except Exception as e:
            return {
                "error": f"Failed to execute command: {str(e)}",
                "details": {"command": command}
            }

# Initialize clients
llm_client = LLMClient()
mcp_client = MCPClient()

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            # Receive prompt from client
            data = await websocket.receive_json()
            prompt = data.get("prompt", "")
            
            if not prompt:
                await websocket.send_json({
                    "error": "No prompt provided"
                })
                continue
            
            # Generate command using LLM
            await websocket.send_json({
                "status": "Generating command...",
                "prompt": prompt
            })
            
            llm_result = await llm_client.generate_command(prompt)
            
            if "error" in llm_result:
                await websocket.send_json({
                    "error": llm_result["error"],
                    "details": llm_result.get("details", {})
                })
                continue
            
            command = llm_result["command"]
            explanation = llm_result.get("explanation", "")
            
            # Send the generated command to client
            await websocket.send_json({
                "status": "Command generated",
                "command": command,
                "explanation": explanation
            })
            
            # Execute the command
            await websocket.send_json({
                "status": "Executing command...",
                "command": command
            })
            
            result = await mcp_client.execute_command(command, prompt)
            
            # Send the result back to client
            await websocket.send_json({
                "status": "Command executed",
                "result": result
            })
            
    except Exception as e:
        await websocket.send_json({
            "error": f"WebSocket error: {str(e)}"
        })
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)  # Changed port to 8003 