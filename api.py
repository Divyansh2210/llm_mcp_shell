from fastapi import FastAPI, HTTPException
import subprocess
from pydantic import BaseModel

app = FastAPI()

class CommandRequest(BaseModel):
    command: str

@app.get("/")
def root():
    return {"status": "sandbox ready"}

@app.post("/run")
async def run_bash(command_request: CommandRequest):
    try:
        # Run the command securely and return the output
        output = subprocess.check_output(command_request.command, shell=True, stderr=subprocess.STDOUT, timeout=10, executable="/bin/bash")
        return {"output": output.decode()}
    except subprocess.CalledProcessError as e:
        error_msg = e.output.decode()
        raise HTTPException(status_code=400, detail=error_msg)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="command timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
