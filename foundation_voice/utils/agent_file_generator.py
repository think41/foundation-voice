"""Module for generating agent files and configurations.

This module provides functionality to create zip archives containing agent
configuration, Python code, and documentation for voice agent deployment.
"""

import json
import zipfile
from datetime import datetime
from io import BytesIO
from typing import Dict, Any


class FileGenerator:
    """Utility class for generating and packaging agent files.

    This class provides methods to create zip archives containing all necessary
    files for deploying a voice agent, including configuration, code, and documentation.
    """

    @staticmethod
    def create_zip_file(
        agent_config: Dict[str, Any],
        python_content: str,
        agent_type: str,
    ) -> BytesIO:
        """Create a zip file containing agent configuration and Python files.

        Args:
            agent_config: Dictionary containing agent configuration
            python_content: String containing Python code for the agent tools
            agent_type: Type of the agent (e.g., 'voice', 'chat')

        Returns:
            BytesIO: In-memory zip file containing all agent files
        """
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
        """Generate README content for the agent.

        Args:
            agent_config: Dictionary containing agent configuration
            agent_type: Type of the agent

        Returns:
            str: Formatted README content
        """
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
        """Generate appropriate filename for the zip file.

        Args:
            agent_config: Dictionary containing agent configuration
            agent_type: Type of the agent

        Returns:
            str: Generated filename in format: `{agent_name}_{agent_type}_agent.zip`
        """
        agent_name = agent_config["agent"]["title"].replace(" ", "_").lower()
        clean_name = "".join(c for c in agent_name if c.isalnum() or c == "_")
        return f"{clean_name}_{agent_type}_agent.zip"
