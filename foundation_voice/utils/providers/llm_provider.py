"""
Large Language Model (LLM) provider module.
"""

from typing import Dict, Any, Optional

from loguru import logger
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext

from foundation_voice.utils.api_utils import get_api_key

DEFAULT_PROMPT = "You are a helpful LLM in a WebRTC call. Your goal is to demonstrate your capabilities in a succinct way. Your output will be converted to audio so don't include special characters in your answers. Respond to what the user said in a creative and helpful way."
DEFAULT_INITIAL_GREETING = "Hello. How can I help you today?"

def _create_openai_service(llm_config: Dict[str, Any]) -> Any:
    """Create an OpenAI LLM service."""
    try:
        from pipecat.services.openai import OpenAILLMService
    except ImportError as e:
        logger.error(
            "The 'openai' package, required for OpenAI LLM service, was not found. "
            "To use this service, please install the SDK with the 'openai' extra: "
            "pip install foundation-voice[openai]"
        )
        raise ImportError(
            "OpenAI LLM service dependencies not found. Install with: pip install foundation-voice[openai]"
        ) from e
    
    return OpenAILLMService(
        api_key=get_api_key("openai", llm_config),
        model=llm_config.get("model", "gpt-4o-mini"),
    )

def _create_openai_agent_plugin_service(llm_config: Dict[str, Any], data: Dict[str, Any]) -> Any:
    """Create an OpenAI Agent Plugin service."""
    try:
        from foundation_voice.custom_plugins.services.openai_agents.llm import OpenAIAgentPlugin
    except ImportError as e:
        logger.error(
            "OpenAI Agents Plugin dependencies not found. "
            "To use the 'openai_agents' LLM provider, please install with: pip install foundation-voice[openai_agents]"
        )
        raise ImportError(
            "OpenAI Agents Plugin dependencies not found. Install with: pip install foundation-voice[openai_agents]"
        ) from e

    return OpenAIAgentPlugin(
        api_key=get_api_key("openai", llm_config),
        agent_config=llm_config.get("agent_config"),
        data=data,
    )

def create_llm_service(
    llm_config: Dict[str, Any],
    data: Dict[str, Any],
) -> Any:
    """
    Create an LLM service based on configuration.

    Args:
        llm_config: Dictionary containing LLM configuration
        data: Dictionary containing additional data including tools

    Returns:
        LLM service instance
    """
    llm_provider = llm_config.get("provider", "openai")

    # Dictionary mapping providers to their service creation functions
    llm_provider_factories = {
        "openai": lambda: _create_openai_service(llm_config),
        "openai_agents": lambda: _create_openai_agent_plugin_service(llm_config, data),
    }

    # Get the factory function for the selected provider
    provider_factory = llm_provider_factories.get(llm_provider.lower())
    if provider_factory is None:
        raise ValueError(
            f"Unsupported LLM provider: {llm_provider}. "
            f"Available providers: {', '.join(llm_provider_factories.keys())}"
        )
    
    logger.debug(f"Creating LLM service with provider: {llm_provider}")
    
    # Create the LLM service
    llm = provider_factory()
    
    # Register tools if this is an OpenAI provider and tools are specified
    tools = llm_config.get("tools")
    if tools is not None and llm_provider == "openai":
        for key, value in data.get("tools", {}).items():
            if key in tools and callable(getattr(value, "get", None)) and callable(value.get("function")):
                llm.register_function(key, value["function"])
    
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
            from foundation_voice.custom_plugins.processors.aggregators.agent_context import AgentChatContext
        except ImportError as e:
            logger.error(
                "AgentChatContext (part of OpenAI Agents Plugin) not found. "
                "To use the 'openai_agents' LLM provider, please install with: pip install foundation_voice[openai_agents]"
            )
            raise ImportError(
                "AgentChatContext dependencies not found. Install with: pip install foundation_voice[openai_agents]"
            ) from e

        try:
            config = agent_config.get("llm", {}).get("agent_config", {})
            start_agent = config.get("start_agent", None)
            return AgentChatContext(
                agent=start_agent, messages=messages, context=context
            )
        except Exception as e:
            logger.error(f"Failed to create OpenAI Agent LLM context: {e}")
            raise