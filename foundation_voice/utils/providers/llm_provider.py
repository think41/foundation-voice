"""
Large Language Model (LLM) provider module.
"""

from loguru import logger
from typing import Dict, Any
import os

from foundation_voice.utils.api_utils import _raise_missing_api_key
from foundation_voice.utils.provider_utils import import_provider_service

# Imports for type hinting, actual service imports are in helper functions
from pipecat.services.llm_service import LLMService
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from dotenv import load_dotenv

load_dotenv()

DEFAULT_PROMPT = "You are a helpful LLM in a WebRTC call. Your goal is to demonstrate your capabilities in a succinct way. Your output will be converted to audio so don't include special characters in your answers. Respond to what the user said in a creative and helpful way."
DEFAULT_INITIAL_GREETING = "Hello. How can I help you today?"


def _create_openai_llm_service(llm_config: Dict[str, Any]) -> LLMService:
    """Create an OpenAI LLM service."""
    OpenAILLMService = import_provider_service(
        "pipecat.services.openai.llm", "OpenAILLMService", "openai"
    )
    return OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY")
        or _raise_missing_api_key("OpenAI", "OPENAI_API_KEY"),
        model=llm_config.get("model", "gpt-4o-mini"),
    )


def _create_openai_agent_plugin_service(
    llm_config: Dict[str, Any], data: Dict[str, Any]
) -> LLMService:
    """Create an OpenAI Agent Plugin service."""
    OpenAIAgentPlugin = import_provider_service(
        "foundation_voice.custom_plugins.services.openai_agents.llm",
        "OpenAIAgentPlugin",
        "openai_agents",
    )
    return OpenAIAgentPlugin(
        api_key=os.getenv("OPENAI_API_KEY")
        or _raise_missing_api_key(
            "OpenAI", "OPENAI_API_KEY"
        ),  # Assuming agent plugin uses OPENAI_API_KEY
        agent_config=llm_config.get("agent_config"),
        data=data,
    )


def _create_cerebras_llm_service(llm_config: Dict[str, Any]) -> LLMService:
    """Create a Cerebras LLM service."""
    CerebrasLLMService = import_provider_service(
        "pipecat.services.cerebras.llm", "CerebrasLLMService", "cerebras"
    )
    return CerebrasLLMService(
        api_key=os.getenv("CEREBRAS_API_KEY")
        or _raise_missing_api_key("Cerebras", "CEREBRAS_API_KEY"),
        model=llm_config.get("model", "llama3.1-8b"),
    )


def _create_groq_llm_service(llm_config: Dict[str, Any]) -> LLMService:
    """Create a Groq LLM service."""
    GroqLLMService = import_provider_service(
        "pipecat.services.groq.llm", "GroqLLMService", "groq"
    )
    return GroqLLMService(
        api_key=os.getenv("GROQ_API_KEY")
        or _raise_missing_api_key("Groq", "GROQ_API_KEY"),
        model=llm_config.get("model", "llama3.1-8b"),
    )


def create_llm_service(
    agent_config: Dict[str, Any],
    data: Dict[str, Any],
) -> LLMService:
    """
    Create an LLM service based on configuration.

    Args:
        agent_config: Dictionary containing agent configuration.
        data: Dictionary containing tools and other relevant data.

    Returns:
        LLMService: An instance of the configured LLM service.
    """

    llm_config = agent_config.get("llm", {})

    llm_provider = llm_config.get("provider", "openai").lower()

    llm_provider_factories = {
        "openai": lambda: _create_openai_llm_service(llm_config),
        "openai_agents": lambda: _create_openai_agent_plugin_service(llm_config, data),
        "cerebras": lambda: _create_cerebras_llm_service(llm_config),
        "groq": lambda: _create_groq_llm_service(llm_config),
    }

    provider_factory = llm_provider_factories.get(llm_provider)
    if not provider_factory:
        # Default to OpenAI if provider is unknown or not specified properly
        logger.warning(
            f"Unsupported LLM provider: '{llm_provider}'. Defaulting to 'openai'."
        )
        provider_factory = llm_provider_factories["openai"]
    llm = provider_factory()

    # Register tools if applicable
    # Based on function_adapter.py and create_llm_context, both openai and cerebras might support tools.
    configured_tools = llm_config.get("tools")
    if configured_tools and llm_provider in ["openai", "cerebras", "groq"]:
        if hasattr(llm, "register_function"):
            user_defined_tools = data.get("tools", {})
            for tool_name, tool_details in user_defined_tools.items():
                if tool_name in configured_tools:
                    function_to_register = tool_details.get("function")
                    if callable(function_to_register):
                        llm.register_function(tool_name, function_to_register)
                    else:
                        logger.warning(
                            f"Tool '{tool_name}' is configured but its 'function' is missing or not callable."
                        )
        else:
            logger.warning(
                f"LLM provider '{llm_provider}' is configured with tools, "
                f"but the service instance does not support 'register_function'. Tools will not be registered."
            )

    guardrails = llm_config.get("guardrails", None)
    if guardrails is not None and llm_provider != "openai_agents":
        from foundation_voice.custom_plugins.services.guardrailed_cerebras.guardrail_llm import (
            GuardrailedLLMService,
        )

        guardrail_llm = GuardrailedLLMService(
            llm,
            guardrails=guardrails,
            prompt=agent_config.get("prompt", DEFAULT_PROMPT),
            api_key=os.getenv("CEREBRAS_API_KEY"),
        )

        # Register tools with the guardrailed LLM service as well
        configured_tools = llm_config.get("tools")
        if configured_tools:
            if hasattr(guardrail_llm, "register_function"):
                user_defined_tools = data.get("tools", {})
                for tool_name, tool_details in user_defined_tools.items():
                    if tool_name in configured_tools:
                        function_to_register = tool_details.get("function")
                        if callable(function_to_register):
                            guardrail_llm.register_function(
                                tool_name, function_to_register
                            )
                        else:
                            logger.warning(
                                f"Tool '{tool_name}' is configured but its 'function' is missing or not callable."
                            )
            else:
                logger.warning(
                    "GuardrailedLLMService is configured with tools, "
                    "but the service instance does not support 'register_function'. Tools will not be registered."
                )

        return guardrail_llm

    logger.debug(f"Creating LLM service with provider: {llm_provider}")
    return llm


def create_llm_context(agent_config: Dict[str, Any], context=None, tools={}):
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

    if llm_provider in ["openai", "cerebras", "groq"]:
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
                    logger.error(
                        "No valid schemas found in tools for OpenAI LLM context"
                    )

                tools_schema = ToolsSchema(schemas)

                logger.debug("Creating OpenAI LLM context")
                return OpenAILLMContext(messages=messages, tools=tools_schema)

            except Exception as e:
                raise RuntimeError("Failed to create OpenAI LLM context") from e

        else:
            return OpenAILLMContext(messages=messages)

    elif llm_provider == "openai_agents":
        from foundation_voice.custom_plugins.processors.aggregators.agent_context import (
            AgentChatContext,
        )

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
