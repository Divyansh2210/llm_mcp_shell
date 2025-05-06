import httpx
import json
from typing import Dict, Any, Optional
import asyncio
from enum import Enum
import time
from action_logger import ActionLogger

class ErrorType(Enum):
    TIMEOUT = "timeout"
    NETWORK = "network"
    SERVER = "server"
    COMMAND = "command"
    VALIDATION = "validation"
    UNKNOWN = "unknown"

class MCPError(Exception):
    def __init__(self, error_type: ErrorType, message: str, details: Optional[Dict] = None):
        self.error_type = error_type
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class MCPClient:
    def __init__(self, server_url: str = "http://localhost:8001", timeout: float = 30.0, max_retries: int = 3):
        self.server_url = server_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.context: Dict[str, Any] = {}
        self.last_command_time: float = 0
        self.command_cooldown: float = 0.1  # 100ms between commands
        self.logger = ActionLogger()
        
    def _validate_command(self, command: str) -> None:
        """Validate the command before sending it to the server."""
        if not command or not isinstance(command, str):
            raise MCPError(
                ErrorType.VALIDATION,
                "Command must be a non-empty string",
                {"command": command}
            )
        
        # Add more validation rules as needed
        dangerous_commands = ["rm -rf", "mkfs", "dd", ":(){ :|:& };:"]  # Example dangerous commands
        if any(dc in command.lower() for dc in dangerous_commands):
            raise MCPError(
                ErrorType.VALIDATION,
                "Potentially dangerous command detected",
                {"command": command}
            )
    
    def _check_command_cooldown(self) -> None:
        """Ensure commands aren't sent too frequently."""
        current_time = time.time()
        time_since_last = current_time - self.last_command_time
        if time_since_last < self.command_cooldown:
            time.sleep(self.command_cooldown - time_since_last)
        self.last_command_time = time.time()
        
    async def execute_command(self, command: str, purpose: Optional[str] = None) -> Dict[str, Any]:
        """Execute a command through the MCP server with enhanced error handling."""
        try:
            # Log the start of command execution
            self.logger.log_action(
                action_type="command_execution_start",
                prompt=purpose,
                command=command,
                reasoning="Executing command through MCP server"
            )

            # Validate command
            self._validate_command(command)
            
            # Check command cooldown
            self._check_command_cooldown()
            
            # Prepare the request payload
            payload = {
                "command": command,
                "context": {
                    "purpose": purpose,
                    "previous_context": self.context,
                    "timestamp": time.time()
                }
            }
            
            # Retry logic
            for attempt in range(self.max_retries):
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"{self.server_url}/execute",
                            json=payload,
                            timeout=self.timeout
                        )
                        
                        if response.status_code == 503:
                            error_msg = "Server is temporarily unavailable"
                            self.logger.log_action(
                                action_type="command_execution_error",
                                command=command,
                                status="error",
                                error=error_msg,
                                details={"status_code": response.status_code}
                            )
                            raise MCPError(
                                ErrorType.SERVER,
                                error_msg,
                                {"status_code": response.status_code}
                            )
                        
                        if response.status_code != 200:
                            error_msg = f"Server error: {response.status_code}"
                            self.logger.log_action(
                                action_type="command_execution_error",
                                command=command,
                                status="error",
                                error=error_msg,
                                details={"response": response.text}
                            )
                            return {
                                "error": error_msg,
                                "error_type": ErrorType.SERVER.value,
                                "details": response.text
                            }
                        
                        result = response.json()
                        
                        # Validate response format
                        if not isinstance(result, dict):
                            error_msg = "Invalid response format from server"
                            self.logger.log_action(
                                action_type="command_execution_error",
                                command=command,
                                status="error",
                                error=error_msg,
                                details={"response": result}
                            )
                            raise MCPError(
                                ErrorType.VALIDATION,
                                error_msg,
                                {"response": result}
                            )
                        
                        # Update context with the response
                        if "context" in result:
                            self.context.update(result["context"])
                        
                        # Log successful execution
                        self.logger.log_action(
                            action_type="command_execution_success",
                            command=command,
                            status="success",
                            output=result.get("output"),
                            details={"context": result.get("context", {})}
                        )
                        
                        return result
                        
                except httpx.TimeoutException:
                    if attempt == self.max_retries - 1:
                        error_msg = f"Command timed out after {self.timeout} seconds"
                        self.logger.log_action(
                            action_type="command_execution_error",
                            command=command,
                            status="error",
                            error=error_msg,
                            details={"attempt": attempt + 1}
                        )
                        raise MCPError(
                            ErrorType.TIMEOUT,
                            error_msg,
                            {"command": command, "attempt": attempt + 1}
                        )
                    await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
                    
                except httpx.RequestError as e:
                    if attempt == self.max_retries - 1:
                        error_msg = f"Failed to communicate with MCP server: {str(e)}"
                        self.logger.log_action(
                            action_type="command_execution_error",
                            command=command,
                            status="error",
                            error=error_msg,
                            details={"attempt": attempt + 1}
                        )
                        raise MCPError(
                            ErrorType.NETWORK,
                            error_msg,
                            {"command": command, "attempt": attempt + 1}
                        )
                    await asyncio.sleep(1 * (attempt + 1))
                
        except MCPError as e:
            self.logger.log_action(
                action_type="command_execution_error",
                command=command,
                status="error",
                error=e.message,
                details=e.details
            )
            return {
                "error": e.message,
                "error_type": e.error_type.value,
                "details": e.details
            }
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.log_action(
                action_type="command_execution_error",
                command=command,
                status="error",
                error=error_msg,
                details={"command": command}
            )
            return {
                "error": error_msg,
                "error_type": ErrorType.UNKNOWN.value,
                "details": {"command": command}
            }

async def main():
    # Create MCP client
    client = MCPClient()
    
    # Test scenarios
    test_scenarios = [
        # Normal commands
        ("ls", "List files in current directory"),
        ("pwd", "Show current working directory"),
        
        # Error scenarios
        ("nonexistentcommand", "Test invalid command"),
        ("sleep 2", "Test command timeout"),
        ("", "Test empty command"),
        ("rm -rf /", "Test dangerous command"),
    ]
    
    # Execute test scenarios
    for command, purpose in test_scenarios:
        print(f"\n{'='*50}")
        print(f"Executing command: {command}")
        print(f"Purpose: {purpose}")
        
        result = await client.execute_command(command, purpose)
        
        if "error" in result:
            print(f"Error Type: {result.get('error_type', 'unknown')}")
            print(f"Error: {result['error']}")
            if "details" in result:
                print("Details:")
                print(json.dumps(result["details"], indent=2))
        else:
            print("Output:")
            print(result.get("output", ""))
            print("\nContext:")
            print(json.dumps(result.get("context", {}), indent=2))

if __name__ == "__main__":
    asyncio.run(main()) 