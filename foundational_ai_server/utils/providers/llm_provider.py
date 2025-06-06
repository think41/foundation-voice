"""
Large Language Model (LLM) provider module.
"""

import os
from loguru import logger
from typing import Dict, Any
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.openai.llm import OpenAILLMService

from foundational_ai_server.custom_plugins.services.openai_agents.llm import OpenAIAgentPlugin
from foundational_ai_server.custom_plugins.processors.aggregators.agent_context import AgentChatContext


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
    logger.debug(f"Creating LLM service with provider: {llm_provider}")
    return provider_func()


def create_llm_context(agent_config: Dict[str, Any], context):
    """
    Create an LLM context based on configuration.

    Args:
        agent_config: Dictionary containing agent configuration

    Returns:
        LLM context instance
    """
    prompt = agent_config.get(
        "prompt",
        "You are a helpful LLM in a WebRTC call. Your goal is to demonstrate your capabilities in a succinct way. Your output will be converted to audio so don't include special characters in your answers. Respond to what the user said in a creative and helpful way.",
    )
    initial_greeting = agent_config.get(
        "initial_greeting",
        "Hello. How can I help you today?",
    )

    messages = [
        {
            "role": "system",
            "content": f"{prompt}. Start by greeting the user with: '{initial_greeting}'",
        }
    ]

    llm_provider = agent_config["llm"]["provider"]

    if llm_provider == "openai":
        logger.debug("Creating OpenAI LLM context")
        return OpenAILLMContext(messages=messages, tools=[])

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