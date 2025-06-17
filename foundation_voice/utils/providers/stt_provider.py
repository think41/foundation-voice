"""
Speech-to-Text (STT) provider module.
"""

from typing import Dict, Any

from loguru import logger

from foundation_voice.utils.api_utils import get_api_key

def _create_deepgram_service(stt_config: Dict[str, Any]) -> Any:
    """Create a Deepgram STT service."""
    try:
        from pipecat.services.deepgram.stt import DeepgramSTTService
        from deepgram import LiveOptions
    except ImportError as e:
        logger.error(
            "Deepgram STT dependencies not found. "
            "To use Deepgram STT, please install with: pip install foundation-voice[deepgram]"
        )
        raise ImportError(
            "Deepgram STT dependencies not found. "
            "Install with: pip install foundation-voice[deepgram]"
        ) from e
        
    return DeepgramSTTService(
        api_key=get_api_key("deepgram", stt_config),
        live_options=LiveOptions(
            model=stt_config.get("model", "nova-2-general"),
            language=stt_config.get("language", "en-us")
        ),
        audio_passthrough=stt_config.get("audio_passthrough", False)
    )

def _create_openai_service(stt_config: Dict[str, Any]) -> Any:
    """Create an OpenAI STT service."""
    try:
        from pipecat.services.openai.stt import OpenAISTTService
    except ImportError as e:
        logger.error(
            "OpenAI STT dependencies not found. "
            "To use OpenAI STT, please install with: pip install foundation-voice[openai]"
        )
        raise ImportError(
            "OpenAI STT dependencies not found. "
            "Install with: pip install foundation-voice[openai]"
        ) from e
        
    return OpenAISTTService(
        api_key=get_api_key("openai", stt_config),
        model=stt_config.get("model", "whisper-1"),
        language=stt_config.get("language")
    )

def create_stt_service(stt_config: Dict[str, Any]) -> Any:
    """
    Create an STT service based on configuration.

    Args:
        stt_config: Dictionary containing STT configuration

    Returns:
        STT service instance
    """
    stt_provider = stt_config.get("provider", "deepgram")

    # Dictionary mapping providers to their service creation functions
    stt_provider_factories = {
        "deepgram": _create_deepgram_service,
        "openai": _create_openai_service,
    }

    # Get the factory function for the selected provider
    provider_factory = stt_provider_factories.get(stt_provider.lower())
    if provider_factory is None:
        raise ValueError(
            f"Unsupported STT provider: {stt_provider}. "
            f"Available providers: {', '.join(stt_provider_factories.keys())}"
        )
    
    logger.debug(f"Creating STT service with provider: {stt_provider}")
    return provider_factory(stt_config)
