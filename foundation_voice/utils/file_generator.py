import json
import zipfile
from io import BytesIO
from datetime import datetime
from typing import Dict, Any


class FileGenerator:
    """Utility class for generating agent files"""

    @staticmethod
    def create_zip_file(
        agent_config: Dict[str, Any], python_content: str, agent_type: str
    ) -> BytesIO:
        """Create a zip file containing agent configuration and Python files"""
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Add JSON config file
            zip_file.writestr("agent_config.json", json.dumps(agent_config, indent=2))

            # Add Python file
            zip_file.writestr("agent_tools.py", python_content)

            # Add README
            readme_content = FileGenerator._generate_readme(agent_config, agent_type)
            zip_file.writestr("README.md", readme_content)

        zip_buffer.seek(0)
        return zip_buffer

    @staticmethod
    def _generate_readme(agent_config: Dict[str, Any], agent_type: str) -> str:
        """Generate README content for the agent"""
        return f"""# Voice Agent: {agent_config["agent"]["title"]}

## Agent Type: {agent_type.upper()}

## Files:
- `agent_config.json`: Voice agent configuration
- `agent_tools.py`: Tools, callbacks, and context definitions

## Usage:
1. Configure your environment with the necessary API keys
2. Load the agent configuration 
3. Import the tools and callbacks from agent_tools.py
4. Deploy using your voice agent platform

## Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Configuration:
- Transport: {agent_config["agent"]["transport"]["type"]}
- TTS Provider: {agent_config["agent"]["tts"]["provider"]}
- STT Provider: {agent_config["agent"]["stt"]["provider"]}
- LLM Provider: {agent_config["agent"]["llm"]["provider"]}
"""

    @staticmethod
    def generate_filename(agent_config: Dict[str, Any], agent_type: str) -> str:
        """Generate appropriate filename for the zip file"""
        agent_name = agent_config["agent"]["title"].replace(" ", "_").lower()
        clean_name = "".join(c for c in agent_name if c.isalnum() or c == "_")
        return f"{clean_name}_{agent_type}_agent.zip"
