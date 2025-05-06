import asyncio
from llm_client import MCPClient

async def main():
    # Create MCP client
    client = MCPClient()
    
    # Run a simple command
    command = "pwd"
    purpose = "Show current working directory"
    
    print(f"\nExecuting command: {command}")
    print(f"Purpose: {purpose}")
    
    result = await client.execute_command(command, purpose)
    
    if "error" in result:
        print(f"Error Type: {result.get('error_type', 'unknown')}")
        print(f"Error: {result['error']}")
    else:
        print("Output:")
        print(result.get("output", ""))

if __name__ == "__main__":
    asyncio.run(main()) 