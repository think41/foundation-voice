from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

class GuardrailRule(BaseModel):
    name: str = Field(..., description="Name of the guardrail")
    model: str = Field(default="llama-3.3-70b", description="Model to use for guardrail")
    instructions: str = Field(..., description="Instructions for the guardrail")

class GuardrailConfig(BaseModel):
    enabled: bool = Field(default=False, description="Whether guardrails are enabled")
    rules: Optional[List[GuardrailRule]] = Field(default=None, description="List of guardrail rules")

class AgentRequest(BaseModel):
    user_prompt: str = Field(..., description="Description of the agent to create")
    agent_type: str = Field(default="single", description="Type of agent: 'single' or 'multi'")
    additional_info: Optional[Dict[str, Any]] = Field(default=None, description="Additional context information")
    guardrails: Optional[GuardrailConfig] = Field(default=None, description="Guardrail configuration")

class AgentResponse(BaseModel):
    agent_config: Dict[str, Any] = Field(..., description="Complete agent JSON configuration")
    python_file_content: str = Field(..., description="Python file with tools and callbacks")
    agent_type: str = Field(..., description="Type of agent generated")
