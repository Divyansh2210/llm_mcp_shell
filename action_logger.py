import json
from datetime import datetime
from typing import Optional, Dict, Any

class ActionLogger:
    def __init__(self, log_file: str = "llm_actions.json"):
        self.log_file = log_file
        self.actions = self._load_actions()

    def _load_actions(self) -> list:
        try:
            with open(self.log_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_actions(self):
        with open(self.log_file, 'w') as f:
            json.dump(self.actions, f, indent=2)

    def log_action(self, action_type: str, command: str, status: str = "success", 
                  reasoning: Optional[str] = None, prompt: Optional[str] = None,
                  output: Optional[str] = None, error: Optional[str] = None,
                  context: Optional[Dict[str, Any]] = None, **kwargs):
        action = {
            "timestamp": datetime.now().isoformat(),
            "action_type": action_type,
            "command": command,
            "status": status
        }

        if reasoning:
            action["reasoning"] = reasoning
        if prompt:
            action["prompt"] = prompt
        if output:
            action["output"] = output
        if error:
            action["error"] = error
        if context:
            action["context"] = context
        
        # Add any additional fields
        for key, value in kwargs.items():
            action[key] = value

        self.actions.append(action)
        self._save_actions()

    def get_recent_actions(self, limit: int = 10) -> list:
        return self.actions[-limit:]

    def clear_logs(self):
        self.actions = []
        self._save_actions() 