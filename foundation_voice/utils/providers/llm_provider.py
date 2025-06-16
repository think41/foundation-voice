"""
Large Language Model (LLM) provider module.
"""

import os

from loguru import logger
from typing import Dict, Any

from pipecat.services.openai.llm import OpenAILLMService
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext

from foundation_voice.custom_plugins.services.openai_agents.llm import OpenAIAgentPlugin
from foundation_voice.custom_plugins.processors.aggregators.agent_context import AgentChatContext


DEFAULT_PROMPT = "You are a helpful LLM in a WebRTC call. Your goal is to demonstrate your capabilities in a succinct way. Your output will be converted to audio so don't include special characters in your answers. Respond to what the user said in a creative and helpful way."
DEFAULT_INITIAL_GREETING = "Hello. How can I help you today?"


def create_llm_service(
    llm_config: Dict[str, Any],
    data: Dict[str, Any],
) -> Any:
    """
    Create an LLM service based on configuration.

    Args:
        llm_config: Dictionary containing LLM configuration
        tools: Dictionary containing user-defined tools
        rtvi: RTVIProcessor instance for RTVI integration

    Returns:
        LLM service instance
    """
    llm_provider = llm_config.get("provider", "openai")

    def _raise_missing_llm_api_key():
        raise ValueError(
            "Missing API key for LLM provider. Please set 'api_key' in the config or the OPENAI_API_KEY environment variable."
        )

    llm_providers = {
        "openai": lambda: OpenAILLMService(
            api_key=llm_config.get("api_key")
            or os.getenv("OPENAI_API_KEY")
            or _raise_missing_llm_api_key(),
            model=llm_config.get("model", "gpt-4o-mini"),
        ),
        "openai_agents": lambda: OpenAIAgentPlugin(
            api_key=llm_config.get("api_key")
            or os.getenv("OPENAI_API_KEY")
            or _raise_missing_llm_api_key(),
            agent_config=llm_config.get("agent_config"),
            data=data,
        ),
    }

    provider_func = llm_providers.get(llm_provider, llm_providers["openai"])

    llm = provider_func()

    tools = llm_config.get("tools", None)
    if tools is not None and llm_provider == "openai":
        
        for key, value in data.get("tools", {}).items():
            if key in tools:
                llm.register_function(key, value["function"])

    logger.debug(f"Creating LLM service with provider: {llm_provider}")
    return llm


def create_llm_context(
    agent_config: Dict[str, Any], 
    context=None, 
    tools={}
):
    """
    Create an LLM context based on configuration.

    Args:
        agent_config: Dictionary containing agent configuration
        context: RunContextWrapper object for OpenAI Agents SDK
        tools: Tools object

    Returns:
        LLM context instance
    """
    prompt = agent_config.get(
        "prompt",
        DEFAULT_PROMPT,
    )
    initial_greeting = agent_config.get(
        "initial_greeting",
        DEFAULT_INITIAL_GREETING,
    )

    messages = [
        {
            "role": "system",
            "content": f"{prompt}. Start by greeting the user with: '{initial_greeting}'",
        }
    ]

    llm_provider = agent_config["llm"]["provider"]
    
    req_tools = agent_config.get("llm", {}).get("tools", None)

    if llm_provider == "openai":
        if req_tools is not None:
            
            try:
                schemas = []
                for key, value in tools.items():
                    if "schema" not in value:
                        logger.warning(f"Skipping tool without 'schema': {value}")
                        continue

                    if key in req_tools:
                        schemas.append(value["schema"])

                if not schemas:
                    logger.error("No valid schemas found in tools for OpenAI LLM context")

                tools_schema = ToolsSchema(schemas)

                logger.debug("Creating OpenAI LLM context")
                return OpenAILLMContext(messages=messages, tools=tools_schema)

            except Exception as e:
                raise RuntimeError("Failed to create OpenAI LLM context") from e

        else:
            return OpenAILLMContext(messages=messages)


    elif llm_provider == "openai_agents":
        logger.debug("Creating OpenAI Agent LLM context")
        try:
            config = agent_config.get("llm", {}).get("agent_config", {})

            start_agent = config.get("start_agent", None)

            return AgentChatContext(
                agent=start_agent, messages=messages, context=context
            )

        except Exception as e:
            logger.error(f"Failed to create OpenAI Agent LLM context: {e}")
            raise