import json
from typing import Dict, Any, Tuple, List
from openai import OpenAI
from foundation_voice.utils.templates import AgentTemplates
from foundation_voice.utils.llm_prompts import LLMPrompts
from foundation_voice.models.schemas import GuardrailConfig
from loguru import logger
import os

class AgentGenerationService:
    """Service class for generating voice agents"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.templates = AgentTemplates()
        self.prompts = LLMPrompts()
    
    async def generate_agent(self, prompt: str, agent_type: str, additional_info: Dict[str, Any] = None, guardrails: GuardrailConfig = None) -> Tuple[Dict[str, Any], str]:
        """Generate agent configuration and Python file using LLM"""
        
        # Get the appropriate template
        if agent_type == "single":
            template = self.templates.get_single_agent_template()
        else:
            template = self.templates.get_multi_agent_template()

        logger.info(f"Template: {template}");
        
        # Enhance prompt with additional context (only if provided)
        enhanced_prompt = self._enhance_prompt(prompt, additional_info)
        logger.info(f"Enhanced prompt: {enhanced_prompt}");
        # Get LLM response
        response = await self._get_llm_response(enhanced_prompt, agent_type, template, guardrails)
        logger.info(f"Response: {response}");
        # Parse response
        agent_config, python_content = self._parse_llm_response(response)
        logger.info(f"Agent config: {agent_config}");
        logger.info(f"Python content: {python_content}");
        # Apply guardrails to config if specified
        if guardrails and guardrails.enabled and guardrails.rules:
            guardrails_list = self._build_guardrails_list(guardrails.rules)
            agent_config = self.templates.add_guardrails_to_config(agent_config, guardrails_list, agent_type)
        
        return agent_config, python_content
    
    def _enhance_prompt(self, prompt: str, additional_info: Dict[str, Any] = None) -> str:
        """Enhance user prompt with additional context"""
        enhanced_prompt = prompt
        if additional_info:
            enhanced_prompt += f"\n\nAdditional context: {json.dumps(additional_info)}"
        return enhanced_prompt
    
    async def _get_llm_response(self, prompt: str, agent_type: str, template: Dict[str, Any], guardrails: GuardrailConfig = None) -> str:
        """Get response from LLM"""
        system_prompt = self.prompts.get_system_prompt(agent_type, template, guardrails)
        
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
            logger.info(f"Response content: {response_content}");
            result = json.loads(response_content)
            logger.info(f"Result: {result}");
            return result["agent_config"], result["python_content"]
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {str(e)}")
        except KeyError as e:
            raise ValueError(f"Missing required key in LLM response: {str(e)}")
    
    def _build_guardrails_list(self, rules: List) -> List[Dict[str, Any]]:
        """Build guardrails list from GuardrailRule objects"""
        guardrails_list = []
        for rule in rules:
            guardrails_list.append({
                "name": rule.name,
                "model": rule.model,
                "instructions": rule.instructions
            })
        return guardrails_list