from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class AgentRequest(BaseModel):
    user_prompt: str = Field(..., description="Description of the agent to create")
    agent_type: str = Field(default="single", description="Type of agent: 'single' or 'multi'")
    additional_info: Optional[Dict[str, Any]] = Field(default=None, description="Additional context information")

class AgentResponse(BaseModel):
    agent_config: Dict[str, Any] = Field(..., description="Complete agent JSON configuration")
    python_file_content: str = Field(..., description="Python file with tools and callbacks")
    agent_type: str = Field(..., description="Type of agent generated")
