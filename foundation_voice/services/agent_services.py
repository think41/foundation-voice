import json
from typing import Dict, Any, Tuple
from openai import OpenAI
from foundation_voice.utils.templates import AgentTemplates
from foundation_voice.utils.llm_prompts import LLMPrompts
import os

class AgentGenerationService:
    """Service class for generating voice agents"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.templates = AgentTemplates()
        self.prompts = LLMPrompts()
    
    async def generate_agent(self, prompt: str, agent_type: str, additional_info: Dict[str, Any] = None) -> Tuple[Dict[str, Any], str]:
        """Generate agent configuration and Python file using LLM"""
        
        # Enhance prompt with additional context
        enhanced_prompt = self._enhance_prompt(prompt, additional_info)
        
        # Get LLM response
        response = await self._get_llm_response(enhanced_prompt, agent_type)
        
        # Parse response
        return self._parse_llm_response(response)
    
    def _enhance_prompt(self, prompt: str, additional_info: Dict[str, Any] = None) -> str:
        """Enhance user prompt with additional context"""
        enhanced_prompt = prompt
        if additional_info:
            enhanced_prompt += f" Additional context: {json.dumps(additional_info)}"
        return enhanced_prompt
    
    async def _get_llm_response(self, prompt: str, agent_type: str) -> str:
        """Get response from LLM"""
        system_prompt = self.prompts.get_system_prompt(agent_type)
        
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Create a {agent_type} agent for: {prompt}"}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        return response.choices[0].message.content
    
    def _parse_llm_response(self, response_content: str) -> Tuple[Dict[str, Any], str]:
        """Parse LLM response to extract JSON config and Python content"""
        try:
            result = json.loads(response_content)
            return result["json_config"], result["python_content"]
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {str(e)}")
        except KeyError as e:
            raise ValueError(f"Missing required key in LLM response: {str(e)}")
