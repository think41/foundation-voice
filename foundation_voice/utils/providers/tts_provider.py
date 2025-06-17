"""
Text-to-Speech (TTS) provider module.
"""

from typing import Dict, Any

from loguru import logger
from foundation_voice.utils.api_utils import get_api_key

def _create_cartesia_tts_service(tts_config: Dict[str, Any]) -> Any:
    try:
        from pipecat.services.cartesia.tts import CartesiaTTSService
    except ImportError as e:
        logger.error(
            "Cartesia TTS dependencies not found. "
            "To use Cartesia TTS, please install with: pip install foundation-voice[cartesia]"
        )
        raise ImportError(
            "Cartesia TTS dependencies not found. Install with: pip install foundation-voice[cartesia]"
        ) from e
    api_key = _get_api_key("api_key", "CARTESIA_API_KEY", "Cartesia", tts_config)
    return CartesiaTTSService(
        api_key=api_key,
        voice_id=tts_config.get("voice", "71a7ad14-091c-4e8e-a314-022ece01c121"),
    )

def _create_openai_tts_service(tts_config: Dict[str, Any]) -> Any:
    try:
        from pipecat.services.openai.tts import OpenAITTSService
    except ImportError as e:
        logger.error(
            "OpenAI TTS dependencies not found. "
            "To use OpenAI TTS, please install with: pip install foundation_voice[openai]"
        )
        raise ImportError(
            "OpenAI TTS dependencies not found. Install with: pip install foundation_voice[openai]"
        ) from e
    api_key = get_api_key("openai", tts_config)
    return OpenAITTSService(
        api_key=api_key,
        voice=tts_config.get("voice", "alloy"),
    )

def _create_deepgram_tts_service(tts_config: Dict[str, Any]) -> Any:
    try:
        from pipecat.services.deepgram.tts import DeepgramTTSService
    except ImportError as e:
        logger.error(
            "Deepgram TTS dependencies not found. "
            "To use Deepgram TTS, please install with: pip install foundation_voice[deepgram]"
        )
        raise ImportError(
            "Deepgram TTS dependencies not found. Install with: pip install foundation_voice[deepgram]"
        ) from e
    api_key = get_api_key("deepgram", tts_config)
    return DeepgramTTSService(
        api_key=api_key,
        # model=tts_config.get("model", "aura-asteria-en") # Example if model is configurable
    )

def _create_smallestai_tts_service(tts_config: Dict[str, Any]) -> Any:
    try:
        from foundation_voice.custom_plugins.services.smallest.tts import SmallestTTSService
    except ImportError as e: # This might catch issues if SmallestTTSService itself has uninstalled deps
        logger.error(
            "SmallestAI TTS (or its dependencies) not found. "
            "To use SmallestAI TTS, ensure it's correctly installed, potentially with: pip install foundation-voice[smallestai]"
        )
        raise ImportError(
            "SmallestAI TTS (or its dependencies) not found. Install with: pip install foundation-voice[smallestai]"
        ) from e
    api_key = get_api_key("smallest_ai", tts_config)
    return SmallestTTSService(
        api_key=api_key,
        model=tts_config.get("model","lightning-v2"), # Retain original default
        voice_id=tts_config.get("voice_id", None),
    )

def create_tts_service(tts_config: Dict[str, Any]) -> Any:
    """
    Create a TTS service based on configuration.

    Args:
        tts_config: Dictionary containing TTS configuration

    Returns:
        TTS service instance
    """
    tts_provider = tts_config.get("provider", "cartesia") # Default provider

    # Dictionary mapping providers to their service creation helper functions
    tts_provider_factories = {
        "cartesia": _create_cartesia_tts_service,
        "openai": _create_openai_tts_service,
        "deepgram": _create_deepgram_tts_service,
        "smallestai": _create_smallestai_tts_service,
    }

    # Get the factory function for the selected provider
    # If the provider is not found, default to cartesia's factory as per original logic
    provider_factory = tts_provider_factories.get(tts_provider, _create_cartesia_tts_service)
    
    logger.debug(f"Creating TTS service with provider: {tts_provider}")
    return provider_factory(tts_config)
