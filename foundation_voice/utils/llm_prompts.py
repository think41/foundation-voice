from typing import Dict, Any, List
from foundation_voice.models.schemas import GuardrailConfig
import json

class LLMPrompts:
    """Utility class for LLM prompts and instructions"""
    
    BASE_INSTRUCTIONS = """
You are an expert AI assistant that creates voice agent configurations. You will be given a template configuration and need to customize it based on the user's requirements.

Your task is to:
1. Fill in the template with appropriate content for the user's use case
2. Add relevant tools to the tools list
3. Generate Python code for the tools and callbacks
4. Create proper context models when needed
5. Apply guardrails if specified

Key requirements:
- Use the provided template as the base structure
- Only modify the fields that need customization
- Keep the existing structure and providers unless the user specifically requests changes
- Make responses natural and conversational
- Include proper error handling in Python code
- Generate realistic, functional tools based on the agent's purpose

For SINGLE AGENTS:
- Add guardrails directly to the LLM section as an array of objects
- Each guardrail should have: name, model, instructions

For MULTI-AGENTS:
- Add guardrails definitions to agent_config.guardrails as key-value pairs
- Each agent should specify which guardrails to use in their guardrails array
- Structure agents properly with all required fields

Return your response as JSON with these exact keys:
- "agent_config": The customized agent configuration (based on the template)
- "python_content": The complete Python file content
- "tools_list": Array of tool names that were added to the configuration
"""

    @staticmethod
    def get_system_prompt(agent_type: str, template: Dict[str, Any], guardrails: GuardrailConfig = None) -> str:
        """Get system prompt for LLM based on agent type and template"""
        guardrails_instruction = ""
        if guardrails and guardrails.enabled and guardrails.rules:
            guardrails_list = []
            for rule in guardrails.rules:
                guardrails_list.append(f"- {rule.name}: {rule.instructions}")
            
            guardrails_instruction = f"""
GUARDRAILS TO IMPLEMENT:
{chr(10).join(guardrails_list)}

For SINGLE agents: Add these to llm.guardrails as array of objects with name, model, instructions
For MULTI agents: Add to agent_config.guardrails as definitions AND specify in each agent's guardrails array
"""

        multi_agent_structure = ""
        if agent_type == "multi":
            multi_agent_structure = """
MULTI-AGENT STRUCTURE REQUIREMENTS:
Each agent in the agents object should have this structure:
"agent_name": {
    "name": "agent_name",
    "prompt": "Agent-specific system prompt",
    "tools": ["tool1", "tool2"],
    "guardrails": ["guardrail_name1", "guardrail_name2"]
}

Example:
"agents": {
    "triage_agent": {
        "name": "triage_agent",
        "prompt": "You are a triage agent that categorizes user requests...",
        "tools": ["categorize_request", "route_to_specialist"],
        "guardrails": ["off_topic_guardrail", "medical_disclaimer_guardrail"]
    },
    "appointment_agent": {
        "name": "appointment_agent", 
        "prompt": "You are an appointment scheduling agent...",
        "tools": ["check_availability", "book_appointment"],
        "guardrails": ["off_topic_guardrail"]
    }
}
"""
        
        return f"""
{LLMPrompts.BASE_INSTRUCTIONS}

AGENT TYPE: {agent_type}

TEMPLATE TO CUSTOMIZE:
{json.dumps(template, indent=2)}

{guardrails_instruction}

{multi_agent_structure}

Customize this template based on the user's requirements. Fill in:
- title: Appropriate title for the agent
- initial_greeting: Natural greeting message
- prompt: Detailed system prompt for the agent's behavior
- tools: List of relevant tool names
- For multi-agent: customize the agents config, start_agent, and guardrails

Generate appropriate Python code with:
- Tool implementations
- Callback functions
- Context models (if needed)
"""
    