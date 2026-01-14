# File: app/core/prompts.py
import yaml
import os
from pathlib import Path
from typing import Dict, Any

class PromptManager:
    def __init__(self, prompt_dir: str = "app/prompts"):
        # Resolves to project_root/app/prompts
        self.prompt_dir = Path(__file__).parent.parent / "prompts"
        self._cache: Dict[str, Any] = {}

    def load_prompt(self, filename: str, key: str) -> str:
        """
        Loads a specific key from a YAML file.
        Example: load_prompt("chat.yaml", "rag_system")
        """
        if filename not in self._cache:
            file_path = self.prompt_dir / filename
            if not file_path.exists():
                raise FileNotFoundError(f"Prompt file not found: {file_path}")
            
            with open(file_path, "r") as f:
                self._cache[filename] = yaml.safe_load(f)
        
        return self._cache[filename].get(key, {}).get("content", "")

prompt_manager = PromptManager()